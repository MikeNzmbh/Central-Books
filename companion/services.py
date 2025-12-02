from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, Tuple, Iterable

from django.db import transaction
from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.models import BankTransaction, Expense, Invoice, JournalEntry
from core.services.bank_matching import BankMatchingEngine, MatchingConfig
from core.services.bank_reconciliation import BankReconciliationService
from .models import CompanionInsight, CompanionSuggestedAction, HealthIndexSnapshot, WorkspaceMemory


def _safe_int(value: int | None, default: int = 0) -> int:
    return int(value) if value is not None else default


def _as_date(value) -> date | None:
    if value is None:
        return None
    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            return None
    return value


def gather_workspace_metrics(workspace) -> Dict[str, int]:
    """
    Collect lightweight, deterministic metrics per workspace.
    """
    today = timezone.now().date()
    days_60 = today - timedelta(days=60)
    days_90 = today - timedelta(days=90)

    unreconciled_qs = BankTransaction.objects.filter(
        bank_account__business=workspace,
        reconciliation_status=BankTransaction.RECO_STATUS_UNRECONCILED,
    )
    unreconciled_count = unreconciled_qs.count()
    old_unreconciled_60d = unreconciled_qs.filter(date__lte=days_60).count()
    old_unreconciled_90d = unreconciled_qs.filter(date__lte=days_90).count()

    journal_totals = (
        JournalEntry.objects.filter(business=workspace, is_void=False)
        .annotate(
            total_debit=Coalesce(Sum("lines__debit"), Decimal("0.0000")),
            total_credit=Coalesce(Sum("lines__credit"), Decimal("0.0000")),
        )
        .filter(
            Q(total_debit=Decimal("0.0000"))
            | Q(total_credit=Decimal("0.0000"))
            | ~Q(total_debit=F("total_credit"))
        )
    )
    unbalanced_journal_entries = journal_totals.count()
    future_dated_entries = JournalEntry.objects.filter(business=workspace, date__gt=today).count()

    overdue_qs = Invoice.objects.filter(
        business=workspace,
        status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL],
        due_date__lt=today,
    )
    overdue_invoices = overdue_qs.count()
    overdue_invoices_60d = overdue_qs.filter(due_date__lte=days_60).count()

    uncategorized_expenses = Expense.objects.filter(
        business=workspace,
        category__isnull=True,
    ).count()

    unlinked_bank_transactions = unreconciled_qs.filter(
        matched_invoice__isnull=True,
        matched_expense__isnull=True,
    ).count()

    tax_mismatches = (
        Invoice.objects.filter(
            business=workspace,
            tax_amount__gt=0,
            tax_group__isnull=True,
            tax_rate__isnull=True,
        ).count()
        + Expense.objects.filter(
            business=workspace,
            tax_amount__gt=0,
            tax_group__isnull=True,
            tax_rate__isnull=True,
        ).count()
    )

    activity_dates = []
    latest_invoice = Invoice.objects.filter(business=workspace).order_by("-issue_date").values_list("issue_date", flat=True).first()
    latest_expense = Expense.objects.filter(business=workspace).order_by("-date").values_list("date", flat=True).first()
    latest_bank_tx = (
        BankTransaction.objects.filter(bank_account__business=workspace)
        .order_by("-date")
        .values_list("date", flat=True)
        .first()
    )
    latest_journal = JournalEntry.objects.filter(business=workspace).order_by("-date").values_list("date", flat=True).first()

    for candidate in [latest_invoice, latest_expense, latest_bank_tx, latest_journal]:
        candidate_date = _as_date(candidate)
        if candidate_date:
            activity_dates.append(candidate_date)

    if hasattr(workspace, "created_at") and workspace.created_at:
        created_date = _as_date(workspace.created_at)
        if created_date:
            activity_dates.append(created_date)

    last_activity_days_ago = 999
    if activity_dates:
        most_recent = max(activity_dates)
        last_activity_days_ago = max(0, (today - most_recent).days)

    return {
        "unreconciled_count": _safe_int(unreconciled_count),
        "old_unreconciled_60d": _safe_int(old_unreconciled_60d),
        "old_unreconciled_90d": _safe_int(old_unreconciled_90d),
        "unbalanced_journal_entries": _safe_int(unbalanced_journal_entries),
        "future_dated_entries": _safe_int(future_dated_entries),
        "overdue_invoices": _safe_int(overdue_invoices),
        "overdue_invoices_60d": _safe_int(overdue_invoices_60d),
        "uncategorized_expenses": _safe_int(uncategorized_expenses),
        "unlinked_bank_transactions": _safe_int(unlinked_bank_transactions),
        "tax_mismatches": _safe_int(tax_mismatches),
        "last_activity_days_ago": _safe_int(last_activity_days_ago),
    }


