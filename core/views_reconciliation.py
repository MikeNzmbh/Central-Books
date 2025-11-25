from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from django.db import models
from core.utils import get_current_business
from core.services.reconciliation_engine import ReconciliationEngine
from core.services.bank_reconciliation import BankReconciliationService
from core.services.bank_matching import BankMatchingEngine
from core.reconciliation import recompute_bank_transaction_status
from core.models import (
    BankAccount,
    BankTransaction,
    JournalLine,
    BankReconciliationMatch,
    Account,
    BankRule,
)


@login_required
def reconcile_bank_account(request: HttpRequest, pk: int) -> HttpResponse:
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    bank_account = get_object_or_404(BankAccount, pk=pk, business=business)
    today = date.today()
    start_param = request.GET.get("start")
    end_param = request.GET.get("end")
    start_date = date.fromisoformat(start_param) if start_param else today.replace(day=1)
    end_date = date.fromisoformat(end_param) if end_param else today

    engine = ReconciliationEngine(business, bank_account)

    if request.method == "POST":
        bank_line_id = request.POST.get("bank_line_id")
        journal_line_id = request.POST.get("journal_line_id")
        bank_line = get_object_or_404(
            BankTransaction,
            pk=bank_line_id,
            bank_account=bank_account,
            bank_account__business=business,
        )
        journal_line = get_object_or_404(
            JournalLine,
            pk=journal_line_id,
            account=bank_account.account,
            journal_entry__business=business,
        )
        engine.reconcile(bank_line, [journal_line], session=None)
        if request.headers.get("Accept") == "application/json" or request.GET.get("format") == "json":
            return JsonResponse({"status": "ok"})
        return redirect("reconcile_bank_account", pk=bank_account.pk)

    bank_lines = engine.get_unreconciled_bank_lines(start_date, end_date)
    bank_lines_with_candidates = [
        {"obj": bl, "candidates": engine.get_candidate_matches(bl)} for bl in bank_lines
    ]

    context = {
        "business": business,
        "bank_account": bank_account,
        "period": {"start": start_date, "end": end_date},
        "bank_lines": bank_lines_with_candidates,
    }
    return render(request, "reconciliation/reconcile.html", context)


# --- API endpoints for React reconciliation page ---

def _json_error(message, status=400):
    return JsonResponse({"error": message}, status=status)


def _parse_json(request):
    import json

    try:
        return json.loads(request.body.decode("utf-8"))
    except Exception:
        return None


def _ensure_business(request):
    business = get_current_business(request.user)
    if business is None:
        return None, JsonResponse({"error": "No business selected"}, status=401)
    return business, None


def _mark_reconciled(bank_tx: BankTransaction, journal_entry):
    ts = timezone.now()
    bank_tx.is_reconciled = True
    bank_tx.reconciled_at = ts
    bank_tx.status = BankTransaction.TransactionStatus.MATCHED_SINGLE
    bank_tx.allocated_amount = abs(bank_tx.amount or 0)
    bank_tx.save(update_fields=["is_reconciled", "reconciled_at", "status", "allocated_amount"])

    bank_account = bank_tx.bank_account.account
    if bank_account:
        journal_lines = JournalLine.objects.filter(
            journal_entry=journal_entry, account=bank_account
        )
        for line in journal_lines:
            line.is_reconciled = True
            line.reconciled_at = ts
            line.save(update_fields=["is_reconciled", "reconciled_at"])


@login_required
@require_GET
def api_reconciliation_overview(request: HttpRequest, pk: int):
    business, error = _ensure_business(request)
    if error:
        return error

    bank_account = get_object_or_404(BankAccount, pk=pk, business=business)
    qs = BankTransaction.objects.filter(bank_account=bank_account).exclude(
        status=BankTransaction.TransactionStatus.EXCLUDED
    )
    total = qs.count()
    reconciled = qs.filter(is_reconciled=True).count()
    unreconciled = total - reconciled
    reconciled_amount = qs.filter(is_reconciled=True).aggregate(total=models.Sum("amount"))["total"] or 0
    unreconciled_amount = qs.filter(is_reconciled=False).aggregate(total=models.Sum("amount"))["total"] or 0
    progress = float((reconciled / total) * 100) if total else 0.0
    last4 = (bank_account.account and bank_account.account.code[-4:]) or ""
    return JsonResponse(
        {
            "bank_account": {
                "id": bank_account.id,
                "name": bank_account.name,
                "last4": last4,
                "currency": bank_account.business.currency or "USD",
                "is_live": True,
            },
            "period_label": "Current month",  # placeholder; adjust when statement logic exists
            "total_transactions": total,
            "reconciled": reconciled,
            "unreconciled": unreconciled,
            "total_reconciled_amount": str(reconciled_amount),
            "total_unreconciled_amount": str(unreconciled_amount),
            "progress_percent": progress,
            "cleared_balance": str(reconciled_amount),
            "statement_ending_balance": str(reconciled_amount + unreconciled_amount),
            "last_reconciled_at": None,
            "last_reconciled_by": None,
        }
    )


