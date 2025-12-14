from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, Iterable, Optional, Tuple

from django.db import transaction
from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.models import Account, BankTransaction, Expense, Invoice, JournalEntry, JournalLine, Customer, Category, ReconciliationSession
from core.services.bank_matching import BankMatchingEngine, MatchingConfig
from core.services.bank_reconciliation import BankReconciliationService
from .models import CompanionInsight, CompanionSuggestedAction, HealthIndexSnapshot, WorkspaceMemory

SEVERITY_INFO = CompanionSuggestedAction.SEVERITY_INFO
SEVERITY_LOW = CompanionSuggestedAction.SEVERITY_LOW
SEVERITY_MEDIUM = CompanionSuggestedAction.SEVERITY_MEDIUM
SEVERITY_HIGH = CompanionSuggestedAction.SEVERITY_HIGH
SEVERITY_CRITICAL = CompanionSuggestedAction.SEVERITY_CRITICAL


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


SEVERITY_ORDER = {
    SEVERITY_CRITICAL: 0,
    SEVERITY_HIGH: 1,
    SEVERITY_MEDIUM: 2,
    SEVERITY_LOW: 3,
    SEVERITY_INFO: 4,
}


def _severity_rank(value: str | None) -> int:
    return SEVERITY_ORDER.get(value or SEVERITY_INFO, len(SEVERITY_ORDER))


def _fmt_amount(amount: Decimal | float | int | None) -> str:
    try:
        return f"{Decimal(str(amount or 0)):.2f}"
    except Exception:
        return "0.00"


def _overdue_severity(total: Decimal, oldest_days: int) -> str:
    if total < Decimal("500") and oldest_days < 15:
        return SEVERITY_LOW if total > 0 else SEVERITY_INFO
    if total >= Decimal("5000") or oldest_days >= 30:
        return SEVERITY_HIGH
    return SEVERITY_MEDIUM


def _unreconciled_severity(count: int, oldest_days: int) -> str:
    if count == 0:
        return SEVERITY_INFO
    if count < 5 and oldest_days < 15:
        return SEVERITY_LOW
    if count >= 20 or oldest_days >= 45:
        return SEVERITY_HIGH
    return SEVERITY_MEDIUM


def _uncategorized_severity(total_amount: Decimal) -> str:
    if total_amount >= Decimal("2000"):
        return SEVERITY_HIGH
    if total_amount > 0:
        return SEVERITY_MEDIUM
    return SEVERITY_INFO


