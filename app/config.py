from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def refresh_env() -> None:
    load_dotenv(ROOT / ".env", override=True)
    global FISH_API_KEY, APP_PASSWORD, DEFAULT_MODEL
    FISH_API_KEY = os.getenv("FISH_API_KEY", "").strip()
    APP_PASSWORD = os.getenv("APP_PASSWORD", "").strip()
    DEFAULT_MODEL = os.getenv("FISH_TTS_MODEL", "s2.1-pro-free")

FISH_API_KEY = os.getenv("FISH_API_KEY", "").strip()
APP_PASSWORD = os.getenv("APP_PASSWORD", "").strip()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEFAULT_MODEL = os.getenv("FISH_TTS_MODEL", "s2.1-pro-free")
CHUNK_CHARS = int(os.getenv("CHUNK_CHARS", "1500"))

DATA_DIR = ROOT / "data"
OUTPUT_DIR = DATA_DIR / "output"
VOICES_PATH = DATA_DIR / "voices.json"
HISTORY_PATH = DATA_DIR / "history.json"

TTS_MODELS = [
    "s2.1-pro-free",
    "s2.1-pro",
    "s2-pro",
    "s1",
]


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not VOICES_PATH.exists():
        VOICES_PATH.write_text("[]\n", encoding="utf-8")
    if not HISTORY_PATH.exists():
        HISTORY_PATH.write_text("[]\n", encoding="utf-8")
