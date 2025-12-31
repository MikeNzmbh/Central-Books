import json
from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .agentic_bank_review import BankInputLine, run_bank_reconciliation_workflow
from .models import BankReviewRun, BankTransactionReview
from .utils import get_current_business

RISK_MEDIUM_THRESHOLD = Decimal("40.0")
RISK_HIGH_THRESHOLD = Decimal("70.0")


def _parse_date(raw: str | None):
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


def _parse_lines(raw_lines: str | None):
    if not raw_lines:
        return []
    try:
        data = json.loads(raw_lines)
        return data if isinstance(data, list) else []
    except Exception:
        return []


@csrf_exempt
@login_required
@require_POST
def api_bank_review_run(request):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    try:
        period_start_raw = request.POST.get("period_start")
        period_end_raw = request.POST.get("period_end")
        period_start = date.fromisoformat(period_start_raw) if period_start_raw else None
        period_end = date.fromisoformat(period_end_raw) if period_end_raw else None
    except Exception:
        return JsonResponse({"error": "Invalid period. Use YYYY-MM-DD."}, status=400)

    lines_payload = _parse_lines(request.POST.get("lines"))
    bank_lines: list[BankInputLine] = []
    for line in lines_payload:
        try:
            line_date = _parse_date(line.get("date")) or timezone.localdate()
            amount = Decimal(str(line.get("amount", "0")))
            bank_lines.append(
                BankInputLine(
                    date=line_date,
                    description=line.get("description") or "Bank transaction",
                    amount=amount,
                    external_id=line.get("external_id"),
                )
            )
        except Exception:
            continue

    if not bank_lines:
        return JsonResponse({"error": "No bank lines provided"}, status=400)

    run = BankReviewRun.objects.create(
        business=business,
        created_by=request.user,
        period_start=period_start,
        period_end=period_end,
        status=BankReviewRun.RunStatus.RUNNING,
    )

    try:
        result = run_bank_reconciliation_workflow(
            business_id=business.id,
            bank_lines=bank_lines,
            period_start=period_start,
            period_end=period_end,
            triggered_by_user_id=request.user.id,
            ai_companion_enabled=business.ai_companion_enabled,
        )

        high_risk_count = 0
        reference_to_pk: dict[str, int] = {}
        with transaction.atomic():
            for tx in result.transactions:
                audit_score = tx.audit_score
                if audit_score is not None and Decimal(audit_score) >= RISK_HIGH_THRESHOLD:
                    high_risk_count += 1
                created = BankTransactionReview.objects.create(
                    business=business,
                    run=run,
                    raw_payload=tx.raw_payload,
                    matched_journal_ids=tx.matched_journal_ids,
                    status=tx.status,
                    audit_flags=tx.audit_flags,
                    audit_score=tx.audit_score,
                    audit_explanations=tx.audit_explanations,
                    error_message=tx.error or "",
                )
                if tx.reference_id:
                    reference_to_pk[str(tx.reference_id)] = created.id

            run.status = BankReviewRun.RunStatus.COMPLETED
            run.metrics = {
                **result.metrics,
                "transactions_high_risk": high_risk_count or result.metrics.get("transactions_high_risk", 0),
            }
            run.trace_id = result.trace_id
            run.overall_risk_score = result.overall_risk_score
            mapped_rankings: list[dict] = []
            for item in result.llm_ranked_transactions:
                ref = str(item.get("transaction_id")) if isinstance(item, dict) else None
                if not ref:
                    continue
                pk = reference_to_pk.get(ref)
                if not pk:
                    continue
                mapped = {**item, "transaction_id": pk}
                mapped_rankings.append(mapped)
            run.llm_explanations = result.llm_explanations
            run.llm_ranked_transactions = mapped_rankings
            run.llm_suggested_followups = result.llm_suggested_followups
            run.save()
    except Exception as exc:  # pragma: no cover
        run.status = BankReviewRun.RunStatus.FAILED
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
            "transactions": [
                {
                    "id": tx.id,
                    "status": tx.status,
                    "raw_payload": tx.raw_payload,
                    "matched_journal_ids": tx.matched_journal_ids,
                    "audit_flags": tx.audit_flags,
                    "audit_score": str(tx.audit_score) if tx.audit_score is not None else None,
                    "audit_explanations": tx.audit_explanations,
                    "error_message": tx.error_message,
                    "risk_level": _risk_level(tx.audit_score),
                }
                for tx in run.transactions.all()
            ],
            "llm_explanations": run.llm_explanations,
            "llm_ranked_transactions": run.llm_ranked_transactions,
            "llm_suggested_followups": run.llm_suggested_followups,
            "companion_enabled": business.ai_companion_enabled,
        }
    )


@login_required
@require_GET
def api_bank_review_runs(request):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)
    runs = BankReviewRun.objects.filter(business=business).order_by("-created_at")[:50]
    data = [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat(),
            "status": r.status,
            "period_start": r.period_start.isoformat() if r.period_start else None,
            "period_end": r.period_end.isoformat() if r.period_end else None,
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
def api_bank_review_run_detail(request, run_id: int):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)
    run = BankReviewRun.objects.filter(business=business, pk=run_id).first()
    if not run:
        return JsonResponse({"error": "Run not found"}, status=404)
    return JsonResponse(
        {
            "id": run.id,
            "created_at": run.created_at.isoformat(),
            "status": run.status,
            "period_start": run.period_start.isoformat() if run.period_start else None,
            "period_end": run.period_end.isoformat() if run.period_end else None,
            "metrics": run.metrics,
            "overall_risk_score": str(run.overall_risk_score) if run.overall_risk_score is not None else None,
            "risk_level": _risk_level(run.overall_risk_score),
            "trace_id": run.trace_id,
            "transactions": [
                {
                    "id": tx.id,
                    "status": tx.status,
                    "raw_payload": tx.raw_payload,
                    "matched_journal_ids": tx.matched_journal_ids,
                    "audit_flags": tx.audit_flags,
                    "audit_score": str(tx.audit_score) if tx.audit_score is not None else None,
                    "audit_explanations": tx.audit_explanations,
                    "error_message": tx.error_message,
                    "risk_level": _risk_level(tx.audit_score),
                }
                for tx in run.transactions.all()
            ],
            "llm_explanations": run.llm_explanations,
            "llm_ranked_transactions": run.llm_ranked_transactions,
            "llm_suggested_followups": run.llm_suggested_followups,
            "companion_enabled": business.ai_companion_enabled,
        }
    )


@login_required
def bank_review_page(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")
    return render(
        request,
        "bank_review.html",
        {
            "business": business,
        },
    )