def _suspense_severity(balance: Decimal) -> str:
    abs_balance = abs(balance)
    if abs_balance >= Decimal("2000"):
        return SEVERITY_HIGH
    if abs_balance > 0:
        return SEVERITY_MEDIUM
    return SEVERITY_INFO


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
    unreconciled_oldest = unreconciled_qs.order_by("date").values_list("date", flat=True).first()
    unreconciled_oldest_age = max(0, (today - unreconciled_oldest).days) if unreconciled_oldest else 0
    unreconciled_abs_total = sum(abs(tx.amount or Decimal("0")) for tx in unreconciled_qs)
    recent_period_start = today - timedelta(days=60)
    recent_bank_total = BankTransaction.objects.filter(
        bank_account__business=workspace,
        date__gte=recent_period_start,
    ).count()
    unreconciled_ratio_pct = float((unreconciled_count / recent_bank_total * 100) if recent_bank_total else 0)

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
    open_invoice_qs = Invoice.objects.filter(
        business=workspace,
        status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL],
    ).exclude(due_date__isnull=True)
    oldest_unpaid_due = open_invoice_qs.order_by("due_date").values_list("due_date", flat=True).first()
    oldest_unpaid_invoice_days = max(0, (today - oldest_unpaid_due).days) if oldest_unpaid_due else 0
    open_invoices_total = open_invoice_qs.aggregate(total=Coalesce(Sum("grand_total"), Decimal("0.00")))["total"] or Decimal("0.00")
    overdue_amount_total = overdue_qs.aggregate(total=Coalesce(Sum("grand_total"), Decimal("0.00")))["total"] or Decimal("0.00")
    percent_overdue_by_amount = float((overdue_amount_total / open_invoices_total * 100) if open_invoices_total else 0)
    open_invoice_count = open_invoice_qs.count()
    percent_overdue_by_count = float((overdue_invoices / open_invoice_count * 100) if open_invoice_count else 0)
    top_late_customers = list(
        overdue_qs.values("customer__name")
        .annotate(total=Coalesce(Sum("grand_total"), Decimal("0.00")))
        .order_by("-total")[:3]
    )
    overdue_amount_total = overdue_qs.aggregate(total=Coalesce(Sum("grand_total"), Decimal("0.00")))["total"] or Decimal("0.00")

    # Revenue trend: compare this month vs last month
    first_of_month = today.replace(day=1)
    last_month_end = first_of_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    revenue_this_month = (
        Invoice.objects.filter(
            business=workspace,
            status=Invoice.Status.PAID,
            issue_date__gte=first_of_month,
            issue_date__lte=today,
        ).aggregate(total=Coalesce(Sum("grand_total"), Decimal("0.00")))["total"]
        or Decimal("0.00")
    )
    revenue_last_month = (
        Invoice.objects.filter(
            business=workspace,
            status=Invoice.Status.PAID,
            issue_date__gte=last_month_start,
            issue_date__lte=last_month_end,
        ).aggregate(total=Coalesce(Sum("grand_total"), Decimal("0.00")))["total"]
        or Decimal("0.00")
    )

    uncategorized_expenses = Expense.objects.filter(
        business=workspace,
        category__isnull=True,
    ).count()
    expenses_mtd_total = (
        Expense.objects.filter(business=workspace, date__gte=first_of_month, date__lte=today).aggregate(
            total=Coalesce(Sum("amount"), Decimal("0.00"))
        )["total"]
        or Decimal("0.00")
    )
    expenses_last_month_total = (
        Expense.objects.filter(business=workspace, date__gte=last_month_start, date__lte=last_month_end).aggregate(
            total=Coalesce(Sum("amount"), Decimal("0.00"))
        )["total"]
        or Decimal("0.00")
    )
    top_vendor_share_mtd = Decimal("0.00")
    if expenses_mtd_total:
        top_vendor = (
            Expense.objects.filter(business=workspace, date__gte=first_of_month, date__lte=today)
            .values("supplier__name")
            .annotate(total=Coalesce(Sum("amount"), Decimal("0.00")))
            .order_by("-total")
            .first()
        )
        if top_vendor and top_vendor.get("total"):
            top_vendor_share_mtd = (top_vendor["total"] or Decimal("0.00")) / expenses_mtd_total

    uncategorized_expense_amount = (
        Expense.objects.filter(business=workspace, category__isnull=True, date__gte=first_of_month, date__lte=today).aggregate(
            total=Coalesce(Sum("amount"), Decimal("0.00"))
        )["total"]
        or Decimal("0.00")
    )
    uncategorized_expense_share_pct = float((uncategorized_expense_amount / expenses_mtd_total * 100) if expenses_mtd_total else 0)

    top_vendors_by_spend = []
    vendor_rows = (
        Expense.objects.filter(business=workspace, date__gte=first_of_month, date__lte=today)
        .values("supplier__name")
        .annotate(total=Coalesce(Sum("amount"), Decimal("0.00")))
        .order_by("-total")[:3]
    )
    for row in vendor_rows:
        total = row.get("total") or Decimal("0.00")
        share = float((total / expenses_mtd_total * 100) if expenses_mtd_total else 0)
        top_vendors_by_spend.append({"vendor": row.get("supplier__name"), "total": float(total), "share_pct": share})

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

    # Activity tracking - include journal entries for accurate "last activity" metric
    from core.services import calculate_ledger_activity_date

    activity_dates = []
    latest_invoice = Invoice.objects.filter(business=workspace).order_by("-issue_date").values_list("issue_date", flat=True).first()
    latest_expense = Expense.objects.filter(business=workspace).order_by("-date").values_list("date", flat=True).first()
    latest_bank_tx = (
        BankTransaction.objects.filter(bank_account__business=workspace)
        .order_by("-date")
        .values_list("date", flat=True)
        .first()
    )
    latest_journal = calculate_ledger_activity_date(workspace)

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

    # Ledger suspense / uncategorized balance
    suspense_balance = Decimal("0.00")
    suspense_accounts = Account.objects.filter(
        business=workspace
    ).filter(Q(code="9999") | Q(name__icontains="uncategorized"))
    if suspense_accounts.exists():
        suspense_totals = JournalLine.objects.filter(
            journal_entry__business=workspace, account__in=suspense_accounts
        ).aggregate(
            debit=Coalesce(Sum("debit"), Decimal("0.00")),
            credit=Coalesce(Sum("credit"), Decimal("0.00")),
        )
        suspense_balance = (suspense_totals.get("debit") or Decimal("0.00")) - (suspense_totals.get("credit") or Decimal("0.00"))

    asset_totals = JournalLine.objects.filter(journal_entry__business=workspace, account__type=Account.AccountType.ASSET).aggregate(
        debit=Coalesce(Sum("debit"), Decimal("0.00")),
        credit=Coalesce(Sum("credit"), Decimal("0.00")),
    )
    asset_balance = (asset_totals.get("debit") or Decimal("0.00")) - (asset_totals.get("credit") or Decimal("0.00")) or Decimal("0.00")
    suspense_share_of_assets_pct = float((suspense_balance / asset_balance * 100) if asset_balance else 0)

    # Missing activity months (last 6) for income/expense
    months_with_missing_activity = 0
    start_month = first_of_month - timedelta(days=150)
    cursor = start_month.replace(day=1)
    for _ in range(6):
        month_end = (cursor + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        income_count = Invoice.objects.filter(business=workspace, issue_date__gte=cursor, issue_date__lte=month_end).count()
        expense_count = Expense.objects.filter(business=workspace, date__gte=cursor, date__lte=month_end).count()
        if income_count == 0 and expense_count == 0:
            months_with_missing_activity += 1
        cursor = (cursor + timedelta(days=32)).replace(day=1)

    # Trends 3m for revenue and expenses
    three_months_ago = first_of_month - timedelta(days=90)
    six_months_ago = three_months_ago - timedelta(days=90)
    revenue_last_3m = (
        Invoice.objects.filter(
            business=workspace,
            status=Invoice.Status.PAID,
            issue_date__gte=three_months_ago,
            issue_date__lt=first_of_month,
        ).aggregate(total=Coalesce(Sum("grand_total"), Decimal("0.00")))["total"]
        or Decimal("0.00")
    )
    revenue_prev_3m = (
        Invoice.objects.filter(
            business=workspace,
            status=Invoice.Status.PAID,
            issue_date__gte=six_months_ago,
            issue_date__lt=three_months_ago,
        ).aggregate(total=Coalesce(Sum("grand_total"), Decimal("0.00")))["total"]
        or Decimal("0.00")
    )
    expense_last_3m = (
        Expense.objects.filter(
            business=workspace,
            date__gte=three_months_ago,
            date__lt=first_of_month,
        ).aggregate(total=Coalesce(Sum("amount"), Decimal("0.00")))["total"]
        or Decimal("0.00")
    )
    expense_prev_3m = (
        Expense.objects.filter(
            business=workspace,
            date__gte=six_months_ago,
            date__lt=three_months_ago,
        ).aggregate(total=Coalesce(Sum("amount"), Decimal("0.00")))["total"]
        or Decimal("0.00")
    )

    return {
        "unreconciled_count": _safe_int(unreconciled_count),
        "old_unreconciled_60d": _safe_int(old_unreconciled_60d),
        "old_unreconciled_90d": _safe_int(old_unreconciled_90d),
        "unbalanced_journal_entries": _safe_int(unbalanced_journal_entries),
        "future_dated_entries": _safe_int(future_dated_entries),
        "overdue_invoices": _safe_int(overdue_invoices),
        "overdue_invoices_60d": _safe_int(overdue_invoices_60d),
        "oldest_unpaid_invoice_days": _safe_int(oldest_unpaid_invoice_days),
        "avg_days_to_get_paid": 0,
        "percent_overdue_by_amount": percent_overdue_by_amount,
        "percent_overdue_by_count": percent_overdue_by_count,
        "top_late_customers": [{"customer": row.get("customer__name"), "total": float(row.get("total") or 0)} for row in top_late_customers],
        "uncategorized_expenses": _safe_int(uncategorized_expenses),
        "unlinked_bank_transactions": _safe_int(unlinked_bank_transactions),
        "tax_mismatches": _safe_int(tax_mismatches),
        "last_activity_days_ago": _safe_int(last_activity_days_ago),
        "revenue_this_month": float(revenue_this_month),
        "revenue_last_month": float(revenue_last_month),
        "expenses_mtd_total": float(expenses_mtd_total),
        "expenses_last_month_total": float(expenses_last_month_total),
        "top_vendor_share_mtd": float(top_vendor_share_mtd),
        "has_unfinished_reconciliation_period": bool(_safe_int(unreconciled_count) > 0),
        "unreconciled_ratio_pct": unreconciled_ratio_pct,
        "suspense_balance": float(suspense_balance),
        "suspense_share_of_assets_pct": suspense_share_of_assets_pct,
        "uncategorized_expense_share_pct": float(uncategorized_expense_share_pct),
        "top_vendors_by_spend": top_vendors_by_spend,
        "months_with_missing_activity": months_with_missing_activity,
        "revenue_last_3m": float(revenue_last_3m),
        "revenue_prev_3m": float(revenue_prev_3m),
        "expense_last_3m": float(expense_last_3m),
        "expense_prev_3m": float(expense_prev_3m),
        "overdue_amount_total": float(overdue_amount_total),
        "unreconciled_abs_total": float(unreconciled_abs_total),
        "unreconciled_oldest_age": unreconciled_oldest_age,
        "uncategorized_expense_amount": float(uncategorized_expense_amount),
    }


# --- Context evaluators ---


def evaluate_invoices_context(_business, metrics: dict) -> dict:
    reasons: list[str] = []
    overdue_count = _safe_int(metrics.get("overdue_invoices", 0))
    oldest_unpaid_days = _safe_int(metrics.get("oldest_unpaid_invoice_days", 0))
    overdue_total = Decimal(str(metrics.get("overdue_amount_total", 0) or 0))

    severity = SEVERITY_INFO
    if overdue_count == 0 and overdue_total == 0:
        severity = SEVERITY_INFO
    else:
        severity = SEVERITY_LOW
        if overdue_total >= Decimal("500") or oldest_unpaid_days >= 15:
            severity = SEVERITY_MEDIUM
        if overdue_total >= Decimal("5000") or oldest_unpaid_days >= 30:
            severity = SEVERITY_HIGH

    if overdue_count > 0:
        reasons.append(
            f"{overdue_count} overdue invoices (oldest {oldest_unpaid_days} days, total {_fmt_amount(overdue_total)})"
        )
    if overdue_count == 0 and overdue_total == 0:
        reasons.append("No overdue invoices")

    return {"all_clear": overdue_count == 0 and overdue_total == 0, "severity": severity, "reasons": reasons}


def evaluate_expenses_context(_business, metrics: dict) -> dict:
    reasons: list[str] = []
    uncategorized = _safe_int(metrics.get("uncategorized_expenses", 0))
    uncategorized_amount = Decimal(str(metrics.get("uncategorized_expense_amount", 0) or 0))
    severity = SEVERITY_INFO
    if uncategorized > 0:
        severity = SEVERITY_MEDIUM if uncategorized_amount < Decimal("2000") else SEVERITY_HIGH
        reasons.append(
            f"{uncategorized} uncategorized expenses this month totaling {_fmt_amount(uncategorized_amount)}"
        )
    else:
        reasons.append("No uncategorized expenses in the last 30 days")

    return {"all_clear": uncategorized == 0, "severity": severity, "reasons": reasons}


def evaluate_bank_context(_business, metrics: dict) -> dict:
    reasons: list[str] = []
    unreconciled_count = _safe_int(metrics.get("unreconciled_count", 0))
    unreconciled_total = Decimal(str(metrics.get("unreconciled_abs_total", 0) or 0))
    oldest_age = _safe_int(metrics.get("unreconciled_oldest_age", 0))

    severity = SEVERITY_INFO
    if unreconciled_count > 0:
        severity = SEVERITY_LOW
        if unreconciled_count >= 5 or oldest_age >= 15:
            severity = SEVERITY_MEDIUM
        if unreconciled_count >= 20 or oldest_age >= 45:
            severity = SEVERITY_HIGH
        reasons.append(
            f"{unreconciled_count} unreconciled transactions (oldest {oldest_age} days, total {_fmt_amount(unreconciled_total)})"
        )
    else:
        reasons.append("No unreconciled transactions in this period")

    return {"all_clear": unreconciled_count == 0, "severity": severity, "reasons": reasons}


def evaluate_reconciliation_context(_business, metrics: dict) -> dict:
    reasons: list[str] = []
    unreconciled_count = _safe_int(metrics.get("unreconciled_count", 0))
    oldest_age = _safe_int(metrics.get("unreconciled_oldest_age", 0))

    severity = SEVERITY_INFO
    if unreconciled_count > 0:
        severity = SEVERITY_LOW
        if unreconciled_count >= 5 or oldest_age >= 15:
            severity = SEVERITY_MEDIUM
        if unreconciled_count >= 20 or oldest_age >= 45:
            severity = SEVERITY_HIGH
        reasons.append(
            f"{unreconciled_count} transactions pending reconciliation (oldest {oldest_age} days)"
        )
    else:
        reasons.append("Reconciliation is up to date")

    return {"all_clear": unreconciled_count == 0, "severity": severity, "reasons": reasons}


def evaluate_ledger_context(_business, metrics: dict) -> dict:
    reasons: list[str] = []
    unbalanced = _safe_int(metrics.get("unbalanced_journal_entries", 0))
    suspense_balance = Decimal(str(metrics.get("suspense_balance", 0) or 0))
    missing_months = _safe_int(metrics.get("months_with_missing_activity", 0))

    severity = SEVERITY_INFO
    if unbalanced > 0 or suspense_balance != 0:
        severity = SEVERITY_MEDIUM
        if abs(suspense_balance) >= Decimal("2000") or unbalanced > 3:
            severity = SEVERITY_HIGH
    if unbalanced > 0:
        reasons.append(f"{unbalanced} unbalanced journal entries detected")
    if suspense_balance != 0:
        reasons.append(f"Suspense account balance {_fmt_amount(suspense_balance)}")
    if missing_months > 0:
        reasons.append(f"{missing_months} months missing income/expense activity")

    if unbalanced == 0 and suspense_balance == 0 and missing_months == 0:
        reasons.append("Ledger balances and suspense account are clean")

    return {
        "all_clear": unbalanced == 0 and suspense_balance == 0 and missing_months == 0,
        "severity": severity,
        "reasons": reasons,
    }


def _score_from_penalty(base: int, penalty: float) -> int:
    return max(0, min(100, int(round(base - penalty))))


def get_last_seen_field_name(context: str) -> str | None:
    mapping = {
        CompanionSuggestedAction.CONTEXT_BANK: "last_seen_bank_at",
        CompanionSuggestedAction.CONTEXT_RECONCILIATION: "last_seen_reconciliation_at",
        CompanionSuggestedAction.CONTEXT_INVOICES: "last_seen_invoices_at",
        CompanionSuggestedAction.CONTEXT_EXPENSES: "last_seen_expenses_at",
        CompanionSuggestedAction.CONTEXT_REPORTS: "last_seen_reports_at",
        CompanionSuggestedAction.CONTEXT_TAX_FX: "last_seen_tax_fx_at",
        CompanionSuggestedAction.CONTEXT_DASHBOARD: "last_seen_dashboard_at",
    }
    return mapping.get(context)


def get_last_seen_value(profile, context: str):
    field = get_last_seen_field_name(context)
    if not field or not profile:
        return None
    return getattr(profile, field, None)


def get_new_actions_count(workspace, context: str, last_seen_at: Optional[datetime]) -> int:
    qs = CompanionSuggestedAction.objects.filter(
        workspace=workspace,
        context=context,
        status=CompanionSuggestedAction.STATUS_OPEN,
    )
    if last_seen_at is not None:
        qs = qs.filter(created_at__gt=last_seen_at)
    return qs.count()


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

    today = timezone.now().date()

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
                "severity": CompanionSuggestedAction.SEVERITY_MEDIUM,
            },
            confidence=confidence,
            summary=summary[:255],
            source_snapshot=snapshot,
            severity=_unreconciled_severity(1, (today - tx.date).days if tx.date else 0),
            short_title="Bank match review",
        )
        open_count += 1