@login_required
@require_GET
def api_reconciliation_transactions(request: HttpRequest, pk: int):
    business, error = _ensure_business(request)
    if error:
        return error
    bank_account = get_object_or_404(BankAccount, pk=pk, business=business)
    status = request.GET.get("status", "ALL")
    qs = BankTransaction.objects.filter(bank_account=bank_account).order_by("-date", "-id")
    if status == "UNRECONCILED":
        qs = qs.filter(is_reconciled=False).exclude(
            status=BankTransaction.TransactionStatus.EXCLUDED
        )
    data = []
    for tx in qs:
        counterparty = tx.customer.name if tx.customer else (tx.supplier.name if tx.supplier else None)
        status = "RECONCILED" if tx.is_reconciled else tx.status
        match_confidence = None
        engine_reason = None
        top_match = None
        if not tx.is_reconciled:
            matches = BankMatchingEngine.find_matches(tx, limit=1)
            if matches:
                top_match = matches[0]
                match_confidence = float(top_match["confidence"])
                engine_reason = top_match["reason"]

        data.append(
            {
                "id": tx.id,
                "date": tx.date.isoformat(),
                "description": tx.description,
                "counterparty": counterparty,
                "amount": str(tx.amount),
                "currency": bank_account.business.currency,
                "status": status,
                "match_confidence": match_confidence,
                "engine_reason": engine_reason,
                "match_type": top_match["match_type"] if top_match else None,
                "is_soft_locked": False,
            }
        )
    return JsonResponse(data, safe=False)


@login_required
@require_GET
def api_reconciliation_matches(request: HttpRequest):
    business, error = _ensure_business(request)
    if error:
        return error
    tx_id = request.GET.get("transaction_id")
    if not tx_id:
        return _json_error("transaction_id is required")
    bank_tx = get_object_or_404(
        BankTransaction, pk=tx_id, bank_account__business=business
    )
    matches = BankMatchingEngine.find_matches(bank_tx)
    payload = []
    for m in matches:
        je = m["journal_entry"]
        payload.append(
            {
                "journal_entry_id": je.id,
                "reference": getattr(je, "description", "") or f"Journal #{je.id}",
                "description": je.description,
                "date": je.date.isoformat() if je.date else "",
                "amount": str(
                    je.lines.filter(account=bank_tx.bank_account.account)
                    .aggregate(total=models.Sum(models.F("debit") - models.F("credit")))["total"] or 0
                ),
                "confidence": str(m["confidence"]),
                "match_type": m["match_type"],
                "reason": m["reason"],
            }
        )
    return JsonResponse(payload, safe=False)


@login_required
@require_POST
def api_reconciliation_confirm_match(request: HttpRequest):
    business, error = _ensure_business(request)
    if error:
        return error
    body = _parse_json(request)
    if not body:
        return _json_error("Invalid JSON")
    bank_tx_id = body.get("bank_transaction_id")
    je_id = body.get("journal_entry_id")
    confidence = body.get("match_confidence") or 1.0
    if not bank_tx_id or not je_id:
        return _json_error("bank_transaction_id and journal_entry_id are required")
    bank_tx = get_object_or_404(
        BankTransaction, pk=bank_tx_id, bank_account__business=business
    )
    from core.models import JournalEntry
    journal_entry = get_object_or_404(JournalEntry, pk=je_id, business=business)

    BankReconciliationService.confirm_match(
        bank_transaction=bank_tx,
        journal_entry=journal_entry,
        match_confidence=Decimal(str(confidence)),
        user=request.user,
    )
    _mark_reconciled(bank_tx, journal_entry)
    recompute_bank_transaction_status(bank_tx)
    return JsonResponse({"status": "ok"})


