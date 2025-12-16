"""
Deterministic finance companion snapshot for micro-SMBs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db.models import F, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import Account, BankAccount, BankTransaction, Invoice, JournalLine
from .llm_reasoning import _invoke_llm, LLMProfile


def _sum_bank_balances(business) -> Decimal:
    total = Decimal("0.00")
    for acct in BankAccount.objects.filter(business=business):
        try:
            total += acct.current_balance
        except Exception:
            continue
    return total


def _monthly_series(queryset, value_expr, months: int):
    series: Dict[str, Decimal] = {}
    for row in queryset.annotate(month=TruncMonth("journal_entry__date")).values("month").annotate(
        total=Sum(value_expr)
    ):
        month = row.get("month")
        if not month:
            continue
        series[month.strftime("%Y-%m")] = row.get("total") or Decimal("0.00")
    # normalize order
    today = timezone.localdate().replace(day=1)
    ordered: List[str] = []
    for i in range(months):
        m = (today - timedelta(days=30 * (months - 1 - i))).strftime("%Y-%m")
        ordered.append(m)
    values = [float(series.get(m, 0)) for m in ordered]
    return ordered, values


def compute_finance_snapshot(business, *, include_narrative: bool = False, user_name: Optional[str] = None) -> Dict[str, Any]:
    today = timezone.localdate()
    start_90 = today - timedelta(days=90)

    # Cash balances and burn (approximate via bank transactions)
    cash_balance = _sum_bank_balances(business)
    txs = BankTransaction.objects.filter(
        bank_account__business=business,
        date__gte=start_90,
    )
    burn_total = Decimal("0.00")
    for tx in txs:
        burn_total += tx.amount or Decimal("0.00")
    monthly_burn = Decimal("0.00")
    if burn_total < 0:
        monthly_burn = (-burn_total) / Decimal("3")
    runway_months = float(cash_balance / monthly_burn) if monthly_burn > 0 else None

    # Revenue & expense trends (last 6 months)
    months_back = 6
    income_lines = JournalLine.objects.filter(
        journal_entry__business=business,
        account__type=Account.AccountType.INCOME,
        journal_entry__date__gte=today - timedelta(days=30 * months_back),
    )
    expense_lines = JournalLine.objects.filter(
        journal_entry__business=business,
        account__type=Account.AccountType.EXPENSE,
        journal_entry__date__gte=today - timedelta(days=30 * months_back),
    )
    months_labels, revenue_values = _monthly_series(income_lines, F("credit") - F("debit"), months_back)
    _, expense_values = _monthly_series(expense_lines, F("debit") - F("credit"), months_back)

    # AR health
    overdue = Invoice.objects.filter(
        business=business,
        status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL],
        due_date__lt=today,
    )
    buckets = {
        "current": float(
            Invoice.objects.filter(business=business, status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL], due_date__gte=today).aggregate(
                total=Sum("balance")
            ).get("total")
            or 0
        ),
        "30": float(overdue.filter(due_date__gte=today - timedelta(days=30)).aggregate(total=Sum("balance")).get("total") or 0),
        "60": float(overdue.filter(due_date__lt=today - timedelta(days=30), due_date__gte=today - timedelta(days=60)).aggregate(total=Sum("balance")).get("total") or 0),
        "90": float(overdue.filter(due_date__lt=today - timedelta(days=60), due_date__gte=today - timedelta(days=90)).aggregate(total=Sum("balance")).get("total") or 0),
        "120": float(overdue.filter(due_date__lt=today - timedelta(days=90)).aggregate(total=Sum("balance")).get("total") or 0),
    }
    total_overdue = float(sum(v for k, v in buckets.items() if k != "current"))

    snapshot: Dict[str, Any] = {
        "cash_health": {
            "ending_cash": float(cash_balance),
            "monthly_burn": float(monthly_burn),
            "runway_months": float(runway_months) if runway_months is not None else None,
        },
        "revenue_expense": {
            "months": months_labels,
            "revenue": revenue_values,
            "expense": expense_values,
        },
        "ar_health": {
            "buckets": buckets,
            "total_overdue": total_overdue,
        },
    }

    if include_narrative:
        prompt = (
            "Provide one sentence finance summary for a small business. "
            "Use revenue trend, expense trend, and cash runway. "
            "Keep it under 35 words."
            f"\nDATA: {snapshot}"
        )
        raw = _invoke_llm(
            prompt,
            llm_client=None,
            timeout_seconds=15,
            profile=LLMProfile.LIGHT_CHAT,
            context_tag="finance_companion",
        )
        if raw:
            snapshot["narrative"] = raw.strip()
            snapshot["narrative_source"] = "ai"

    return snapshot