def generate_overdue_invoice_suggestions_for_workspace(
    workspace,
    snapshot: HealthIndexSnapshot | None = None,
    grace_days: int = 7,
    max_actions: int = 20,
    metrics: dict | None = None,
):
    """
    Create reminder suggestions for overdue invoices without duplicating existing open actions.
    Aggregates overdue invoices into a single action for efficient follow-up.
    """
    if not workspace:
        return []

    today = timezone.now().date()
    cutoff = today - timedelta(days=grace_days)

    if CompanionSuggestedAction.objects.filter(
        workspace=workspace,
        status=CompanionSuggestedAction.STATUS_OPEN,
        action_type=CompanionSuggestedAction.ACTION_OVERDUE_INVOICE_REMINDERS,
    ).exists():
        return []

    candidates = (
        Invoice.objects.filter(
            business=workspace,
            status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL],
            due_date__lt=cutoff,
        )
        .select_related("customer")
        .order_by("due_date")[:max_actions]
    )

    if not candidates:
        return []

    invoices_payload = []
    total_amount = Decimal("0.00")
    oldest_due_date = None
    for invoice in candidates:
        days_overdue = (today - invoice.due_date).days if invoice.due_date else 0
        amount = invoice.grand_total or invoice.total_amount or Decimal("0.00")
        total_amount += amount
        if oldest_due_date is None or (invoice.due_date and invoice.due_date < oldest_due_date):
            oldest_due_date = invoice.due_date
        invoices_payload.append(
            {
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "customer_name": getattr(invoice.customer, "name", None),
                "amount": str(amount),
                "days_overdue": days_overdue,
                "due_date": str(invoice.due_date) if invoice.due_date else None,
            }
        )

    pct_overdue_amount = float((metrics or {}).get("percent_overdue_by_amount", 0) or 0)
    severity = _overdue_severity(total_amount, (today - oldest_due_date).days if oldest_due_date else 0)
    impact = "cashflow"
    summary = f"Send reminders for {len(invoices_payload)} overdue invoices"
    action = CompanionSuggestedAction.objects.create(
        workspace=workspace,
        context=CompanionSuggestedAction.CONTEXT_INVOICES,
        action_type=CompanionSuggestedAction.ACTION_OVERDUE_INVOICE_REMINDERS,
        status=CompanionSuggestedAction.STATUS_OPEN,
        payload={
            "invoice_ids": [item["invoice_id"] for item in invoices_payload],
            "invoices": invoices_payload,
            "oldest_due_date": str(oldest_due_date) if oldest_due_date else None,
            "total_amount": str(total_amount),
            "severity": severity,
            "impact": impact,
            "metadata": {
                "target_url": "/invoices/?view=overdue",
                "target_context": "invoices",
            },
        },
        confidence=Decimal("0.8"),
        summary=summary[:255],
        source_snapshot=snapshot,
        severity=severity,
        short_title="Overdue invoices",
    )
    return [action]


