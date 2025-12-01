from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from rest_framework.permissions import BasePermission

from .models import AdminRole


User = get_user_model()

ROLE_ORDER = {
    AdminRole.SUPPORT: 1,
    AdminRole.OPS: 2,
    AdminRole.ENGINEERING: 3,
    AdminRole.SUPERADMIN: 4,
}


def get_user_admin_role(user: User) -> Optional[str]:
    profile = getattr(user, "internal_admin_profile", None)
    if profile and profile.role:
        return profile.role
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return AdminRole.SUPERADMIN
    return None


def has_min_role(user: User, min_role: str) -> bool:
    role = get_user_admin_role(user)
    if role is None:
        return False
    return ROLE_ORDER.get(role, 0) >= ROLE_ORDER.get(min_role, 0)


class IsInternalAdminWithRole(BasePermission):
    """
    Ensures the user is authenticated and has an internal admin role.
    Supports per-view minimum role via `required_role` attribute or `get_min_role` method.
    """

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False

        min_role = None
        if hasattr(view, "get_min_role"):
            try:
                min_role = view.get_min_role(request)
            except TypeError:
                min_role = view.get_min_role()  # type: ignore[call-arg]
        if min_role is None:
            min_role = getattr(view, "required_role", AdminRole.SUPPORT)

        return has_min_role(user, min_role)
