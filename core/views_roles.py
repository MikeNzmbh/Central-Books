from __future__ import annotations

import json
import logging
import re
from typing import Any

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods

from .models import RoleDefinition, WorkspaceMembership, UserPermissionOverride
from .permissions import has_permission
from .sod import validate_role_permissions
from .utils import get_current_business

logger = logging.getLogger(__name__)


def _slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "custom-role"


def _require_manage_roles(request, business):
    if not has_permission(request.user, business, "users.manage_roles"):
        return JsonResponse({"error": "Permission denied."}, status=403)
    return None


@login_required
@require_http_methods(["GET", "POST"])
def api_roles_collection(request):
    """
    GET/POST /api/settings/roles/
    """
    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)
    denied = _require_manage_roles(request, business)
    if denied:
        return denied

    if request.method == "GET":
        roles = (
            RoleDefinition.objects.filter(business=business)
            .only("id", "key", "label", "is_builtin", "updated_at")
            .order_by("-is_builtin", "key")
        )
        return JsonResponse(
            {
                "roles": [
                    {
                        "id": r.id,
                        "key": r.key,
                        "label": r.label,
                        "is_builtin": r.is_builtin,
                        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                    }
                    for r in roles
                ]
            }
        )

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    label = (payload.get("label") or "").strip()
    if not label:
        return JsonResponse({"error": "label is required"}, status=400)

    key = (payload.get("key") or "").strip()
    if not key:
        key = _slugify(label).upper()
    key = re.sub(r"[^A-Z0-9_\\-]+", "_", key.upper())

    clone_from_id = payload.get("clone_from_id")
    permissions: dict[str, Any] = {}
    if clone_from_id:
        template = RoleDefinition.objects.filter(business=business, id=clone_from_id).first()
        if not template:
            return JsonResponse({"error": "clone_from_id not found"}, status=404)
        permissions = dict(template.permissions or {})

    # Ensure unique key
    if RoleDefinition.objects.filter(business=business, key=key).exists():
        base = key
        suffix = 2
        while RoleDefinition.objects.filter(business=business, key=f"{base}_{suffix}").exists():
            suffix += 1
        key = f"{base}_{suffix}"

    role = RoleDefinition.objects.create(
        business=business,
        key=key,
        label=label,
        is_builtin=False,
        permissions=permissions,
    )

    return JsonResponse(
        {"role": {"id": role.id, "key": role.key, "label": role.label, "is_builtin": role.is_builtin}},
        status=201,
    )


