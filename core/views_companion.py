from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone

from .models import (
    ReceiptRun,
    InvoiceRun,
    BooksReviewRun,
    BankReviewRun,
)
from .utils import get_current_business

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
        },
    }

    return JsonResponse(summary)


from django.shortcuts import render, redirect  # noqa: E402


@login_required
def companion_overview_page(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")
    return render(request, "companion_overview.html", {"business": business})
