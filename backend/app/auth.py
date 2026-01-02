from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from pydantic import BaseModel

from .config import settings

ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"


class TokenSubject(BaseModel):
    email: str
    name: str | None = None
    role: str | None = None
    is_admin: bool | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


def _create_token(subject: TokenSubject, expires_delta: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject.email,
        "name": subject.name,
        "role": subject.role,
        "is_admin": subject.is_admin,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: TokenSubject) -> str:
    return _create_token(
        subject,
        timedelta(minutes=settings.access_token_ttl_minutes),
        token_type="access",
    )


def create_refresh_token(subject: TokenSubject) -> str:
    return _create_token(
        subject,
        timedelta(days=settings.refresh_token_ttl_days),
        token_type="refresh",
    )


def decode_token(token: str, expected_type: str) -> TokenSubject | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError:
        return None

    if payload.get("type") != expected_type:
        return None

    email = payload.get("sub")
    if not email:
        return None

    return TokenSubject(
        email=email,
        name=payload.get("name"),
        role=payload.get("role"),
        is_admin=payload.get("is_admin"),
    )
