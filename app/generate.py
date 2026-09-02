from __future__ import annotations

import json
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app import config
from app import fish

_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+")


def estimate_seconds(text: str, speed: float) -> float:
    chars = len(re.sub(r"\s+", " ", text.strip()))
    if chars == 0:
        return 0.0
    speed = speed or 1.0
    return round((chars / 14.0) / max(speed, 0.25), 1)


def chunk_text(text: str, limit: int = config.CHUNK_CHARS) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    sentences = _SENTENCE_RE.split(text)
    chunks: list[str] = []
    buf = ""
    for sentence in sentences:
        piece = sentence.strip()
        if not piece:
            continue
        candidate = f"{buf} {piece}".strip() if buf else piece
        if len(candidate) <= limit:
            buf = candidate
            continue
        if buf:
            chunks.append(buf)
            buf = ""
        if len(piece) <= limit:
            buf = piece
            continue
        for i in range(0, len(piece), limit):
            part = piece[i : i + limit].strip()
            if part:
                chunks.append(part)
        buf = ""
    if buf:
        chunks.append(buf)
    return chunks


def _load_history() -> list[dict[str, Any]]:
    config.ensure_dirs()
    try:
        data = json.loads(config.HISTORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = []
    return data if isinstance(data, list) else []


def _save_history(items: list[dict[str, Any]]) -> None:
    config.ensure_dirs()
    config.HISTORY_PATH.write_text(json.dumps(items, indent=2) + "\n", encoding="utf-8")


def list_generations() -> list[dict[str, Any]]:
    items = []
    for rec in _load_history():
        path = config.OUTPUT_DIR / rec.get("filename", "")
        if path.exists():
            items.append(rec)
    return items


def get_generation(gen_id: str) -> dict[str, Any] | None:
    for rec in _load_history():
        if rec.get("id") == gen_id:
            return rec
    return None


def audio_path(rec: dict[str, Any]) -> Path:
    return config.OUTPUT_DIR / rec["filename"]


def delete_generation(gen_id: str) -> bool:
    items = _load_history()
    rec = next((r for r in items if r.get("id") == gen_id), None)
    if not rec:
        return False
    path = audio_path(rec)
    if path.exists():
        path.unlink()
    _save_history([r for r in items if r.get("id") != gen_id])
    return True


def _ffmpeg_concat(parts: list[Path], dest: Path) -> None:
    listing = dest.with_suffix(".concat.txt")
    lines = []
    for part in parts:
        escaped = str(part.resolve()).replace("'", r"'\''")
        lines.append(f"file '{escaped}'")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(listing),
        "-c",
        "copy",
        str(dest),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="ffmpeg is not installed.") from exc
    except subprocess.CalledProcessError as exc:
        raise HTTPException(
            status_code=500,
            detail=exc.stderr[-800:] if exc.stderr else "ffmpeg concat failed.",
        ) from exc
    finally:
        listing.unlink(missing_ok=True)


def _probe_duration(path: Path) -> float | None:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return round(float(result.stdout.strip()), 2)
    except Exception:
        return None


def generate(
    *,
    text: str,
    voice_id: str,
    voice_title: str,
    model: str,
    speed: float,
    volume: float,
    audio_format: str,
) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Script is empty.")
    if audio_format not in {"mp3", "wav"}:
        raise HTTPException(status_code=400, detail="Format must be mp3 or wav.")

    chunks = chunk_text(text)
    gen_id = uuid.uuid4().hex[:12]
    dest = config.OUTPUT_DIR / f"{gen_id}.{audio_format}"
    config.ensure_dirs()

    if len(chunks) == 1:
        dest.write_bytes(
            fish.tts_convert(
                chunks[0],
                voice_id,
                model=model,
                speed=speed,
                volume=volume,
                audio_format=audio_format,
            )
        )
    else:
        parts: list[Path] = []
        try:
            for i, chunk in enumerate(chunks):
                part = config.OUTPUT_DIR / f"{gen_id}.part{i}.{audio_format}"
                part.write_bytes(
                    fish.tts_convert(
                        chunk,
                        voice_id,
                        model=model,
                        speed=speed,
                        volume=volume,
                        audio_format=audio_format,
                    )
                )
                parts.append(part)
            _ffmpeg_concat(parts, dest)
        finally:
            for part in parts:
                part.unlink(missing_ok=True)

    duration = _probe_duration(dest) or estimate_seconds(text, speed)
    rec = {
        "id": gen_id,
        "filename": dest.name,
        "format": audio_format,
        "text": text,
        "voice_id": voice_id,
        "voice_title": voice_title,
        "model": model,
        "speed": speed,
        "volume": volume,
        "duration": duration,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "bytes": dest.stat().st_size,
    }
    history = _load_history()
    history.insert(0, rec)
    _save_history(history[:100])
    return rec
