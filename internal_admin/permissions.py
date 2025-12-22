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
    AdminRole.PRIMARY_ADMIN: 5,
}

STAFF_ROLE_TO_ADMIN_ROLE: dict[str, str] = {
    "support": AdminRole.SUPPORT,
    "finance": AdminRole.OPS,
    "engineering": AdminRole.ENGINEERING,
    "superadmin": AdminRole.SUPERADMIN,
}


def _staff_profile_for(user: User):
    try:
        return getattr(user, "staff_profile", None)
    except Exception:
        return None


def can_access_admin_panel(user: User) -> bool:
    """
    Source-of-truth guard for /internal-admin access.

    Rules:
    - Django superuser always allowed (break-glass).
    - If StaffProfile exists: requires admin_panel_access + active employee + not deleted.
    - Legacy fallback: InternalAdminProfile grants access when StaffProfile absent.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True

    staff_profile = _staff_profile_for(user)
    if staff_profile is not None:
        return (
            bool(getattr(staff_profile, "admin_panel_access", False))
            and bool(getattr(staff_profile, "is_active_employee", True))
            and (not bool(getattr(staff_profile, "is_deleted", False)))
        )

    profile = getattr(user, "internal_admin_profile", None)
    return bool(profile and getattr(profile, "role", None))


def can_manage_admin_users(user: User) -> bool:
    role = get_user_admin_role(user)
    if getattr(user, "is_superuser", False):
        return True
    return role in {AdminRole.SUPERADMIN, AdminRole.PRIMARY_ADMIN}


def can_grant_superadmin(user: User) -> bool:
    role = get_user_admin_role(user)
    if getattr(user, "is_superuser", False):
        return True
    return role == AdminRole.PRIMARY_ADMIN


def get_user_admin_role(user: User) -> Optional[str]:
    if not can_access_admin_panel(user):
        return None

    staff_profile = _staff_profile_for(user)
    if staff_profile is not None:
        role_value = getattr(staff_profile, "primary_admin_role", None) or ""
        mapped = STAFF_ROLE_TO_ADMIN_ROLE.get(str(role_value).strip().lower())
        if mapped:
            return mapped

    profile = getattr(user, "internal_admin_profile", None)
    if profile and profile.role:
        return profile.role
    if getattr(user, "is_superuser", False):
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

        deny_reason = ""
        allowed = has_min_role(user, min_role)
        if not allowed:
            deny_reason = "insufficient_role"
        else:
            try:
                from internal_admin.access_policy import check_internal_admin_access

                policy_allowed, policy_reason = check_internal_admin_access(request, user)
                if not policy_allowed:
                    allowed = False
                    deny_reason = policy_reason or "policy_denied"
            except Exception:
                allowed = False
                deny_reason = "policy_error"

        if not allowed and not getattr(request, "_internal_admin_denied_logged", False):
            try:
                request._internal_admin_denied_logged = True  # type: ignore[attr-defined]
                from internal_admin.utils import log_admin_action

                log_admin_action(
                    request,
                    action="access.denied",
                    obj=None,
                    extra={
                        "path": getattr(request, "path", ""),
                        "method": getattr(request, "method", ""),
                        "required_role": min_role,
                        "view": view.__class__.__name__,
                        "reason": deny_reason,
                    },
                    level="WARNING",
                    category="security",
                )
            except Exception:
                pass
        return allowed
