from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app import config
from app import fish


def _load() -> list[dict[str, Any]]:
    config.ensure_dirs()
    try:
        data = json.loads(config.VOICES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = []
    return data if isinstance(data, list) else []


def _save(items: list[dict[str, Any]]) -> None:
    config.ensure_dirs()
    config.VOICES_PATH.write_text(json.dumps(items, indent=2) + "\n", encoding="utf-8")


def list_local() -> list[dict[str, Any]]:
    return _load()


def upsert(voice: dict[str, Any]) -> dict[str, Any]:
    items = [v for v in _load() if v.get("id") != voice.get("id")]
    record = {
        "id": voice["id"],
        "title": voice.get("title") or "My Voice",
        "state": voice.get("state") or "trained",
        "description": voice.get("description") or "",
        "created_at": voice.get("created_at") or datetime.now(timezone.utc).isoformat(),
        "local": True,
    }
    items.insert(0, record)
    _save(items)
    return record


def remove(voice_id: str) -> None:
    _save([v for v in _load() if v.get("id") != voice_id])


def merged() -> list[dict[str, Any]]:
    local = {v["id"]: v for v in _load() if v.get("id")}
    if not config.FISH_API_KEY:
        return list(local.values())
    remote: list[dict[str, Any]] = []
    try:
        remote = fish.list_voices()
    except Exception:
        if local:
            return list(local.values())
        raise
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in remote:
        vid = item["id"]
        seen.add(vid)
        loc = local.get(vid, {})
        out.append({**item, "local": bool(loc), "created_at": loc.get("created_at")})
    for vid, loc in local.items():
        if vid not in seen:
            out.append(loc)
    return out
