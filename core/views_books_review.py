import uuid
from decimal import Decimal
from datetime import date

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .agentic_books_review import run_books_review_workflow
from .models import BooksReviewRun
from .utils import get_current_business

RISK_MEDIUM_THRESHOLD = Decimal("40.0")
RISK_HIGH_THRESHOLD = Decimal("70.0")


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return timezone.datetime.fromisoformat(raw).date()
    except Exception:
        return None


def _risk_level(score: Decimal | None):
    if score is None:
        return None
    try:
        score_d = Decimal(score)
        if score_d >= RISK_HIGH_THRESHOLD:
            return "high"
        if score_d >= RISK_MEDIUM_THRESHOLD:
            return "medium"
        return "low"
    except Exception:
        return None


@csrf_exempt
@login_required
@require_POST
def api_books_review_run(request):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    try:
        period_start_raw = request.POST.get("period_start")
        period_end_raw = request.POST.get("period_end")
        period_start = date.fromisoformat(period_start_raw) if period_start_raw else None
        period_end = date.fromisoformat(period_end_raw) if period_end_raw else None
    except Exception:
        return JsonResponse({"error": "Invalid period. Use YYYY-MM-DD and ensure start <= end."}, status=400)

    if not period_start or not period_end or period_start > period_end:
        return JsonResponse({"error": "Invalid period. Use YYYY-MM-DD and ensure start <= end."}, status=400)

    run = BooksReviewRun.objects.create(
        business=business,
        created_by=request.user,
        period_start=period_start,
        period_end=period_end,
        status=BooksReviewRun.RunStatus.RUNNING,
    )

    try:
        result = run_books_review_workflow(
            business_id=business.id,
            period_start=period_start,
            period_end=period_end,
            triggered_by_user_id=request.user.id,
            ai_companion_enabled=business.ai_companion_enabled,
        )

        with transaction.atomic():
            run.status = BooksReviewRun.RunStatus.COMPLETED
            run.metrics = result.metrics
            run.findings = result.findings
            run.trace_id = result.trace_id
            run.overall_risk_score = result.overall_risk_score
            run.llm_explanations = result.llm_explanations
            run.llm_ranked_issues = result.llm_ranked_issues
            run.llm_suggested_checks = result.llm_suggested_checks
            run.save()
    except Exception as exc:  # pragma: no cover - defensive
        run.status = BooksReviewRun.RunStatus.FAILED
        run.save(update_fields=["status"])
        return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse(
        {
            "run_id": run.id,
            "status": run.status,
            "trace_id": run.trace_id,
            "metrics": run.metrics,
            "overall_risk_score": str(run.overall_risk_score) if run.overall_risk_score is not None else None,
            "risk_level": _risk_level(run.overall_risk_score),
            "findings": run.findings,
            "llm_explanations": run.llm_explanations,
            "llm_ranked_issues": run.llm_ranked_issues,
            "llm_suggested_checks": run.llm_suggested_checks,
            "period_start": run.period_start.isoformat(),
            "period_end": run.period_end.isoformat(),
            "companion_enabled": business.ai_companion_enabled,
        }
    )


@login_required
@require_GET
def api_books_review_runs(request):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)
    runs = BooksReviewRun.objects.filter(business=business).order_by("-created_at")[:50]
    data = [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat(),
            "created_by": r.created_by_id,
            "status": r.status,
            "period_start": r.period_start.isoformat(),
            "period_end": r.period_end.isoformat(),
            "metrics": r.metrics,
            "overall_risk_score": str(r.overall_risk_score) if r.overall_risk_score is not None else None,
            "risk_level": _risk_level(r.overall_risk_score),
            "trace_id": r.trace_id,
        }
        for r in runs
    ]
    return JsonResponse({"runs": data})


@login_required
@require_GET
def api_books_review_run_detail(request, run_id: int):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)
    run = BooksReviewRun.objects.filter(business=business, pk=run_id).first()
    if not run:
        return JsonResponse({"error": "Run not found"}, status=404)
    return JsonResponse(
        {
            "id": run.id,
            "created_at": run.created_at.isoformat(),
            "created_by": run.created_by_id,
            "status": run.status,
            "period_start": run.period_start.isoformat(),
            "period_end": run.period_end.isoformat(),
            "metrics": run.metrics,
            "overall_risk_score": str(run.overall_risk_score) if run.overall_risk_score is not None else None,
            "risk_level": _risk_level(run.overall_risk_score),
            "trace_id": run.trace_id,
            "findings": run.findings,
            "llm_explanations": run.llm_explanations,
            "llm_ranked_issues": run.llm_ranked_issues,
            "llm_suggested_checks": run.llm_suggested_checks,
            "companion_enabled": business.ai_companion_enabled,
        }
    )


@login_required
def books_review_page(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")
    return render(
        request,
        "books_review.html",
        {
            "business": business,
            "default_currency": business.currency,
        },
    )
