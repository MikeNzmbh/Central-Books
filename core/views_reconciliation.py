from datetime import date, timedelta
import logging
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from django.db import models
from django.db.models import Q
from core.utils import get_current_business
from core.permissions import has_permission
from core.services.periods import resolve_comparison, resolve_period
from core.services.reconciliation_engine import ReconciliationEngine
from core.services.bank_reconciliation import (
    BankReconciliationService,
    RECONCILED_STATUSES,
    set_reconciled_state,
)
from core.services.bank_matching import BankMatchingEngine
from core.reconciliation import recompute_bank_transaction_status
from core.llm_reasoning import audit_high_risk_transaction
from core.models import (
    BankAccount,
    BankTransaction,
    JournalLine,
    BankReconciliationMatch,
    Account,
    BankRule,
    ReconciliationSession,
    JournalEntry,
)

logger = logging.getLogger(__name__)


def _require_reconciliation_permission(request, business, *, action="view"):
    """
    RBAC-based permission check for Reconciliation endpoints.
    
    Actions:
    - view: requires bank.view_transactions or reconciliation.view
    - reconcile: requires bank.reconcile
    - complete: requires reconciliation.complete_session
    - reset: requires reconciliation.reset_session
    """
    permission_map = {
        "view": "reconciliation.view",
        "reconcile": "bank.reconcile",
        "complete": "reconciliation.complete_session",
        "reset": "reconciliation.reset_session",
    }
    required_permission = permission_map.get(action, "reconciliation.view")
    if not has_permission(request.user, business, required_permission):
        return JsonResponse({"error": "Permission denied"}, status=403)
    return None

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

def _parse_period_id(period_id: str | None):
    """
    Accepts YYYY-MM and returns (start_date, end_date, label).
    Raises ValueError if invalid.
    """
    import calendar
    from datetime import date

    if not period_id:
        raise ValueError("period_id is required")
    year, month = map(int, period_id.split("-"))
    start_date = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    end_date = date(year, month, last_day)
    label = start_date.strftime("%B %Y")
    return start_date, end_date, label


def _period_options_for_account(bank_account: BankAccount) -> list[dict]:
    """
    Build period options based on existing bank transactions; fall back to empty list.
    """
    tx_dates = BankTransaction.objects.filter(bank_account=bank_account).values_list("date", flat=True)
    months = set()
    for d in tx_dates:
        if d:
            months.add((d.year, d.month))

    periods: list[dict] = []
    for year, month in sorted(months, reverse=True):
        pid = f"{year}-{month:02d}"
        start, end, label = _parse_period_id(pid)
        periods.append(
            {
                "id": pid,
                "label": label,
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "isCurrent": False,
                "isLocked": False,
            }
        )
    return periods


def _json_error(message, status=400, code: str | None = None):
    payload = {"detail": message, "error": message}
    if code:
        payload["code"] = code
    return JsonResponse(payload, status=status)


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


def _session_mutable_or_error(session: ReconciliationSession):
    if session.status == ReconciliationSession.Status.COMPLETED:
        return _json_error(
            "This reconciliation period is completed and cannot be modified. Reopen the period to make changes.",
            status=400,
            code="session_completed",
        )
    return None


def _assert_tx_in_session_period(bank_tx: BankTransaction, session: ReconciliationSession):
    if bank_tx.date and (
        bank_tx.date < session.statement_start_date or bank_tx.date > session.statement_end_date
    ):
        raise ValidationError("Transaction is out of period for this session.")


def _assert_entry_in_session_period(entry: JournalEntry, session: ReconciliationSession):
    if entry.date and (
        entry.date < session.statement_start_date or entry.date > session.statement_end_date
    ):
        raise ValidationError("Journal entry is out of period for this session.")


def _attach_transactions_to_session(session: ReconciliationSession):
    """
    Attach any orphan bank transactions in the session period to this session
    and normalize their reconciliation flags.
    """
    candidates = BankTransaction.objects.filter(
        bank_account=session.bank_account,
        date__gte=session.statement_start_date,
        date__lte=session.statement_end_date,
        reconciliation_session__isnull=True,
    ).order_by("date", "id")

    for tx in candidates:
        reconciled_flag = tx.status in RECONCILED_STATUSES
        set_reconciled_state(
            tx,
            reconciled=reconciled_flag,
            session=session,
            status=tx.status,
        )


def _session_for_tx(bank_tx: BankTransaction) -> ReconciliationSession:
    """
    Resolve or create the reconciliation session that should own this transaction.
    Prefers an existing reconciliation_session if already set.
    """
    if bank_tx.reconciliation_session_id:
        return bank_tx.reconciliation_session  # type: ignore[return-value]

    import calendar

    tx_date = bank_tx.date or timezone.localdate()
    start_date = tx_date.replace(day=1)
    _, last_day = calendar.monthrange(tx_date.year, tx_date.month)
    end_date = date(tx_date.year, tx_date.month, last_day)
    return _get_or_create_session(bank_tx.bank_account.business, bank_tx.bank_account, start_date, end_date)


# --- Reconciliation V1 (stable API for React UI) ---

def _decimal_from_payload(value, default: Decimal = Decimal("0.00")) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return default


