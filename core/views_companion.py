import json
import logging
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import models
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone

logger = logging.getLogger(__name__)

# Cache TTL for companion summary (short-lived to ensure fresh data while reducing load)
COMPANION_SUMMARY_CACHE_TTL = 45  # seconds

from .models import (
    ReceiptRun,
    InvoiceRun,
    BooksReviewRun,
    BankReviewRun,
    CompanionIssue,
)
from .utils import get_current_business
from .companion_issues import (
    get_issue_counts,
    build_companion_radar,
    build_companion_coverage,
    evaluate_period_close_readiness,
    build_companion_playbook,
)
from .companion_voice import build_voice_snapshot
from .llm_reasoning import generate_companion_story

RISK_MEDIUM_THRESHOLD = Decimal("40.0")
RISK_HIGH_THRESHOLD = Decimal("70.0")


def _risk_level(score):
    if score is None:
        return None
    try:
        val = Decimal(score)
        if val >= RISK_HIGH_THRESHOLD:
            return "high"
        if val >= RISK_MEDIUM_THRESHOLD:
            return "medium"
        return "low"
    except Exception:
        return None


def _metrics_sum(runs, key: str):
    total = 0
    for r in runs:
        try:
            total += int(r.metrics.get(key, 0) or 0)
        except Exception:
            continue
    return total


def _serialize_run(run, high_risk_key: str, total_key: str, error_key: str | None = None):
    return {
        "id": run.id,
        "created_at": run.created_at.isoformat(),
        "period_start": getattr(run, "period_start", None).isoformat() if getattr(run, "period_start", None) else None,
        "period_end": getattr(run, "period_end", None).isoformat() if getattr(run, "period_end", None) else None,
        "risk_level": _risk_level(run.metrics.get(high_risk_key)) if hasattr(run, "metrics") else None,
        "high_risk_count": run.metrics.get(high_risk_key, 0) if hasattr(run, "metrics") else 0,
        "total": run.metrics.get(total_key, 0) if hasattr(run, "metrics") else 0,
        "errors_count": run.error_count if hasattr(run, "error_count") else (run.metrics.get(error_key, 0) if error_key else 0),
        "trace_id": getattr(run, "trace_id", None),
    }


