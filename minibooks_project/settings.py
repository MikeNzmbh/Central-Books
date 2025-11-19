from pathlib import Path
import os

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


def _parse_hosts(value: str | None) -> list[str]:
    if not value:
        return []
    return [host.strip() for host in value.split(",") if host.strip()]


allowed_hosts = _parse_hosts(os.getenv("DJANGO_ALLOWED_HOSTS") or os.getenv("ALLOWED_HOSTS"))
ALLOWED_HOSTS: list[str] = allowed_hosts or ["127.0.0.1", "localhost"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
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
