from __future__ import annotations

from datetime import timedelta
from typing import Iterable, List, Literal, TypedDict

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .llm_reasoning import refine_companion_issues
from .companion_tasks import CompanionTask, first_task_for_surface, get_task, valid_task_code
from .models import (
    CompanionIssue,
    ReceiptDocument,
    Invoice,
    BankTransaction,
    BankAccount,
    Account,
)
from taxes.models import TaxAnomaly


def _current_period_key() -> str:
    today = timezone.localdate()
    return f"{today.year}-{today.month:02d}"


def _base_issue(surface: str, run_type: str, run_id: int | None, trace_id: str | None, title: str, description: str):
    """
    Base issue payload. Severity and impact will be refined below using materiality/compliance/recurrence heuristics.
    """
    return {
        "surface": surface,
        "run_type": run_type,
        "run_id": run_id,
        "trace_id": trace_id or "",
        "title": title,
        "description": description,
        "recommended_action": "",
        "estimated_impact": "",
        "severity": CompanionIssue.Severity.LOW,
        "data": {},
        "status": CompanionIssue.Status.OPEN,
    }


def _severity_from_materiality(amount: float, compliance_risk: bool = False, recurring: bool = False):
    """
    Heuristic:
    - High if compliance_risk, or amount >= ~1000, or recurring + amount >= 500.
    - Medium if amount >= ~250 or recurring.
    - Low otherwise.
    """
    if compliance_risk or amount >= 1000 or (recurring and amount >= 500):
        return CompanionIssue.Severity.HIGH
    if amount >= 250 or recurring:
        return CompanionIssue.Severity.MEDIUM
    return CompanionIssue.Severity.LOW


def build_receipts_issues(run, trace_id: str | None) -> list[dict]:
    metrics = run.metrics or {}
    issues: list[dict] = []
    high = int(metrics.get("documents_high_risk", 0) or 0)
    errors = int(run.error_count or 0)
    warnings = int(run.warning_count or 0)
    total_amount = float(metrics.get("total_amount", 0) or 0)
    if high > 0:
        issue = _base_issue("receipts", "receipts", run.id, trace_id, "High-risk receipts detected", f"{high} receipts flagged high risk.")
        issue["severity"] = _severity_from_materiality(total_amount, compliance_risk=False, recurring=high > 1)
        issue["recommended_action"] = "Review high-risk receipts and confirm classifications."
        issue["data"] = {"high_risk": high}
        issues.append(issue)
    if errors > 0:
        issue = _base_issue("receipts", "receipts", run.id, trace_id, "Receipts failed processing", f"{errors} receipts failed processing.")
        issue["severity"] = _severity_from_materiality(total_amount, compliance_risk=True)
        issue["recommended_action"] = "Open the run and resolve the errored receipts."
        issue["data"] = {"errors": errors}
        issues.append(issue)
    if warnings > 0 and high == 0:
        issue = _base_issue("receipts", "receipts", run.id, trace_id, "Receipts need review", f"{warnings} receipts have warnings.")
        issue["severity"] = _severity_from_materiality(total_amount * 0.25, recurring=warnings > 1)
        issue["recommended_action"] = "Check warning receipts and confirm vendors/categories."
        issue["data"] = {"warnings": warnings}
        issues.append(issue)
    return issues


def build_invoices_issues(run, trace_id: str | None) -> list[dict]:
    metrics = run.metrics or {}
    issues: list[dict] = []
    high = int(metrics.get("documents_high_risk", 0) or 0)
    errors = int(run.error_count or 0)
    overdue_total = float(metrics.get("overdue_total", 0) or 0)
    overdue_count = int(metrics.get("overdue_count", 0) or 0)
    if high > 0:
        issues.append(
            {
                **_base_issue("invoices", "invoices", run.id, trace_id, "High-risk invoices detected", f"{high} invoices flagged high risk."),
                "severity": _severity_from_materiality(overdue_total or high * 500, recurring=high > 1),
                "recommended_action": "Review high-risk invoices and verify amounts/dates.",
                "data": {"high_risk": high},
            }
        )
    if errors > 0:
        issues.append(
            {
                **_base_issue("invoices", "invoices", run.id, trace_id, "Invoices failed processing", f"{errors} invoices failed processing."),
                "severity": _severity_from_materiality(overdue_total or errors * 500, compliance_risk=True),
                "recommended_action": "Open the run and resolve the errored invoices.",
                "data": {"errors": errors},
            }
        )
    if overdue_total > 0:
        issues.append(
            {
                **_base_issue("invoices", "invoices", run.id, trace_id, "Overdue invoices impacting cash flow", f"Overdue total ≈ {overdue_total:,.2f} across {overdue_count} invoices."),
                "severity": _severity_from_materiality(overdue_total, recurring=overdue_count > 1),
                "recommended_action": "Prioritize collection: send reminders or set payment plans.",
                "estimated_impact": f"≈ {overdue_total:,.2f}",
                "data": {"overdue_total": overdue_total, "overdue_count": overdue_count},
            }
        )
    return issues


