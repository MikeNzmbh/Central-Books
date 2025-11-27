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
@require_POST
def api_bank_import(request: HttpRequest):
    """
    Import bank transactions from CSV.
    Expected body:
    {
        "bank_account_id": 1,
        "csv_content": "Date,Description,Amount\n2023-01-01,Test,-10.00",
        "mapping": {"date": "Date", "description": "Description", "amount": "Amount"}
    }
    """
    business, error = _ensure_business(request)
    if error:
        return error
    
    body = _parse_json(request)
    if not body:
        return _json_error("Invalid JSON")
        
    bank_account_id = body.get("bank_account_id")
    csv_content = body.get("csv_content")
    
    if not bank_account_id or not csv_content:
        return _json_error("bank_account_id and csv_content are required")
        
    bank_account = get_object_or_404(BankAccount, pk=bank_account_id, business=business)
    
    # Simple CSV parsing
    import csv
    import io
    from datetime import datetime
    
    reader = csv.DictReader(io.StringIO(csv_content))
    created_count = 0
    errors = []
    
    for row in reader:
        try:
            # Basic mapping - in real app, use the mapping dict
            date_str = row.get("Date")
            desc = row.get("Description")
            amount_str = row.get("Amount")
            
            if not date_str or not amount_str:
                continue
                
            # Parse date (assume ISO or simple format for now)
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                dt = datetime.strptime(date_str, "%m/%d/%Y").date()
                
            amount = Decimal(amount_str)
            
            # Generate hash for dedupe
            import hashlib
            raw = f"{dt.isoformat()}{amount}{desc}"
            normalized_hash = hashlib.sha256(raw.encode()).hexdigest()
            
            # Check duplicate
            if BankTransaction.objects.filter(
                bank_account=bank_account, 
                normalized_hash=normalized_hash
            ).exists():
                continue
                
            tx = BankTransaction.objects.create(
                bank_account=bank_account,
                date=dt,
                description=desc,
                amount=amount,
                normalized_hash=normalized_hash,
                status=BankTransaction.TransactionStatus.NEW
            )
            
            # Run suggestion engine
            BankMatchingEngine.apply_suggestions(tx)
            created_count += 1
            
        except Exception as e:
            errors.append(str(e))
            
    return JsonResponse({
        "created": created_count,
        "errors": errors
    })


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
        
        # Use stored suggestion data
        match_confidence = tx.suggestion_confidence
        engine_reason = tx.suggestion_reason
        
        # If no stored suggestion but status is NEW, try running engine (lazy load)
        if not tx.is_reconciled and tx.status == "NEW" and not match_confidence:
            BankMatchingEngine.apply_suggestions(tx)
            tx.refresh_from_db()
            match_confidence = tx.suggestion_confidence
            engine_reason = tx.suggestion_reason

        data.append(
            {
                "id": tx.id,
                "date": tx.date.isoformat(),
                "description": tx.description,
                "counterparty": counterparty,
                "amount": str(tx.amount),
                "currency": bank_account.business.currency,
                "status": status,
                "match_confidence": float(match_confidence) / 100.0 if match_confidence else None,
                "engine_reason": engine_reason,
                "match_type": "SUGGESTION" if match_confidence else None,
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
        if "rule" in m:
            rule = m["rule"]
            payload.append({
                "rule_id": rule.id,
                "reference": f"Rule: {rule.merchant_name}",
                "description": f"Apply rule: {rule.merchant_name}",
                "date": "",
                "amount": "",
                "confidence": str(m["confidence"]),
                "match_type": "RULE",
                "reason": m["reason"],
            })
        else:
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
    rule_id = body.get("rule_id")
    confidence = body.get("match_confidence") or 1.0
    
    if not bank_tx_id:
        return _json_error("bank_transaction_id is required")
        
    bank_tx = get_object_or_404(
        BankTransaction, pk=bank_tx_id, bank_account__business=business
    )

    if rule_id:
        # Apply rule
        rule = get_object_or_404(BankRule, pk=rule_id, business=business)
        # Create expense/transaction based on rule
        # For now, just mark as matched if we had logic to create entries from rules
        # This part requires more logic to actually create the journal entry from the rule
        # For this MVP, we'll assume rules just suggest categories and user must confirm creation
        pass
        
    if je_id:
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
    pattern = (body.get("pattern") or "").strip()
    category_id = body.get("category_id")
    account_id = body.get("account_id")
    auto_confirm = body.get("auto_confirm", False)
    
    if not merchant:
        return _json_error("merchant is required")

    account = None
    if account_id:
        account = get_object_or_404(Account, id=account_id, business=business)
        
    category = None
    if category_id:
        category = get_object_or_404(Category, id=category_id, business=business)

    rule, created = BankRule.objects.update_or_create(
        business=business,
        merchant_name=merchant,
        defaults={
            "pattern": pattern,
            "category": category,
            "account": account,
            "auto_confirm": auto_confirm,
            "created_by": request.user,
        },
    )
    
    return JsonResponse(
        {
            "id": rule.id,
            "created": created,
            "merchant": rule.merchant_name,
            "pattern": rule.pattern,
            "category_id": rule.category_id,
            "account_id": rule.account_id,
        }
    )

def _mark_reconciled(bank_tx: BankTransaction, journal_entry):
    ts = timezone.now()
    bank_tx.is_reconciled = True
    bank_tx.reconciled_at = ts
    bank_tx.status = BankTransaction.TransactionStatus.MATCHED
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
def api_reconciliation_config(request: HttpRequest):
    business, error = _ensure_business(request)
    if error:
        return error
    
    accounts = BankAccount.objects.filter(business=business).select_related("account")
    data = [
        {
            "id": str(acc.id),
            "name": acc.name,
            "bankLabel": acc.bank_name,
            "currency": acc.currency,
            "isDefault": False, # Logic for default?
        }
        for acc in accounts
    ]
    return JsonResponse(data, safe=False)

@login_required
def api_reconciliation_session(request: HttpRequest):
    business, error = _ensure_business(request)
    if error:
        return error

    if request.method == "GET":
        bank_account_id = request.GET.get("bank_account_id")
        period_id = request.GET.get("period_id") # Format: YYYY-MM
        
        if not bank_account_id:
            return _json_error("bank_account_id is required")

        bank_account = get_object_or_404(BankAccount, pk=bank_account_id, business=business)
        
        # Determine dates from period_id
        import calendar
        from datetime import date, datetime
        
        if not period_id:
            today = date.today()
            period_id = f"{today.year}-{today.month:02d}"
            
        try:
            year, month = map(int, period_id.split("-"))
            start_date = date(year, month, 1)
            _, last_day = calendar.monthrange(year, month)
            end_date = date(year, month, last_day)
        except ValueError:
            return _json_error("Invalid period_id format. Use YYYY-MM")

        # Find or create session
        session, created = ReconciliationSession.objects.get_or_create(
            business=business,
            bank_account=bank_account,
            statement_start_date=start_date,
            statement_end_date=end_date,
            defaults={
                "status": ReconciliationSession.Status.DRAFT
            }
        )
        
        # Calculate derived fields
        # Transactions in this session are those explicitly linked OR (in date range AND not linked to another session)
        # Actually, for simplicity, let's say we auto-link transactions in range to this session if they are not linked.
        # But the user might want to exclude them.
        # So, we query transactions that are EITHER:
        # 1. Linked to this session
        # 2. In date range AND reconciliation_session IS NULL
        
        # For the "cleared balance", we sum amounts of RECONCILED transactions linked to this session.
        # AND we should probably include previous sessions? 
        # Usually "cleared balance" = Opening Balance + Sum of Cleared Transactions in this period.
        
        cleared_txs = BankTransaction.objects.filter(
            reconciliation_session=session,
            is_reconciled=True
        )
        cleared_sum = cleared_txs.aggregate(total=models.Sum("amount"))["total"] or Decimal("0")
        
        cleared_balance = session.opening_balance + cleared_sum
        difference = session.closing_balance - cleared_balance
        
        total_txs_count = BankTransaction.objects.filter(
            models.Q(reconciliation_session=session) | 
            (models.Q(date__range=(start_date, end_date)) & models.Q(reconciliation_session__isnull=True) & models.Q(bank_account=bank_account))
        ).count()
        
        # Reconciled count in this session
        reconciled_count = BankTransaction.objects.filter(
            reconciliation_session=session,
            is_reconciled=True
        ).count()
        
        unreconciled_count = total_txs_count - reconciled_count
        reconciled_percent = (reconciled_count / total_txs_count * 100) if total_txs_count > 0 else 0
        
        # Generate period options (last 12 months)
        periods = []
        today = date.today()
        for i in range(12):
            d = date(today.year, today.month, 1)
            if i > 0:
                # Subtract months
                month = today.month - i
                year = today.year
                if month <= 0:
                    month += 12
                    year -= 1
                d = date(year, month, 1)
            
            pid = f"{d.year}-{d.month:02d}"
            label = d.strftime("%B %Y")
            
            # Check if locked (completed session exists)
            # We already have the session object for the requested period, check others if needed
            # For now, just mark current requested one
            is_locked = False
            if pid == period_id:
                is_locked = session.status == ReconciliationSession.Status.COMPLETED
            
            periods.append({
                "id": pid,
                "label": label,
                "startDate": d.isoformat(),
                "endDate": date(d.year, d.month, calendar.monthrange(d.year, d.month)[1]).isoformat(),
                "isCurrent": pid == f"{today.year}-{today.month:02d}",
                "isLocked": is_locked # In real app, query DB for status of each
            })

        return JsonResponse({
            "id": str(session.id),
            "status": session.status,
            "bankAccount": {
                "id": str(bank_account.id),
                "name": bank_account.name,
                "currency": bank_account.currency,
            },
            "period": {
                "id": period_id,
                "label": start_date.strftime("%B %Y"),
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "isCurrent": period_id == f"{today.year}-{today.month:02d}",
                "isLocked": session.status == ReconciliationSession.Status.COMPLETED,
            },
            "beginningBalance": float(session.opening_balance),
            "endingBalance": float(session.closing_balance),
            "clearedBalance": float(cleared_balance),
            "difference": float(difference),
            "reconciledPercent": float(reconciled_percent),
            "totalTransactions": total_txs_count,
            "unreconciledCount": unreconciled_count,
            "periods": periods
        })

    elif request.method == "POST":
        body = _parse_json(request)
        session_id = body.get("session_id")
        if not session_id:
            return _json_error("session_id is required")
            
        session = get_object_or_404(ReconciliationSession, pk=session_id, business=business)
        
        if "beginningBalance" in body:
            session.opening_balance = Decimal(str(body["beginningBalance"]))
        if "endingBalance" in body:
            session.closing_balance = Decimal(str(body["endingBalance"]))
            
        session.save()
        return JsonResponse({"status": "ok"})

    return _json_error("Method not allowed", 405)

@login_required
@require_POST
def api_reconciliation_complete(request: HttpRequest):
    business, error = _ensure_business(request)
    if error: return error
    
    body = _parse_json(request)
    session_id = body.get("session_id")
    session = get_object_or_404(ReconciliationSession, pk=session_id, business=business)
    
    # Recalculate difference to be safe
    cleared_txs = BankTransaction.objects.filter(reconciliation_session=session, is_reconciled=True)
    cleared_sum = cleared_txs.aggregate(total=models.Sum("amount"))["total"] or Decimal("0")
    cleared_balance = session.opening_balance + cleared_sum
    difference = session.closing_balance - cleared_balance
    
    if abs(difference) > Decimal("0.01"):
        return _json_error(f"Cannot complete: Difference is {difference}")
        
    session.status = ReconciliationSession.Status.COMPLETED
    session.completed_at = timezone.now()
    session.save()
    
    return JsonResponse({"status": "ok"})

@login_required
@require_POST
def api_reconciliation_toggle_include(request: HttpRequest):
    business, error = _ensure_business(request)
    if error: return error
    
    body = _parse_json(request)
    tx_id = body.get("transaction_id")
    session_id = body.get("session_id")
    included = body.get("included")
    
    tx = get_object_or_404(BankTransaction, pk=tx_id, bank_account__business=business)
    session = get_object_or_404(ReconciliationSession, pk=session_id, business=business)
    
    if included:
        tx.reconciliation_session = session
    else:
        if tx.reconciliation_session == session:
            tx.reconciliation_session = None
            
    tx.save(update_fields=["reconciliation_session"])
    return JsonResponse({"status": "ok"})

@login_required
@require_POST
def api_reconciliation_create_adjustment(request: HttpRequest):
    business, error = _ensure_business(request)
    if error: return error
    
    body = _parse_json(request)
    session_id = body.get("session_id")
    adj_type = body.get("type")
    amount = Decimal(str(body.get("amount") or 0))
    account_name = body.get("account_name") # e.g. "Bank Fee"
    
    session = get_object_or_404(ReconciliationSession, pk=session_id, business=business)
    
    # Create a BankTransaction for the adjustment
    # and immediately reconcile it against a new JournalEntry
    
    # 1. Create BankTransaction
    tx = BankTransaction.objects.create(
        bank_account=session.bank_account,
        date=session.statement_end_date, # Date of adjustment = end of period
        description=f"Adjustment: {adj_type}",
        amount=-amount if adj_type == "Bank fee" else amount, # Fee is negative
        status=BankTransaction.TransactionStatus.MATCHED,
        is_reconciled=True,
        reconciled_at=timezone.now(),
        reconciliation_session=session,
        allocated_amount=amount
    )
    
    # 2. Create JournalEntry
    je = JournalEntry.objects.create(
        business=business,
        date=session.statement_end_date,
        description=f"Adjustment: {adj_type}",
    )
    
    # 3. Create JournalLines
    # Bank line
    JournalLine.objects.create(
        journal_entry=je,
        account=session.bank_account.account,
        debit=Decimal("0") if tx.amount < 0 else tx.amount,
        credit=abs(tx.amount) if tx.amount < 0 else Decimal("0"),
        description=f"Adjustment: {adj_type}",
        is_reconciled=True,
        reconciled_at=timezone.now()
    )
    
    # Counterpart line (Expense/Income)
    # Find or create account based on name
    # This is simplified. In real app, pass account_id.
    # Mapping "Service charges" -> Expense
    
    account_type = Account.AccountType.EXPENSE
    if adj_type == "Interest income":
        account_type = Account.AccountType.INCOME
        
    counter_account, _ = Account.objects.get_or_create(
        business=business,
        name=account_name,
        defaults={
            "type": account_type,
            "code": "8000" if account_type == Account.AccountType.EXPENSE else "4000"
        }
    )
    
    JournalLine.objects.create(
        journal_entry=je,
        account=counter_account,
        debit=abs(tx.amount) if tx.amount < 0 else Decimal("0"),
        credit=Decimal("0") if tx.amount < 0 else tx.amount,
        description=f"Adjustment: {adj_type}"
    )
    
    je.check_balance()
    
    # 4. Link match
    BankReconciliationMatch.objects.create(
        bank_transaction=tx,
        journal_entry=je,
        match_type="ONE_TO_ONE",
        match_confidence=Decimal("1.00"),
        matched_amount=abs(tx.amount),
        reconciled_by=request.user
    )
    
    return JsonResponse({"status": "ok"})