@login_required
def api_companion_summary(request):
    business = get_current_business(request.user)
    if business is None:
        return HttpResponseBadRequest("No business context")

    # Check cache first (scoped by business ID to prevent data leakage)
    cache_key = f"companion_summary_{business.id}"
    cached_summary = cache.get(cache_key)
    if cached_summary is not None:
        logger.debug("Returning cached companion summary for business %s", business.id)
        return JsonResponse(cached_summary)

    now = timezone.now()
    since = now - timedelta(days=30)
    receipts_runs_recent = list(ReceiptRun.objects.filter(business=business).order_by("-created_at")[:3])
    invoices_runs_recent = list(InvoiceRun.objects.filter(business=business).order_by("-created_at")[:3])
    books_runs_recent = list(BooksReviewRun.objects.filter(business=business).order_by("-created_at")[:3])
    bank_runs_recent = list(BankReviewRun.objects.filter(business=business).order_by("-created_at")[:3])

    receipts_30 = ReceiptRun.objects.filter(business=business, created_at__gte=since)
    invoices_30 = InvoiceRun.objects.filter(business=business, created_at__gte=since)
    books_30 = BooksReviewRun.objects.filter(business=business, created_at__gte=since)
    bank_30 = BankReviewRun.objects.filter(business=business, created_at__gte=since)

    last_books = BooksReviewRun.objects.filter(business=business).order_by("-created_at").first()
    issues_total, issues_by_sev, issues_by_surface, issues_qs = get_issue_counts(business, days=30)
    headline_issue = (
        issues_qs.order_by(
            models.Case(
                models.When(severity="high", then=0),
                models.When(severity="medium", then=1),
                default=2,
                output_field=models.IntegerField(),
            ),
            "-created_at",
        ).first()
        if issues_qs.exists()
        else None
    )

    summary = {
        "ai_companion_enabled": business.ai_companion_enabled,
        "surfaces": {
            "receipts": {
                "recent_runs": [
                    {
                        "id": r.id,
                        "created_at": r.created_at.isoformat(),
                        "risk_level": _risk_level(r.metrics.get("documents_high_risk")),
                        "documents_total": r.metrics.get("documents_total", r.total_documents),
                        "high_risk_count": r.metrics.get("documents_high_risk", 0),
                        "errors_count": r.error_count,
                        "trace_id": r.trace_id,
                    }
                    for r in receipts_runs_recent
                ],
                "totals_last_30_days": {
                    "runs": receipts_30.count(),
                    "documents_total": _metrics_sum(receipts_30, "documents_total"),
                    "high_risk_documents": _metrics_sum(receipts_30, "documents_high_risk"),
                    "errors": sum(r.error_count for r in receipts_30),
                },
                "open_issues_count": issues_by_surface.get("receipts", 0),
                "high_risk_issues_count": issues_qs.filter(surface="receipts", severity="high").count(),
                "headline_issue": None,
            },
            "invoices": {
                "recent_runs": [
                    {
                        "id": r.id,
                        "created_at": r.created_at.isoformat(),
                        "risk_level": _risk_level(r.metrics.get("documents_high_risk")),
                        "documents_total": r.metrics.get("documents_total", r.total_documents),
                        "high_risk_count": r.metrics.get("documents_high_risk", 0),
                        "errors_count": r.error_count,
                        "trace_id": r.trace_id,
                    }
                    for r in invoices_runs_recent
                ],
                "totals_last_30_days": {
                    "runs": invoices_30.count(),
                    "documents_total": _metrics_sum(invoices_30, "documents_total"),
                    "high_risk_documents": _metrics_sum(invoices_30, "documents_high_risk"),
                    "errors": sum(r.error_count for r in invoices_30),
                },
                "open_issues_count": issues_by_surface.get("invoices", 0),
                "high_risk_issues_count": issues_qs.filter(surface="invoices", severity="high").count(),
                "headline_issue": None,
            },
            "books_review": {
                "recent_runs": [
                    {
                        "id": r.id,
                        "created_at": r.created_at.isoformat(),
                        "period_start": r.period_start.isoformat(),
                        "period_end": r.period_end.isoformat(),
                        "risk_level": _risk_level(r.overall_risk_score),
                        "overall_risk_score": str(r.overall_risk_score) if r.overall_risk_score is not None else None,
                        "trace_id": r.trace_id,
                    }
                    for r in books_runs_recent
                ],
                "totals_last_30_days": {
                    "runs": books_30.count(),
                    "high_risk_count": _metrics_sum(books_30, "journals_high_risk"),
                    "agent_retries": _metrics_sum(books_30, "agent_retries"),
                },
                "open_issues_count": issues_by_surface.get("books", 0),
                "high_risk_issues_count": issues_qs.filter(surface="books", severity="high").count(),
                "headline_issue": None,
            },
            "bank_review": {
                "recent_runs": [
                    {
                        "id": r.id,
                        "created_at": r.created_at.isoformat(),
                        "risk_level": _risk_level(r.overall_risk_score),
                        "transactions_total": r.metrics.get("transactions_total", 0),
                        "high_risk_count": r.metrics.get("transactions_high_risk", 0),
                        "unreconciled": r.metrics.get("transactions_unreconciled", 0),
                        "trace_id": r.trace_id,
                    }
                    for r in bank_runs_recent
                ],
                "totals_last_30_days": {
                    "runs": bank_30.count(),
                    "transactions_total": _metrics_sum(bank_30, "transactions_total"),
                    "transactions_high_risk": _metrics_sum(bank_30, "transactions_high_risk"),
                    "unreconciled": _metrics_sum(bank_30, "transactions_unreconciled"),
                },
                "open_issues_count": issues_by_surface.get("bank", 0),
                "high_risk_issues_count": issues_qs.filter(surface="bank", severity="high").count(),
                "headline_issue": None,
            },
        },
        "global": {
            "last_books_review": None
            if not last_books
            else {
                "run_id": last_books.id,
                "period_start": last_books.period_start.isoformat(),
                "period_end": last_books.period_end.isoformat(),
                "overall_risk_score": str(last_books.overall_risk_score) if last_books.overall_risk_score is not None else None,
                "risk_level": _risk_level(last_books.overall_risk_score),
                "trace_id": last_books.trace_id,
            },
            "high_risk_items_30d": {
                "receipts": _metrics_sum(receipts_30, "documents_high_risk"),
                "invoices": _metrics_sum(invoices_30, "documents_high_risk"),
                "bank_transactions": _metrics_sum(bank_30, "transactions_high_risk"),
            },
            "agent_retries_30d": _metrics_sum(receipts_30, "agent_retries")
            + _metrics_sum(invoices_30, "agent_retries")
            + _metrics_sum(books_30, "agent_retries")
            + _metrics_sum(bank_30, "agent_retries"),
            "open_issues_total": issues_total,
            "open_issues_by_severity": issues_by_sev,
            "open_issues_by_surface": issues_by_surface,
        },
    }

    if headline_issue:
        summary["global"]["headline_issue"] = {
            "id": headline_issue.id,
            "title": headline_issue.title,
            "severity": headline_issue.severity,
            "surface": headline_issue.surface,
        }
    for surf in ["receipts", "invoices", "books_review", "bank_review"]:
        if surf == "books_review":
            surface_key = "books"
        elif surf == "bank_review":
            surface_key = "bank"
        else:
            surface_key = surf
        hi = issues_qs.filter(surface=surface_key).order_by(
            models.Case(
                models.When(severity="high", then=0),
                models.When(severity="medium", then=1),
                default=2,
                output_field=models.IntegerField(),
            ),
            "-created_at",
        ).first()
        if hi:
            summary["surfaces"][surf]["headline_issue"] = {"id": hi.id, "title": hi.title, "severity": hi.severity}

    # Build deterministic voice snapshot (NO LLM calls)
    voice = build_voice_snapshot(
        user_name=request.user.first_name,
        issues=list(issues_qs),
        severity_counts=issues_by_sev,
    )
    
    # Add voice fields to response
    summary["voice"] = {
        "greeting": voice.greeting,
        "focus_mode": voice.focus_mode,
        "tone_tagline": voice.tone_tagline,
        "primary_call_to_action": voice.primary_call_to_action,
    }
    
    # Build 4-axis risk radar (deterministic, no LLM)
    radar = build_companion_radar(business)
    summary["radar"] = radar
    
    # Generate story narrative (DeepSeek Reasoner, only if AI enabled)
    story = None
    if business.ai_companion_enabled:
        story = generate_companion_story(
            first_name=request.user.first_name,
            radar=radar,
            recent_metrics=summary.get("global", {}),
            recent_issues=list(issues_qs[:10]),
            focus_mode=voice.focus_mode,
        )
    
    # Add story to response with graceful fallback
    if story:
        summary["story"] = {
            "overall_summary": story.overall_summary,
            "timeline_bullets": story.timeline_bullets,
        }
    else:
        summary["story"] = {
            "overall_summary": "Companion story is temporarily unavailable.",
            "timeline_bullets": [],
        }
    
    # Build coverage metrics (deterministic, no LLM)
    coverage = build_companion_coverage(business)
    summary["coverage"] = coverage
    
    # Evaluate close-readiness (deterministic, no LLM)
    close_readiness = evaluate_period_close_readiness(business)
    summary["close_readiness"] = close_readiness
    
    # Build today's playbook (deterministic, no LLM)
    playbook = build_companion_playbook(business)
    summary["playbook"] = playbook

    # Cache successful summary (short TTL to balance freshness vs. performance)
    # Only cache on success - errors/exceptions should not be cached
    cache.set(cache_key, summary, COMPANION_SUMMARY_CACHE_TTL)
    logger.debug("Cached companion summary for business %s (TTL=%ss)", business.id, COMPANION_SUMMARY_CACHE_TTL)

    return JsonResponse(summary)


