from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from .llm_reasoning import refine_companion_issues
from .models import CompanionIssue


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