def _score_from_penalty(base: int, penalty: float) -> int:
    return max(0, min(100, int(round(base - penalty))))


def compute_health_index(workspace) -> Tuple[int, Dict[str, int], Dict[str, int]]:
    """
    Returns (score, breakdown, raw_metrics).
    """
    raw_metrics = gather_workspace_metrics(workspace)

    reconciliation_penalty = (
        raw_metrics["unreconciled_count"] * 2
        + raw_metrics["old_unreconciled_60d"] * 3
        + raw_metrics["old_unreconciled_90d"] * 4
    )
    ledger_penalty = (
        raw_metrics["unbalanced_journal_entries"] * 5
        + raw_metrics["future_dated_entries"] * 2
    )
    invoices_penalty = (
        raw_metrics["overdue_invoices"] * 2
        + raw_metrics["overdue_invoices_60d"] * 3
    )
    expenses_penalty = raw_metrics["uncategorized_expenses"] * 1.5
    bank_penalty = raw_metrics["unlinked_bank_transactions"] * 2
    tax_fx_penalty = raw_metrics["tax_mismatches"] * 3

    breakdown = {
        "reconciliation": _score_from_penalty(100, reconciliation_penalty),
        "ledger_integrity": _score_from_penalty(100, ledger_penalty),
        "invoices": _score_from_penalty(100, invoices_penalty),
        "expenses": _score_from_penalty(100, expenses_penalty),
        "tax_fx": _score_from_penalty(100, tax_fx_penalty),
        "bank": _score_from_penalty(100, bank_penalty),
    }

    avg_score = sum(breakdown.values()) / max(len(breakdown), 1)
    score = _score_from_penalty(100, 100 - avg_score)

    # Penalize inactivity gently after 30 days.
    inactivity_days = raw_metrics.get("last_activity_days_ago", 0) or 0
    if inactivity_days > 30:
        score -= min(15, int((inactivity_days - 30) / 7) * 2)

    score = max(0, min(100, int(round(score))))
    return score, breakdown, raw_metrics


def create_health_snapshot(workspace) -> HealthIndexSnapshot:
    score, breakdown, raw = compute_health_index(workspace)
    return HealthIndexSnapshot.objects.create(
        workspace=workspace,
        score=score,
        breakdown=breakdown,
        raw_metrics=raw,
    )


def get_latest_health_snapshot(workspace, max_age_minutes: int | None = None) -> HealthIndexSnapshot | None:
    snapshot = (
        HealthIndexSnapshot.objects.filter(workspace=workspace).order_by("-created_at").first()
    )
    if snapshot and max_age_minutes:
        cutoff = timezone.now() - timedelta(minutes=max_age_minutes)
        if snapshot.created_at < cutoff:
            return None
    return snapshot


def get_or_refresh_health_snapshot_for_workspace(workspace, max_age_minutes: int = 60) -> HealthIndexSnapshot:
    """
    Get latest snapshot or create fresh one if stale/missing.
    Implements 1-hour freshness by default.
    """
    snapshot = get_latest_health_snapshot(workspace, max_age_minutes=max_age_minutes)
    if snapshot is None:
        snapshot = create_health_snapshot(workspace)
    return snapshot


def _should_seed_insight(existing: Iterable[CompanionInsight], domain: str, title: str) -> bool:
    for insight in existing:
        if insight.domain == domain and insight.title == title and not insight.is_dismissed:
            return False
    return True


