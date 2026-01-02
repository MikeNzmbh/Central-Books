from __future__ import annotations

from ipaddress import ip_address, ip_network
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpRequest

from core.ip_utils import get_client_ip

try:
    from allauth.socialaccount.models import SocialAccount
except ImportError:  # pragma: no cover
    SocialAccount = None


User = get_user_model()


def _iter_allowlist() -> list[str]:
    allowlist = getattr(settings, "INTERNAL_ADMIN_IP_ALLOWLIST", None)
    if not allowlist:
        return []
    if isinstance(allowlist, (list, tuple, set)):
        return [str(v).strip() for v in allowlist if str(v).strip()]
    if isinstance(allowlist, str):
        return [v.strip() for v in allowlist.split(",") if v.strip()]
    return [str(allowlist).strip()] if str(allowlist).strip() else []


def is_ip_allowed(ip: Optional[str]) -> bool:
    allowlist = _iter_allowlist()
    if not allowlist:
        return True
    if not ip:
        return False
    try:
        ip_obj = ip_address(ip)
    except Exception:
        return False

    for entry in allowlist:
        try:
            if "/" in entry:
                if ip_obj in ip_network(entry, strict=False):
                    return True
            else:
                if ip_obj == ip_address(entry):
                    return True
        except Exception:
            continue
    return False


def _requires_sso() -> bool:
    return bool(getattr(settings, "INTERNAL_ADMIN_REQUIRE_SSO", False))


def has_required_sso(user: User) -> bool:
    if not _requires_sso():
        return True
    if getattr(user, "is_superuser", False) and bool(getattr(settings, "INTERNAL_ADMIN_SSO_EXEMPT_SUPERUSER", True)):
        return True
    if SocialAccount is None:
        return False
    providers = getattr(settings, "INTERNAL_ADMIN_SSO_PROVIDERS", ["google"]) or ["google"]
    providers = [str(p).strip() for p in providers if str(p).strip()]
    return SocialAccount.objects.filter(user=user, provider__in=providers).exists()


def check_internal_admin_access(request: HttpRequest, user: User) -> tuple[bool, str]:
    """
    Defense-in-depth access policy for internal admin.

    Returns: (allowed, reason)
    """
    client_ip = get_client_ip(request)
    if not is_ip_allowed(client_ip):
        return False, "ip_not_allowed"
    if not has_required_sso(user):
        return False, "sso_required"
    return True, ""

