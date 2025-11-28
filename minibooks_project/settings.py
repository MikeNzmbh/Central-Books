from pathlib import Path
import os

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration


try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback when dependency missing
    def load_dotenv(*args, **kwargs) -> bool:
        return False

try:
    import dj_database_url
except ImportError:  # pragma: no cover - fallback minimal parser
    class _FallbackDBURL:
        @staticmethod
        def parse(url):
            if url.startswith("sqlite:///"):
                return {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": url.replace("sqlite:///", "", 1),
                }
            return {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": url,
            }

    dj_database_url = _FallbackDBURL()

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")  # explicit .env location

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY") or os.getenv("SECRET_KEY") or "dev-key"


def _get_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.lower() in {"1", "true", "yes", "on"}


DEBUG = _get_bool_env("DJANGO_DEBUG", _get_bool_env("DEBUG", True))
SHOW_LOGIN_FALLBACK = os.getenv("SHOW_LOGIN_FALLBACK", "true").lower() == "true"


def _parse_hosts(value: str | None) -> list[str]:
    if not value:
        return []
    return [host.strip() for host in value.split(",") if host.strip()]


allowed_hosts = _parse_hosts(os.getenv("DJANGO_ALLOWED_HOSTS") or os.getenv("ALLOWED_HOSTS"))
ALLOWED_HOSTS: list[str] = allowed_hosts or ["127.0.0.1", "localhost"]

# Trust deployment hosts for CSRF-protected POSTs (Render + optional overrides)
if not DEBUG:
    CSRF_TRUSTED_ORIGINS = [
        "https://central-books-web.onrender.com",
        "https://central-books.onrender.com",
    ]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    
    # Sites framework (required by allauth)
    "django.contrib.sites",
    
    # Allauth apps
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    
    # Project apps
    "core",
    "taxes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",  # Required for django-allauth
]


ROOT_URLCONF = "minibooks_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.business_context",
            ],
        },
    }
]

WSGI_APPLICATION = "minibooks_project.wsgi.application"

default_db = "sqlite:///" + str((BASE_DIR / "db.sqlite3").resolve())
database_url = os.getenv("DATABASE_URL", default_db)
DATABASES = {"default": dj_database_url.parse(database_url)}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Kigali"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",
    BASE_DIR / "frontend" / "static",
]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": MEDIA_ROOT,
            "base_url": MEDIA_URL,
        },
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

LOGIN_URL = "/login"
LOGIN_REDIRECT_URL = "/dashboard"
LOGOUT_REDIRECT_URL = "/login"

# Cookie flags (safe defaults; local dev unaffected when DEBUG=True)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # Django needs JS-less forms to read it
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Sentry & production security hardening ---

SENTRY_DSN = os.getenv("SENTRY_DSN", "")

if not DEBUG:
    # Error monitoring (Sentry)
    if SENTRY_DSN:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=0.1,   # sample 10% of requests for performance traces
            send_default_pii=False,   # keep it privacy-friendly
            environment="production",
        )

    # Trust Render's HTTPS proxy headers
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True

    # HSTS: tell browsers to always use HTTPS
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Cookies
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
    CSRF_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SAMESITE = "Lax"

    # Browser safety
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = "DENY"

# ===================================
# Django Allauth Configuration
# ===================================

# Required for django.contrib.sites
SITE_ID = 1

# Authentication backends
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",  # Default Django auth
    "allauth.account.auth_backends.AuthenticationBackend",  # Allauth
]

# Allauth settings
LOGIN_REDIRECT_URL = "/dashboard"
LOGOUT_REDIRECT_URL = "/"

ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = "none"  # Change to "mandatory" in production if needed

# Google OAuth provider configuration
# Required environment variables:
# - GOOGLE_CLIENT_ID: OAuth 2.0 Client ID from Google Cloud Console
# - GOOGLE_CLIENT_SECRET: OAuth 2.0 Client Secret from Google Cloud Console
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            "key": "",
        },
        "SCOPE": [
            "email",
            "profile",
        ],
        "AUTH_PARAMS": {
            "access_type": "offline",
        },
    }
}
