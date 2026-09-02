#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"

if ! command -v cloudflared >/dev/null 2>&1; then
  if [[ -x /opt/homebrew/bin/cloudflared ]]; then
    PATH="/opt/homebrew/bin:$PATH"
  elif [[ -x /usr/local/bin/cloudflared ]]; then
    PATH="/usr/local/bin:$PATH"
  fi
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is not installed."
  echo "Install with: brew install cloudflared"
  echo "Then keep ./run.sh running and run this script again."
  exit 1
fi

echo "Start ./run.sh in another terminal first if it is not already running."
echo "Opening a public HTTPS URL to http://127.0.0.1:${PORT}"
echo "Open the printed URL on your iPhone, then Share → Add to Home Screen."
exec cloudflared tunnel --url "http://127.0.0.1:${PORT}"