def generate_uncategorized_expense_suggestions_for_workspace(
    workspace,
    max_actions: int = 5,
    metrics: dict | None = None,
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
        action_type__in=[
            CompanionSuggestedAction.ACTION_CATEGORIZE_EXPENSES_BATCH,
            CompanionSuggestedAction.ACTION_UNCATEGORIZED_EXPENSE_REVIEW,
        ],
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

    uncategorized_amount = Decimal(
        str((metrics or {}).get("uncategorized_expense_amount", 0) or sum(Decimal(str(e.amount or 0)) for e in selected))
    )
    severity = _uncategorized_severity(uncategorized_amount)
    impact = "accuracy"
    summary = f"Review {len(expenses_payload)} uncategorized expenses"
    action = CompanionSuggestedAction.objects.create(
        workspace=workspace,
        context=CompanionSuggestedAction.CONTEXT_EXPENSES,
        action_type=CompanionSuggestedAction.ACTION_UNCATEGORIZED_EXPENSE_REVIEW,
        status=CompanionSuggestedAction.STATUS_OPEN,
        payload={
            "expense_ids": [e["expense_id"] for e in expenses_payload],
            "expenses": expenses_payload,
            "severity": severity,
            "impact": impact,
            "metadata": {
                "target_url": "/expenses/?view=uncategorized",
                "target_context": "expenses",
            },
        },
        confidence=Decimal("0.6"),
        summary=summary[:255],
        severity=severity,
        short_title="Uncategorized expenses",
    )
    return [action]


def generate_uncategorized_transactions_cleanup_actions(workspace, metrics: dict | None = None):
    """
    Suggest cleaning up uncategorized/suspense account balances.
    """
    if not workspace:
        return []
    metrics = metrics or gather_workspace_metrics(workspace)
    suspense_balance = Decimal(str(metrics.get("suspense_balance", 0) or 0))
    if suspense_balance == 0:
        return []

    if CompanionSuggestedAction.objects.filter(
        workspace=workspace,
        status=CompanionSuggestedAction.STATUS_OPEN,
        action_type=CompanionSuggestedAction.ACTION_UNCATEGORIZED_TRANSACTIONS_CLEANUP,
    ).exists():
        return []

    summary = "Clear Uncategorized Transactions balance"
    severity = _suspense_severity(suspense_balance)
    impact = "accuracy"
    action = CompanionSuggestedAction.objects.create(
        workspace=workspace,
        context=CompanionSuggestedAction.CONTEXT_REPORTS,
        action_type=CompanionSuggestedAction.ACTION_UNCATEGORIZED_TRANSACTIONS_CLEANUP,
        status=CompanionSuggestedAction.STATUS_OPEN,
        payload={"balance": str(suspense_balance), "account_code": "9999", "severity": severity, "impact": impact},
        confidence=Decimal("0.5"),
        summary=summary,
        severity=severity,
        short_title="Suspense balance",
    )
    return [action]


def generate_reconciliation_period_close_actions(workspace, metrics: dict | None = None):
    """
    Suggest closing reconciliation periods that are mostly reconciled.
    """
    if not workspace:
        return []
    metrics = metrics or gather_workspace_metrics(workspace)
    unreconciled = _safe_int(metrics.get("unreconciled_count", 0))
    has_unfinished = bool(metrics.get("has_unfinished_reconciliation_period"))
    if not has_unfinished:
        return []
    if CompanionSuggestedAction.objects.filter(
        workspace=workspace,
        status=CompanionSuggestedAction.STATUS_OPEN,
        action_type=CompanionSuggestedAction.ACTION_RECONCILIATION_PERIOD_TO_CLOSE,
    ).exists():
        return []

    summary = "Close the current reconciliation period"
    severity = SEVERITY_MEDIUM
    impact = "accuracy"
    action = CompanionSuggestedAction.objects.create(
        workspace=workspace,
        context=CompanionSuggestedAction.CONTEXT_RECONCILIATION,
        action_type=CompanionSuggestedAction.ACTION_RECONCILIATION_PERIOD_TO_CLOSE,
        status=CompanionSuggestedAction.STATUS_OPEN,
        payload={"unreconciled_remaining": unreconciled, "severity": severity, "impact": impact},
        confidence=Decimal("0.6"),
        summary=summary,
        severity=severity,
        short_title="Close reconciliation period",
    )
    return [action]


def generate_inactive_customers_followup(workspace, cutoff_days: int = 90, max_customers: int = 5):
    if not workspace:
        return []
    if CompanionSuggestedAction.objects.filter(
        workspace=workspace,
        status=CompanionSuggestedAction.STATUS_OPEN,
        action_type=CompanionSuggestedAction.ACTION_INACTIVE_CUSTOMERS_FOLLOWUP,
    ).exists():
        return []
    cutoff = timezone.now().date() - timedelta(days=cutoff_days)
    stale_customers = Customer.objects.filter(business=workspace, invoices__isnull=False).distinct()
    inactive = []
    for customer in stale_customers:
        last_invoice = (
            Invoice.objects.filter(business=workspace, customer=customer).order_by("-issue_date").values_list("issue_date", flat=True).first()
        )
        if last_invoice and last_invoice < cutoff:
            inactive.append({"customer_id": customer.id, "customer_name": customer.name, "last_invoice_date": str(last_invoice)})
    inactive = inactive[:max_customers]
    if not inactive:
        return []
    action = CompanionSuggestedAction.objects.create(
        workspace=workspace,
        context=CompanionSuggestedAction.CONTEXT_INVOICES,
        action_type=CompanionSuggestedAction.ACTION_INACTIVE_CUSTOMERS_FOLLOWUP,
        status=CompanionSuggestedAction.STATUS_OPEN,
        payload={
            "customers": inactive,
            "severity": SEVERITY_MEDIUM,
            "impact": "cashflow",
            "metadata": {
                "target_url": "/invoices/",
                "target_context": "invoices",
            },
        },
        confidence=Decimal("0.4"),
        summary=f"Reconnect with {len(inactive)} inactive customer(s)",
        severity=SEVERITY_MEDIUM,
        short_title="Inactive customers",
    )
    return [action]


def generate_expense_spike_category_review(workspace, threshold_pct: float = 50.0):
    if not workspace:
        return []
    if CompanionSuggestedAction.objects.filter(
        workspace=workspace,
        status=CompanionSuggestedAction.STATUS_OPEN,
        action_type=CompanionSuggestedAction.ACTION_SPIKE_EXPENSE_CATEGORY_REVIEW,
    ).exists():
        return []
    today = timezone.now().date()
    first_of_month = today.replace(day=1)
    last_month_end = first_of_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    prev_month_end = last_month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)

    spikes = []
    categories = Category.objects.filter(business=workspace, type=Category.CategoryType.EXPENSE)
    for cat in categories:
        current = (
            Expense.objects.filter(business=workspace, category=cat, date__gte=last_month_start, date__lte=last_month_end).aggregate(
                total=Coalesce(Sum("amount"), Decimal("0.00"))
            )["total"]
            or Decimal("0.00")
        )
        previous = (
            Expense.objects.filter(business=workspace, category=cat, date__gte=prev_month_start, date__lte=prev_month_end).aggregate(
                total=Coalesce(Sum("amount"), Decimal("0.00"))
            )["total"]
            or Decimal("0.00")
        )
        if previous > 0 and current > previous:
            change = ((current - previous) / previous) * 100
            if change >= threshold_pct:
                spikes.append({"category": cat.name, "change_pct": float(change), "current": float(current)})
    if not spikes:
        return []
    action = CompanionSuggestedAction.objects.create(
        workspace=workspace,
        context=CompanionSuggestedAction.CONTEXT_EXPENSES,
        action_type=CompanionSuggestedAction.ACTION_SPIKE_EXPENSE_CATEGORY_REVIEW,
        status=CompanionSuggestedAction.STATUS_OPEN,
        payload={
            "spikes": spikes[:3],
            "severity": SEVERITY_MEDIUM,
            "impact": "accuracy",
            "metadata": {
                "target_url": "/expenses",
                "target_context": "expenses",
            },
        },
        confidence=Decimal("0.5"),
        summary=f"Review {len(spikes[:3])} expense categories with spikes",
        severity=SEVERITY_MEDIUM,
        short_title="Expense spike review",
    )
    return [action]


