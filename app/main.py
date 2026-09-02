from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import auth, config, fish, generate, voices

config.ensure_dirs()
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="VoiceClone")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class LoginBody(BaseModel):
    password: str = ""


class GenerateBody(BaseModel):
    text: str
    voice_id: str
    model: str = config.DEFAULT_MODEL
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    volume: float = Field(default=0.0, ge=-20, le=20)
    format: str = "mp3"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/manifest.webmanifest")
def manifest() -> FileResponse:
    return FileResponse(STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/api/status")
def status(_: None = Depends(auth.require_auth)) -> dict:
    config.refresh_env()
    key_set = bool(config.FISH_API_KEY)
    payload: dict = {
        "key_set": key_set,
        "password_required": auth.password_required(),
        "models": config.TTS_MODELS,
        "default_model": config.DEFAULT_MODEL,
    }
    if key_set:
        try:
            payload["credits"] = fish.get_credits()
        except HTTPException as exc:
            payload["credits_error"] = exc.detail
    return payload


@app.post("/api/login")
def login(body: LoginBody, response: Response) -> dict:
    auth.login(body.password, response)
    return {"ok": True}


@app.post("/api/logout")
def logout(response: Response) -> dict:
    auth.logout(response)
    return {"ok": True}


@app.get("/api/voices")
def list_voices(_: None = Depends(auth.require_auth)) -> dict:
    return {"voices": voices.merged()}


@app.post("/api/voices")
async def create_voice(
    title: str = Form(...),
    description: str = Form(""),
    texts: list[str] | None = Form(default=None),
    files: list[UploadFile] = File(...),
    _: None = Depends(auth.require_auth),
) -> dict:
    title = title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Give the voice a name.")
    samples: list[bytes] = []
    for upload in files:
        data = await upload.read()
        if data:
            samples.append(data)
    if not samples:
        raise HTTPException(status_code=400, detail="Upload at least one audio sample.")
    transcripts: list[str] = []
    for item in texts or []:
        transcripts.extend(line.strip() for line in item.splitlines() if line.strip())
    created = fish.create_voice(
        title,
        samples,
        description=description.strip(),
        texts=transcripts or None,
    )
    if not created.get("id"):
        raise HTTPException(status_code=502, detail="Fish Audio did not return a voice id.")
    return voices.upsert(created)


@app.delete("/api/voices/{voice_id}")
def delete_voice(voice_id: str, _: None = Depends(auth.require_auth)) -> dict:
    try:
        fish.delete_voice(voice_id)
    except HTTPException as exc:
        if exc.status_code not in {404, 400}:
            raise
    voices.remove(voice_id)
    return {"ok": True}


@app.post("/api/generate")
def create_generation(body: GenerateBody, _: None = Depends(auth.require_auth)) -> dict:
    model = body.model if body.model in config.TTS_MODELS else config.DEFAULT_MODEL
    voice_title = next(
        (v.get("title") for v in voices.list_local() if v.get("id") == body.voice_id),
        "Voice",
    )
    rec = generate.generate(
        text=body.text,
        voice_id=body.voice_id,
        voice_title=voice_title,
        model=model,
        speed=body.speed,
        volume=body.volume,
        audio_format=body.format,
    )
    return rec


@app.get("/api/generations")
def list_generations(_: None = Depends(auth.require_auth)) -> dict:
    return {"generations": generate.list_generations()}


@app.delete("/api/generations/{gen_id}")
def delete_generation(gen_id: str, _: None = Depends(auth.require_auth)) -> dict:
    if not generate.delete_generation(gen_id):
        raise HTTPException(status_code=404, detail="Generation not found.")
    return {"ok": True}


@app.get("/api/audio/{gen_id}")
def download_audio(gen_id: str, _: None = Depends(auth.require_auth)) -> FileResponse:
    rec = generate.get_generation(gen_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Generation not found.")
    path = generate.audio_path(rec)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file is missing.")
    media = "audio/mpeg" if rec.get("format") == "mp3" else "audio/wav"
    return FileResponse(
        path,
        media_type=media,
        filename=path.name,
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )
