"""
Deterministic anomaly detection helpers for Companion v3.

Focus: reconciliation, P&L, AR, and tax surfaces for micro-SMBs.
LLM overlays are optional and token-light; deterministic anomalies remain the source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, List, Literal, Optional

from django.db.models import F, Q, Sum
from django.utils import timezone

from .models import Account, BankTransaction, Invoice, JournalEntry, JournalLine
from .llm_reasoning import LLMCallable, LLMProfile, _invoke_llm, _strip_markdown_json
import json


Severity = Literal["low", "medium", "high"]


@dataclass
class Anomaly:
    code: str
    surface: str
    impact_area: str
    severity: Severity
    explanation: str
    task_code: str
    explanation_source: Literal["auto", "ai"] = "auto"
    linked_issue_id: Optional[int] = None


def _balance_as_of(account: Account, as_of: date) -> Decimal:
    lines = JournalLine.objects.filter(account=account, journal_entry__date__lte=as_of)
    totals = lines.aggregate(total_debit=Sum("debit"), total_credit=Sum("credit"))
    debit = totals.get("total_debit") or Decimal("0.00")
    credit = totals.get("total_credit") or Decimal("0.00")
    return Decimal(debit) - Decimal(credit)


def generate_bank_anomalies(business, period_start: date, period_end: date) -> List[Anomaly]:
    anomalies: List[Anomaly] = []
    aging_threshold = period_end - timedelta(days=14)
    unreconciled_qs = BankTransaction.objects.filter(
        bank_account__business=business,
        status=BankTransaction.TransactionStatus.NEW,
        date__lte=aging_threshold,
        date__gte=period_start,
    )
    unreconciled_count = unreconciled_qs.count()
    if unreconciled_count > 0:
        severity: Severity = "high" if unreconciled_count >= 10 else "medium"
        anomalies.append(
            Anomaly(
                code="BANK_UNRECONCILED_AGING",
                surface="bank",
                impact_area="reconciliation",
                severity=severity,
                explanation=f"{unreconciled_count} unreconciled bank transactions older than 14 days; closing cash may be off.",
                task_code="B1",
            )
        )
    return anomalies


def generate_books_anomalies(business, period_start: date, period_end: date) -> List[Anomaly]:
    anomalies: List[Anomaly] = []

    # Suspense/clearing balances
    suspense_accounts = Account.objects.filter(business=business, is_suspense=True)
    if not suspense_accounts.exists():
        suspense_accounts = Account.objects.filter(business=business, code__in=["9999", "2999", "3999"])
    for acct in suspense_accounts:
        bal = _balance_as_of(acct, period_end)
        if abs(bal) > Decimal("1.00"):
            severity: Severity = "high" if abs(bal) >= Decimal("500") else "medium"
            anomalies.append(
                Anomaly(
                    code="GL_SUSPENSE_BALANCE",
                    surface="books",
                    impact_area="reconciliation",
                    severity=severity,
                    explanation=f"{acct.name} has a suspense balance of {bal:,.2f}.",
                    task_code="G1",
                )
            )

    # Unbalanced entries within period
    unbalanced_qs = (
        JournalEntry.objects.filter(business=business, date__gte=period_start, date__lte=period_end)
        .annotate(total_debit=Sum("lines__debit"), total_credit=Sum("lines__credit"))
        .filter(~Q(total_debit=F("total_credit")))
    )
    if unbalanced_qs.exists():
        count = unbalanced_qs.count()
        anomalies.append(
            Anomaly(
                code="GL_UNBALANCED",
                surface="books",
                impact_area="pnl",
                severity="high",
                explanation=f"{count} journal entries are unbalanced; fix debits/credits before close.",
                task_code="G2",
            )
        )

    # Retained earnings rollforward check (rough)
    retained = Account.objects.filter(
        Q(name__icontains="retained") | Q(code__in=["3000", "3200"]),
        business=business,
        type=Account.AccountType.EQUITY,
    ).first()
    if retained:
        start_bal = _balance_as_of(retained, period_start - timedelta(days=1))
        end_bal = _balance_as_of(retained, period_end)
        movement = end_bal - start_bal
        # Net income for the period = income - expense debits/credits
        income_ids = Account.objects.filter(business=business, type=Account.AccountType.INCOME).values_list("id", flat=True)
        expense_ids = Account.objects.filter(business=business, type=Account.AccountType.EXPENSE).values_list("id", flat=True)
        income_lines = JournalLine.objects.filter(
            journal_entry__business=business,
            journal_entry__date__gte=period_start,
            journal_entry__date__lte=period_end,
            account_id__in=income_ids,
        ).aggregate(total_debit=Sum("debit"), total_credit=Sum("credit"))
        expense_lines = JournalLine.objects.filter(
            journal_entry__business=business,
            journal_entry__date__gte=period_start,
            journal_entry__date__lte=period_end,
            account_id__in=expense_ids,
        ).aggregate(total_debit=Sum("debit"), total_credit=Sum("credit"))
        income = (income_lines.get("total_credit") or Decimal("0")) - (income_lines.get("total_debit") or Decimal("0"))
        expenses = (expense_lines.get("total_debit") or Decimal("0")) - (expense_lines.get("total_credit") or Decimal("0"))
        net_income = income - expenses
        delta = movement - net_income
        if abs(delta) > Decimal("1.00"):
            anomalies.append(
                Anomaly(
                    code="GL_RETAINED_EARNINGS_ROLLFORWARD",
                    surface="books",
                    impact_area="pnl",
                    severity="medium",
                    explanation=f"Retained earnings movement {movement:,.2f} does not match net income {net_income:,.2f} (diff {delta:,.2f}).",
                    task_code="G2B",
                )
            )

    return anomalies


def generate_ar_anomalies(business, as_of: date) -> List[Anomaly]:
    anomalies: List[Anomaly] = []
    overdue = Invoice.objects.filter(
        business=business,
        status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL],
        due_date__lt=as_of,
    )
    overdue_count = overdue.count()
    if overdue_count:
        over_90 = overdue.filter(due_date__lt=as_of - timedelta(days=90)).count()
        severity: Severity = "high" if over_90 >= 3 or overdue_count >= 10 else "medium"
        anomalies.append(
            Anomaly(
                code="AR_OVERDUE_AGING",
                surface="invoices",
                impact_area="ar",
                severity=severity,
                explanation=f"{overdue_count} overdue invoices; {over_90} are 90+ days past due.",
                task_code="I1B",
            )
        )
    return anomalies


def generate_tax_anomalies(business, period_start: date, period_end: date) -> List[Anomaly]:
    anomalies: List[Anomaly] = []
    # Negative tax payable / receivable
    tax_accounts = Account.objects.filter(
        Q(name__icontains="tax") | Q(code__icontains="tax"),
        business=business,
        type__in=[Account.AccountType.LIABILITY, Account.AccountType.ASSET],
    )
    for acct in tax_accounts:
        bal = _balance_as_of(acct, period_end)
        if acct.type == Account.AccountType.LIABILITY and bal < Decimal("0"):
            anomalies.append(
                Anomaly(
                    code="TAX_NEGATIVE_PAYABLE",
                    surface="tax",
                    impact_area="tax",
                    severity="medium",
                    explanation=f"{acct.name} liability is negative ({bal:,.2f}); confirm filings and postings.",
                    task_code="T2",
                )
            )
        if acct.type == Account.AccountType.ASSET and bal < Decimal("-100"):
            anomalies.append(
                Anomaly(
                    code="TAX_NEGATIVE_RECEIVABLE",
                    surface="tax",
                    impact_area="tax",
                    severity="medium",
                    explanation=f"{acct.name} receivable is negative ({bal:,.2f}); verify tax postings.",
                    task_code="T2",
                )
            )

    return anomalies


def apply_llm_explanations(
    anomalies: List[Anomaly],
    *,
    ai_enabled: bool,
    user_name: Optional[str],
    llm_client: LLMCallable | None = None,
    limit: int = 3,
    timeout_seconds: int | None = 20,
) -> List[Anomaly]:
    """
    Overlay short AI explanations on top anomalies (HEAVY_REASONING).
    """
    if not ai_enabled or not anomalies:
        return anomalies

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    top = sorted(anomalies, key=lambda a: severity_rank.get(a.severity, 3))[:limit]
    payload = [
        {
            "code": a.code,
            "surface": a.surface,
            "severity": a.severity,
            "impact_area": a.impact_area,
            "task_code": a.task_code,
            "explanation": a.explanation,
        }
        for a in top
    ]
    prompt = (
        "Provide concise, plain-language explanations for the following accounting anomalies. "
        "Return JSON array of objects {code, explanation, next_action}. "
        "Keep each explanation under 30 words. Map next_action to the provided task_code."
        f"\nUser: {user_name or 'there'}\n\nDATA:\n{json.dumps(payload)}"
    )
    raw = _invoke_llm(
        prompt,
        llm_client=llm_client,
        timeout_seconds=timeout_seconds,
        profile=LLMProfile.HEAVY_REASONING,
        context_tag="anomaly_explain",
    )
    if not raw:
        return anomalies
    try:
        parsed = json.loads(_strip_markdown_json(raw))
    except Exception:
        return anomalies

    explanations_by_code = {item.get("code"): item for item in parsed if isinstance(item, dict)}
    enriched: List[Anomaly] = []
    for a in anomalies:
        enriched_anomaly = a
        if a.code in explanations_by_code:
            detail = explanations_by_code[a.code]
            explanation = detail.get("explanation") or a.explanation
            task_code = detail.get("task_code") or a.task_code
            enriched_anomaly = Anomaly(
                code=a.code,
                surface=a.surface,
                impact_area=a.impact_area,
                severity=a.severity,
                explanation=explanation,
                task_code=task_code,
                explanation_source="ai",
                linked_issue_id=a.linked_issue_id,
            )
        enriched.append(enriched_anomaly)
    return enriched


def bundle_anomalies(
    business,
    *,
    period_start: date,
    period_end: date,
    as_of: date | None = None,
) -> List[Anomaly]:
    """
    Helper to generate all deterministic anomalies for a period.
    """
    as_of = as_of or period_end
    anomalies: List[Anomaly] = []
    anomalies.extend(generate_bank_anomalies(business, period_start, period_end))
    anomalies.extend(generate_books_anomalies(business, period_start, period_end))
    anomalies.extend(generate_ar_anomalies(business, as_of))
    anomalies.extend(generate_tax_anomalies(business, period_start, period_end))
    return anomalies