def ensure_metric_insights(workspace, metrics: Dict[str, int]) -> list[CompanionInsight]:
    """
    Create a handful of deterministic insights derived from current metrics.
    Avoids duplicating already-present active insights.
    """
    created: list[CompanionInsight] = []
    current_insights = list(
        CompanionInsight.objects.filter(workspace=workspace, is_dismissed=False)
    )

    candidates: list[dict] = []
    if metrics.get("unreconciled_count", 0) > 0:
        candidates.append(
            {
                "domain": "reconciliation",
                "context": CompanionInsight.CONTEXT_RECONCILIATION,
                "title": "Unreconciled transactions to clear",
                "body": f"{metrics.get('unreconciled_count', 0)} bank items need reconciliation.",
                "severity": "warning" if metrics.get("old_unreconciled_60d", 0) else "info",
                "suggested_actions": [{"label": "Open reconciliation", "action": "/banking/"}],
            }
        )
    if metrics.get("overdue_invoices", 0) > 0:
        candidates.append(
            {
                "domain": "invoices",
                "context": CompanionInsight.CONTEXT_INVOICES,
                "title": "Customers have overdue invoices",
                "body": f"{metrics.get('overdue_invoices', 0)} invoices past due. Follow up to improve cash flow.",
                "severity": "warning" if metrics.get("overdue_invoices_60d", 0) else "info",
                "suggested_actions": [{"label": "Review invoices", "action": "/invoices/"}],
            }
        )
    if metrics.get("uncategorized_expenses", 0) > 0:
        candidates.append(
            {
                "domain": "expenses",
                "context": CompanionInsight.CONTEXT_EXPENSES,
                "title": "Expenses missing categories",
                "body": f"{metrics.get('uncategorized_expenses', 0)} expenses need a category for clean books.",
                "severity": "info",
                "suggested_actions": [{"label": "Categorize expenses", "action": "/expenses/"}],
            }
        )

    for candidate in candidates:
        if not _should_seed_insight(current_insights, candidate["domain"], candidate["title"]):
            continue
        insight = CompanionInsight.objects.create(workspace=workspace, **candidate)
        current_insights.append(insight)
        created.append(insight)

    return created


def remember_vendor_category(workspace, vendor_name: str, category_id: int, expense_id: int | None = None):
    """
    Persist a lightweight memory linking a vendor to a category.
    """
    if not workspace or not vendor_name or not category_id:
        return
    normalized = vendor_name.strip().lower()
    if not normalized:
        return

    WorkspaceMemory.objects.update_or_create(
        workspace=workspace,
        key=f"vendor:{normalized}",
        defaults={
            "value": {"category_id": category_id, "last_expense_id": expense_id},
        },
    )


def get_vendor_category_hint(workspace, vendor_name: str) -> dict | None:
    if not workspace or not vendor_name:
        return None
    normalized = vendor_name.strip().lower()
    if not normalized:
        return None
    memory = WorkspaceMemory.objects.filter(
        workspace=workspace,
        key=f"vendor:{normalized}",
    ).first()
    return memory.value if memory else None


# --- Suggested actions (bank match review) ---


