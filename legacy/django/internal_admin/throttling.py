from __future__ import annotations

from rest_framework.throttling import ScopedRateThrottle

from core.ip_utils import get_client_ip


class InternalAdminScopedRateThrottle(ScopedRateThrottle):
    """
    Scoped rate throttle for internal-admin endpoints.

    Uses the authenticated user ID when available, otherwise falls back to a
    proxy-aware client IP.
    """

    def get_ident(self, request):
        ip = get_client_ip(request)
        if ip:
            return ip
        return super().get_ident(request)

