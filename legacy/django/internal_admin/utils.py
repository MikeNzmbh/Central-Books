from __future__ import annotations

from typing import Any, Optional

from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest

from core.ip_utils import get_client_ip
from .models import AdminAuditLog, InternalAdminProfile


def _object_type_and_id(obj: Any) -> tuple[str, str]:
    if obj is None:
        return "", ""
    if hasattr(obj, "_meta"):
        model = obj._meta.model  # type: ignore[attr-defined]
        ct = ContentType.objects.get_for_model(model, for_concrete_model=False)
        object_type = f"{ct.app_label}.{ct.model}"
    else:
        object_type = obj.__class__.__name__.lower()
    object_id = ""
    if hasattr(obj, "pk"):
        object_id = str(obj.pk)
    elif hasattr(obj, "id"):
        object_id = str(getattr(obj, "id"))
    return object_type, object_id


def _get_actor_role(user) -> str:
    """
    Get the admin role for the user at time of action.
    Returns empty string if user doesn't have an internal admin profile.
    """
    if not user:
        return ""

    # Prefer legacy InternalAdminProfile when present.
    if hasattr(user, "internal_admin_profile"):
        try:
            profile = user.internal_admin_profile
            if profile and getattr(profile, "role", ""):
                return profile.role
        except InternalAdminProfile.DoesNotExist:
            pass

    # Fall back to StaffProfile mapping.
    try:
        staff_profile = getattr(user, "staff_profile", None)
        if staff_profile:
            from internal_admin.permissions import STAFF_ROLE_TO_ADMIN_ROLE

            mapped = STAFF_ROLE_TO_ADMIN_ROLE.get(str(staff_profile.primary_admin_role).strip().lower())
            if mapped:
                return mapped
    except Exception:
        pass

    if getattr(user, "is_superuser", False):
        return "SUPERADMIN"
    return ""


def log_admin_action(
    request: HttpRequest,
    action: str,
    obj: Optional[Any] = None,
    extra: Optional[dict[str, Any]] = None,
    level: str = "INFO",
    category: str | None = None,
) -> AdminAuditLog:
    """
    Log an admin action for audit trail.
    
    Aligned with Gemini spec's "Log-First Architecture" principle:
    - Captures actor identity and role at time of action
    - Records client info (IP, user agent)
    - Stores action-specific metadata
    
    Args:
        request: The HTTP request (for user, IP, user agent)
        action: Action identifier (e.g., "impersonation.start", "feature_flag.toggle")
        obj: Target object of the action (optional)
        extra: Additional metadata dict (optional)
        level: Log level (INFO, WARNING, ERROR)
        category: Action category for filtering (e.g., "security", "billing")
    
    Returns:
        Created AdminAuditLog instance
    """
    object_type, object_id = _object_type_and_id(obj)
    remote_ip = get_client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    request_id = getattr(request, "request_id", "") or (request.META.get("HTTP_X_REQUEST_ID") or "").strip()
    category_value = category or ""
    
    # Get actor role at time of action
    user = getattr(request, "user", None)
    actor_role = _get_actor_role(user)
    actor_user = user if getattr(user, "is_authenticated", False) else None

    entry = AdminAuditLog.objects.create(
        admin_user=actor_user,
        actor_role=actor_role,
        action=action,
        object_type=object_type,
        object_id=object_id,
        extra=extra or {},
        remote_ip=remote_ip,
        user_agent=user_agent,
        request_id=request_id[:128],
        level=level,
        category=category_value,
    )
    return entry