def build_books_review_issues(run, trace_id: str | None) -> list[dict]:
    metrics = run.metrics or {}
    issues: list[dict] = []
    high = int(metrics.get("journals_high_risk", 0) or 0)
    findings = int(metrics.get("findings_count", 0) or 0)
    suspense_balance = float(metrics.get("suspense_balance", 0) or 0)
    if high > 0:
        issues.append(
            {
                **_base_issue("books", "books_review", run.id, trace_id, "High-risk journals detected", f"{high} journals flagged high risk in this period."),
                "severity": _severity_from_materiality(abs(suspense_balance) or high * 1000, compliance_risk=True),
                "recommended_action": "Open the Books Review and inspect high-risk journals.",
                "data": {"journals_high_risk": high},
            }
        )
    if findings and high == 0:
        issues.append(
            {
                **_base_issue("books", "books_review", run.id, trace_id, "Findings require review", f"{findings} findings generated in this review."),
                "severity": _severity_from_materiality(findings * 100, recurring=findings > 1),
                "recommended_action": "Review findings for the period and confirm any adjustments manually.",
                "data": {"findings": findings},
            }
        )
    if suspense_balance:
        issues.append(
            {
                **_base_issue("books", "books_review", run.id, trace_id, "Suspense balance present", f"Suspense/clearing balance ≈ {suspense_balance:,.2f}."),
                "severity": _severity_from_materiality(abs(suspense_balance), compliance_risk=True, recurring=abs(suspense_balance) > 0),
                "recommended_action": "Clear suspense to proper accounts; investigate source transactions.",
                "estimated_impact": f"≈ {suspense_balance:,.2f}",
                "data": {"suspense_balance": suspense_balance},
            }
        )
    return issues


def build_bank_review_issues(run, trace_id: str | None) -> list[dict]:
    metrics = run.metrics or {}
    issues: list[dict] = []
    unreconciled = int(metrics.get("transactions_unreconciled", 0) or 0)
    high = int(metrics.get("transactions_high_risk", 0) or 0)
    unreconciled_total = float(metrics.get("unreconciled_total", 0) or 0)
    duplicate_count = int(metrics.get("transactions_duplicate", 0) or 0)
    if unreconciled > 0:
        issues.append(
            {
                **_base_issue("bank", "bank_review", run.id, trace_id, "Unreconciled bank transactions", f"{unreconciled} transactions remain unreconciled."),
                "severity": _severity_from_materiality(unreconciled_total or unreconciled * 200, recurring=unreconciled > 2),
                "recommended_action": "Match or explain unreconciled transactions.",
                "estimated_impact": f"≈ {unreconciled_total:,.2f}" if unreconciled_total else "",
                "data": {"unreconciled": unreconciled, "unreconciled_total": unreconciled_total},
            }
        )
    if high > 0:
        issues.append(
            {
                **_base_issue("bank", "bank_review", run.id, trace_id, "High-risk bank lines", f"{high} bank lines flagged high risk."),
                "severity": _severity_from_materiality(unreconciled_total or high * 500, recurring=high > 1, compliance_risk=True),
                "recommended_action": "Review high-risk bank lines and confirm matches.",
                "data": {"high_risk": high},
            }
        )
    if duplicate_count > 0:
        issues.append(
            {
                **_base_issue("bank", "bank_review", run.id, trace_id, "Possible duplicate bank lines", f"{duplicate_count} lines look duplicated."),
                "severity": _severity_from_materiality(duplicate_count * 100, recurring=duplicate_count > 1),
                "recommended_action": "Deduplicate bank lines and ensure GL reflects reality.",
                "data": {"duplicates": duplicate_count},
            }
        )
    return issues


