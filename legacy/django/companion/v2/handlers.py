from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Optional, Tuple
from uuid import UUID

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction

from companion.models import (
    AICommandRecord,
    BusinessPolicy,
    CanonicalLedgerProvenance,
    ProvisionalLedgerEvent,
)
from core.models import Account, BankTransaction, JournalEntry, ReconciliationSession
from core.services.bank_reconciliation import BankReconciliationService
from taxes.models import TaxPeriodSnapshot

from .commands import (
    ApplyBankMatchCommand,
    ApplyCategorizationCommand,
    CompanionCommand,
    ProposeBankMatchCommand,
    ProposeCategorizationCommand,
)
from .guardrails import (
    BreakerDecision,
    CompanionBlocked,
    enforce_kill_switch,
    ensure_ai_settings,
    value_breaker,
    velocity_breaker,
)


class CommandValidationError(Exception):
    pass


FORBIDDEN_AUTOPILOT_ACCOUNT_TOKENS = (
    "payroll",
    "wages",
    "salary",
    "equity",
    "shareholder",
    "owner draw",
    "owners draw",
    "owner's draw",
    "shareholder loan",
    "loan",
    "intercompany",
    "due to",
    "due from",
)


def _period_key_for_date(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def _is_tax_period_locked(*, workspace, txn_date: date) -> bool:
    period_key = _period_key_for_date(txn_date)
    return TaxPeriodSnapshot.objects.filter(
        business=workspace,
        period_key=period_key,
        status=TaxPeriodSnapshot.SnapshotStatus.FILED,
    ).exists()


def _require_not_locked(*, workspace, bank_tx: BankTransaction) -> None:
    if bank_tx.reconciliation_session_id:
        session = ReconciliationSession.objects.filter(id=bank_tx.reconciliation_session_id).first()
        if session and session.status == ReconciliationSession.Status.COMPLETED:
            raise CommandValidationError("Bank transaction is in a completed reconciliation session (locked).")
    if _is_tax_period_locked(workspace=workspace, txn_date=bank_tx.date):
        raise CommandValidationError("Tax period is filed/locked for this transaction date.")


def _normalize_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _stable_snapshot_hash(snapshot: dict[str, Any]) -> str:
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _bank_tx_snapshot(bank_tx: BankTransaction) -> dict[str, Any]:
    return {
        "version": 1,
        "model": "core.BankTransaction",
        "id": bank_tx.id,
        "bank_account_id": bank_tx.bank_account_id,
        "date": bank_tx.date.isoformat() if bank_tx.date else None,
        "amount": str(bank_tx.amount),
        "allocated_amount": str(bank_tx.allocated_amount),
        "status": bank_tx.status,
        "posted_journal_entry_id": bank_tx.posted_journal_entry_id,
        "reconciliation_session_id": bank_tx.reconciliation_session_id,
        "reconciliation_status": bank_tx.reconciliation_status,
        "is_reconciled": bool(bank_tx.is_reconciled),
    }


def _validate_account_for_bank_tx(*, workspace, bank_tx: BankTransaction, account: Account) -> None:
    if account.business_id != workspace.id:
        raise CommandValidationError("Account does not belong to this workspace.")
    is_deposit = bank_tx.amount > 0
    if is_deposit and account.type != Account.AccountType.INCOME:
        raise CommandValidationError("Deposits must use an income account.")
    if (not is_deposit) and account.type != Account.AccountType.EXPENSE:
        raise CommandValidationError("Withdrawals must use an expense account.")


def _is_forbidden_autopilot_account(account: Account) -> bool:
    name = (account.name or "").strip().lower()
    if account.type == Account.AccountType.EQUITY:
        return True
    return any(token in name for token in FORBIDDEN_AUTOPILOT_ACCOUNT_TOKENS)


@dataclass(frozen=True)
class CategorizationProposal:
    bank_tx: BankTransaction
    splits: list[dict[str, Any]]
    forced_tier: Optional[int]
    high_risk_reasons: list[str]


def _validate_and_normalize_splits(
    *,
    workspace,
    bank_tx: BankTransaction,
    splits: list[dict[str, Any]],
) -> CategorizationProposal:
    if not splits:
        raise CommandValidationError("At least one split is required.")

    normalized: list[dict[str, Any]] = []
    split_total = Decimal("0.00")
    high_risk_reasons: list[str] = []

    for split in splits:
        if not isinstance(split, dict):
            raise CommandValidationError("Each split must be an object.")
        if "account_id" not in split:
            raise CommandValidationError("Split is missing account_id.")
        if "amount" not in split:
            raise CommandValidationError("Split is missing amount.")
        account_id = int(split["account_id"])
        amount = _normalize_decimal(split["amount"])
        if amount <= 0:
            raise CommandValidationError("Split amount must be positive.")
        account = Account.objects.filter(id=account_id).first()
        if not account:
            raise CommandValidationError(f"Account {account_id} not found.")
        _validate_account_for_bank_tx(workspace=workspace, bank_tx=bank_tx, account=account)
        if _is_forbidden_autopilot_account(account):
            high_risk_reasons.append("scope_boundary_account")

        normalized.append(
            {
                "account_id": account_id,
                "account_name": account.name,
                "account_type": account.type,
                "amount": str(amount),
                "description": (split.get("description") or bank_tx.description or "").strip()[:255],
            }
        )
        split_total += amount

    tx_amount_abs = abs(_normalize_decimal(bank_tx.amount))
    if abs(split_total - tx_amount_abs) > Decimal("0.01"):
        raise CommandValidationError(f"Splits must sum to {tx_amount_abs}, got {split_total}.")

    forced_tier: Optional[int] = None
    settings_row = ensure_ai_settings(workspace)
    value_decision = value_breaker(amount=tx_amount_abs, settings_row=settings_row, action="categorization", workspace=workspace)
    if value_decision.forced_tier is not None:
        forced_tier = value_decision.forced_tier
        high_risk_reasons.append(value_decision.reason)

    return CategorizationProposal(
        bank_tx=bank_tx,
        splits=normalized,
        forced_tier=forced_tier,
        high_risk_reasons=sorted(set(high_risk_reasons)),
    )


def _policy_snapshot(*, workspace) -> dict[str, Any]:
    policy, _ = BusinessPolicy.objects.get_or_create(workspace=workspace)
    return {
        "materiality_threshold": str(policy.materiality_threshold),
        "risk_appetite": policy.risk_appetite,
        "commingling_risk_vendors": policy.commingling_risk_vendors,
        "related_entities": policy.related_entities,
        "intercompany_enabled": policy.intercompany_enabled,
        "sector_archetype": policy.sector_archetype,
        "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
    }


def _create_command_record(
    *,
    workspace,
    command: CompanionCommand,
    status: str,
    created_by,
    error_message: str = "",
    shadow_event: ProvisionalLedgerEvent | None = None,
) -> AICommandRecord:
    return AICommandRecord.objects.create(
        workspace=workspace,
        command_type=getattr(command, "type", command.__class__.__name__),
        payload=command.model_dump(mode="json", exclude_none=True),
        metadata=command.metadata.model_dump(mode="json", exclude_none=True),
        actor=command.metadata.actor,
        status=status,
        error_message=error_message or "",
        created_by=created_by,
        shadow_event=shadow_event,
    )


def _shadow_event_base_metadata(command: CompanionCommand, *, workspace) -> dict[str, Any]:
    meta = command.metadata.model_dump(mode="json", exclude_none=True)
    meta["command_id"] = str(command.command_id)
    meta["command_type"] = getattr(command, "type", command.__class__.__name__)
    meta["policy_snapshot"] = _policy_snapshot(workspace=workspace)
    return meta


@transaction.atomic
def propose_categorization(*, workspace, command: ProposeCategorizationCommand, created_by) -> ProvisionalLedgerEvent:
    if command.workspace_id != workspace.id:
        raise CommandValidationError("workspace_id mismatch.")

    settings_row = enforce_kill_switch(workspace=workspace, require_apply_allowed=False, action=command.type)
    velocity = velocity_breaker(workspace=workspace, settings_row=settings_row, actor=command.metadata.actor, action=command.type)
    if not velocity.allowed:
        _create_command_record(workspace=workspace, command=command, status=AICommandRecord.Status.REJECTED, created_by=created_by, error_message=velocity.reason)
        raise CompanionBlocked("Velocity circuit breaker tripped.")

    bank_tx = (
        BankTransaction.objects.select_related("bank_account", "bank_account__business")
        .filter(id=command.bank_transaction_id)
        .first()
    )
    if not bank_tx or bank_tx.bank_account.business_id != workspace.id:
        raise CommandValidationError("Bank transaction not found in this workspace.")

    proposal = _validate_and_normalize_splits(workspace=workspace, bank_tx=bank_tx, splits=command.proposed_splits)

    forced_tier = proposal.forced_tier
    tier = forced_tier if forced_tier is not None else command.metadata.human_in_the_loop.tier
    human = command.metadata.human_in_the_loop.model_dump(mode="json")
    human["tier"] = tier
    human.setdefault("status", "proposed")
    if proposal.high_risk_reasons:
        human["risk_reasons"] = proposal.high_risk_reasons

    metadata = _shadow_event_base_metadata(command, workspace=workspace)
    snapshot = _bank_tx_snapshot(bank_tx)
    metadata["resource_snapshot"] = snapshot
    metadata["resource_snapshot_hash"] = _stable_snapshot_hash(snapshot)
    bank_tx_ct = ContentType.objects.get_for_model(BankTransaction)
    shadow_event = ProvisionalLedgerEvent.objects.create(
        workspace=workspace,
        command_id=command.command_id,
        bank_transaction=bank_tx,
        event_type="CategorizationProposed",
        status=ProvisionalLedgerEvent.Status.PROPOSED,
        subject_content_type=bank_tx_ct,
        subject_object_id=bank_tx.id,
        data={
            "bank_transaction_id": bank_tx.id,
            "bank_account_id": bank_tx.bank_account_id,
            "bank_transaction_description": bank_tx.description,
            "bank_transaction_amount": str(bank_tx.amount),
            "bank_transaction_date": bank_tx.date.isoformat(),
            "splits": proposal.splits,
        },
        actor=command.metadata.actor,
        confidence_score=command.metadata.confidence_score,
        logic_trace_id=command.metadata.logic_trace_id or "",
        rationale=command.metadata.rationale or "",
        business_profile_constraint=command.metadata.business_profile_constraint or "",
        human_in_the_loop=human,
        metadata=metadata,
        created_by=created_by,
    )

    command_record = _create_command_record(
        workspace=workspace,
        command=command,
        status=AICommandRecord.Status.ACCEPTED,
        created_by=created_by,
        shadow_event=shadow_event,
    )
    shadow_event.source_command = command_record
    shadow_event.save(update_fields=["source_command", "updated_at"])
    return shadow_event


@transaction.atomic
def propose_bank_match(*, workspace, command: ProposeBankMatchCommand, created_by) -> ProvisionalLedgerEvent:
    if command.workspace_id != workspace.id:
        raise CommandValidationError("workspace_id mismatch.")
    settings_row = enforce_kill_switch(workspace=workspace, require_apply_allowed=False, action=command.type)
    velocity = velocity_breaker(workspace=workspace, settings_row=settings_row, actor=command.metadata.actor, action=command.type)
    if not velocity.allowed:
        _create_command_record(workspace=workspace, command=command, status=AICommandRecord.Status.REJECTED, created_by=created_by, error_message=velocity.reason)
        raise CompanionBlocked("Velocity circuit breaker tripped.")

    bank_tx = BankTransaction.objects.select_related("bank_account").filter(id=command.bank_transaction_id).first()
    if not bank_tx or bank_tx.bank_account.business_id != workspace.id:
        raise CommandValidationError("Bank transaction not found in this workspace.")

    journal_entry = JournalEntry.objects.filter(id=command.journal_entry_id, business=workspace).first()
    if not journal_entry:
        raise CommandValidationError("Journal entry not found in this workspace.")

    metadata = _shadow_event_base_metadata(command, workspace=workspace)
    snapshot = _bank_tx_snapshot(bank_tx)
    metadata["resource_snapshot"] = snapshot
    metadata["resource_snapshot_hash"] = _stable_snapshot_hash(snapshot)
    bank_tx_ct = ContentType.objects.get_for_model(BankTransaction)
    human = command.metadata.human_in_the_loop.model_dump(mode="json")
    human.setdefault("status", "proposed")
    shadow_event = ProvisionalLedgerEvent.objects.create(
        workspace=workspace,
        command_id=command.command_id,
        bank_transaction=bank_tx,
        event_type="BankMatchProposed",
        status=ProvisionalLedgerEvent.Status.PROPOSED,
        subject_content_type=bank_tx_ct,
        subject_object_id=bank_tx.id,
        data={
            "bank_transaction_id": bank_tx.id,
            "bank_account_id": bank_tx.bank_account_id,
            "bank_transaction_description": bank_tx.description,
            "journal_entry_id": journal_entry.id,
            "journal_entry_date": journal_entry.date.isoformat(),
            "journal_entry_description": journal_entry.description,
            "match_confidence": str(command.match_confidence),
        },
        actor=command.metadata.actor,
        confidence_score=command.metadata.confidence_score,
        logic_trace_id=command.metadata.logic_trace_id or "",
        rationale=command.metadata.rationale or "",
        business_profile_constraint=command.metadata.business_profile_constraint or "",
        human_in_the_loop=human,
        metadata=metadata,
        created_by=created_by,
    )
    command_record = _create_command_record(
        workspace=workspace,
        command=command,
        status=AICommandRecord.Status.ACCEPTED,
        created_by=created_by,
        shadow_event=shadow_event,
    )
    shadow_event.source_command = command_record
    shadow_event.save(update_fields=["source_command", "updated_at"])
    return shadow_event


def _load_shadow_event(*, workspace, shadow_event_id: UUID) -> ProvisionalLedgerEvent:
    event = ProvisionalLedgerEvent.objects.filter(id=shadow_event_id, workspace=workspace).first()
    if not event:
        raise CommandValidationError("Shadow event not found.")
    if event.status != ProvisionalLedgerEvent.Status.PROPOSED:
        raise CommandValidationError(f"Shadow event is not in proposed state (status={event.status}).")
    return event


def _enforce_shadow_snapshot(*, shadow_event: ProvisionalLedgerEvent, bank_tx: BankTransaction) -> None:
    expected_hash = (shadow_event.metadata or {}).get("resource_snapshot_hash")
    if not expected_hash:
        return
    current = _bank_tx_snapshot(bank_tx)
    current_hash = _stable_snapshot_hash(current)
    if current_hash != expected_hash:
        raise CommandValidationError("StateConflict: bank transaction changed since proposal; re-run Propose* first.")


@transaction.atomic
def apply_categorization(
    *,
    workspace,
    command: ApplyCategorizationCommand,
    approved_by,
) -> Tuple[JournalEntry, Any]:
    if command.workspace_id != workspace.id:
        raise CommandValidationError("workspace_id mismatch.")
    enforce_kill_switch(workspace=workspace, require_apply_allowed=True, action=command.type)

    shadow_event = _load_shadow_event(workspace=workspace, shadow_event_id=command.shadow_event_id)
    if shadow_event.event_type != "CategorizationProposed":
        raise CommandValidationError("Shadow event type is not CategorizationProposed.")

    bank_transaction_id = int((shadow_event.data or {}).get("bank_transaction_id") or 0)
    bank_tx = (
        BankTransaction.objects.select_for_update()
        .select_related("bank_account")
        .filter(id=bank_transaction_id)
        .first()
    )
    if not bank_tx or bank_tx.bank_account.business_id != workspace.id:
        raise CommandValidationError("Bank transaction not found in this workspace.")

    _enforce_shadow_snapshot(shadow_event=shadow_event, bank_tx=bank_tx)
    _require_not_locked(workspace=workspace, bank_tx=bank_tx)

    splits = command.override_splits if command.override_splits is not None else (shadow_event.data or {}).get("splits") or []
    proposal = _validate_and_normalize_splits(workspace=workspace, bank_tx=bank_tx, splits=splits)

    journal_entry, match = BankReconciliationService.create_split_entry(
        bank_transaction=bank_tx,
        splits=[{**s, "amount": _normalize_decimal(s["amount"])} for s in proposal.splits],
        user=approved_by,
        session=bank_tx.reconciliation_session,
    )
    try:
        journal_entry.check_balance()
    except ValidationError as exc:
        raise CommandValidationError(str(exc)) from exc

    shadow_event.status = ProvisionalLedgerEvent.Status.APPLIED
    human = dict(shadow_event.human_in_the_loop or {})
    human["status"] = "accepted"
    human["approved_by_user_id"] = getattr(approved_by, "id", None)
    shadow_event.human_in_the_loop = human
    shadow_event.save(update_fields=["status", "human_in_the_loop", "updated_at"])

    CanonicalLedgerProvenance.objects.create(
        workspace=workspace,
        shadow_event=shadow_event,
        content_type=ContentType.objects.get_for_model(JournalEntry),
        object_id=journal_entry.id,
        actor=shadow_event.actor,
        applied_by=approved_by,
        metadata=shadow_event.metadata or {},
    )
    CanonicalLedgerProvenance.objects.create(
        workspace=workspace,
        shadow_event=shadow_event,
        content_type=ContentType.objects.get_for_model(type(match)),
        object_id=match.id,
        actor=shadow_event.actor,
        applied_by=approved_by,
        metadata=shadow_event.metadata or {},
    )

    _create_command_record(
        workspace=workspace,
        command=command,
        status=AICommandRecord.Status.ACCEPTED,
        created_by=approved_by,
        shadow_event=shadow_event,
    )
    return journal_entry, match


@transaction.atomic
def apply_bank_match(*, workspace, command: ApplyBankMatchCommand, approved_by):
    if command.workspace_id != workspace.id:
        raise CommandValidationError("workspace_id mismatch.")
    enforce_kill_switch(workspace=workspace, require_apply_allowed=True, action=command.type)

    shadow_event = _load_shadow_event(workspace=workspace, shadow_event_id=command.shadow_event_id)
    if shadow_event.event_type != "BankMatchProposed":
        raise CommandValidationError("Shadow event type is not BankMatchProposed.")

    bank_transaction_id = int((shadow_event.data or {}).get("bank_transaction_id") or 0)
    journal_entry_id = int((shadow_event.data or {}).get("journal_entry_id") or 0)
    match_confidence = _normalize_decimal((shadow_event.data or {}).get("match_confidence") or "1.00")

    bank_tx = (
        BankTransaction.objects.select_for_update()
        .select_related("bank_account")
        .filter(id=bank_transaction_id)
        .first()
    )
    if not bank_tx or bank_tx.bank_account.business_id != workspace.id:
        raise CommandValidationError("Bank transaction not found in this workspace.")
    _enforce_shadow_snapshot(shadow_event=shadow_event, bank_tx=bank_tx)
    _require_not_locked(workspace=workspace, bank_tx=bank_tx)

    journal_entry = JournalEntry.objects.filter(id=journal_entry_id, business=workspace).first()
    if not journal_entry:
        raise CommandValidationError("Journal entry not found in this workspace.")

    match = BankReconciliationService.confirm_match(
        bank_transaction=bank_tx,
        journal_entry=journal_entry,
        match_confidence=match_confidence,
        user=approved_by,
        session=bank_tx.reconciliation_session,
    )

    shadow_event.status = ProvisionalLedgerEvent.Status.APPLIED
    human = dict(shadow_event.human_in_the_loop or {})
    human["status"] = "accepted"
    human["approved_by_user_id"] = getattr(approved_by, "id", None)
    shadow_event.human_in_the_loop = human
    shadow_event.save(update_fields=["status", "human_in_the_loop", "updated_at"])

    CanonicalLedgerProvenance.objects.create(
        workspace=workspace,
        shadow_event=shadow_event,
        content_type=ContentType.objects.get_for_model(JournalEntry),
        object_id=journal_entry.id,
        actor=shadow_event.actor,
        applied_by=approved_by,
        metadata=shadow_event.metadata or {},
    )
    CanonicalLedgerProvenance.objects.create(
        workspace=workspace,
        shadow_event=shadow_event,
        content_type=ContentType.objects.get_for_model(type(match)),
        object_id=match.id,
        actor=shadow_event.actor,
        applied_by=approved_by,
        metadata=shadow_event.metadata or {},
    )

    _create_command_record(
        workspace=workspace,
        command=command,
        status=AICommandRecord.Status.ACCEPTED,
        created_by=approved_by,
        shadow_event=shadow_event,
    )
    return match
