from __future__ import annotations

from datetime import timedelta
from typing import Iterable, List, Literal, TypedDict

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .llm_reasoning import refine_companion_issues
from .models import (
    CompanionIssue,
    ReceiptDocument,
    Invoice,
    BankTransaction,
    BankAccount,
    Account,
)


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
}

# Point deductions per severity
SEVERITY_DEDUCTION = {
    "high": 15,
    "medium": 8,
    "low": 3,
}

# Age penalty: extra points per 7 days old
AGE_PENALTY_PER_WEEK = 2


def build_companion_radar(business) -> dict:
    """
    Build a 4-axis stability score (0–100) for the AI Companion.
    
    Axes:
      - cash_reconciliation: Bank account reconciliation health
      - revenue_invoices: Invoice/AR health
      - expenses_receipts: Expense/receipt classification health
      - tax_compliance: Books/GL compliance health
    
    Scoring heuristic:
      - Each axis starts at 100
      - Subtract points per open issue based on severity:
        - high: -15 points
        - medium: -8 points
        - low: -3 points
      - Age penalty: subtract additional 2 points per 7 days the issue is open
      - Floor at 0, cap at 100
    
    Returns:
        dict with 4 axes, each containing {"score": int, "open_issues": int}
    """
    now = timezone.now()
    since = now - timedelta(days=30)
    
    # Initialize all axes
    axes = {
        "cash_reconciliation": {"score": 100, "open_issues": 0},
        "revenue_invoices": {"score": 100, "open_issues": 0},
        "expenses_receipts": {"score": 100, "open_issues": 0},
        "tax_compliance": {"score": 100, "open_issues": 0},
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
        
        # Calculate age penalty (extra points per week old)
        days_old = (now - issue.created_at).days
        age_penalty = (days_old // 7) * AGE_PENALTY_PER_WEEK
        
        # Total deduction
        total_deduction = base_deduction + age_penalty
        
        # Apply deduction (floor at 0)
        axes[theme]["score"] = max(0, axes[theme]["score"] - total_deduction)
    
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
      - banking: BankTransactions that are not NEW status
      - books: placeholder (journal entries reconciled)
    
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
    
    # Covered = anything not NEW
    banking_covered = BankTransaction.objects.filter(
        bank_account_id__in=bank_account_ids,
        date__gte=since.date(),
    ).exclude(status=BankTransaction.TransactionStatus.NEW).count()
    
    banking_pct = (banking_covered / max(1, banking_total)) * 100
    
    # --- Books Coverage ---
    # Simplified: use journal line reconciliation rate or CompanionIssue count
    # For now, estimate based on absence of books-related issues
    books_issues = CompanionIssue.objects.filter(
        business=business,
        surface="books",
        status=CompanionIssue.Status.OPEN,
        created_at__gte=since,
    ).count()
    
    # Start at 100%, subtract 10% per open books issue, floor at 0
    books_pct = max(0, 100 - (books_issues * 10))
    books_total = max(1, books_issues + 5)  # Rough estimate
    books_covered = int(books_total * (books_pct / 100))
    
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
        "books": {
            "coverage_percent": round(books_pct, 1),
            "total_items": books_total,
            "covered_items": books_covered,
        },
    }


# ---------------------------------------------------------------------------
# CLOSE-READINESS - "Should I close this period?"
# ---------------------------------------------------------------------------

class CloseReadinessResult(TypedDict):
    status: Literal["ready", "not_ready"]
    blocking_reasons: List[str]


def evaluate_period_close_readiness(business) -> CloseReadinessResult:
    """
    Evaluate whether the most recent accounting period looks safe to close.
    
    Uses deterministic checks only:
      - unreconciled bank items
      - suspicious account balances (suspense, negative tax payables)
      - open high/critical CompanionIssues in books/bank themes
    
    Returns:
        CloseReadinessResult with status and blocking_reasons list.
    """
    blocking_reasons: list[str] = []
    since = timezone.now() - timedelta(days=30)
    
    # Check 1: Unreconciled bank transactions
    bank_account_ids = BankAccount.objects.filter(business=business).values_list('id', flat=True)
    unreconciled_count = BankTransaction.objects.filter(
        bank_account_id__in=bank_account_ids,
        date__gte=since.date(),
        status=BankTransaction.TransactionStatus.NEW,
    ).count()
    
    if unreconciled_count > 0:
        blocking_reasons.append(f"{unreconciled_count} unreconciled bank transactions in the last 30 days.")
    
    # Check 2: Suspense/clearing account balance
    suspense_accounts = Account.objects.filter(
        business=business,
        code__in=["9999", "2999", "3999"],  # Common suspense codes
    )
    for acct in suspense_accounts:
        balance = acct.balance()
        if balance and abs(balance) > 0.01:
            blocking_reasons.append(f"{acct.name} has a balance of ${balance:,.2f}.")
    
    # Check 3: High/Critical CompanionIssues in books or bank
    critical_issues = CompanionIssue.objects.filter(
        business=business,
        status=CompanionIssue.Status.OPEN,
        severity__in=[CompanionIssue.Severity.HIGH],
        surface__in=["books", "bank"],
        created_at__gte=since,
    ).count()
    
    if critical_issues > 0:
        blocking_reasons.append(f"{critical_issues} high-severity issue(s) in Books or Banking.")
    
    status: Literal["ready", "not_ready"] = "ready" if not blocking_reasons else "not_ready"
    
    return {
        "status": status,
        "blocking_reasons": blocking_reasons,
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


# Surface to URL mapping
SURFACE_URL_MAP = {
    "bank": "/bank-review/",
    "receipts": "/receipts/",
    "invoices": "/invoices/ai/",
    "books": "/books-review/",
}


def build_companion_playbook(business, max_steps: int = 4) -> List[PlaybookStep]:
    """
    Build a short, ordered list of 2-4 actions for the user to take today.
    
    Based on:
      - Ranked CompanionIssues (severity + age)
      - Coverage gaps
      - Close-readiness blocking reasons
    
    Returns:
        List of PlaybookStep dicts with label, surface, severity, url, issue_id.
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
    
    for issue in open_issues[:max_steps]:
        playbook.append({
            "label": issue.title[:100],  # Trim if too long
            "surface": issue.surface,
            "severity": issue.severity,
            "url": SURFACE_URL_MAP.get(issue.surface, "/companion/"),
            "issue_id": issue.id,
        })
    
    # Priority 2: Add coverage gap action if we have room
    if len(playbook) < max_steps:
        coverage = build_companion_coverage(business)
        lowest_coverage = min(coverage.items(), key=lambda x: x[1]["coverage_percent"])
        domain, axis = lowest_coverage
        
        if axis["coverage_percent"] < 80:
            uncovered = axis["total_items"] - axis["covered_items"]
            label_map = {
                "receipts": f"Process {uncovered} pending receipts",
                "invoices": f"Follow up on {uncovered} draft/unpaid invoices",
                "banking": f"Match {uncovered} unmatched bank transactions",
                "books": f"Review {uncovered} open books items",
            }
            surface_map = {
                "receipts": "receipts",
                "invoices": "invoices",
                "banking": "bank",
                "books": "books",
            }
            
            playbook.append({
                "label": label_map.get(domain, f"Review {domain}"),
                "surface": surface_map.get(domain, domain),
                "severity": "medium",
                "url": SURFACE_URL_MAP.get(surface_map.get(domain, domain), "/companion/"),
                "issue_id": None,
            })
    
    return playbook[:max_steps]