def persist_companion_issues(business, issues: Iterable[dict], ai_companion_enabled: bool, user_name: str | None = None):
    """Create CompanionIssue rows. If AI companion is on, optionally refine/rank via LLM; fallback to deterministic issues."""
    issue_list = list(issues)
    if not issue_list:
        return []
    if ai_companion_enabled:
        # Determine overall risk level from issues
        has_high = any(i.get("severity") == "high" for i in issue_list)
        risk_level = "high" if has_high else "medium" if issue_list else "low"
        refined = refine_companion_issues(issue_list, user_name=user_name, risk_level=risk_level) or issue_list
    else:
        refined = issue_list
    objects = []
    for issue in refined:
        objects.append(
            CompanionIssue(
                business=business,
                surface=issue.get("surface", ""),
                run_type=issue.get("run_type", ""),
                run_id=issue.get("run_id"),
                severity=issue.get("severity", CompanionIssue.Severity.LOW),
                status=issue.get("status", CompanionIssue.Status.OPEN),
                title=issue.get("title", "")[:255],
                description=issue.get("description", ""),
                recommended_action=issue.get("recommended_action", "")[:255],
                estimated_impact=issue.get("estimated_impact", "")[:255],
                data=issue.get("data", {}) or {},
                trace_id=issue.get("trace_id", "")[:255],
            )
        )
    with transaction.atomic():
        created = CompanionIssue.objects.bulk_create(objects)
    return created


def rank_issues_for_summary(issues_qs):
    """
    Ordering: severity (high>medium>low) -> estimated impact (desc) -> created_at desc.
    """
    severity_rank = {"high": 0, "medium": 1, "low": 2}

    def _impact_val(issue):
        est = issue.estimated_impact or ""
        # crude parse for leading currency/number
        import re
        m = re.search(r"([\d,]+(?:\.\d+)?)", est.replace(",", ""))
        try:
            return float(m.group(1)) if m else 0.0
        except Exception:
            return 0.0

    sorted_issues = sorted(
        issues_qs,
        key=lambda i: (
            severity_rank.get(i.severity, 3),
            -_impact_val(i),
            i.created_at,
        ),
        reverse=False,
    )
    return sorted_issues


def get_issue_counts(business, days: int = 30):
    since = timezone.now() - timedelta(days=days)
    qs = CompanionIssue.objects.filter(business=business, status=CompanionIssue.Status.OPEN, created_at__gte=since)
    total = qs.count()
    by_severity = {sev: qs.filter(severity=sev).count() for sev, _ in CompanionIssue.Severity.choices}
    by_surface = {surf: qs.filter(surface=surf).count() for surf, _ in CompanionIssue.Surface.choices}
    return total, by_severity, by_surface, qs


# ---------------------------------------------------------------------------
# COMPANION RISK RADAR - 4-axis stability scoring (deterministic, no LLM)
# ---------------------------------------------------------------------------

# Map surfaces to radar axes (themes)
SURFACE_TO_THEME = {
    "bank": "cash_reconciliation",
    "invoices": "revenue_invoices",
    "receipts": "expenses_receipts",
    "books": "tax_compliance",
    "tax": "tax_guardian",
}

# Point deductions per severity
SEVERITY_DEDUCTION = {
    "high": 15,
    "medium": 8,
    "low": 3,
}

# Age penalty: extra points per 7 days old (softened from 2 to 1)
AGE_PENALTY_PER_WEEK = 1

# Maximum age penalty per issue to avoid old low-severity issues tanking the score
MAX_AGE_PENALTY = 5


