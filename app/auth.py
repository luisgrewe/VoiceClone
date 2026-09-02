from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import Cookie, HTTPException, Response

from app import config

COOKIE_NAME = "vc_auth"


def _token() -> str:
    return hashlib.sha256(f"voiceclone:{config.APP_PASSWORD}".encode()).hexdigest()


def password_required() -> bool:
    config.refresh_env()
    return bool(config.APP_PASSWORD)


def login(password: str, response: Response) -> None:
    if not password_required():
        return
    if not secrets.compare_digest(password, config.APP_PASSWORD):
        raise HTTPException(status_code=401, detail="Wrong password.")
    response.set_cookie(
        COOKIE_NAME,
        _token(),
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 24 * 30,
        path="/",
    )


def logout(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def require_auth(vc_auth: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> None:
    if not password_required():
        return
    expected = _token()
    if not vc_auth or not hmac.compare_digest(vc_auth, expected):
        raise HTTPException(status_code=401, detail="Password required.")
