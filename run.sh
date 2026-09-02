#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env — add your FISH_API_KEY from https://fish.audio/app/api-keys"
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
echo "VoiceClone: http://127.0.0.1:${PORT}"
exec uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