def build_companion_radar(business) -> dict:
    """
    Build a 5-axis stability score (0–100) for the AI Companion.
    
    Axes:
      - cash_reconciliation: Bank account reconciliation health
      - revenue_invoices: Invoice/AR health
      - expenses_receipts: Expense/receipt classification health
      - tax_compliance: Books/GL compliance health
      - tax_guardian: Deterministic tax anomalies (TaxAnomaly)
    
    Scoring heuristic:
      - Each axis starts at 100
      - Subtract points per open issue based on severity:
        - high: -15 points
        - medium: -8 points
        - low: -3 points
      - Age penalty: subtract additional 1 point per 7 days (capped at 5 points per issue)
      - Floor at 0, cap at 100
    
    Returns:
        dict with 5 axes, each containing {"score": int, "open_issues": int}
    """
    now = timezone.now()
    since = now - timedelta(days=30)
    
    # Initialize all axes
    axes = {
        "cash_reconciliation": {"score": 100, "open_issues": 0},
        "revenue_invoices": {"score": 100, "open_issues": 0},
        "expenses_receipts": {"score": 100, "open_issues": 0},
        "tax_compliance": {"score": 100, "open_issues": 0},
        "tax_guardian": {"score": 100, "open_issues": 0},
    }
    
    # Get open issues for this business
    open_issues = CompanionIssue.objects.filter(
        business=business,
        status=CompanionIssue.Status.OPEN,
        created_at__gte=since,
    )
    
    for issue in open_issues:
        # Determine which axis this issue affects
        theme = SURFACE_TO_THEME.get(issue.surface)
        if not theme or theme not in axes:
            continue
        
        # Count the issue
        axes[theme]["open_issues"] += 1
        
        # Calculate base deduction from severity
        severity = issue.severity.lower() if issue.severity else "low"
        base_deduction = SEVERITY_DEDUCTION.get(severity, 3)
        
        # Calculate age penalty (extra points per week old, capped)
        days_old = (now - issue.created_at).days
        age_penalty = min((days_old // 7) * AGE_PENALTY_PER_WEEK, MAX_AGE_PENALTY)
        
        # Total deduction
        total_deduction = base_deduction + age_penalty
        
        # Apply deduction (floor at 0)
        axes[theme]["score"] = max(0, axes[theme]["score"] - total_deduction)

    # Tax anomalies (deterministic, TaxAnomaly)
    tax_anomalies = TaxAnomaly.objects.filter(
        business=business,
        status=TaxAnomaly.AnomalyStatus.OPEN,
    )
    for anomaly in tax_anomalies:
        severity = (anomaly.severity or "low").lower()
        deduction = SEVERITY_DEDUCTION.get(severity, 3)
        axes["tax_guardian"]["open_issues"] += 1
        axes["tax_guardian"]["score"] = max(0, axes["tax_guardian"]["score"] - deduction)
    
    return axes


# ---------------------------------------------------------------------------
# COMPANION COVERAGE METRICS - "How much is actually done?"
# ---------------------------------------------------------------------------

class CoverageAxis(TypedDict):
    coverage_percent: float
    total_items: int
    covered_items: int


def build_companion_coverage(business) -> dict[str, CoverageAxis]:
    """
    Build coverage metrics per domain for the Companion.
    
    Domains:
      - receipts: ReceiptDocuments that are POSTED or PROCESSED
      - invoices: Invoices that are PAID, PARTIAL, or SENT
      - banking: BankTransactions that are POSTED, MATCHED, RECONCILED, or EXCLUDED
    
    Note: "books" coverage is intentionally omitted until we have real journal
    reconciliation metrics. The frontend handles books being absent gracefully.
    
    Returns:
        Dict with coverage_percent, total_items, covered_items per domain.
    """
    since = timezone.now() - timedelta(days=30)
    
    # --- Receipts Coverage ---
    receipts_total = ReceiptDocument.objects.filter(
        business=business,
        created_at__gte=since,
    ).exclude(status=ReceiptDocument.DocumentStatus.DISCARDED).count()
    
    receipts_covered = ReceiptDocument.objects.filter(
        business=business,
        created_at__gte=since,
        status__in=[
            ReceiptDocument.DocumentStatus.POSTED,
            ReceiptDocument.DocumentStatus.PROCESSED,
        ],
    ).count()
    
    receipts_pct = (receipts_covered / max(1, receipts_total)) * 100
    
    # --- Invoices Coverage ---
    invoices_total = Invoice.objects.filter(
        business=business,
        issue_date__gte=since.date(),
    ).exclude(status=Invoice.Status.VOID).count()
    
    invoices_covered = Invoice.objects.filter(
        business=business,
        issue_date__gte=since.date(),
        status__in=[
            Invoice.Status.PAID,
            Invoice.Status.PARTIAL,
            Invoice.Status.SENT,
        ],
    ).count()
    
    invoices_pct = (invoices_covered / max(1, invoices_total)) * 100
    
    # --- Banking Coverage ---
    # Get all bank accounts for this business
    bank_account_ids = BankAccount.objects.filter(business=business).values_list('id', flat=True)
    
    banking_total = BankTransaction.objects.filter(
        bank_account_id__in=bank_account_ids,
        date__gte=since.date(),
    ).count()
    
    # Covered = MATCHED, MATCHED_SINGLE, MATCHED_MULTI, RECONCILED, or EXCLUDED
    # NEW/SUGGESTED/PARTIAL = not fully reviewed, so not covered
    # EXCLUDED = intentionally excluded from reconciliation, counts as covered decision
    banking_covered = BankTransaction.objects.filter(
        bank_account_id__in=bank_account_ids,
        date__gte=since.date(),
        status__in=[
            BankTransaction.TransactionStatus.MATCHED,
            BankTransaction.TransactionStatus.MATCHED_SINGLE,
            BankTransaction.TransactionStatus.MATCHED_MULTI,
            BankTransaction.TransactionStatus.RECONCILED,
            BankTransaction.TransactionStatus.EXCLUDED,
        ],
    ).count()
    
    banking_pct = (banking_covered / max(1, banking_total)) * 100
    
    # Note: "books" domain is omitted until we have real journal reconciliation metrics.
    # The frontend handles this gracefully by checking if books key exists.
    
    return {
        "receipts": {
            "coverage_percent": round(receipts_pct, 1),
            "total_items": receipts_total,
            "covered_items": receipts_covered,
        },
        "invoices": {
            "coverage_percent": round(invoices_pct, 1),
            "total_items": invoices_total,
            "covered_items": invoices_covered,
        },
        "banking": {
            "coverage_percent": round(banking_pct, 1),
            "total_items": banking_total,
            "covered_items": banking_covered,
        },
    }


# ---------------------------------------------------------------------------
# CLOSE-READINESS - "Should I close this period?"
# ---------------------------------------------------------------------------

# Close-readiness thresholds (documented):
# - Don't block for trivial unreconciled counts (<5)
# - Don't block if unreconciled rate is <2% of total transactions
UNRECONCILED_ABSOLUTE_THRESHOLD = 5
UNRECONCILED_RATIO_THRESHOLD = 0.02


class CloseReadinessResult(TypedDict):
    status: Literal["ready", "not_ready"]
    blocking_reasons: List[str]
    blocking_items: List["CloseBlockingItem"]


class CloseBlockingItem(TypedDict):
    reason: str
    task_code: str | None
    surface: str | None


def evaluate_period_close_readiness(business) -> CloseReadinessResult:
    """
    Evaluate whether the most recent accounting period looks safe to close.
    
    Uses deterministic checks only:
      - unreconciled bank items (only if material: >=5 OR >=2% of total)
      - suspicious account balances (suspense accounts with non-zero balance)
      - open high/critical CompanionIssues in books/bank themes
    
    Returns:
        CloseReadinessResult with status and blocking_reasons list.
    """
    blocking_reasons: list[str] = []
    blocking_items: list[CloseBlockingItem] = []
    since = timezone.now() - timedelta(days=30)
    
    # Check 1: Unreconciled bank transactions (with thresholds)
    bank_account_ids = BankAccount.objects.filter(business=business).values_list('id', flat=True)
    
    total_bank_txns = BankTransaction.objects.filter(
        bank_account_id__in=bank_account_ids,
        date__gte=since.date(),
    ).count()
    
    unreconciled_count = BankTransaction.objects.filter(
        bank_account_id__in=bank_account_ids,
        date__gte=since.date(),
        status=BankTransaction.TransactionStatus.NEW,
    ).count()
    
    # Only block if unreconciled count is material:
    # - At least UNRECONCILED_ABSOLUTE_THRESHOLD (5) unreconciled items, OR
    # - Unreconciled ratio >= UNRECONCILED_RATIO_THRESHOLD (2%)
    if total_bank_txns > 0:
        unreconciled_ratio = unreconciled_count / total_bank_txns
        if unreconciled_count >= UNRECONCILED_ABSOLUTE_THRESHOLD or unreconciled_ratio >= UNRECONCILED_RATIO_THRESHOLD:
            reason = f"B1 – {unreconciled_count} unreconciled bank transactions ({unreconciled_ratio:.1%} of total)."
            blocking_reasons.append(reason)
            blocking_items.append({"reason": reason, "task_code": "B1", "surface": "bank"})
    
    # Check 2: Suspense/clearing account balance
    # Priority 1: Look for accounts with is_suspense=True (business-scoped)
    # Priority 2: Fall back to common suspense codes if none marked
    suspense_accounts = Account.objects.filter(
        business=business,
        is_suspense=True,
    )
    if not suspense_accounts.exists():
        # Fallback: use heuristic codes (9999, 2999, 3999) if no accounts are marked as suspense
        suspense_accounts = Account.objects.filter(
            business=business,
            code__in=["9999", "2999", "3999"],
        )
    
    # Avoid N+1 queries: compute all suspense balances in a single query
    # by annotating with the sum of journal line debits - credits
    if suspense_accounts.exists():
        from decimal import Decimal as D
        from django.db.models import Sum, F, Value, DecimalField
        from django.db.models.functions import Coalesce
        
        # Get balances via annotation to avoid N+1 .balance() calls
        # JournalLine has debit/credit fields, not amount - balance = debits - credits
        # Use DecimalField output_field to avoid mixed type errors
        suspense_with_balance = suspense_accounts.annotate(
            total_debits=Coalesce(
                Sum('journal_lines__debit'),
                Value(D('0')),
                output_field=DecimalField()
            ),
            total_credits=Coalesce(
                Sum('journal_lines__credit'),
                Value(D('0')),
                output_field=DecimalField()
            ),
        ).annotate(
            computed_balance=F('total_debits') - F('total_credits')
        ).exclude(computed_balance=0)  # Only accounts with non-zero balance
        
        for acct in suspense_with_balance:
            bal = float(acct.computed_balance or 0)
            if abs(bal) > 0.01:
                reason = f"G1 – {acct.name} has a balance of ${bal:,.2f}."
                blocking_reasons.append(reason)
                blocking_items.append({"reason": reason, "task_code": "G1", "surface": "books"})
    
    # Check 3: High/Critical CompanionIssues in books or bank
    critical_issues = CompanionIssue.objects.filter(
        business=business,
        status=CompanionIssue.Status.OPEN,
        severity__in=[CompanionIssue.Severity.HIGH],
        surface__in=["books", "bank"],
        created_at__gte=since,
    ).count()
    
    if critical_issues > 0:
        reason = f"C1 – {critical_issues} high-severity issue(s) in Books or Banking."
        blocking_reasons.append(reason)
        blocking_items.append({"reason": reason, "task_code": "C1", "surface": "close"})

    # Check 4: Tax anomalies (high severity open for current period)
    current_period_key = _current_period_key()
    tax_blockers = TaxAnomaly.objects.filter(
        business=business,
        period_key=current_period_key,
        severity=TaxAnomaly.AnomalySeverity.HIGH,
        status=TaxAnomaly.AnomalyStatus.OPEN,
    ).count()
    if tax_blockers > 0:
        reason = f"T2 – Unresolved high-severity tax anomalies for period {current_period_key}."
        blocking_reasons.append(reason)
        blocking_items.append({"reason": reason, "task_code": "T2", "surface": "tax"})
    
    status: Literal["ready", "not_ready"] = "ready" if not blocking_reasons else "not_ready"
    
    return {
        "status": status,
        "blocking_reasons": blocking_reasons,
        "blocking_items": blocking_items,
    }


# ---------------------------------------------------------------------------
# TODAY'S PLAYBOOK - 2-4 prioritized actions
# ---------------------------------------------------------------------------

class PlaybookStep(TypedDict):
    label: str
    surface: str
    severity: str
    url: str
    issue_id: int | None
    task_code: str
    requires_premium: bool


# Surface to URL mapping
SURFACE_URL_MAP = {
    "bank": "/bank-review/",
    "receipts": "/receipts/",
    "invoices": "/invoices/ai/",
    "books": "/books-review/",
    "tax": "/tax-guardian/",
}

TAX_ANOMALY_TASK_MAP = {
    "T1_RATE_MISMATCH": "T1",
    "T2_POSSIBLE_OVERCHARGE": "T1",
    "T3_MISSING_TAX": "T2",
    "T3_MISSING_COMPONENT": "T1",
    "T4_ROUNDING_ANOMALY": "T3",
    "T5_EXEMPT_TAXED": "T1",
    "T6_NEGATIVE_BALANCE": "T2",
}


def _build_action_label(issue, task: CompanionTask | None = None) -> str:
    """
    Build an action-oriented label for a playbook step.
    
    Uses issue context (surface, data, title) to create specific,
    actionable labels like:
      - "Reconcile 9 unmatched transactions in Scotia Business Checking"
      - "Follow up on 3 overdue invoices"
      - "Clear $3,200 from suspense account"
    
    Keeps labels under ~80 characters for readability.
    This is deterministic - no LLM calls.
    """
    data = issue.data or {}
    surface = issue.surface
    title = issue.title or ""
    
    # Bank-related issues
    if surface == "bank":
        if data.get("unreconciled"):
            return f"Reconcile {data['unreconciled']} unmatched bank transactions"
        if data.get("high_risk"):
            return f"Review {data['high_risk']} high-risk bank lines"
        if data.get("duplicates"):
            return f"Resolve {data['duplicates']} possible duplicate bank entries"
        if "unreconciled" in title.lower():
            return "Match unreconciled bank transactions"
    
    # Invoice-related issues
    if surface == "invoices":
        if data.get("overdue_count"):
            total = data.get("overdue_total", 0)
            if total:
                return f"Follow up on {data['overdue_count']} overdue invoices (${total:,.0f})"
            return f"Follow up on {data['overdue_count']} overdue invoices"
        if data.get("high_risk"):
            return f"Review {data['high_risk']} high-risk invoices"
        if data.get("errors"):
            return f"Fix {data['errors']} failed invoice processing errors"
    
    # Receipt-related issues
    if surface == "receipts":
        if data.get("high_risk"):
            return f"Classify {data['high_risk']} high-risk receipts"
        if data.get("errors"):
            return f"Resolve {data['errors']} receipt processing errors"
        if data.get("warnings"):
            return f"Review {data['warnings']} receipts with warnings"
    
    # Books-related issues
    if surface == "books":
        if data.get("suspense_balance"):
            bal = data["suspense_balance"]
            return f"Clear ${abs(bal):,.0f} from suspense account"
        if data.get("journals_high_risk"):
            return f"Review {data['journals_high_risk']} high-risk journal entries"
        if data.get("findings"):
            return f"Address {data['findings']} findings in books review"
    
    # Fallback: use the issue title, trimmed
    if task:
        return task.label
    return title[:80] if title else "Review open issue"


def _task_for_issue(issue) -> CompanionTask | None:
    """
    Map an issue to a canonical Companion task.
    """
    data = getattr(issue, "data", {}) or {}
    surface = getattr(issue, "surface", None)
    title = (getattr(issue, "title", "") or "").lower()

    if surface == "bank":
        if data.get("unreconciled") or "unreconciled" in title:
            return get_task("B1")
        if data.get("high_risk") or data.get("duplicates"):
            return get_task("B1")
        return get_task("B2")

    if surface == "receipts":
        if data.get("high_risk") or data.get("errors") or data.get("warnings"):
            return get_task("R1")
        return get_task("R2")

    if surface == "invoices":
        if data.get("overdue_count") or data.get("high_risk") or data.get("errors"):
            return get_task("I1B" if data.get("overdue_count") else "I1")
        return get_task("I1")

    if surface == "books":
        if data.get("suspense_balance") or "suspense" in title:
            return get_task("G1")
        if data.get("findings") or data.get("journals_high_risk"):
            return get_task("G4")
        return get_task("G2")

    return first_task_for_surface(surface) if surface else None


def _task_or_default(surface: str, task: CompanionTask | None = None) -> CompanionTask | None:
    return task or first_task_for_surface(surface)


def _task_for_tax_anomaly(anomaly: TaxAnomaly) -> CompanionTask | None:
    mapped = TAX_ANOMALY_TASK_MAP.get(anomaly.code, "T1")
    return get_task(mapped) or first_task_for_surface("tax")


def _label_for_tax_anomaly(anomaly: TaxAnomaly, task: CompanionTask | None) -> str:
    desc = (anomaly.description or "").strip()
    if desc:
        return f"{anomaly.code}: {desc[:90]}"
    return task.label if task else anomaly.code


def build_companion_playbook(business, max_steps: int = 4) -> List[PlaybookStep]:
    """
    Build a short, ordered list of 2-4 actions for the user to take today.
    
    Based on:
      - Ranked CompanionIssues (severity + age)
      - Coverage gaps
      - Close-readiness blocking reasons
    
    Labels are action-oriented and anchored to canonical Companion tasks
    (task_code), with premium tasks marked via requires_premium.
    
    Returns:
        List of PlaybookStep dicts with label, surface, severity, url, issue_id, task_code.
    """
    since = timezone.now() - timedelta(days=30)
    playbook: List[PlaybookStep] = []
    
    # Priority 1: Get top open issues by severity
    severity_order = {
        CompanionIssue.Severity.HIGH: 0,
        CompanionIssue.Severity.MEDIUM: 1,
        CompanionIssue.Severity.LOW: 2,
    }
    
    open_issues = list(CompanionIssue.objects.filter(
        business=business,
        status=CompanionIssue.Status.OPEN,
        created_at__gte=since,
    ).order_by('-created_at')[:20])
    
    # Sort by severity
    open_issues.sort(key=lambda i: (severity_order.get(i.severity, 3), -i.created_at.timestamp()))
    
    for issue in open_issues:
        if len(playbook) >= max_steps:
            break
        task = _task_or_default(issue.surface, _task_for_issue(issue))
        if not task or not valid_task_code(task.code):
            continue
        playbook.append({
            "label": _build_action_label(issue, task),  # Action-oriented label
            "surface": issue.surface,
            "severity": issue.severity,
            "url": SURFACE_URL_MAP.get(issue.surface, "/companion/"),
            "issue_id": issue.id,
            "task_code": task.code,
            "requires_premium": task.requires_premium,
        })

    # Priority 1b: Tax anomalies (deterministic)
    if len(playbook) < max_steps:
        sev_order = {
            TaxAnomaly.AnomalySeverity.HIGH: 0,
            TaxAnomaly.AnomalySeverity.MEDIUM: 1,
            TaxAnomaly.AnomalySeverity.LOW: 2,
        }
        tax_anomalies = list(
            TaxAnomaly.objects.filter(
                business=business,
                status=TaxAnomaly.AnomalyStatus.OPEN,
            )
        )
        tax_anomalies.sort(key=lambda a: sev_order.get(a.severity, 3))
        for anomaly in tax_anomalies:
            if len(playbook) >= max_steps:
                break
            task = _task_for_tax_anomaly(anomaly)
            if not task or not valid_task_code(task.code):
                continue
            playbook.append(
                {
                    "label": _label_for_tax_anomaly(anomaly, task),
                    "surface": "tax",
                    "severity": anomaly.severity,
                    "url": SURFACE_URL_MAP.get("tax", "/companion/"),
                    "issue_id": None,
                    "task_code": task.code,
                    "requires_premium": task.requires_premium,
                }
            )
    
    # Priority 2: Add coverage gap action if we have room
    if len(playbook) < max_steps:
        coverage = build_companion_coverage(business)
        if coverage:  # May be empty if no data
            lowest_coverage = min(coverage.items(), key=lambda x: x[1]["coverage_percent"])
            domain, axis = lowest_coverage
            
            if axis["coverage_percent"] < 80:
                uncovered = axis["total_items"] - axis["covered_items"]
                label_map = {
                    "receipts": f"Process {uncovered} pending receipts" if uncovered > 0 else "Post approved receipts",
                    "invoices": f"Follow up on {uncovered} draft/unpaid invoices" if uncovered > 0 else "Match payments to invoices",
                    "banking": f"Match {uncovered} unmatched bank transactions" if uncovered > 0 else "Review unreconciled transactions",
                }
                surface_map = {
                    "receipts": "receipts",
                    "invoices": "invoices",
                    "banking": "bank",
                }
                coverage_task_code_map = {
                    "receipts": "R2",
                    "invoices": "I1",
                    "banking": "B1",
                }
                surface = surface_map.get(domain, domain)
                task = _task_or_default(surface, get_task(coverage_task_code_map.get(domain, "")))
                if task and valid_task_code(task.code):
                    playbook.append({
                        "label": label_map.get(domain, task.label),
                        "surface": surface,
                        "severity": "medium",
                        "url": SURFACE_URL_MAP.get(surface, "/companion/"),
                        "issue_id": None,
                        "task_code": task.code,
                        "requires_premium": task.requires_premium,
                    })
    
    return playbook[:max_steps]