@login_required
@require_http_methods(["GET", "PATCH", "DELETE"])
def api_role_resource(request, role_id: int):
    """
    GET/PATCH/DELETE /api/settings/roles/<id>/
    """
    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)
    denied = _require_manage_roles(request, business)
    if denied:
        return denied

    role = RoleDefinition.objects.filter(business=business, id=role_id).first()
    if not role:
        return JsonResponse({"error": "Role not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(
            {
                "role": {
                    "id": role.id,
                    "key": role.key,
                    "label": role.label,
                    "is_builtin": role.is_builtin,
                    "permissions": role.permissions or {},
                }
            }
        )

    if request.method == "PATCH":
        try:
            payload = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        next_permissions = role.permissions or {}
        if "permissions" in payload:
            if not isinstance(payload["permissions"], dict):
                return JsonResponse({"error": "permissions must be an object"}, status=400)
            next_permissions = payload["permissions"]

        warnings = validate_role_permissions(next_permissions or {})
        ignore_warnings = payload.get("ignore_warnings") is True
        if warnings and not ignore_warnings:
            return JsonResponse({"warnings": warnings, "error": "SoD warnings"}, status=409)

        updates = {}
        if "label" in payload and (payload.get("label") or "").strip():
            updates["label"] = (payload.get("label") or "").strip()
        if "permissions" in payload:
            updates["permissions"] = next_permissions

        if updates:
            RoleDefinition.objects.filter(id=role.id).update(**updates)
            role.refresh_from_db()

        return JsonResponse(
            {
                "role": {
                    "id": role.id,
                    "key": role.key,
                    "label": role.label,
                    "is_builtin": role.is_builtin,
                    "permissions": role.permissions or {},
                },
                "warnings": warnings,
            }
        )

    # DELETE
    if role.is_builtin:
        return JsonResponse({"error": "Built-in roles cannot be deleted"}, status=400)
    if WorkspaceMembership.objects.filter(business=business, role_definition=role).exists():
        return JsonResponse({"error": "Role is in use by one or more users"}, status=400)
    role.delete()
    return JsonResponse({"deleted": True})


# ---------------------------------------------------------------------------
# Users / Membership assignments
# ---------------------------------------------------------------------------


@login_required
@require_GET
def api_settings_users_list(request):
    """
    GET /api/settings/users/
    """
    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)
    denied = _require_manage_roles(request, business)
    if denied:
        return denied

    memberships = (
        WorkspaceMembership.objects.filter(business=business)
        .select_related("user", "role_definition")
        .order_by("user__email")
    )

    overrides = (
        UserPermissionOverride.objects.filter(membership__business=business)
        .select_related("membership")
        .order_by("membership_id", "action")
    )
    overrides_by_membership: dict[int, list[dict[str, Any]]] = {}
    for o in overrides:
        overrides_by_membership.setdefault(o.membership_id, []).append(
            {
                "action": o.action,
                "effect": o.effect,
                "level_override": o.level_override,
                "scope_override": o.scope_override,
            }
        )

    return JsonResponse(
        {
            "users": [
                {
                    "user_id": m.user_id,
                    "email": m.user.email,
                    "full_name": m.user.get_full_name() or m.user.email,
                    "membership_id": m.id,
                    "role_key": m.role_definition.key if m.role_definition else m.role,
                    "role_definition_id": m.role_definition_id,
                    "overrides": overrides_by_membership.get(m.id, []),
                }
                for m in memberships
            ]
        }
    )


@login_required
@require_http_methods(["PATCH"])
def api_settings_user_membership_update(request, user_id: int):
    """
    PATCH /api/settings/users/<user_id>/membership/
    Body: {role_definition_id?, overrides?}
    """
    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)
    denied = _require_manage_roles(request, business)
    if denied:
        return denied

    membership = WorkspaceMembership.objects.filter(business=business, user_id=user_id).select_related("role_definition").first()
    if not membership:
        return JsonResponse({"error": "Membership not found"}, status=404)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    updates = {}
    if "role_definition_id" in payload:
        role_def_id = payload.get("role_definition_id")
        if role_def_id is None:
            updates["role_definition_id"] = None
        else:
            role_def = RoleDefinition.objects.filter(business=business, id=role_def_id).first()
            if not role_def:
                return JsonResponse({"error": "role_definition_id not found"}, status=404)
            updates["role_definition_id"] = role_def.id
            updates["role"] = role_def.key  # keep v1 compatibility

    if updates:
        WorkspaceMembership.objects.filter(id=membership.id).update(**updates)
        membership.refresh_from_db()

    if "overrides" in payload:
        overrides_payload = payload.get("overrides") or []
        if not isinstance(overrides_payload, list):
            return JsonResponse({"error": "overrides must be a list"}, status=400)
        UserPermissionOverride.objects.filter(membership=membership).delete()
        for row in overrides_payload:
            if not isinstance(row, dict):
                continue
            action = (row.get("action") or "").strip()
            effect = (row.get("effect") or "").strip().upper()
            if not action or effect not in {"ALLOW", "DENY"}:
                continue
            UserPermissionOverride.objects.create(
                membership=membership,
                action=action,
                effect=effect,
                level_override=row.get("level_override") or None,
                scope_override=row.get("scope_override"),
            )

    return JsonResponse({"updated": True})
