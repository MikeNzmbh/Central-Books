from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .permissions_engine import PermissionLevel
from .permissions_registry import equivalent_actions


SoDSeverity = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class SoDWarning:
    id: str
    severity: SoDSeverity
    message: str
    actions: list[str]


TOXIC_COMBINATIONS: list[SoDWarning] = [
    SoDWarning(
        id="vendor_fraud",
        actions=["vendor.edit_payment_details", "expenses.pay"],
        severity="high",
        message="This combination can enable fake-vendor fraud (edit vendor payment + pay bills).",
    ),
    SoDWarning(
        id="invoice_writeoff",
        actions=["invoices.create", "invoices.delete"],
        severity="medium",
        message="Creating and voiding invoices can enable concealment workflows; require approvals/limits.",
    ),
    SoDWarning(
        id="bank_reco_and_vendors",
        actions=["bank.reconcile", "suppliers.manage"],
        severity="high",
        message="Reconciliation + vendor creation can enable lapping/skimming/fake-vendor schemes.",
    ),
]


def _extract_level(entry: Any) -> PermissionLevel:
    if not isinstance(entry, dict):
        return "none"
    level = (entry.get("level") or "none").strip().lower()
    if level in {"none", "view", "edit", "approve"}:
        return level  # type: ignore[return-value]
    return "none"


def _level_order(level: PermissionLevel) -> int:
    return {"none": 0, "view": 1, "edit": 2, "approve": 3}.get(level, 0)


def _grants(permissions: dict[str, Any], action: str, min_level: PermissionLevel = "view") -> bool:
    for candidate in equivalent_actions(action):
        entry = permissions.get(candidate)
        if _level_order(_extract_level(entry)) >= _level_order(min_level):
            return True
    return False


def validate_role_permissions(permissions: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Return SoD warnings for a role permission matrix.

    The return shape is JSON-friendly for APIs.
    """
    warnings: list[dict[str, Any]] = []
    for rule in TOXIC_COMBINATIONS:
        if all(_grants(permissions, action, min_level="edit") for action in rule.actions):
            warnings.append(
                {
                    "id": rule.id,
                    "actions": rule.actions,
                    "severity": rule.severity,
                    "message": rule.message,
                }
            )
    return warnings