def generate_old_unreconciled_investigate(workspace, metrics: dict | None = None):
    if not workspace:
        return []
    metrics = metrics or gather_workspace_metrics(workspace)
    old_90 = _safe_int(metrics.get("old_unreconciled_90d", 0))
    if old_90 <= 0:
        return []
    if CompanionSuggestedAction.objects.filter(
        workspace=workspace,
        status=CompanionSuggestedAction.STATUS_OPEN,
        action_type=CompanionSuggestedAction.ACTION_OLD_UNRECONCILED_INVESTIGATE,
    ).exists():
        return []
    severity = _unreconciled_severity(old_90, 90)
    action = CompanionSuggestedAction.objects.create(
        workspace=workspace,
        context=CompanionSuggestedAction.CONTEXT_BANK,
        action_type=CompanionSuggestedAction.ACTION_OLD_UNRECONCILED_INVESTIGATE,
        status=CompanionSuggestedAction.STATUS_OPEN,
        payload={
            "old_unreconciled": old_90,
            "severity": severity,
            "impact": "accuracy",
            "metadata": {
                "target_url": "/banking/?view=unreconciled",
                "target_context": "bank",
            },
        },
        confidence=Decimal("0.7"),
        summary=f"Investigate {old_90} old unreconciled items",
        severity=severity,
        short_title="Old unreconciled transactions",
    )
    return [action]


