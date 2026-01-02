from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import (
    ACCESS_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    LoginRequest,
    TokenSubject,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from .config import settings
from .db import Base, SessionLocal, engine, get_db
from .models import User
from .security import hash_password, verify_password

app = FastAPI(title="Clover Books API", version="0.2.0")

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


class UserOut(BaseModel):
    id: int
    email: str
    name: str | None = None
    is_admin: bool = False
    role: str | None = None


class AuthResponse(BaseModel):
    authenticated: bool
    user: UserOut


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


def _user_to_subject(user: User) -> TokenSubject:
    return TokenSubject(
        email=user.email,
        name=user.name,
        role=user.role,
        is_admin=user.is_admin,
    )


def _user_to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        is_admin=user.is_admin,
        role=user.role,
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_ttl_days * 86400,
        domain=settings.cookie_domain,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        domain=settings.cookie_domain,
        path="/",
    )


def _get_access_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()

    return request.cookies.get(ACCESS_COOKIE_NAME)


def _get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def _ensure_dev_user() -> None:
    if not settings.seed_dev_user:
        return

    with SessionLocal() as db:
        existing = _get_user_by_email(db, settings.seed_dev_email)
        if existing:
            return
        user = User(
            email=settings.seed_dev_email,
            name=settings.seed_dev_name,
            password_hash=hash_password(settings.seed_dev_password),
            is_admin=settings.seed_dev_is_admin,
            role="superadmin" if settings.seed_dev_is_admin else "user",
        )
        db.add(user)
        db.commit()


@app.on_event("startup")
def startup() -> None:
    if settings.app_env != "production":
        Base.metadata.create_all(bind=engine)
    _ensure_dev_user()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    user = _get_user_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    subject = _user_to_subject(user)
    access_token = create_access_token(subject)
    refresh_token = create_refresh_token(subject)
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token, user=_user_to_out(user))


@app.post("/auth/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    subject = decode_token(token, expected_type="refresh")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = _get_user_by_email(db, subject.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    new_subject = _user_to_subject(user)
    access_token = create_access_token(new_subject)
    refresh_token = create_refresh_token(new_subject)
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token, user=_user_to_out(user))


@app.post("/auth/logout")
def logout(response: Response) -> dict[str, bool]:
    _clear_refresh_cookie(response)
    return {"ok": True}


@app.get("/me", response_model=AuthResponse)
def me(request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    token = _get_access_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing access token")

    subject = decode_token(token, expected_type="access")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

    user = _get_user_by_email(db, subject.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return AuthResponse(authenticated=True, user=_user_to_out(user))
