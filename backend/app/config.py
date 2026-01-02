from __future__ import annotations

from dataclasses import dataclass
import os


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_env: str
    jwt_secret: str
    jwt_algorithm: str
    access_token_ttl_minutes: int
    refresh_token_ttl_days: int
    database_url: str
    seed_dev_user: bool
    seed_dev_email: str
    seed_dev_password: str
    seed_dev_name: str
    seed_dev_is_admin: bool
    cors_origins: list[str]
    cookie_secure: bool
    cookie_samesite: str
    cookie_domain: str | None


def load_settings() -> Settings:
    app_env = os.getenv("APP_ENV", "development")
    cookie_secure = _parse_bool(os.getenv("COOKIE_SECURE"), app_env == "production")
    cookie_samesite = os.getenv("COOKIE_SAMESITE")
    if not cookie_samesite:
        cookie_samesite = "none" if cookie_secure else "lax"
    return Settings(
        app_env=app_env,
        jwt_secret=os.getenv("JWT_SECRET", "dev-secret"),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        access_token_ttl_minutes=int(os.getenv("ACCESS_TOKEN_TTL_MINUTES", "30")),
        refresh_token_ttl_days=int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "7")),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./cloverbooks.db"),
        seed_dev_user=_parse_bool(os.getenv("SEED_DEV_USER"), app_env != "production"),
        seed_dev_email=os.getenv("SEED_DEV_EMAIL", "demo@cloverbooks.local"),
        seed_dev_password=os.getenv("SEED_DEV_PASSWORD", "changeme"),
        seed_dev_name=os.getenv("SEED_DEV_NAME", "Demo User"),
        seed_dev_is_admin=_parse_bool(os.getenv("SEED_DEV_IS_ADMIN"), True),
        cors_origins=_parse_csv(
            os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://localhost:5174",
            )
        ),
        cookie_secure=cookie_secure,
        cookie_samesite=cookie_samesite,
        cookie_domain=os.getenv("COOKIE_DOMAIN") or None,
    )


settings = load_settings()