def generate_suspense_balance_review(workspace, metrics: dict | None = None, threshold_pct: float = 2.0):
    if not workspace:
        return []
    metrics = metrics or gather_workspace_metrics(workspace)
    share = float(metrics.get("suspense_share_of_assets_pct", 0) or 0)
    if share <= threshold_pct:
        return []
    if CompanionSuggestedAction.objects.filter(
        workspace=workspace,
        status=CompanionSuggestedAction.STATUS_OPEN,
        action_type=CompanionSuggestedAction.ACTION_SUSPENSE_BALANCE_REVIEW,
    ).exists():
        return []
    balance = Decimal(str(metrics.get("suspense_balance", 0) or 0))
    severity = _suspense_severity(balance)
    action = CompanionSuggestedAction.objects.create(
        workspace=workspace,
        context=CompanionSuggestedAction.CONTEXT_REPORTS,
        action_type=CompanionSuggestedAction.ACTION_SUSPENSE_BALANCE_REVIEW,
        status=CompanionSuggestedAction.STATUS_OPEN,
        payload={"balance": str(balance), "share_pct": share, "severity": severity, "impact": "accuracy"},
        confidence=Decimal("0.5"),
        summary="Review large suspense/uncategorized balance",
        severity=severity,
        short_title="Suspense balance",
    )
    return [action]