def generate_bank_match_suggestions_for_workspace(workspace, snapshot: HealthIndexSnapshot | None = None, max_open: int = 50):
    """
    Deterministically propose bank-to-ledger matches for review.
    """
    if not workspace:
        return

    open_count = CompanionSuggestedAction.objects.filter(workspace=workspace, status=CompanionSuggestedAction.STATUS_OPEN).count()
    if open_count >= max_open:
        return

    cutoff = timezone.now().date() - timedelta(days=90)
    candidate_txs = BankTransaction.objects.filter(
        bank_account__business=workspace,
        reconciliation_status=BankTransaction.RECO_STATUS_UNRECONCILED,
        date__gte=cutoff,
    ).order_by("-date")[:200]

    for tx in candidate_txs:
        if open_count >= max_open:
            break
        matches = BankMatchingEngine.find_matches(tx, limit=1)
        if not matches:
            continue
        match = matches[0]
        confidence = match.get("confidence") or Decimal("0")
        if confidence < MatchingConfig.CONFIDENCE_TIER3_SINGLE:
            continue
        journal_entry = match.get("journal_entry")
        if not journal_entry:
            continue
        # Skip if already matched/reconciled
        if tx.reconciliation_status == BankTransaction.RECO_STATUS_RECONCILED:
            continue
        if CompanionSuggestedAction.objects.filter(
            workspace=workspace,
            status=CompanionSuggestedAction.STATUS_OPEN,
            payload__bank_transaction_id=tx.id,
            payload__journal_entry_id=journal_entry.id,
        ).exists():
            continue

        summary = (
            f"Likely match: bank txn {tx.date} {tx.amount} to journal entry {journal_entry.id}"
        )
        CompanionSuggestedAction.objects.create(
            workspace=workspace,
            context=CompanionSuggestedAction.CONTEXT_BANK,
            action_type=CompanionSuggestedAction.ACTION_BANK_MATCH_REVIEW,
            status=CompanionSuggestedAction.STATUS_OPEN,
            payload={
                "bank_transaction_id": tx.id,
                "journal_entry_id": journal_entry.id,
                "amount": str(tx.amount),
                "date": str(tx.date),
                "currency": getattr(tx.bank_account, "currency", None) or getattr(workspace, "currency", None),
            },
            confidence=confidence,
            summary=summary[:255],
            source_snapshot=snapshot,
        )
        open_count += 1


def generate_overdue_invoice_suggestions_for_workspace(
    workspace,
    snapshot: HealthIndexSnapshot | None = None,
    grace_days: int = 7,
    max_actions: int = 20,
):
    """
    Create reminder suggestions for overdue invoices without duplicating existing open actions.
    """
    if not workspace:
        return []

    today = timezone.now().date()
    cutoff = today - timedelta(days=grace_days)

    existing_invoice_ids: set[int] = set()
    for action in CompanionSuggestedAction.objects.filter(
        workspace=workspace,
        status=CompanionSuggestedAction.STATUS_OPEN,
        action_type=CompanionSuggestedAction.ACTION_INVOICE_REMINDER,
    ):
        payload = action.payload or {}
        inv_id = payload.get("invoice_id")
        if inv_id is not None:
            try:
                existing_invoice_ids.add(int(inv_id))
            except (TypeError, ValueError):
                continue

    candidates = Invoice.objects.filter(
        business=workspace,
        status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL],
        due_date__lt=cutoff,
    ).order_by("due_date")

    created: list[CompanionSuggestedAction] = []
    for invoice in candidates:
        if len(created) >= max_actions:
            break
        if invoice.id in existing_invoice_ids:
            continue
        days_overdue = (today - invoice.due_date).days if invoice.due_date else 0
        customer_name = getattr(invoice.customer, "name", None)
        payload = {
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "customer_name": customer_name,
            "amount": str(invoice.grand_total or invoice.total_amount),
            "days_overdue": days_overdue,
        }
        summary = f"Follow up on invoice {invoice.invoice_number or invoice.id} ({days_overdue} days overdue)"
        created.append(
            CompanionSuggestedAction.objects.create(
                workspace=workspace,
                context=CompanionSuggestedAction.CONTEXT_INVOICES,
                action_type=CompanionSuggestedAction.ACTION_INVOICE_REMINDER,
                status=CompanionSuggestedAction.STATUS_OPEN,
                payload=payload,
                confidence=Decimal("0.8"),
                summary=summary[:255],
                source_snapshot=snapshot,
            )
        )

    return created


