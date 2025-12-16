from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any, Literal, Optional

from django.http import JsonResponse

from .permissions_registry import equivalent_actions, is_sensitive_action

PermissionLevel = Literal["none", "view", "edit", "approve"]

_LEVEL_ORDER: dict[PermissionLevel, int] = {"none": 0, "view": 1, "edit": 2, "approve": 3}


def _normalize_level(level: str | None) -> PermissionLevel:
    if not level:
        return "none"
    level = level.lower().strip()
    if level in _LEVEL_ORDER:
        return level  # type: ignore[return-value]
    return "none"


def _level_gte(actual: PermissionLevel, required: PermissionLevel) -> bool:
    return _LEVEL_ORDER.get(actual, 0) >= _LEVEL_ORDER.get(required, 0)


def _as_scope(scope: Any) -> dict[str, Any]:
    if isinstance(scope, dict):
        return scope
    if isinstance(scope, str) and scope:
        return {"type": scope}
    return {"type": "all"}


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    level: PermissionLevel
    mask_sensitive: bool


def _resolve_membership(user, business):
    from .models import WorkspaceMembership

    if not user or not getattr(user, "is_authenticated", False):
        return None
    if not business:
        return None
    membership = (
        WorkspaceMembership.objects.filter(user=user, business=business, is_active=True)
        .select_related("role_definition")
        .first()
    )
    if not membership or not membership.is_effective:
        return None
    return membership


def _resolve_role_definition(membership):
    if not membership:
        return None
    role_def = getattr(membership, "role_definition", None)
    if role_def and getattr(role_def, "business_id", None) == membership.business_id:
        return role_def
    from .models import RoleDefinition

    role_def = RoleDefinition.objects.filter(business_id=membership.business_id, key=membership.role).first()
    if role_def:
        return role_def

    # Business created after seed migration: lazily ensure built-ins exist.
    try:
        from .rbac_seeding import ensure_builtin_role_definitions

        ensure_builtin_role_definitions(membership.business)
    except Exception:
        return None

    return RoleDefinition.objects.filter(business_id=membership.business_id, key=membership.role).first()


def _get_role_entry(role_def, action: str) -> tuple[PermissionLevel, dict[str, Any]]:
    if not role_def:
        return "none", {"type": "all"}
    permissions = role_def.permissions or {}
    for candidate in equivalent_actions(action):
        entry = permissions.get(candidate)
        if isinstance(entry, dict):
            level = _normalize_level(entry.get("level"))
            scope = _as_scope(entry.get("scope"))
            return level, scope
    return "none", {"type": "all"}


def _get_override_entry(membership, action: str):
    if not membership:
        return None
    from .models import UserPermissionOverride

    return (
        UserPermissionOverride.objects.filter(membership=membership, action__in=equivalent_actions(action))
        .order_by("id")
        .first()
    )


def _scope_allows(scope: dict[str, Any], membership, context: Optional[dict[str, Any]]) -> bool:
    scope_type = (scope.get("type") or "all").strip().lower()
    if scope_type in {"all", "*"}:
        return True
    if membership is None:
        return False
    if not context:
        return False

    if scope_type == "own_department":
        member_dept = membership.attributes.get("department") if isinstance(membership.attributes, dict) else None
        member_dept = member_dept or getattr(membership, "department", None)
        ctx_dept = context.get("department") or context.get("department_key") or context.get("department_id")
        return bool(member_dept) and bool(ctx_dept) and str(member_dept) == str(ctx_dept)

    if scope_type == "own_created":
        created_by = context.get("created_by_user_id") or context.get("owner_user_id") or context.get("transaction_owner_id")
        return created_by is not None and int(created_by) == int(membership.user_id)

    if scope_type == "selected_accounts":
        account_ids = scope.get("account_ids") or scope.get("selected_accounts") or []
        try:
            account_ids_set = {int(x) for x in account_ids if x is not None}
        except Exception:
            account_ids_set = set()
        ctx_account_id = context.get("bank_account_id") or context.get("account_id")
        if ctx_account_id is None:
            return False
        try:
            return int(ctx_account_id) in account_ids_set
        except Exception:
            return False

    return False


