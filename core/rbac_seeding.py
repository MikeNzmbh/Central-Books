from __future__ import annotations

from typing import Any

from django.db import transaction


BUILTIN_ROLE_LABELS = {
    "OWNER": "Owner",
    "SYSTEM_ADMIN": "System Admin",
    "CONTROLLER": "Controller",
    "CASH_MANAGER": "Cash Manager",
    "AP_SPECIALIST": "AP Specialist",
    "AR_SPECIALIST": "AR Specialist",
    "BOOKKEEPER": "Bookkeeper",
    "VIEW_ONLY": "View Only",
    "EXTERNAL_ACCOUNTANT": "External Accountant",
    "AUDITOR": "Auditor",
}

ACTION_CANONICAL = {
    "bank.view_balance": "bank.accounts.view_balance",
}


def guess_level(action: str) -> str:
    action = action or ""
    if any(
        token in action
        for token in (
            ".approve",
            ".pay",
            ".file_return",
            ".close_period",
            ".delete",
            ".remove",
            ".reset",
            "manage_roles",
            "workspace.delete",
            "workspace.billing",
        )
    ):
        return "approve"
    if any(
        token in action
        for token in (
            ".create",
            ".edit",
            ".manage",
            ".import",
            ".upload",
            ".invite",
            ".settings",
            ".catalog",
            ".actions",
            "journal_entry",
        )
    ):
        return "edit"
    return "view"


@transaction.atomic
def ensure_builtin_role_definitions(business) -> None:
    """
    Ensure RBAC v2 RoleDefinition rows exist for the business.

    Uses RBAC v1 permission map as defaults.
    """
    from .models import RoleDefinition
    from .permissions import PERMISSIONS

    role_defs_by_key: dict[str, Any] = {}
    for key, label in BUILTIN_ROLE_LABELS.items():
        role_def, _created = RoleDefinition.objects.get_or_create(
            business=business,
            key=key,
            defaults={"label": label, "is_builtin": True, "permissions": {}},
        )
        role_defs_by_key[key] = role_def

    # Populate default permissions only for brand-new roles (empty permissions)
    for key, role_def in role_defs_by_key.items():
        if role_def.permissions:
            continue
        permissions: dict[str, Any] = {}
        for action, roles in (PERMISSIONS or {}).items():
            canonical_action = ACTION_CANONICAL.get(action, action)
            for role_enum in roles:
                role_key = getattr(role_enum, "value", None) or str(role_enum)
                if role_key != key:
                    continue
                permissions[canonical_action] = {"level": guess_level(canonical_action), "scope": {"type": "all"}}
        RoleDefinition.objects.filter(id=role_def.id).update(permissions=permissions)