def generate_uncategorized_expense_suggestions_for_workspace(
    workspace,
    max_actions: int = 5,
):
    """
    Suggest categorizing uncategorized expenses, leveraging vendor memory hints when available.
    """
    if not workspace:
        return []

    existing_expense_ids: set[int] = set()
    for action in CompanionSuggestedAction.objects.filter(
        workspace=workspace,
        status=CompanionSuggestedAction.STATUS_OPEN,
        action_type=CompanionSuggestedAction.ACTION_CATEGORIZE_EXPENSES_BATCH,
    ):
        for exp_id in action.payload.get("expense_ids", []):
            if exp_id is None:
                continue
            try:
                existing_expense_ids.add(int(exp_id))
            except (TypeError, ValueError):
                continue

    uncategorized = Expense.objects.filter(
        business=workspace,
    ).filter(
        Q(category__isnull=True)
        | Q(category__name__icontains="uncategorized")
        | Q(category__account__code="9999")
    ).order_by("-date")[: max_actions * 3]

    selected: list[Expense] = []
    for expense in uncategorized:
        if expense.id in existing_expense_ids:
            continue
        selected.append(expense)
        if len(selected) >= max_actions:
            break

    if not selected:
        return []

    expenses_payload = []
    for expense in selected:
        vendor_name = getattr(expense.supplier, "name", None)
        memory = get_vendor_category_hint(workspace, vendor_name) or {}
        expenses_payload.append(
            {
                "expense_id": expense.id,
                "vendor_name": vendor_name,
                "amount": str(expense.amount),
                "date": str(expense.date),
                "suggested_category_id": memory.get("category_id"),
            }
        )

    summary = f"Categorize {len(expenses_payload)} expenses"
    action = CompanionSuggestedAction.objects.create(
        workspace=workspace,
        context=CompanionSuggestedAction.CONTEXT_EXPENSES,
        action_type=CompanionSuggestedAction.ACTION_CATEGORIZE_EXPENSES_BATCH,
        status=CompanionSuggestedAction.STATUS_OPEN,
        payload={"expense_ids": [e["expense_id"] for e in expenses_payload], "expenses": expenses_payload},
        confidence=Decimal("0.6"),
        summary=summary[:255],
    )
    return [action]


def refresh_suggested_actions_for_workspace(workspace, snapshot: HealthIndexSnapshot | None = None):
    """
    Run all deterministic suggestion generators for a workspace.
    """
    generate_bank_match_suggestions_for_workspace(workspace, snapshot=snapshot)
    generate_overdue_invoice_suggestions_for_workspace(workspace, snapshot=snapshot)
    generate_uncategorized_expense_suggestions_for_workspace(workspace)


def apply_suggested_action(action: CompanionSuggestedAction, user=None):
    """
    Apply a bank match review suggestion using existing reconciliation service.
    """
    if action.status != CompanionSuggestedAction.STATUS_OPEN:
        raise ValueError("Action is not open.")
    payload = action.payload or {}
    if action.action_type == CompanionSuggestedAction.ACTION_BANK_MATCH_REVIEW:
        bank_tx_id = payload.get("bank_transaction_id")
        journal_entry_id = payload.get("journal_entry_id")
        if not bank_tx_id or not journal_entry_id:
            raise ValueError("Missing payload identifiers.")

        bank_tx = BankTransaction.objects.select_related("bank_account").get(
            id=bank_tx_id, bank_account__business=action.workspace
        )
        journal_entry = JournalEntry.objects.get(id=journal_entry_id, business=action.workspace)

        with transaction.atomic():
            BankReconciliationService.confirm_match(
                bank_transaction=bank_tx,
                journal_entry=journal_entry,
                match_confidence=Decimal(action.confidence or 0),
                user=user,
            )
            action.status = CompanionSuggestedAction.STATUS_APPLIED
            action.resolved_at = timezone.now()
            action.save(update_fields=["status", "resolved_at"])
    elif action.action_type in {
        CompanionSuggestedAction.ACTION_INVOICE_REMINDER,
        CompanionSuggestedAction.ACTION_CATEGORIZE_EXPENSES_BATCH,
    }:
        action.status = CompanionSuggestedAction.STATUS_APPLIED
        action.resolved_at = timezone.now()
        action.save(update_fields=["status", "resolved_at"])
    else:
        raise ValueError("Unsupported action type.")


def dismiss_suggested_action(action: CompanionSuggestedAction):
    if action.status != CompanionSuggestedAction.STATUS_OPEN:
        return
    action.status = CompanionSuggestedAction.STATUS_DISMISSED
    action.resolved_at = timezone.now()
    action.save(update_fields=["status", "resolved_at"])