from django.shortcuts import render, redirect  # noqa: E402


@login_required
def companion_overview_page(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")
    return render(request, "companion_overview.html", {"business": business})


@login_required
def companion_issues_page(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")
    return render(request, "companion_issues.html", {"business": business})


@login_required
def api_companion_issues(request):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    status = request.GET.get("status", CompanionIssue.Status.OPEN)
    surface = request.GET.get("surface")
    severity = request.GET.get("severity")

    qs = CompanionIssue.objects.filter(business=business)
    if status:
        qs = qs.filter(status=status)
    if surface:
        qs = qs.filter(surface=surface)
    if severity:
        qs = qs.filter(severity=severity)

    data = [
        {
            "id": issue.id,
            "surface": issue.surface,
            "severity": issue.severity,
            "status": issue.status,
            "title": issue.title,
            "recommended_action": issue.recommended_action,
            "estimated_impact": issue.estimated_impact,
            "run_type": issue.run_type,
            "run_id": issue.run_id,
            "created_at": issue.created_at.isoformat(),
            "trace_id": issue.trace_id,
        }
        for issue in qs.order_by("-created_at")[:200]
    ]
    return JsonResponse({"issues": data})


@login_required
def api_companion_issue_patch(request, issue_id: int):
    if request.method not in {"PATCH", "POST"}:
        return JsonResponse({"error": "Method not allowed"}, status=405)
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)
    issue = CompanionIssue.objects.filter(business=business, pk=issue_id).first()
    if not issue:
        return JsonResponse({"error": "Issue not found"}, status=404)
    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}
    new_status = payload.get("status")
    if new_status and new_status in CompanionIssue.Status.values:
        issue.status = new_status
        issue.save(update_fields=["status", "updated_at"])
    return JsonResponse({"id": issue.id, "status": issue.status})
