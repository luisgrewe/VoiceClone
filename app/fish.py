from __future__ import annotations

from typing import Any, Literal

from fastapi import HTTPException
from fishaudio import FishAudio
from fishaudio.exceptions import (
    AuthenticationError,
    FishAudioError,
    RateLimitError,
    ValidationError,
)
from fishaudio.types.tts import Prosody, TTSConfig

from app import config


def require_key() -> None:
    config.refresh_env()
    if not config.FISH_API_KEY:
        raise HTTPException(
            status_code=400,
            detail="FISH_API_KEY is not set. Copy .env.example to .env and add your key.",
        )


def get_client() -> FishAudio:
    require_key()
    return FishAudio(api_key=config.FISH_API_KEY)


def map_fish_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, AuthenticationError):
        return HTTPException(status_code=400, detail="Fish Audio rejected the API key. Check FISH_API_KEY in .env.")
    if isinstance(exc, RateLimitError):
        return HTTPException(status_code=429, detail="Fish Audio rate limit hit. Try again in a moment.")
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=400, detail=str(exc) or "Fish Audio rejected the request.")
    if isinstance(exc, FishAudioError):
        return HTTPException(status_code=502, detail=str(exc) or "Fish Audio request failed.")
    return HTTPException(status_code=500, detail=str(exc))


def _as_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        try:
            data = dump(by_alias=False)
            if isinstance(data, dict):
                return data
        except TypeError:
            data = dump()
            if isinstance(data, dict):
                return data
    data: dict[str, Any] = {}
    for key in ("id", "_id", "title", "state", "description", "credit"):
        if hasattr(obj, key):
            data[key] = getattr(obj, key)
    return data


def list_voices() -> list[dict[str, Any]]:
    try:
        result = get_client().voices.list(self_only=True, page_size=50, page_number=1)
    except Exception as exc:
        raise map_fish_error(exc) from exc

    items = getattr(result, "items", None)
    if items is None:
        dump = _as_dict(result)
        items = dump.get("items") or []

    voices: list[dict[str, Any]] = []
    for item in items or []:
        data = _as_dict(item)
        vid = str(data.get("id") or data.get("_id") or "")
        if not vid:
            continue
        voices.append(
            {
                "id": vid,
                "title": data.get("title") or "Untitled",
                "state": data.get("state"),
                "description": data.get("description") or "",
            }
        )
    return voices


def create_voice(
    title: str,
    samples: list[bytes],
    description: str = "",
    texts: list[str] | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "title": title,
        "voices": samples,
        "description": description or "VoiceClone enrollment",
        "visibility": "private",
    }
    if texts:
        kwargs["texts"] = texts
    try:
        voice = get_client().voices.create(**kwargs)
    except Exception as exc:
        raise map_fish_error(exc) from exc
    data = _as_dict(voice)
    vid = str(data.get("id") or data.get("_id") or getattr(voice, "id", ""))
    return {
        "id": vid,
        "title": data.get("title") or title,
        "state": data.get("state") or "trained",
        "description": data.get("description") or description,
    }


def delete_voice(voice_id: str) -> None:
    try:
        get_client().voices.delete(voice_id)
    except Exception as exc:
        raise map_fish_error(exc) from exc


def tts_convert(
    text: str,
    reference_id: str,
    *,
    model: str,
    speed: float,
    volume: float,
    audio_format: str,
) -> bytes:
    allowed = set(config.TTS_MODELS)
    tts_model = model if model in allowed else config.DEFAULT_MODEL
    fmt: Literal["wav", "pcm", "mp3", "opus"] = "wav" if audio_format == "wav" else "mp3"
    try:
        audio = get_client().tts.convert(
            text=text,
            reference_id=reference_id,
            model=tts_model,  # type: ignore[arg-type]
            format=fmt,
            speed=speed,
            config=TTSConfig(
                format=fmt,
                reference_id=reference_id,
                prosody=Prosody(speed=speed, volume=volume),
            ),
        )
    except Exception as exc:
        raise map_fish_error(exc) from exc
    if isinstance(audio, (bytes, bytearray)):
        return bytes(audio)
    raise HTTPException(status_code=500, detail="Fish Audio did not return audio bytes.")


def get_credits() -> dict[str, Any]:
    try:
        info = get_client().account.get_credits()
    except Exception as exc:
        raise map_fish_error(exc) from exc
    data = _as_dict(info)
    credit = data.get("credit")
    try:
        credit = float(credit) if credit is not None else None
    except (TypeError, ValueError):
        pass
    return {"credit": credit}