def evaluate_permission(
    user,
    business,
    action: str,
    required_level: PermissionLevel = "view",
    context: Optional[dict[str, Any]] = None,
) -> PermissionDecision:
    """
    Central RBAC v2 evaluation (role definition + overrides + scope).
    """
    required_level = _normalize_level(required_level)
    membership = _resolve_membership(user, business)
    role_def = _resolve_role_definition(membership)

    base_level, base_scope = _get_role_entry(role_def, action)
    if role_def is None and membership:
        # Backwards-compatible fallback to RBAC v1 mapping when role definitions
        # have not been created yet for a business.
        try:
            from .permissions import PERMISSIONS, Role
            from .rbac_seeding import ACTION_CANONICAL, guess_level

            user_role = Role(membership.role)
            for candidate in equivalent_actions(action):
                allowed_roles = PERMISSIONS.get(candidate)
                if allowed_roles and user_role in allowed_roles:
                    canonical_action = ACTION_CANONICAL.get(candidate, candidate)
                    base_level = _normalize_level(guess_level(canonical_action))
                    base_scope = {"type": "all"}
                    break
        except Exception:
            pass

    override = _get_override_entry(membership, action)
    if override and override.effect == "DENY":
        allowed = False
        level: PermissionLevel = "none"
        mask_sensitive = is_sensitive_action(action)
        return PermissionDecision(allowed=allowed, level=level, mask_sensitive=mask_sensitive)

    level = base_level
    scope = base_scope
    if override and override.effect == "ALLOW":
        if override.level_override:
            level = _normalize_level(override.level_override)
        elif level == "none":
            level = "view"
        if override.scope_override is not None:
            scope = _as_scope(override.scope_override)

    allowed = _level_gte(level, required_level) and _scope_allows(scope, membership, context)
    mask_sensitive = is_sensitive_action(action) and not _level_gte(level, "view")
    return PermissionDecision(allowed=allowed, level=level, mask_sensitive=mask_sensitive)


def can(user, business, action: str, context: Optional[dict[str, Any]] = None, level: PermissionLevel = "view") -> bool:
    return evaluate_permission(user, business, action, required_level=level, context=context).allowed


def get_effective_permission_matrix(user, business) -> dict[str, dict[str, Any]]:
    """
    Return action -> {level, scope, allowed_unscoped} for the current user.

    This is intended for frontend gating and settings UI; scope enforcement
    still happens per request with context.
    """
    membership = _resolve_membership(user, business)
    role_def = _resolve_role_definition(membership)
    permissions = dict(role_def.permissions or {}) if role_def else {}

    if not permissions and membership:
        # Backwards-compatible fallback to RBAC v1 mapping.
        try:
            from .permissions import PERMISSIONS, Role
            from .rbac_seeding import ACTION_CANONICAL, guess_level

            user_role = Role(membership.role)
            for action, roles in (PERMISSIONS or {}).items():
                if user_role not in roles:
                    continue
                canonical_action = ACTION_CANONICAL.get(action, action)
                permissions[canonical_action] = {"level": guess_level(canonical_action), "scope": {"type": "all"}}
        except Exception:
            pass

    out: dict[str, dict[str, Any]] = {}
    for action, entry in permissions.items():
        if not isinstance(entry, dict):
            continue
        level = _normalize_level(entry.get("level"))
        scope = _as_scope(entry.get("scope"))
        out[action] = {
            "level": level,
            "scope": scope,
            "allowed_unscoped": _level_gte(level, "view"),
        }

    # Apply overrides (DENY first, then ALLOW)
    if membership:
        from .models import UserPermissionOverride

        overrides = list(UserPermissionOverride.objects.filter(membership=membership).order_by("id"))
        for override in overrides:
            if override.effect != "DENY":
                continue
            out[override.action] = {"level": "none", "scope": {"type": "all"}, "allowed_unscoped": False}
        for override in overrides:
            if override.effect != "ALLOW":
                continue
            level = _normalize_level(override.level_override) if override.level_override else "view"
            scope = _as_scope(override.scope_override) if override.scope_override is not None else {"type": "all"}
            out[override.action] = {"level": level, "scope": scope, "allowed_unscoped": _level_gte(level, "view")}

    return out


def require_permission(action: str, level: PermissionLevel = "view"):
    """
    View decorator enforcing RBAC v2 permission.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from .utils import get_current_business

            business = get_current_business(request.user)
            decision = evaluate_permission(request.user, business, action, required_level=level)
            if not decision.allowed:
                return JsonResponse({"error": f"Permission denied for action: {action}"}, status=403)
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
