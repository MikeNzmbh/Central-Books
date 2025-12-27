from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from companion.models import AICircuitBreakerEvent, AICommandRecord, WorkspaceAISettings


class CompanionBlocked(Exception):
    pass


@dataclass(frozen=True)
class BreakerDecision:
    allowed: bool
    forced_tier: Optional[int] = None
    reason: str = ""


def global_ai_enabled() -> bool:
    return bool(getattr(settings, "COMPANION_AI_GLOBAL_ENABLED", True))


def ensure_ai_settings(workspace) -> WorkspaceAISettings:
    settings_row, _ = WorkspaceAISettings.objects.get_or_create(
        workspace=workspace,
        defaults={
            "ai_enabled": bool(getattr(workspace, "ai_companion_enabled", False)),
            "kill_switch": False,
        },
    )
    return settings_row


def enforce_kill_switch(*, workspace, require_apply_allowed: bool, action: str = "") -> WorkspaceAISettings:
    settings_row = ensure_ai_settings(workspace)
    if not global_ai_enabled():
        raise CompanionBlocked("Companion is globally disabled.")
    if not bool(getattr(workspace, "ai_companion_enabled", False)):
        raise CompanionBlocked("AI Companion is disabled for this workspace.")
    if not settings_row.ai_enabled:
        raise CompanionBlocked("Companion is disabled for this workspace.")
    if bool(getattr(settings_row, "kill_switch", False)):
        record_breaker(
            workspace=workspace,
            breaker=AICircuitBreakerEvent.Breaker.KILL_SWITCH,
            action=action,
            details={"kill_switch": True},
        )
        raise CompanionBlocked("Companion kill switch is enabled for this workspace.")
    if require_apply_allowed and settings_row.ai_mode == WorkspaceAISettings.AIMode.SHADOW_ONLY:
        raise CompanionBlocked("Shadow-only mode: proposals are allowed, but apply/promote is disabled.")
    return settings_row


@transaction.atomic
def record_breaker(*, workspace, breaker: str, action: str, details: dict) -> None:
    AICircuitBreakerEvent.objects.create(workspace=workspace, breaker=breaker, action=action or "", details=details or {})


def velocity_breaker(*, workspace, settings_row: WorkspaceAISettings, actor: str, action: str) -> BreakerDecision:
    window_start = timezone.now() - timedelta(minutes=1)
    recent = (
        AICommandRecord.objects.filter(workspace=workspace, actor=actor, created_at__gte=window_start)
        .filter(Q(command_type__startswith="Propose") | Q(command_type__startswith="Apply"))
        .count()
    )
    if recent >= int(settings_row.velocity_limit_per_minute or 0):
        record_breaker(
            workspace=workspace,
            breaker=AICircuitBreakerEvent.Breaker.VELOCITY,
            action=action,
            details={"recent_per_minute": recent, "limit": settings_row.velocity_limit_per_minute},
        )
        return BreakerDecision(allowed=False, reason="velocity_breaker")
    return BreakerDecision(allowed=True)


def value_breaker(*, amount: Decimal | None, settings_row: WorkspaceAISettings, action: str, workspace) -> BreakerDecision:
    if amount is None:
        return BreakerDecision(allowed=True)
    threshold = Decimal(str(settings_row.value_breaker_threshold or 0))
    if threshold > 0 and abs(Decimal(str(amount))) >= threshold:
        record_breaker(
            workspace=workspace,
            breaker=AICircuitBreakerEvent.Breaker.VALUE,
            action=action,
            details={"amount": str(amount), "threshold": str(threshold)},
        )
        return BreakerDecision(allowed=True, forced_tier=2, reason="value_breaker")
    return BreakerDecision(allowed=True)


def trust_breaker(*, workspace, settings_row: WorkspaceAISettings, rejection_rate: float, action: str) -> BreakerDecision:
    try:
        threshold = float(settings_row.trust_downgrade_rejection_rate or 0)
    except Exception:
        threshold = 0.0
    if threshold > 0 and rejection_rate >= threshold and settings_row.ai_mode == WorkspaceAISettings.AIMode.AUTOPILOT_LIMITED:
        settings_row.ai_mode = WorkspaceAISettings.AIMode.SUGGEST_ONLY
        settings_row.save(update_fields=["ai_mode", "updated_at"])
        record_breaker(
            workspace=workspace,
            breaker=AICircuitBreakerEvent.Breaker.TRUST,
            action=action,
            details={"rejection_rate": rejection_rate, "threshold": threshold, "new_mode": settings_row.ai_mode},
        )
        return BreakerDecision(allowed=True, forced_tier=1, reason="trust_breaker_downgrade")
    return BreakerDecision(allowed=True)
