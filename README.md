# VoiceClone

Paste a reel script on your Mac, get an MP3 in your cloned [Fish Audio](https://fish.audio) voice.

## Setup

1. Get an API key at [fish.audio/app/api-keys](https://fish.audio/app/api-keys).
2. Clone your voice on Fish (or later in **Voice setup** in this app).
3. From this folder:

```bash
chmod +x run.sh
./run.sh
```

4. First run copies `.env.example` to `.env`. Put your key in `.env`:

```
FISH_API_KEY=...
```

5. Open **http://127.0.0.1:8000**.

## Daily use

1. **Voice setup** (once, if you did not already clone on Fish): upload a clean 10s–2 min sample of you speaking.
2. **Studio**: paste the exact script. Default model is **s2.1-pro-free** (same quality as paid S2.1, $0). Generate, download the MP3.

Generated files land in `data/output/`. Do not commit `.env` or `data/`.
