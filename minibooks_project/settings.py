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


def _get_list_env(name: str) -> list[str]:
    raw_value = os.getenv(name, "")
    if not raw_value:
        return []
    parts = raw_value.replace(";", ",").split(",")
    return [p.strip() for p in parts if p.strip()]


DEBUG = _get_bool_env("DJANGO_DEBUG", _get_bool_env("DEBUG", True))
SHOW_LOGIN_FALLBACK = os.getenv("SHOW_LOGIN_FALLBACK", "true").lower() == "true"

# ALLOWED_HOSTS / CSRF_TRUSTED_ORIGINS (Render + env overrides)
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")

base_allowed_hosts = [
    "localhost",
    "127.0.0.1",
    "central-books.onrender.com",
]
env_allowed_hosts = _get_list_env("DJANGO_ALLOWED_HOSTS")
ALLOWED_HOSTS = list(dict.fromkeys(base_allowed_hosts + env_allowed_hosts))

if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

def _https_origin(host: str) -> str:
    if host.startswith("http://") or host.startswith("https://"):
        return host
    return f"https://{host}"

base_csrf_origins = ["https://central-books.onrender.com"]
env_csrf_origins = _get_list_env("CSRF_TRUSTED_ORIGINS")
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(base_csrf_origins + env_csrf_origins))

# Add HTTPS versions of allowed hosts (exclude localhost)
for host in ALLOWED_HOSTS:
    if host in {"localhost", "127.0.0.1"}:
        continue
    origin = _https_origin(host)
    if origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)


def _preferred_site_domain() -> str:
    explicit = os.getenv("SITE_DOMAIN")
    if explicit:
        return explicit
    if RENDER_EXTERNAL_HOSTNAME:
        return RENDER_EXTERNAL_HOSTNAME
    for host in ALLOWED_HOSTS:
        if host not in {"localhost", "127.0.0.1"}:
            return host
    return ALLOWED_HOSTS[0] if ALLOWED_HOSTS else "localhost"


SITE_DOMAIN = _preferred_site_domain()

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    
    # Third-party
    "rest_framework",
    
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
    "internal_admin",
    "companion",
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
    "core.middleware.GoogleOAuthLoggingMiddleware",
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
                "core.context_processors.impersonation_context",
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

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# Cookie flags (safe defaults; local dev unaffected when DEBUG=True)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # Django needs JS-less forms to read it
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INTERNAL_ADMIN_METRICS_MAX_AGE_MINUTES = 5

# Companion LLM (DeepSeek or provider-agnostic) settings
COMPANION_LLM_ENABLED = os.getenv("COMPANION_LLM_ENABLED", "false").lower() in {"1", "true", "yes"}
COMPANION_LLM_API_BASE = os.getenv("COMPANION_LLM_API_BASE", "")
COMPANION_LLM_API_KEY = os.getenv("COMPANION_LLM_API_KEY", "")
COMPANION_LLM_MODEL = os.getenv("COMPANION_LLM_MODEL", "deepseek-v3.2")
COMPANION_LLM_TIMEOUT_SECONDS = int(os.getenv("COMPANION_LLM_TIMEOUT_SECONDS", "15"))
COMPANION_LLM_MAX_TOKENS = int(os.getenv("COMPANION_LLM_MAX_TOKENS", "512"))

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
else:
    # In DEBUG/tests, avoid manifest lookups for static files
    STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.StaticFilesStorage"

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
LOGOUT_REDIRECT_URL = "/login"
ACCOUNT_LOGOUT_REDIRECT_URL = "/login"

ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = "none"  # Change to "mandatory" in production if needed

# Skip intermediate allauth pages - go directly to Google OAuth
SOCIALACCOUNT_LOGIN_ON_GET = True

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

# Google OAuth provider configuration
# Credentials are stored ONLY in the database via SocialApp (use setup_google_oauth command)
# The APP configuration below was causing MultipleObjectsReturned errors
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": [
            "email",
            "profile",
        ],
        "AUTH_PARAMS": {
            "access_type": "offline",
        },
    }
}

# NOTE: APP configuration removed - credentials must be in database SocialApp only
# Run: python manage.py setup_google_oauth to configure


# ===================================
# Email Configuration
# ===================================

# Email backend: use environment-aware settings
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = _get_bool_env("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = _get_bool_env("EMAIL_USE_SSL", False)

# Default from email
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "")

# In development, use console backend if SMTP is not configured
if DEBUG and not EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "oauth.google": {
            "handlers": ["console"],
            "level": "INFO",
        },
    },
}
