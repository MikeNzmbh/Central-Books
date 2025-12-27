from __future__ import annotations

from ipaddress import ip_address
from typing import Optional

from django.conf import settings
from django.http import HttpRequest


def _parse_ip(value: str) -> Optional[str]:
    try:
        return str(ip_address(value.strip()))
    except Exception:
        return None


def _should_trust_proxy_headers() -> bool:
    configured = getattr(settings, "TRUST_PROXY_HEADERS", None)
    if configured is not None:
        return bool(configured)

    # Reasonable default: if you're in production and have a proxy SSL header configured,
    # you likely run behind a reverse proxy (Render, Heroku, etc).
    return (not getattr(settings, "DEBUG", False)) and bool(getattr(settings, "SECURE_PROXY_SSL_HEADER", None))


def get_client_ip(request: HttpRequest) -> Optional[str]:
    """
    Best-effort client IP extraction.

    By default, trusts X-Forwarded-For only in production when SECURE_PROXY_SSL_HEADER
    is configured, or when TRUST_PROXY_HEADERS=True is explicitly set.
    """
    remote_addr = request.META.get("REMOTE_ADDR") or ""
    remote_ip = _parse_ip(remote_addr) if remote_addr else None

    xff = request.META.get("HTTP_X_FORWARDED_FOR") or ""
    if not xff or not _should_trust_proxy_headers():
        return remote_ip

    # Standard format: "client, proxy1, proxy2"
    for part in xff.split(","):
        candidate = _parse_ip(part)
        if candidate:
            return candidate

    return remote_ip