@login_required
@require_POST
def api_reconciliation_create_split(request: HttpRequest):
    business, error = _ensure_business(request)
    if error:
        return error
    body = _parse_json(request)
    if not body:
        return _json_error("Invalid JSON")
    bank_tx_id = body.get("bank_transaction_id")
    splits = body.get("splits") or []
    if not bank_tx_id or not splits:
        return _json_error("bank_transaction_id and splits are required")
    bank_tx = get_object_or_404(
        BankTransaction, pk=bank_tx_id, bank_account__business=business
    )
    je, _match = BankReconciliationService.create_split_entry(
        bank_transaction=bank_tx,
        splits=splits,
        user=request.user,
        description=bank_tx.description,
    )
    _mark_reconciled(bank_tx, je)
    recompute_bank_transaction_status(bank_tx)
    return JsonResponse({"status": "ok"})


@login_required
@require_GET
def api_reconciliation_audit(request: HttpRequest):
    """
    Minimal audit trail endpoint. Surfaces reconciliation match history for a bank transaction.
    """
    tx_id = request.GET.get("transaction_id")
    if not tx_id:
        return _json_error("transaction_id is required")
    business, error = _ensure_business(request)
    if error:
        return error
    bank_tx = get_object_or_404(
        BankTransaction, pk=tx_id, bank_account__business=business
    )
    events = []
    matches = (
        BankReconciliationMatch.objects.filter(bank_transaction=bank_tx)
        .select_related("reconciled_by")
        .order_by("-created_at")
    )
    for m in matches:
        actor = None
        if m.reconciled_by:
            actor = m.reconciled_by.get_full_name() or m.reconciled_by.username
        events.append(
            {
                "id": str(m.id),
                "timestamp": (m.reconciled_at or m.created_at).isoformat(),
                "actor": actor or "System",
                "action": "Matched",
                "details": f"{m.match_type} · {round(float(m.match_confidence) * 100)}% → Journal #{m.journal_entry_id}",
            }
        )
    if not events and bank_tx.reconciled_at:
        events.append(
            {
                "id": f"tx-{bank_tx.id}",
                "timestamp": bank_tx.reconciled_at.isoformat(),
                "actor": "System",
                "action": "Reconciled",
                "details": "Marked as reconciled",
            }
        )
    return JsonResponse(events, safe=False)


@login_required
@require_GET
def api_ledger_search(request: HttpRequest):
    """
    Lightweight ledger search placeholder; returns journal entries by description match.
    """
    business, error = _ensure_business(request)
    if error:
        return error
    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse([], safe=False)
    from core.models import JournalEntry

    hits = (
        JournalEntry.objects.filter(business=business, description__icontains=query)
        .order_by("-date")[:10]
    )
    results = [
        {
            "journal_entry_id": je.id,
            "reference": je.description or f"Journal #{je.id}",
            "date": je.date.isoformat() if je.date else "",
            "amount": str(
                je.lines.filter(account__business=business).aggregate(
                    total=models.Sum(models.F("debit") - models.F("credit"))
                )["total"]
                or 0
            ),
        }
        for je in hits
    ]
    return JsonResponse(results, safe=False)


@login_required
@require_POST
def api_reconciliation_create_rule(request: HttpRequest):
    """
    Create or update a simple bank rule for a merchant/category combination.
    """
    business, error = _ensure_business(request)
    if error:
        return error
    body = _parse_json(request)
    if not body:
        return _json_error("Invalid JSON")
    merchant = (body.get("merchant") or "").strip()
    category_label = (body.get("category") or "").strip()
    account_id = body.get("account_id")
    if not merchant:
        return _json_error("merchant is required")

    account = None
    if account_id:
        account = get_object_or_404(Account, id=account_id, business=business)

    rule, created = BankRule.objects.get_or_create(
        business=business,
        merchant_name=merchant,
        defaults={
            "category_label": category_label,
            "account": account,
            "created_by": request.user,
        },
    )
    updated = False
    if category_label and rule.category_label != category_label:
        rule.category_label = category_label
        updated = True
    if account and rule.account_id != account.id:
        rule.account = account
        updated = True
    if updated:
        rule.save()
    return JsonResponse(
        {
            "id": rule.id,
            "created": created,
            "merchant": rule.merchant_name,
            "category": rule.category_label,
            "account_id": rule.account_id,
        }
    )
