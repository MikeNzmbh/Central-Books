import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .agentic_bank_review import BankInputLine, run_bank_reconciliation_workflow
from .anomaly_detection import apply_llm_explanations, bundle_anomalies
from .companion_issues import build_bank_review_issues, persist_companion_issues
from .models import BankReviewRun, BankTransactionReview, BankTransaction, BankAccount
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


def _fetch_bank_transactions_for_period(
    business, period_start: date | None, period_end: date | None
) -> list[BankInputLine]:
    """
    Auto-fetch bank transactions from the database for the given period.
    This allows users to run bank review without manual JSON input.
    """
    qs = BankTransaction.objects.filter(
        bank_account__business=business,
    ).exclude(
        status=BankTransaction.TransactionStatus.EXCLUDED
    ).order_by("date", "id")
    
    if period_start:
        qs = qs.filter(date__gte=period_start)
    if period_end:
        qs = qs.filter(date__lte=period_end)
    
    bank_lines: list[BankInputLine] = []
    for tx in qs:
        bank_lines.append(
            BankInputLine(
                date=tx.date,
                description=tx.description or "Bank transaction",
                amount=tx.amount,
                external_id=str(tx.id),  # Use DB ID as external reference
            )
        )
    return bank_lines


@csrf_exempt
@login_required
@require_POST
def api_bank_review_run(request):
    """
    Run a bank review for the specified period.
    
    Option B compliant: JSON-only responses, auto-fetches from BankTransaction table.
    
    Response statuses:
    - "completed": Review ran successfully
    - "no_data": No transactions found (HTTP 200, not an error)
    """
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    # Parse period
    try:
        period_start_raw = request.POST.get("period_start")
        period_end_raw = request.POST.get("period_end")
        period_start = date.fromisoformat(period_start_raw) if period_start_raw else None
        period_end = date.fromisoformat(period_end_raw) if period_end_raw else None
    except Exception:
        return JsonResponse({
            "error": "Invalid period format",
            "details": "Use YYYY-MM-DD format for dates."
        }, status=400)

    # Validate period: start must be <= end
    if period_start and period_end and period_start > period_end:
        return JsonResponse({
            "error": "Invalid period",
            "details": "Start date must be before or equal to end date."
        }, status=400)

    # DEV-ONLY: Manual lines override (hidden from normal UI)
    # This is for testing/debugging only. Normal users don't see this option.
    lines_payload = _parse_lines(request.POST.get("lines"))
    bank_lines: list[BankInputLine] = []
    using_manual_override = False
    
    if lines_payload:
        # Dev/test mode: parse manual lines
        using_manual_override = True
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

    # Default: Auto-fetch from BankTransaction table per bank account
    bank_accounts = BankAccount.objects.filter(business=business)
    banks_checked = bank_accounts.count()
    
    if not bank_lines:
        bank_lines = _fetch_bank_transactions_for_period(
            business, period_start, period_end
        )

    # Return no_data status (HTTP 200) if no transactions found
    if not bank_lines:
        return JsonResponse({
            "status": "no_data",
            "message": "No bank transactions found for this period. Import bank statements first.",
            "banks_checked": banks_checked,
            "period_start": period_start.isoformat() if period_start else None,
            "period_end": period_end.isoformat() if period_end else None,
        }, status=200)

    run = BankReviewRun.objects.create(
        business=business,
        created_by=request.user,
        period_start=period_start,
        period_end=period_end,
        status=BankReviewRun.RunStatus.RUNNING,
    )

    anomalies = []
    try:
        result = run_bank_reconciliation_workflow(
            business_id=business.id,
            bank_lines=bank_lines,
            period_start=period_start,
            period_end=period_end,
            triggered_by_user_id=request.user.id,
            ai_companion_enabled=business.ai_companion_enabled,
            user_name=request.user.first_name or None,
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
            if business.ai_companion_enabled:
                issues = build_bank_review_issues(run, run.trace_id)
                persist_companion_issues(business, issues, ai_companion_enabled=business.ai_companion_enabled, user_name=request.user.first_name or None)
        anomalies = bundle_anomalies(
            business,
            period_start=period_start or timezone.now().date() - timedelta(days=30),
            period_end=period_end or timezone.now().date(),
            as_of=period_end or timezone.now().date(),
        )
        anomalies = apply_llm_explanations(
            anomalies,
            ai_enabled=business.ai_companion_enabled,
            user_name=request.user.first_name or None,
        )
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
            "anomalies": [
                {
                    "code": a.code,
                    "surface": a.surface,
                    "impact_area": a.impact_area,
                    "severity": a.severity,
                    "explanation": a.explanation,
                    "task_code": a.task_code,
                    "explanation_source": a.explanation_source,
                    "linked_issue_id": a.linked_issue_id,
                }
                for a in anomalies
            ],
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