def refresh_suggested_actions_for_workspace(workspace, snapshot: HealthIndexSnapshot | None = None, metrics: dict | None = None):
    """
    Run all deterministic suggestion generators for a workspace.
    """
    metrics = metrics or (snapshot.raw_metrics if snapshot else gather_workspace_metrics(workspace))
    generate_bank_match_suggestions_for_workspace(workspace, snapshot=snapshot)
    generate_overdue_invoice_suggestions_for_workspace(workspace, snapshot=snapshot, metrics=metrics)
    generate_uncategorized_expense_suggestions_for_workspace(workspace, metrics=metrics)
    generate_uncategorized_transactions_cleanup_actions(workspace, metrics=metrics)
    generate_reconciliation_period_close_actions(workspace, metrics=metrics)
    generate_inactive_customers_followup(workspace)
    generate_expense_spike_category_review(workspace)
    generate_old_unreconciled_investigate(workspace, metrics=metrics)
    generate_suspense_balance_review(workspace, metrics=metrics)


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
        tx_date = bank_tx.date or timezone.localdate()
        _, last_day = calendar.monthrange(tx_date.year, tx_date.month)
        session, _ = ReconciliationSession.objects.get_or_create(
            business=bank_tx.bank_account.business,
            bank_account=bank_tx.bank_account,
            statement_start_date=tx_date.replace(day=1),
            statement_end_date=date(tx_date.year, tx_date.month, last_day),
            defaults={"opening_balance": Decimal("0.00"), "closing_balance": Decimal("0.00")},
        )

        with transaction.atomic():
            BankReconciliationService.confirm_match(
                bank_transaction=bank_tx,
                journal_entry=journal_entry,
                match_confidence=Decimal(action.confidence or 0),
                user=user,
                session=session,
            )
            action.status = CompanionSuggestedAction.STATUS_APPLIED
            action.resolved_at = timezone.now()
            action.save(update_fields=["status", "resolved_at"])
    elif action.action_type in {
        CompanionSuggestedAction.ACTION_INVOICE_REMINDER,
        CompanionSuggestedAction.ACTION_CATEGORIZE_EXPENSES_BATCH,
        CompanionSuggestedAction.ACTION_OVERDUE_INVOICE_REMINDERS,
        CompanionSuggestedAction.ACTION_UNCATEGORIZED_EXPENSE_REVIEW,
        CompanionSuggestedAction.ACTION_UNCATEGORIZED_TRANSACTIONS_CLEANUP,
        CompanionSuggestedAction.ACTION_RECONCILIATION_PERIOD_TO_CLOSE,
        CompanionSuggestedAction.ACTION_INACTIVE_CUSTOMERS_FOLLOWUP,
        CompanionSuggestedAction.ACTION_SPIKE_EXPENSE_CATEGORY_REVIEW,
        CompanionSuggestedAction.ACTION_OLD_UNRECONCILED_INVESTIGATE,
        CompanionSuggestedAction.ACTION_SUSPENSE_BALANCE_REVIEW,
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