def _quantize_money(value: Decimal) -> Decimal:
    return (value or Decimal("0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _decimal_to_str(value: Decimal) -> str:
    return format(_quantize_money(value), "f")


def _decimal_to_float(value: Decimal) -> float:
    return float(_quantize_money(value))


def _account_balance_as_of(account: Account | None, as_of: date) -> Decimal:
    """
    Compute account balance up to and including the provided date.
    Mirrors get_account_balance but constrained by date.
    """
    if not account or not as_of:
        return Decimal("0.00")

    agg = (
        JournalLine.objects.filter(
            account=account,
            journal_entry__business=account.business,
            journal_entry__is_void=False,
            journal_entry__date__lte=as_of,
        ).aggregate(
            debit_sum=models.Sum("debit"),
            credit_sum=models.Sum("credit"),
        )
    )
    debit = agg["debit_sum"] or Decimal("0.00")
    credit = agg["credit_sum"] or Decimal("0.00")

    if account.type in (Account.AccountType.ASSET, Account.AccountType.EXPENSE):
        return debit - credit
    return credit - debit


def _periods_for_account_v1(bank_account: BankAccount) -> list[dict]:
    """
    Return month buckets spanning available transactions.
    Falls back to current month when no activity exists.
    """
    import calendar

    tx_dates = list(
        BankTransaction.objects.filter(bank_account=bank_account).values_list("date", flat=True)
    )
    tx_dates = [d for d in tx_dates if d]

    def _period_payload(start: date) -> dict:
        _, last_day = calendar.monthrange(start.year, start.month)
        end = date(start.year, start.month, last_day)
        pid = f"{start.year}-{start.month:02d}"
        is_locked = ReconciliationSession.objects.filter(
            bank_account=bank_account,
            statement_start_date=start,
            statement_end_date=end,
            status=ReconciliationSession.Status.COMPLETED,
        ).exists()
        current_month = timezone.localdate().strftime("%Y-%m")
        return {
            "id": pid,
            "label": start.strftime("%B %Y"),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "is_current": pid == current_month,
            "is_locked": is_locked,
        }

    if not tx_dates:
        start = timezone.localdate().replace(day=1)
        return [_period_payload(start)]

    first = date(min(tx_dates).year, min(tx_dates).month, 1)
    last = date(max(tx_dates).year, max(tx_dates).month, 1)

    periods: list[dict] = []
    year, month = first.year, first.month
    while (year < last.year) or (year == last.year and month <= last.month):
        periods.append(_period_payload(date(year, month, 1)))
        month += 1
        if month > 12:
            month = 1
            year += 1

    # Most recent first for dropdown convenience
    periods.sort(key=lambda p: p["start_date"], reverse=True)
    return periods


def _parse_iso_date(value: str | None, field: str) -> date:
    if not value:
        raise ValueError(f"{field} is required")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Invalid {field} format. Use YYYY-MM-DD") from exc


def _simplified_status(tx: BankTransaction, session: ReconciliationSession | None = None) -> str:
    in_session = session is None or tx.reconciliation_session_id == getattr(session, "id", None)
    if tx.status == BankTransaction.TransactionStatus.EXCLUDED:
        return "excluded" if in_session else "new"
    if tx.status == BankTransaction.TransactionStatus.PARTIAL:
        return "partial" if in_session else "new"
    if in_session and tx.status in (
        BankTransaction.TransactionStatus.MATCHED,
        BankTransaction.TransactionStatus.MATCHED_SINGLE,
        BankTransaction.TransactionStatus.MATCHED_MULTI,
        BankTransaction.TransactionStatus.RECONCILED,
        BankTransaction.TransactionStatus.LEGACY_CREATED,
    ):
        return "matched"
    if in_session and tx.is_reconciled:
        return "matched"
    return "new"


def _serialize_tx(tx: BankTransaction, session: ReconciliationSession | None = None) -> dict:
    status = _simplified_status(tx, session)
    counterparty = None
    if tx.customer:
        counterparty = tx.customer.name
    elif tx.supplier:
        counterparty = tx.supplier.name

    in_session = session and tx.reconciliation_session_id == session.id
    rec_status = BankTransaction.RECO_STATUS_RECONCILED if (in_session and tx.status in RECONCILED_STATUSES) else BankTransaction.RECO_STATUS_UNRECONCILED

    latest_audit = None
    audits_rel = getattr(tx, "high_risk_audits", None)
    try:
        audit_obj = audits_rel.order_by("-created_at").first() if audits_rel is not None else None
    except Exception:
        audit_obj = None
    if audit_obj:
        latest_audit = {
            "verdict": audit_obj.verdict,
            "reasons": audit_obj.reasons or [],
            "created_at": audit_obj.created_at.isoformat(),
        }

    return {
        "id": tx.id,
        "date": tx.date.isoformat() if tx.date else "",
        "description": tx.description or "",
        "counterparty": counterparty,
        "amount": _decimal_to_str(tx.amount or Decimal("0.00")),
        "currency": tx.bank_account.business.currency or "USD",
        "status": status,
        "reconciliation_status": rec_status,
        "match_confidence": float(tx.suggestion_confidence) / 100.0 if tx.suggestion_confidence else None,
        "engine_reason": tx.suggestion_reason,
        "includedInSession": bool(in_session),
        "high_risk_audit": latest_audit,
    }


def _session_feed(session: ReconciliationSession) -> dict:
    bank_account = session.bank_account
    qs = (
        BankTransaction.objects.filter(
            bank_account=bank_account,
            date__gte=session.statement_start_date,
            date__lte=session.statement_end_date,
        )
        .filter(Q(reconciliation_session__isnull=True) | Q(reconciliation_session=session))
        .select_related("customer", "supplier")
        .prefetch_related("high_risk_audits")
        .order_by("-date", "-id")
    )

    buckets = {
        "new": [],
        "matched": [],
        "partial": [],
        "excluded": [],
    }

    for tx in qs:
        payload = _serialize_tx(tx, session=session)
        bucket = _simplified_status(tx, session=session)
        payload["ui_status"] = bucket.upper()
        in_session = tx.reconciliation_session_id == session.id
        payload["is_cleared"] = bool(
            in_session
            and tx.status in RECONCILED_STATUSES
            and tx.status != BankTransaction.TransactionStatus.EXCLUDED
        )
        buckets[bucket].append(payload)
    return buckets


def _session_transactions_queryset(session: ReconciliationSession):
    return BankTransaction.objects.filter(
        reconciliation_session=session,
    )


def _cleared_sum_for_session(session: ReconciliationSession) -> Decimal:
    cleared_qs = _session_transactions_queryset(session).filter(status__in=RECONCILED_STATUSES)
    total = Decimal("0.00")
    for tx in cleared_qs:
        signed_amount = tx.amount or Decimal("0.00")
        if tx.status == BankTransaction.TransactionStatus.PARTIAL and tx.allocated_amount is not None:
            signed_amount = tx.allocated_amount
            if tx.amount and tx.amount < 0:
                signed_amount = -signed_amount
        elif tx.status == BankTransaction.TransactionStatus.EXCLUDED:
            signed_amount = Decimal("0.00")
        total += signed_amount
    return _quantize_money(total)


def _get_or_create_session(business, bank_account: BankAccount, start_date: date, end_date: date):
    """
    Ensure a reconciliation session exists for a period.
    Seeds opening/statement balance from the ledger on first creation.
    """
    start_opening = _account_balance_as_of(bank_account.account, start_date - timedelta(days=1))
    end_ledger = _account_balance_as_of(bank_account.account, end_date)
    session, created = ReconciliationSession.objects.get_or_create(
        business=business,
        bank_account=bank_account,
        statement_start_date=start_date,
        statement_end_date=end_date,
        defaults={
            "opening_balance": start_opening,
            "closing_balance": end_ledger,
            "status": ReconciliationSession.Status.DRAFT,
        },
    )

    updates = []
    if created and session.closing_balance == Decimal("0.0000"):
        session.closing_balance = end_ledger
        updates.append("closing_balance")
    if session.opening_balance is None:
        session.opening_balance = start_opening
        updates.append("opening_balance")
    if updates:
        session.save(update_fields=updates)
    _attach_transactions_to_session(session)
    return session


def _session_payload(session: ReconciliationSession, include_periods: bool = False) -> dict:
    ledger_end = _account_balance_as_of(session.bank_account.account, session.statement_end_date)
    feed = _session_feed(session)

    session_txs = _session_transactions_queryset(session)
    total_txs = session_txs.count()
    reconciled_count = session_txs.filter(status__in=RECONCILED_STATUSES).count()
    excluded_count = session_txs.filter(status=BankTransaction.TransactionStatus.EXCLUDED).count()
    reconciled_percent = float(round((reconciled_count / total_txs * 100), 2)) if total_txs else 0.0
    unreconciled_count = total_txs - reconciled_count
    cleared_sum = _cleared_sum_for_session(session)
    cleared_balance = _quantize_money((session.opening_balance or Decimal("0.00")) + cleared_sum)
    difference = _quantize_money((session.closing_balance or Decimal("0.00")) - cleared_balance)

    payload = {
        "session": {
            "id": session.id,
            "bank_account": session.bank_account.id,
            "period_start": session.statement_start_date.isoformat(),
            "period_end": session.statement_end_date.isoformat(),
            "opening_balance": _decimal_to_str(session.opening_balance),
            "statement_ending_balance": _decimal_to_str(session.closing_balance),
            "ledger_ending_balance": _decimal_to_str(ledger_end),
            "cleared_balance": _decimal_to_str(cleared_balance),
            "difference": _decimal_to_str(difference),
            "status": session.status,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "reconciled_percent": reconciled_percent,
            "total_transactions": total_txs,
            "unreconciled_count": unreconciled_count,
            "reconciled_count": reconciled_count,
            "excluded_count": excluded_count,
        },
        "feed": feed,
        "bank_account": {
            "id": session.bank_account.id,
            "name": session.bank_account.name,
            "currency": session.bank_account.business.currency or "USD",
        },
        "period": {
            "start_date": session.statement_start_date.isoformat(),
            "end_date": session.statement_end_date.isoformat(),
        },
    }
    if include_periods:
        payload["periods"] = _periods_for_account_v1(session.bank_account)
    return payload


def _get_or_create_suspense_account(business) -> Account:
    """
    Get or create an 'Uncategorized' expense account for transactions without a category.
    This serves as a fallback when auto-creating journal entries.
    """
    account, created = Account.objects.get_or_create(
        business=business,
        code="9999",
        defaults={
            "name": "Uncategorized Transactions",
            "type": Account.AccountType.EXPENSE,
            "description": "Auto-created holding account for uncategorized bank transactions",
            "is_active": True,
        },
    )
    return account


def _create_simple_entry_for_tx(session: ReconciliationSession, bank_tx: BankTransaction) -> JournalEntry:
    """
    Auto-create a simple double-entry journal entry for a bank transaction.
    
    Logic:
    - Money OUT (negative amount):   Debit Expense/Category, Credit Bank
    - Money IN (positive amount):    Debit Bank, Credit Income/Category
    
    Falls back to Uncategorized account if no category is mapped.
    """
    business = session.business
    bank_account_ledger = session.bank_account.account
    
    if not bank_account_ledger:
        raise ValueError(f"Bank account {session.bank_account.name} has no linked ledger account")
    
    # Determine the offsetting account (category or suspense)
    offset_account = None
    if bank_tx.category and bank_tx.category.account:
        offset_account = bank_tx.category.account
    else:
        # Use suspense/uncategorized account
        offset_account = _get_or_create_suspense_account(business)
    
    # Create journal entry
    je = JournalEntry.objects.create(
        business=business,
        date=bank_tx.date or timezone.localdate(),
        description=bank_tx.description or "Bank transaction",
    )
    
    # Absolute amount for double-entry
    abs_amount = abs(bank_tx.amount or Decimal("0.00"))
    
    # Create journal lines based on transaction direction
    if bank_tx.amount < 0:
        # Money OUT: Debit expense/category, Credit bank
        JournalLine.objects.create(
            journal_entry=je,
            account=offset_account,
            debit=abs_amount,
            credit=Decimal("0.0000"),
            description=f"Auto-matched: {bank_tx.description or 'Bank transaction'}",
        )
        JournalLine.objects.create(
            journal_entry=je,
            account=bank_account_ledger,
            debit=Decimal("0.0000"),
            credit=abs_amount,
            description=f"Auto-matched: {bank_tx.description or 'Bank transaction'}",
        )
    else:
        # Money IN: Debit bank, Credit income/category
        JournalLine.objects.create(
            journal_entry=je,
            account=bank_account_ledger,
            debit=abs_amount,
            credit=Decimal("0.0000"),
            description=f"Auto-matched: {bank_tx.description or 'Bank transaction'}",
        )
        JournalLine.objects.create(
            journal_entry=je,
            account=offset_account,
            debit=Decimal("0.0000"),
            credit=abs_amount,
            description=f"Auto-matched: {bank_tx.description or 'Bank transaction'}",
        )
    
    return je


def _maybe_audit_high_risk_transaction(bank_tx: BankTransaction, *, is_bulk_adjustment: bool = False):
    """
    Trigger the high-risk critic for large or bulk transactions (no auto-posting).
    Skips when AI Companion is disabled or an audit already exists.
    """
    business = getattr(bank_tx.bank_account, "business", None)
    if not business or not getattr(business, "ai_companion_enabled", False):
        return None
    try:
        if bank_tx.high_risk_audits.exists():  # type: ignore[attr-defined]
            return None
    except Exception:
        # If relation missing, fail open (no audit)
        return None

    linked_accounts = []
    if bank_tx.bank_account and bank_tx.bank_account.account:
        linked_accounts.append(bank_tx.bank_account.account.code)
    if bank_tx.category and bank_tx.category.account:
        linked_accounts.append(bank_tx.category.account.code)

    amount_val = abs(bank_tx.amount or Decimal("0"))
    if amount_val <= Decimal("5000") and not is_bulk_adjustment:
        return None

    return audit_high_risk_transaction(
        amount=float(amount_val),
        currency=business.currency or "USD",
        accounts=linked_accounts,
        memo=bank_tx.description or "",
        source="bank_reconciliation",
        is_bulk_adjustment=is_bulk_adjustment,
        attach_to=bank_tx,
    )


def _apply_match(session: ReconciliationSession, bank_tx: BankTransaction, journal_entry: JournalEntry, user):
    """
    Link a bank transaction to a journal entry and mark both sides reconciled.
    """
    _assert_tx_in_session_period(bank_tx, session)
    _assert_entry_in_session_period(journal_entry, session)

    # Clear existing matches to avoid duplicates
    BankReconciliationMatch.objects.filter(bank_transaction=bank_tx).delete()
    ts = timezone.now()
    match = BankReconciliationMatch.objects.create(
        bank_transaction=bank_tx,
        journal_entry=journal_entry,
        match_type="ONE_TO_ONE",
        match_confidence=Decimal("1.00"),
        matched_amount=abs(bank_tx.amount or Decimal("0.00")),
        reconciled_by=user,
    )

    bank_tx.allocated_amount = abs(bank_tx.amount or Decimal("0.00"))
    bank_tx.posted_journal_entry = journal_entry
    bank_tx.save(update_fields=["allocated_amount", "posted_journal_entry"])
    set_reconciled_state(
        bank_tx,
        reconciled=True,
        session=session,
        status=BankTransaction.TransactionStatus.MATCHED_SINGLE,
        reconciled_at=ts,
    )

    if bank_tx.bank_account.account:
        JournalLine.objects.filter(
            journal_entry=journal_entry, account=bank_tx.bank_account.account
        ).update(
            is_reconciled=True,
            reconciled_at=ts,
            reconciliation_session=session,
        )
    _maybe_audit_high_risk_transaction(bank_tx)
    return match


@login_required
@require_GET
def api_reconciliation_accounts_v1(request: HttpRequest):
    business, error = _ensure_business(request)
    if error:
        return error

    accounts = (
        BankAccount.objects.filter(business=business, is_active=True)
        .select_related("account")
        .order_by("name")
    )
    data = [
        {"id": acc.id, "name": acc.name, "currency": business.currency or "USD"}
        for acc in accounts
    ]
    return JsonResponse(data, safe=False)


@login_required
@require_GET
def api_reconciliation_periods_v1(request: HttpRequest, account_id: int):
    business, error = _ensure_business(request)
    if error:
        return error

    bank_account = get_object_or_404(BankAccount, pk=account_id, business=business)
    periods = _periods_for_account_v1(bank_account)
    return JsonResponse(periods, safe=False)


@login_required
@require_GET
def api_reconciliation_session_v1(request: HttpRequest):
    business, error = _ensure_business(request)
    if error:
        return error

    account_id = request.GET.get("account")
    start_raw = request.GET.get("start")
    end_raw = request.GET.get("end")
    if not account_id:
        return _json_error("account is required")

    bank_account = get_object_or_404(BankAccount, pk=account_id, business=business)

    if not start_raw or not end_raw:
        import calendar

        today = timezone.localdate()
        start_date = today.replace(day=1)
        _, last_day = calendar.monthrange(today.year, today.month)
        end_date = date(today.year, today.month, last_day)
    else:
        try:
            start_date = _parse_iso_date(start_raw, "start")
            end_date = _parse_iso_date(end_raw, "end")
        except ValueError as exc:
            return _json_error(str(exc))
    if start_date > end_date:
        return _json_error("start must be on or before end")

    session = _get_or_create_session(business, bank_account, start_date, end_date)
    return JsonResponse(_session_payload(session, include_periods=True))


@login_required
@require_POST
def api_reconciliation_set_statement_balance_v1(request: HttpRequest, session_id: int):
    business, error = _ensure_business(request)
    if error:
        return error

    session = get_object_or_404(ReconciliationSession, pk=session_id, business=business)
    if (resp := _session_mutable_or_error(session)):
        return resp
    body = _parse_json(request) or {}
    opening = body.get("opening_balance")
    statement = body.get("statement_ending_balance")

    if opening is None and statement is None:
        return _json_error("opening_balance or statement_ending_balance is required")

    updates = []
    if opening is not None:
        session.opening_balance = _decimal_from_payload(opening, session.opening_balance)
        updates.append("opening_balance")
    if statement is not None:
        session.closing_balance = _decimal_from_payload(statement, session.closing_balance)
        updates.append("closing_balance")
    if updates:
        session.save(update_fields=updates)

    return JsonResponse(_session_payload(session))


@login_required
@require_POST
def api_reconciliation_match_v1(request: HttpRequest, session_id: int):
    business, error = _ensure_business(request)
    if error:
        return error

    session = get_object_or_404(ReconciliationSession, pk=session_id, business=business)
    if (resp := _session_mutable_or_error(session)):
        return resp
    body = _parse_json(request) or {}
    tx_id = body.get("transaction_id")
    if not tx_id:
        return _json_error("transaction_id is required")

    bank_tx = get_object_or_404(BankTransaction, pk=tx_id, bank_account=session.bank_account)
    if bank_tx.reconciliation_session_id not in (None, session.id):
        return _json_error("Transaction belongs to another reconciliation session.")
    if bank_tx.date and (
        bank_tx.date < session.statement_start_date or bank_tx.date > session.statement_end_date
    ):
        return _json_error("Transaction is outside of the session period")

    journal_entry_id = body.get("journal_entry_id")
    if not journal_entry_id:
        return _json_error(
            "No existing transaction found to match. Create an invoice, expense, or journal entry first, or use 'Add as new' instead."
        )

    journal_entry = get_object_or_404(JournalEntry, pk=journal_entry_id, business=business)

    try:
        _apply_match(session, bank_tx, journal_entry, request.user)
    except ValidationError as exc:
        return _json_error(str(exc))
    return JsonResponse(_session_payload(session))


@login_required
@require_POST
def api_reconciliation_unmatch_v1(request: HttpRequest, session_id: int):
    business, error = _ensure_business(request)
    if error:
        return error

    session = get_object_or_404(ReconciliationSession, pk=session_id, business=business)
    if (resp := _session_mutable_or_error(session)):
        return resp
    body = _parse_json(request) or {}
    tx_id = body.get("transaction_id")
    if not tx_id:
        return _json_error("transaction_id is required")

    bank_tx = get_object_or_404(BankTransaction, pk=tx_id, bank_account=session.bank_account)
    if bank_tx.reconciliation_session_id not in (None, session.id):
        return _json_error("Transaction belongs to another reconciliation session.")

    match_entries = list(
        BankReconciliationMatch.objects.filter(bank_transaction=bank_tx).values_list(
            "journal_entry_id", flat=True
        )
    )
    BankReconciliationMatch.objects.filter(bank_transaction=bank_tx).delete()

    bank_tx.allocated_amount = Decimal("0.0000")
    bank_tx.posted_journal_entry = None
    bank_tx.save(update_fields=["allocated_amount", "posted_journal_entry"])
    try:
        set_reconciled_state(
            bank_tx,
            reconciled=False,
            session=session,
            status=BankTransaction.TransactionStatus.NEW,
        )
    except ValidationError as exc:
        return _json_error(str(exc))

    if bank_tx.bank_account.account and match_entries:
        JournalLine.objects.filter(
            journal_entry_id__in=match_entries, account=bank_tx.bank_account.account
        ).update(
            is_reconciled=False,
            reconciled_at=None,
            reconciliation_session=None,
        )

    return JsonResponse(_session_payload(session))


@login_required
@require_POST
def api_reconciliation_exclude_v1(request: HttpRequest, session_id: int):
    business, error = _ensure_business(request)
    if error:
        return error

    session = get_object_or_404(ReconciliationSession, pk=session_id, business=business)
    if (resp := _session_mutable_or_error(session)):
        return resp
    body = _parse_json(request) or {}
    tx_id = body.get("transaction_id")
    excluded = body.get("excluded", True)
    if not tx_id:
        return _json_error("transaction_id is required")

    bank_tx = get_object_or_404(BankTransaction, pk=tx_id, bank_account=session.bank_account)
    try:
        _assert_tx_in_session_period(bank_tx, session)
    except ValidationError as exc:
        return _json_error(str(exc))
    if bank_tx.reconciliation_session_id not in (None, session.id):
        return _json_error("Transaction belongs to another reconciliation session.")
    if excluded:
        BankReconciliationMatch.objects.filter(bank_transaction=bank_tx).delete()
        bank_tx.allocated_amount = Decimal("0.0000")
        bank_tx.posted_journal_entry = None
        bank_tx.save(update_fields=["allocated_amount", "posted_journal_entry"])
        try:
            set_reconciled_state(
                bank_tx,
                reconciled=True,
                session=session,
                status=BankTransaction.TransactionStatus.EXCLUDED,
            )
        except ValidationError as exc:
            return _json_error(str(exc))
    else:
        if bank_tx.status == BankTransaction.TransactionStatus.EXCLUDED:
            bank_tx.status = BankTransaction.TransactionStatus.NEW
        bank_tx.save(update_fields=["status"])
        try:
            set_reconciled_state(
                bank_tx,
                reconciled=False,
                session=session,
                status=bank_tx.status,
            )
        except ValidationError as exc:
            return _json_error(str(exc))

    return JsonResponse(_session_payload(session))


@login_required
@require_GET
def api_reconciliation_session_report(request: HttpRequest, session_id: int):
    """
    Detail endpoint used by the print view to load a reconciliation session by id.
    """
    business, error = _ensure_business(request)
    if error:
        return error

    session = get_object_or_404(
        ReconciliationSession.objects.select_related("bank_account", "bank_account__business"),
        id=session_id,
        business=business,
    )

    period_key = request.GET.get("period_preset") or request.GET.get("period") or "custom"
    start_param = request.GET.get("start_date") or session.statement_start_date
    end_param = request.GET.get("end_date") or session.statement_end_date
    compare_to = request.GET.get("compare_to") or "none"
    period_info = resolve_period(period_key, start_param, end_param, session.bank_account.business.fiscal_year_start)
    comparison_info = resolve_comparison(period_info["start"], period_info["end"], compare_to)

    payload = _session_payload(session)
    feed = payload.get("feed", {})
    flattened = (feed.get("new", []) or []) + (feed.get("matched", []) or []) + (feed.get("partial", []) or []) + (feed.get("excluded", []) or [])

    def _coerce_feed_date(raw):
        if isinstance(raw, date):
            return raw
        try:
            return date.fromisoformat(str(raw))
        except Exception:
            try:
                return timezone.datetime.fromisoformat(str(raw)).date()  # type: ignore[attr-defined]
            except Exception:
                return None

    filtered_feed = []
    for item in flattened:
        tx_date = _coerce_feed_date(item.get("date"))
        if tx_date and (tx_date < period_info["start"] or tx_date > period_info["end"]):
            continue
        filtered_feed.append(item)

    response = {
        "bank_account": payload.get("bank_account", {}),
        "period": {
            "label": period_info.get("label"),
            "start": period_info["start"].isoformat(),
            "end": period_info["end"].isoformat(),
            "preset": period_info.get("preset"),
        },
        "comparison": {
            "label": comparison_info.get("compare_label"),
            "start": comparison_info.get("compare_start"),
            "end": comparison_info.get("compare_end"),
            "compare_to": comparison_info.get("compare_to"),
        },
        "opening_balance": float(session.opening_balance or 0),
        "statement_ending_balance": float(session.closing_balance or 0),
        "ledger_ending_balance": float(payload.get("session", {}).get("ledger_ending_balance") or 0),
        "cleared_balance": float(payload.get("session", {}).get("cleared_balance") or 0),
        "difference": float(payload.get("session", {}).get("difference") or 0),
        "unreconciled_count": payload.get("session", {}).get("unreconciled_count", 0),
        "reconciled_count": payload.get("session", {}).get("reconciled_count", 0),
        "total_transactions": payload.get("session", {}).get("total_transactions", 0),
        "feed": [
            {
                "id": item.get("id"),
                "date": item.get("date"),
                "description": item.get("description"),
                "amount": float(item.get("amount") or 0),
                "status": item.get("status"),
                "reconciliation_status": item.get("reconciliation_status"),
            }
            for item in filtered_feed
        ],
    }
    return JsonResponse(response)


def _validate_session_ready_for_completion(session: ReconciliationSession):
    payload = _session_payload(session, include_periods=True)
    session_data = payload.get("session", {})

    difference = Decimal(str(session_data.get("difference") or "0"))
    if abs(difference) > Decimal("0.01"):
        return None, _json_error(
            "Difference must be zero before completing this period.",
            code="difference_not_zero",
        )

    unreconciled_count = int(session_data.get("unreconciled_count") or 0)
    if unreconciled_count > 0:
        return None, _json_error(
            "You still have unreconciled transactions in this period.",
            code="unreconciled_transactions_remaining",
        )

    return payload, None


def _complete_session(session: ReconciliationSession):
    payload, error = _validate_session_ready_for_completion(session)
    if error:
        return None, error

    session.status = ReconciliationSession.Status.COMPLETED
    session.completed_at = timezone.now()
    session.save(update_fields=["status", "completed_at"])

    # Recompute payload to reflect new status and ensure totals are fresh
    return _session_payload(session, include_periods=True), None


@login_required
@require_POST
def api_reconciliation_complete_v1(request: HttpRequest, session_id: int):
    business, error = _ensure_business(request)
    if error:
        return error
    
    # Completing a session requires complete_session permission
    forbidden = _require_reconciliation_permission(request, business, action="complete")
    if forbidden:
        return forbidden

    session = get_object_or_404(ReconciliationSession, pk=session_id, business=business)
    payload, error = _complete_session(session)
    if error:
        return error
    return JsonResponse(payload)


@login_required
@require_POST
def api_reconciliation_reopen_session(request: HttpRequest, session_id: int):
    business, error = _ensure_business(request)
    if error:
        return error

    # Reopening a completed session is a staff-only recovery action.
    if not request.user.is_staff:
        return JsonResponse({"error": "Permission denied"}, status=403)
    
    # Reopening a session requires reset_session permission (high privilege)
    forbidden = _require_reconciliation_permission(request, business, action="reset")
    if forbidden:
        return forbidden

    session = get_object_or_404(ReconciliationSession, pk=session_id, business=business)
    if session.status != ReconciliationSession.Status.COMPLETED:
        return _json_error("Only completed sessions can be reopened.", status=400, code="invalid_state")

    session.status = ReconciliationSession.Status.IN_PROGRESS
    session.completed_at = None
    session.save(update_fields=["status", "completed_at"])

    logger.info(
        "reconciliation.session_reopened",
        extra={"session_id": session.id, "user_id": request.user.id},
    )

    return JsonResponse(_session_payload(session, include_periods=True))


@login_required
@require_POST
def api_reconciliation_delete_session(request: HttpRequest, session_id: int):
    """
    Delete a reconciliation session and reset all associated transactions.
    This allows the user to start over for a period.
    """
    business, error = _ensure_business(request)
    if error:
        return error
    
    # Deleting a session requires reset_session permission (high privilege)
    forbidden = _require_reconciliation_permission(request, business, action="reset")
    if forbidden:
        return forbidden

    session = get_object_or_404(ReconciliationSession, pk=session_id, business=business)
    
    # Reset all transactions associated with this session
    # This unlinks them from the session and resets their status to NEW
    affected_txs = BankTransaction.objects.filter(reconciliation_session=session)
    for tx in affected_txs:
        tx.reconciliation_session = None
        tx.is_reconciled = False
        tx.reconciled_at = None
        tx.status = BankTransaction.TransactionStatus.NEW
        tx.reconciliation_status = BankTransaction.RECO_STATUS_UNRECONCILED
        tx.allocated_amount = Decimal("0.00")
        tx.save(update_fields=[
            "reconciliation_session",
            "is_reconciled",
            "reconciled_at",
            "status",
            "reconciliation_status",
            "allocated_amount",
        ])
    
    # Delete matches associated with transactions in this period
    BankReconciliationMatch.objects.filter(
        bank_transaction__bank_account=session.bank_account,
        bank_transaction__date__gte=session.statement_start_date,
        bank_transaction__date__lte=session.statement_end_date,
    ).delete()
    
    # Also reset journal line reconciliation flags
    JournalLine.objects.filter(reconciliation_session=session).update(
        is_reconciled=False,
        reconciled_at=None,
        reconciliation_session=None,
    )
    
    # Store period info before deleting
    bank_account_id = session.bank_account_id
    period_start = session.statement_start_date.isoformat()
    period_end = session.statement_end_date.isoformat()
    
    # Delete the session
    session.delete()

    logger.info(
        "reconciliation.session_deleted",
        extra={
            "session_id": session_id,
            "bank_account_id": bank_account_id,
            "user_id": request.user.id,
        },
    )

    return JsonResponse({
        "ok": True,
        "message": "Session deleted. You can now start a fresh reconciliation for this period.",
        "bank_account_id": bank_account_id,
        "period_start": period_start,
        "period_end": period_end,
    })

def _mark_reconciled(bank_tx: BankTransaction, journal_entry, session: ReconciliationSession | None = None):
    ts = timezone.now()
    target_session = session or _session_for_tx(bank_tx)
    bank_tx.allocated_amount = abs(bank_tx.amount or 0)
    bank_tx.save(update_fields=["allocated_amount"])
    set_reconciled_state(
        bank_tx,
        reconciled=True,
        session=target_session,
        status=BankTransaction.TransactionStatus.MATCHED_SINGLE,
        reconciled_at=ts,
    )

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
        try:
            # Safely get counterparty name with null checks
            counterparty = None
            if tx.customer:
                counterparty = tx.customer.name
            elif tx.supplier:
                counterparty = tx.supplier.name
            
            status = "RECONCILED" if tx.is_reconciled else tx.status
            
            # Use stored suggestion data
            match_confidence = tx.suggestion_confidence
            engine_reason = tx.suggestion_reason
            
            # If no stored suggestion but status is NEW, try running engine (lazy load)
            if not tx.is_reconciled and tx.status == "NEW" and not match_confidence:
                try:
                    BankMatchingEngine.apply_suggestions(tx)
                    tx.refresh_from_db()
                    match_confidence = tx.suggestion_confidence
                    engine_reason = tx.suggestion_reason
                except Exception:
                    # If suggestion engine fails, continue without suggestions
                    pass

            data.append(
                {
                    "id": tx.id,
                    "date": tx.date.isoformat() if tx.date else "",
                    "description": tx.description or "",
                    "counterparty": counterparty,
                    "amount": str(tx.amount),
                    "currency": bank_account.business.currency or "USD",
                    "status": status,
                    "match_confidence": float(match_confidence) / 100.0 if match_confidence else None,
                    "engine_reason": engine_reason,
                    "match_type": "SUGGESTION" if match_confidence else None,
                    "is_soft_locked": False,
                }
            )
        except Exception as e:
            # Log error but continue processing other transactions
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error serializing transaction {tx.id}: {e}", exc_info=True)
            continue
            
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
        
    if not je_id:
        return _json_error(
            "No existing transaction found to match. Create an invoice, expense, or journal entry first, or use 'Add as new' instead."
        )

    from core.models import JournalEntry
    journal_entry = get_object_or_404(JournalEntry, pk=je_id, business=business)

    session = bank_tx.reconciliation_session or _session_for_tx(bank_tx)
    if (resp := _session_mutable_or_error(session)):
        return resp
    try:
        _assert_tx_in_session_period(bank_tx, session)
        _assert_entry_in_session_period(journal_entry, session)
        BankReconciliationService.confirm_match(
            bank_transaction=bank_tx,
            journal_entry=journal_entry,
            match_confidence=Decimal(str(confidence)),
            user=request.user,
            session=session,
        )
        _mark_reconciled(bank_tx, journal_entry, session=session)
        recompute_bank_transaction_status(bank_tx)
    except ValidationError as exc:
        return _json_error(str(exc))

    return JsonResponse({"status": "ok"})


@login_required
@require_POST
def api_reconciliation_add_as_new(request: HttpRequest):
    """
    Create a new journal entry from a bank transaction and mark it as reconciled.
    This is used when there's no existing invoice/expense to match against.
    """
    business, error = _ensure_business(request)
    if error:
        return error
    
    body = _parse_json(request)
    if not body:
        return _json_error("Invalid JSON")
    
    bank_tx_id = body.get("bank_transaction_id")
    session_id = body.get("session_id")
    is_bulk_adjustment = bool(body.get("is_bulk_adjustment", False))
    
    if not bank_tx_id:
        return _json_error("bank_transaction_id is required")
    
    bank_tx = get_object_or_404(
        BankTransaction, pk=bank_tx_id, bank_account__business=business
    )
    
    session = None
    if session_id:
        session = get_object_or_404(ReconciliationSession, pk=session_id, business=business)
    else:
        session = _session_for_tx(bank_tx)

    if (resp := _session_mutable_or_error(session)):
        return resp

    try:
        _assert_tx_in_session_period(bank_tx, session)
        je = _create_simple_entry_for_tx(session, bank_tx) if session else _create_simple_entry_for_tx_no_session(business, bank_tx)
        _mark_reconciled(bank_tx, je, session=session)
        _maybe_audit_high_risk_transaction(bank_tx, is_bulk_adjustment=is_bulk_adjustment)
        recompute_bank_transaction_status(bank_tx)
        return JsonResponse({
            "status": "ok",
            "journal_entry_id": je.id,
            "transaction_id": bank_tx.id,
        })
    except (ValueError, ValidationError) as e:
        return _json_error(str(e))


def _create_simple_entry_for_tx_no_session(business, bank_tx: BankTransaction) -> JournalEntry:
    """
    Create a simple journal entry for a bank transaction when no session is available.
    """
    bank_account_ledger = bank_tx.bank_account.account
    
    if not bank_account_ledger:
        raise ValueError(f"Bank account {bank_tx.bank_account.name} has no linked ledger account")
    
    # Determine the offsetting account
    offset_account = None
    if bank_tx.category and bank_tx.category.account:
        offset_account = bank_tx.category.account
    else:
        offset_account = _get_or_create_suspense_account(business)
    
    # Create journal entry
    je = JournalEntry.objects.create(
        business=business,
        date=bank_tx.date or timezone.localdate(),
        description=bank_tx.description or "Bank transaction",
    )
    
    abs_amount = abs(bank_tx.amount or Decimal("0.00"))
    
    # Create journal lines
    if bank_tx.amount < 0:
        JournalLine.objects.create(
            journal_entry=je,
            account=offset_account,
            debit=abs_amount,
            credit=Decimal("0.0000"),
            description=f"Auto-added: {bank_tx.description or 'Bank transaction'}",
        )
        JournalLine.objects.create(
            journal_entry=je,
            account=bank_account_ledger,
            debit=Decimal("0.0000"),
            credit=abs_amount,
            description=f"Auto-added: {bank_tx.description or 'Bank transaction'}",
        )
    else:
        JournalLine.objects.create(
            journal_entry=je,
            account=bank_account_ledger,
            debit=abs_amount,
            credit=Decimal("0.0000"),
            description=f"Auto-added: {bank_tx.description or 'Bank transaction'}",
        )
        JournalLine.objects.create(
            journal_entry=je,
            account=offset_account,
            debit=Decimal("0.0000"),
            credit=abs_amount,
            description=f"Auto-added: {bank_tx.description or 'Bank transaction'}",
        )
    
    return je


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
    session = bank_tx.reconciliation_session or _session_for_tx(bank_tx)
    if (resp := _session_mutable_or_error(session)):
        return resp
    try:
        _assert_tx_in_session_period(bank_tx, session)
        je, _match = BankReconciliationService.create_split_entry(
            bank_transaction=bank_tx,
            splits=splits,
            user=request.user,
            description=bank_tx.description,
            session=session,
        )
        _mark_reconciled(bank_tx, je, session=session)
        recompute_bank_transaction_status(bank_tx)
    except ValidationError as exc:
        return _json_error(str(exc))
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

@login_required
@require_GET
def api_reconciliation_config(request: HttpRequest):
    # LEGACY: keep for backward compatibility with older clients. Prefer v1 endpoints above.
    business, error = _ensure_business(request)
    if error:
        return error
    
    accounts = BankAccount.objects.filter(
        business=business,
        is_active=True,
    ).select_related("account")

    data = [
        {
            "id": str(acc.id),
            "name": acc.name,
            "bankLabel": acc.bank_name,
            "currency": business.currency,
            "isDefault": False,  # Placeholder for future default logic
        }
        for acc in accounts
    ]

    # Return plain list for compatibility; include metadata headers if needed
    if request.GET.get("include_meta") == "1":
        payload = {
            "accounts": data,
            "can_reconcile": bool(data),
            "reason": None if data else "no_bank_accounts",
        }
        return JsonResponse(payload)

    return JsonResponse(data, safe=False)

@login_required
def api_reconciliation_session(request: HttpRequest):
    # LEGACY: session endpoint used by early SPA. New flows should use v1 session APIs above.
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
                "currency": bank_account.business.currency,
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
@require_GET
def api_reconciliation_periods(request: HttpRequest):
    """
    Returns available statement periods for a bank account based on existing transactions.
    """
    business, error = _ensure_business(request)
    if error:
        return error

    bank_account_id = request.GET.get("bank_account_id")
    if not bank_account_id:
        return _json_error("bank_account_id is required")

    bank_account = get_object_or_404(BankAccount, pk=bank_account_id, business=business)
    periods = _period_options_for_account(bank_account)
    return JsonResponse({"bank_account_id": str(bank_account.id), "periods": periods})


@login_required
@require_GET
def api_reconciliation_feed(request: HttpRequest):
    """
    Feed data for a bank account + period. Returns grouped transactions and balances.
    """
    # LEGACY: retained for backwards compatibility; v1 endpoints provide canonical session views.
    business, error = _ensure_business(request)
    if error:
        return error

    bank_account_id = request.GET.get("bank_account_id")
    period_id = request.GET.get("period_id")
    if not bank_account_id:
        return _json_error("bank_account_id is required")
    if not period_id:
        return _json_error("period_id is required")

    bank_account = get_object_or_404(BankAccount, pk=bank_account_id, business=business)

    try:
        start_date, end_date, label = _parse_period_id(period_id)
    except Exception:
        return _json_error("Invalid period_id format. Use YYYY-MM")

    # Build periods for dropdown convenience
    periods = _period_options_for_account(bank_account)

    # Build or fetch session for this period (safe, idempotent)
    from core.models import ReconciliationSession  # local import to avoid circular

    session, _ = ReconciliationSession.objects.get_or_create(
        business=business,
        bank_account=bank_account,
        statement_start_date=start_date,
        statement_end_date=end_date,
        defaults={"status": ReconciliationSession.Status.DRAFT},
    )

    qs = (
        BankTransaction.objects.filter(
            bank_account=bank_account,
            date__gte=start_date,
            date__lte=end_date,
        )
        .order_by("-date", "-id")
    )

    buckets = {
        "new": [],
        "suggested": [],
        "matched": [],
        "partial": [],
        "excluded": [],
    }

    def _tx_payload(tx: BankTransaction) -> dict:
        counterparty = None
        if tx.customer:
            counterparty = tx.customer.name
        elif tx.supplier:
            counterparty = tx.supplier.name

        match_conf = tx.suggestion_confidence
        engine_reason = tx.suggestion_reason
        return {
            "id": str(tx.id),
            "date": tx.date.isoformat() if tx.date else "",
            "description": tx.description or "",
            "counterparty": counterparty,
            "amount": float(tx.amount),
            "currency": bank_account.business.currency or "USD",
            "status": tx.status,
            "match_confidence": float(match_conf) / 100.0 if match_conf else None,
            "engine_reason": engine_reason,
            "includedInSession": True,
        }

    for tx in qs:
        payload = _tx_payload(tx)
        if tx.status == BankTransaction.TransactionStatus.EXCLUDED:
            buckets["excluded"].append(payload)
        elif tx.status == BankTransaction.TransactionStatus.PARTIAL:
            buckets["partial"].append(payload)
        elif tx.is_reconciled or tx.status in (
            BankTransaction.TransactionStatus.MATCHED,
            BankTransaction.TransactionStatus.MATCHED_SINGLE,
            BankTransaction.TransactionStatus.MATCHED_MULTI,
        ):
            buckets["matched"].append(payload)
        elif tx.suggestion_confidence:
            buckets["suggested"].append(payload)
        else:
            buckets["new"].append(payload)

    cleared_sum = (
        qs.filter(is_reconciled=True).aggregate(total=models.Sum("amount"))["total"] or Decimal("0")
    )

    opening_balance = float(session.opening_balance or Decimal("0"))
    statement_ending_balance = float(session.closing_balance or Decimal("0"))
    difference = statement_ending_balance - float(cleared_sum) - opening_balance
    total_transactions = sum(len(v) for v in buckets.values())
    reconciled_count = len(buckets["matched"])
    unreconciled_count = total_transactions - reconciled_count
    reconciled_percent = (reconciled_count / total_transactions * 100) if total_transactions else 0

    response = {
        "bank_account": {
            "id": str(bank_account.id),
            "name": bank_account.name,
            "currency": bank_account.business.currency or "USD",
        },
        "period": {
            "id": period_id,
            "label": label,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
        },
        "periods": periods,
        "session": {
            "id": str(session.id),
            "status": session.status,
            "opening_balance": opening_balance,
            "statement_ending_balance": statement_ending_balance,
            "difference": difference,
            "total_transactions": total_transactions,
            "reconciled_count": reconciled_count,
            "unreconciled_count": unreconciled_count,
            "reconciled_percent": reconciled_percent,
        },
        "transactions": buckets,
    }
    return JsonResponse(response)


@login_required
@require_POST
def api_reconciliation_complete(request: HttpRequest):
    business, error = _ensure_business(request)
    if error: return error
    
    body = _parse_json(request) or {}
    session_id = body.get("session_id")
    if not session_id:
        return _json_error("session_id is required")
    session = get_object_or_404(ReconciliationSession, pk=session_id, business=business)

    payload, error = _complete_session(session)
    if error:
        return error

    return JsonResponse(payload)

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
    if (resp := _session_mutable_or_error(session)):
        return resp
    if tx.reconciliation_session_id not in (None, session.id):
        return _json_error("Transaction belongs to another reconciliation session.")
    try:
        if included:
            _assert_tx_in_session_period(tx, session)
            set_reconciled_state(
                tx,
                reconciled=False,
                session=session,
                status=tx.status,
            )
        else:
            if tx.reconciliation_session_id == session.id and tx.status in RECONCILED_STATUSES:
                return _json_error("Unmatch transaction before removing it from this session.")
            set_reconciled_state(
                tx,
                reconciled=False,
                session=None,
                status=tx.status,
            )
    except ValidationError as exc:
        return _json_error(str(exc))
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
    if (resp := _session_mutable_or_error(session)):
        return resp
    
    # Create a BankTransaction for the adjustment
    # and immediately reconcile it against a new JournalEntry
    
    # 1. Create BankTransaction
    tx = BankTransaction.objects.create(
        bank_account=session.bank_account,
        date=session.statement_end_date, # Date of adjustment = end of period
        description=f"Adjustment: {adj_type}",
        amount=-amount if adj_type == "Bank fee" else amount, # Fee is negative
        status=BankTransaction.TransactionStatus.MATCHED,
        is_reconciled=False,
        reconciled_at=None,
        reconciliation_session=session,
        allocated_amount=amount,
        reconciliation_status=BankTransaction.RECO_STATUS_UNRECONCILED,
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
        reconciled_at=timezone.now(),
        reconciliation_session=session,
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
        description=f"Adjustment: {adj_type}",
        is_reconciled=True,
        reconciled_at=timezone.now(),
        reconciliation_session=session,
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
    set_reconciled_state(
        tx,
        reconciled=True,
        session=session,
        status=BankTransaction.TransactionStatus.MATCHED,
    )
    
    return JsonResponse({"status": "ok"})
