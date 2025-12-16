import logging
import time
from decimal import Decimal
import re

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum

from .utils import get_current_business
from .models import BankAccount
from taxes.models import TaxPeriodSnapshot, TaxAnomaly, TransactionLineTaxDetail, TaxPayment
from taxes.services import compute_tax_period_snapshot, compute_tax_anomalies, compute_tax_due_date

logger = logging.getLogger(__name__)


def _net_tax_from_summary(summary: dict) -> Decimal:
    total = Decimal("0.00")
    for data in (summary or {}).values():
        net = Decimal(str(data.get("net_tax", 0)))
        total += net
    return total


def _remaining_balance(net_tax: Decimal, payments_total: Decimal) -> Decimal:
    """
    Remaining tax balance after applying payments/refunds.

    Conventions:
    - `net_tax` is signed:
        - > 0: business owes the authority (liability)
        - < 0: authority owes the business (refund/credit)
    - `payments_total` is the signed net settlement amount for the period:
        - `sum(PAYMENT.amount) - sum(REFUND.amount)`
        - > 0: net paid to the authority
        - < 0: net refunded to the business

    With those conventions, `remaining_balance = net_tax - payments_total`:
    - > 0: still owed by the business
    - < 0: still owed to the business
    """
    return net_tax - payments_total


def _payment_status(net_tax: Decimal, payments_total: Decimal) -> str:
    """
    Deterministic payment status for a period, derived from `net_tax` and signed `payments_total`.
    """
    tolerance = Decimal("0.01")
    if net_tax.copy_abs() <= tolerance:
        return "NO_LIABILITY"

    if net_tax > 0:
        if payments_total <= tolerance:
            return "UNPAID"
        if payments_total < net_tax - tolerance:
            return "PARTIALLY_PAID"
        if (payments_total - net_tax).copy_abs() <= tolerance:
            return "PAID"
        if payments_total > net_tax + tolerance:
            return "OVERPAID"
        return "PAID"

    refund_expected = net_tax.copy_abs()
    refund_received = (-payments_total) if payments_total < 0 else Decimal("0.00")
    if refund_received <= tolerance:
        return "REFUND_DUE"
    if refund_received < refund_expected - tolerance:
        return "REFUND_PARTIALLY_RECEIVED"
    if (refund_received - refund_expected).copy_abs() <= tolerance:
        return "REFUND_RECEIVED"
    if refund_received > refund_expected + tolerance:
        return "REFUND_OVERRECEIVED"
    return "REFUND_RECEIVED"


def _serialize_payment(p: TaxPayment) -> dict:
    # Prefer explicit bank_account_label field; fallback to bank_account FK string repr
    bank_label = p.bank_account_label or ""
    if not bank_label and getattr(p, "bank_account", None):
        bank_label = str(p.bank_account)
    return {
        "id": str(p.id),
        "kind": getattr(p, "kind", None) or TaxPayment.Kind.PAYMENT,
        "amount": float(p.amount),
        "currency": p.currency,
        "payment_date": p.payment_date.isoformat() if p.payment_date else None,
        "bank_account_id": str(p.bank_account_id) if p.bank_account_id else None,
        "bank_account_label": bank_label,
        "method": p.method or "",
        "reference": p.reference or "",
        "notes": p.notes or "",
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _compute_payment_breakdown(payments: list) -> dict:
    """
    Compute payment/refund breakdown from a list of TaxPayment objects.
    
    Returns:
        {
            "payments_payment_total": float,  # sum of kind=PAYMENT amounts
            "payments_refund_total": float,   # sum of kind=REFUND amounts
            "payments_net_total": float,      # payment - refund
        }
    """
    payment_total = Decimal("0.00")
    refund_total = Decimal("0.00")
    
    for p in payments:
        kind = getattr(p, "kind", None) or TaxPayment.Kind.PAYMENT
        if kind == TaxPayment.Kind.REFUND:
            refund_total += abs(p.amount)
        else:
            payment_total += abs(p.amount)
    
    net_total = payment_total - refund_total
    return {
        "payments_payment_total": float(payment_total),
        "payments_refund_total": float(refund_total),
        "payments_net_total": float(net_total),
    }


def _compute_payment_status_v2(net_tax: Decimal, payments_payment_total: Decimal, payments_refund_total: Decimal) -> dict:
    """
    Deterministic payment status using explicit kind-based totals.

    Status is derived from signed net settlement:
      `payments_total = payments_payment_total - payments_refund_total`
    """
    payments_total = payments_payment_total - payments_refund_total
    balance = _remaining_balance(net_tax, payments_total)
    status = _payment_status(net_tax, payments_total)
    return {"status": status, "balance": float(balance)}


def _business_label(business) -> str:
    if getattr(business, "slug", None):
        return business.slug
    if getattr(business, "name", None):
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", business.name).strip("-").lower()
        return slug or str(business.id)
    return str(business.id)


def _resolve_linked_object(anomaly: TaxAnomaly):
    if not anomaly.linked_transaction_ct or not anomaly.linked_transaction_id:
        return None
    try:
        return anomaly.linked_transaction_ct.get_object_for_this_type(pk=anomaly.linked_transaction_id)
    except Exception:
        return None


def _friendly_linked_label(anomaly: TaxAnomaly) -> str | None:
    ct = anomaly.linked_transaction_ct
    if not ct:
        return None
    model_name = ct.model.replace("_", " ").title()
    # Shortcut common cases
    if "invoice" in ct.model:
        return "Invoice"
    if "expense" in ct.model:
        return "Expense"
    return model_name


def _anomaly_context(anomaly: TaxAnomaly, business) -> dict:
    detail = None
    jurisdiction_code = None
    expected_tax = None
    actual_tax = None
    difference = None
    ledger_path = None
    document_type = None
    document_id = None

    if anomaly.linked_transaction_ct and anomaly.linked_transaction_id:
        detail = (
            TransactionLineTaxDetail.objects.filter(
                business=business,
                transaction_line_content_type=anomaly.linked_transaction_ct,
                transaction_line_object_id=anomaly.linked_transaction_id,
            )
            .order_by("-transaction_date")
            .first()
        )
        if detail and detail.jurisdiction_code:
            jurisdiction_code = detail.jurisdiction_code

    linked_obj = _resolve_linked_object(anomaly)
    if linked_obj:
        # Attempt to derive parent document id for ledger navigation
        if hasattr(linked_obj, "invoice_id"):
            document_type = "Invoice"
            document_id = getattr(linked_obj, "invoice_id")
        elif hasattr(linked_obj, "expense_id"):
            document_type = "Expense"
            document_id = getattr(linked_obj, "expense_id")
        # Fallback to linked object itself
        if document_type is None:
            document_type = _friendly_linked_label(anomaly)
            document_id = anomaly.linked_transaction_id
        if document_type == "Invoice" and document_id:
            ledger_path = f"/invoices/{document_id}/edit/"
        elif document_type == "Expense" and document_id:
            ledger_path = f"/expenses/{document_id}/edit/"

    if anomaly.code in {"T1_RATE_MISMATCH", "T2_POSSIBLE_OVERCHARGE", "T5_EXEMPT_TAXED"} and detail:
        base = detail.taxable_amount_txn_currency or Decimal("0.00")
        actual_tax = detail.tax_amount_txn_currency or Decimal("0.00")
        component = getattr(detail, "tax_component", None)
        rate = getattr(component, "rate_percentage", None) or Decimal("0.00")
        expected_tax = (base * Decimal(rate)).quantize(Decimal("0.01"))
        difference = (expected_tax - actual_tax).copy_abs()

    if anomaly.code == "T4_ROUNDING_ANOMALY" and anomaly.linked_transaction_ct and anomaly.linked_transaction_id:
        doc_total = None
        if linked_obj:
            doc_total = getattr(linked_obj, "tax_total", None) or getattr(linked_obj, "tax_amount", None)
        detail_sum = sum(
            (
                d.tax_amount_txn_currency or Decimal("0.00")
                for d in TransactionLineTaxDetail.objects.filter(
                    business=business,
                    transaction_line_content_type=anomaly.linked_transaction_ct,
                    transaction_line_object_id=anomaly.linked_transaction_id,
                )
            ),
            Decimal("0.00"),
        )
        if doc_total is not None:
            expected_tax = Decimal(str(doc_total))
            actual_tax = detail_sum
            difference = (expected_tax - actual_tax).copy_abs()

    ctx = {
        "jurisdiction_code": jurisdiction_code,
        "linked_model_friendly": _friendly_linked_label(anomaly),
        "ledger_path": ledger_path,
        "document_type": document_type,
        "document_id": document_id,
    }
    if expected_tax is not None:
        ctx["expected_tax_amount"] = float(expected_tax)
    if actual_tax is not None:
        ctx["actual_tax_amount"] = float(actual_tax)
    if difference is not None:
        ctx["difference"] = float(difference)
    return ctx


def _serialize_anomaly(anomaly: TaxAnomaly, business=None) -> dict:
    base = {
        "id": str(anomaly.id),
        "code": anomaly.code,
        "severity": anomaly.severity,
        "status": anomaly.status,
        "description": anomaly.description,
        "task_code": anomaly.task_code,
        "created_at": anomaly.created_at.isoformat() if anomaly.created_at else None,
        "resolved_at": anomaly.resolved_at.isoformat() if anomaly.resolved_at else None,
        "linked_model": anomaly.linked_transaction_ct.model if anomaly.linked_transaction_ct else None,
        "linked_id": anomaly.linked_transaction_id,
    }
    if business:
        base.update(_anomaly_context(anomaly, business))
    return base


def _due_metadata(business, period_key: str, status: str) -> dict:
    due_date = compute_tax_due_date(business, period_key)
    today = timezone.localdate()
    is_filed = status == TaxPeriodSnapshot.SnapshotStatus.FILED
    is_overdue = (today > due_date) and not is_filed
    is_due_soon = (not is_overdue) and (not is_filed) and 0 <= (due_date - today).days <= 7
    return {
        "due_date": due_date.isoformat(),
        "is_due_soon": is_due_soon,
        "is_overdue": is_overdue,
    }


@login_required
def api_tax_periods(request):
    """GET /api/tax/periods/ - Returns all tax periods with payment breakdown."""
    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    snapshots = TaxPeriodSnapshot.objects.filter(business=business).order_by("-period_key")
    
    # Prefetch payments grouped by period_key for breakdown calculation
    payments_by_period: dict[str, list] = {}
    for payment in TaxPayment.objects.filter(business=business).select_related("bank_account"):
        payments_by_period.setdefault(payment.period_key, []).append(payment)
    
    periods = []
    for snap in snapshots:
        summary = snap.summary_by_jurisdiction or {}
        net_tax = _net_tax_from_summary(summary)
        period_payments = payments_by_period.get(snap.period_key, [])
        breakdown = _compute_payment_breakdown(period_payments)
        pmt_total = Decimal(str(breakdown["payments_payment_total"]))
        ref_total = Decimal(str(breakdown["payments_refund_total"]))
        status_info = _compute_payment_status_v2(net_tax, pmt_total, ref_total)
        
        anomalies = TaxAnomaly.objects.filter(business=business, period_key=snap.period_key)
        due = _due_metadata(business, snap.period_key, snap.status)
        periods.append(
            {
                "period_key": snap.period_key,
                "status": snap.status,
                "net_tax": float(net_tax),
                # New breakdown fields
                "payments_payment_total": breakdown["payments_payment_total"],
                "payments_refund_total": breakdown["payments_refund_total"],
                "payments_net_total": breakdown["payments_net_total"],
                # Legacy field
                "payments_total": breakdown["payments_net_total"],
                "remaining_balance": status_info["balance"],
                "balance": status_info["balance"],
                "payment_status": status_info["status"],
                "anomaly_counts": {
                    "low": anomalies.filter(severity=TaxAnomaly.AnomalySeverity.LOW).count(),
                    "medium": anomalies.filter(severity=TaxAnomaly.AnomalySeverity.MEDIUM).count(),
                    "high": anomalies.filter(severity=TaxAnomaly.AnomalySeverity.HIGH).count(),
                },
                **due,
            }
        )
    return JsonResponse({"periods": periods})


@login_required
def api_tax_period_detail(request, period_key: str):
    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    snapshot = TaxPeriodSnapshot.objects.filter(business=business, period_key=period_key).first()
    if not snapshot:
        try:
            snapshot = compute_tax_period_snapshot(business, period_key)
        except Exception as exc:
            logger.warning("Failed to compute snapshot for %s %s: %s", business.id, period_key, exc)
            return JsonResponse({"error": "Unable to compute snapshot"}, status=500)

    anomalies = TaxAnomaly.objects.filter(business=business, period_key=period_key)
    anomaly_counts = {
        "low": anomalies.filter(severity=TaxAnomaly.AnomalySeverity.LOW).count(),
        "medium": anomalies.filter(severity=TaxAnomaly.AnomalySeverity.MEDIUM).count(),
        "high": anomalies.filter(severity=TaxAnomaly.AnomalySeverity.HIGH).count(),
    }
    has_blockers = anomalies.filter(
        severity=TaxAnomaly.AnomalySeverity.HIGH, status=TaxAnomaly.AnomalyStatus.OPEN
    ).exists()

    summary = snapshot.summary_by_jurisdiction or {}
    net_tax = _net_tax_from_summary(summary)
    payments = list(
        TaxPayment.objects.filter(business=business, period_key=period_key)
        .select_related("bank_account")
        .order_by("-payment_date", "-created_at")
    )
    breakdown = _compute_payment_breakdown(payments)
    pmt_total = Decimal(str(breakdown["payments_payment_total"]))
    ref_total = Decimal(str(breakdown["payments_refund_total"]))
    status_info = _compute_payment_status_v2(net_tax, pmt_total, ref_total)

    return JsonResponse(
        {
            "period_key": snapshot.period_key,
            "country": snapshot.country,
            "status": snapshot.status,
            "filed_at": snapshot.filed_at.isoformat() if snapshot.filed_at else None,
            "last_filed_at": snapshot.last_filed_at.isoformat() if getattr(snapshot, "last_filed_at", None) else None,
            "last_reset_at": snapshot.last_reset_at.isoformat() if getattr(snapshot, "last_reset_at", None) else None,
            "last_reset_reason": getattr(snapshot, "last_reset_reason", "") or "",
            "llm_summary": snapshot.llm_summary or "",
            "llm_notes": snapshot.llm_notes or "",
            "summary_by_jurisdiction": snapshot.summary_by_jurisdiction,
            "line_mappings": snapshot.line_mappings,
            "net_tax": float(net_tax),
            "payments": [_serialize_payment(p) for p in payments],
            # New breakdown fields
            "payments_payment_total": breakdown["payments_payment_total"],
            "payments_refund_total": breakdown["payments_refund_total"],
            "payments_net_total": breakdown["payments_net_total"],
            # Legacy field
            "payments_total": breakdown["payments_net_total"],
            "remaining_balance": status_info["balance"],
            "balance": status_info["balance"],
            "payment_status": status_info["status"],
            "anomaly_counts": anomaly_counts,
            "has_high_severity_blockers": has_blockers,
            **_due_metadata(business, period_key, snapshot.status),
        }
    )


@login_required
def api_tax_period_anomalies(request, period_key: str):
    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    severity = request.GET.get("severity")
    status = request.GET.get("status")

    anomalies = TaxAnomaly.objects.filter(business=business, period_key=period_key)
    if severity:
        anomalies = anomalies.filter(severity=severity)
    if status:
        anomalies = anomalies.filter(status=status)

    data = [_serialize_anomaly(a, business) for a in anomalies.order_by("-created_at")[:200]]
    return JsonResponse({"anomalies": data})


@login_required
def api_tax_anomaly_update(request, period_key: str, anomaly_id):
    if request.method not in {"PATCH", "POST"}:
        return HttpResponseBadRequest("PATCH required")
    import json

    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)
    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}
    new_status = payload.get("status")
    if new_status not in TaxAnomaly.AnomalyStatus.values:
        return JsonResponse({"error": "Invalid status"}, status=400)

    anomaly = TaxAnomaly.objects.filter(business=business, period_key=period_key, id=anomaly_id).first()
    if not anomaly:
        return JsonResponse({"error": "Anomaly not found"}, status=404)

    anomaly.status = new_status
    if new_status == TaxAnomaly.AnomalyStatus.RESOLVED:
        anomaly.resolved_at = timezone.now()
    else:
        anomaly.resolved_at = None
    anomaly.save(update_fields=["status", "resolved_at"])
    return JsonResponse(_serialize_anomaly(anomaly))


@login_required
def api_tax_period_payments(request, period_key: str):
    """
    GET/POST /api/tax/periods/<period_key>/payments/
    
    GET returns:
        - payments: list of serialized payments with kind field
        - payments_payment_total: sum of kind=PAYMENT amounts
        - payments_refund_total: sum of kind=REFUND amounts
        - payments_net_total: payment - refund (backward compat: same as payments_total)
        - payments_total: (legacy) same as payments_net_total
        - payment_status: computed status
        - balance: remaining balance
    
    POST accepts:
        - kind: "PAYMENT" or "REFUND" (default: PAYMENT)
        - bank_account_id: required (int)
        - bank_account_label: optional fallback label (str)
        - amount: must be positive (use kind for direction)
        - payment_date, currency, method, reference, notes
    """
    import json
    from django.utils.dateparse import parse_date

    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    snapshot = TaxPeriodSnapshot.objects.filter(business=business, period_key=period_key).first()
    net_tax = _net_tax_from_summary((snapshot.summary_by_jurisdiction or {}) if snapshot else {})

    if request.method == "GET":
        payments = list(
            TaxPayment.objects.filter(business=business, period_key=period_key)
            .select_related("bank_account")
            .order_by("-payment_date", "-created_at")
        )
        breakdown = _compute_payment_breakdown(payments)
        pmt_total = Decimal(str(breakdown["payments_payment_total"]))
        ref_total = Decimal(str(breakdown["payments_refund_total"]))
        status_info = _compute_payment_status_v2(net_tax, pmt_total, ref_total) if snapshot else {"status": None, "balance": None}
        
        return JsonResponse(
            {
                "payments": [_serialize_payment(p) for p in payments],
                # New explicit breakdown fields
                "payments_payment_total": breakdown["payments_payment_total"],
                "payments_refund_total": breakdown["payments_refund_total"],
                "payments_net_total": breakdown["payments_net_total"],
                # Legacy field for backward compatibility
                "payments_total": breakdown["payments_net_total"],
                "payment_status": status_info["status"],
                "balance": status_info["balance"],
                # Legacy remaining_balance (same as balance)
                "remaining_balance": status_info["balance"],
            }
        )

    if request.method != "POST":
        return HttpResponseBadRequest("GET or POST required")

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}

    errors = {}
    
    # Kind field (PAYMENT or REFUND). If omitted, default based on the period's net_tax sign.
    kind_raw = payload.get("kind")
    if kind_raw:
        kind = str(kind_raw).strip().upper()
    else:
        kind = TaxPayment.Kind.REFUND if snapshot and net_tax < 0 else TaxPayment.Kind.PAYMENT
    if kind not in TaxPayment.Kind.values:
        errors["kind"] = f"kind must be one of: {', '.join(TaxPayment.Kind.values)}"
    
    amount_raw = payload.get("amount")
    try:
        amount = Decimal(str(amount_raw))
        # Enforce positive amounts (use kind for direction)
        if amount < 0:
            errors["amount"] = "amount must be positive. Use kind=REFUND for refunds."
        amount = abs(amount)
    except Exception:
        amount = None
        errors["amount"] = "amount must be a valid number."

    payment_date = parse_date(str(payload.get("payment_date") or ""))
    if not payment_date:
        errors["payment_date"] = "payment_date must be YYYY-MM-DD."

    currency = (payload.get("currency") or getattr(business, "currency", None) or "CAD").strip().upper()
    if not currency or len(currency) != 3:
        errors["currency"] = "currency must be a 3-letter code."

    method = (payload.get("method") or "").strip()
    reference = (payload.get("reference") or "").strip()
    notes = (payload.get("notes") or "").strip()
    bank_account_label = (payload.get("bank_account_label") or "").strip()

    bank_account = None
    bank_account_id_raw = payload.get("bank_account_id")
    if bank_account_id_raw in (None, ""):
        # Bank account is optional if bank_account_label is provided
        if not bank_account_label:
            errors["bank_account_id"] = "bank_account_id or bank_account_label is required."
    else:
        try:
            bank_account_id = int(str(bank_account_id_raw))
        except Exception:
            errors["bank_account_id"] = "bank_account_id must be a valid id."
        else:
            bank_account = BankAccount.objects.filter(business=business, id=bank_account_id).first()
            if not bank_account:
                errors["bank_account_id"] = "Bank account not found for this business."

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    payment = TaxPayment.objects.create(
        business=business,
        period_key=period_key,
        snapshot=snapshot,
        bank_account=bank_account,
        kind=kind,
        bank_account_label=bank_account_label,
        amount=amount,
        currency=currency,
        payment_date=payment_date,
        method=method,
        reference=reference,
        notes=notes,
        created_by=request.user,
    )

    # Recompute breakdown
    payments = list(
        TaxPayment.objects.filter(business=business, period_key=period_key)
        .select_related("bank_account")
    )
    breakdown = _compute_payment_breakdown(payments)
    pmt_total = Decimal(str(breakdown["payments_payment_total"]))
    ref_total = Decimal(str(breakdown["payments_refund_total"]))
    status_info = _compute_payment_status_v2(net_tax, pmt_total, ref_total) if snapshot else {"status": None, "balance": None}
    
    return JsonResponse(
        {
            "payment": _serialize_payment(payment),
            "payments_payment_total": breakdown["payments_payment_total"],
            "payments_refund_total": breakdown["payments_refund_total"],
            "payments_net_total": breakdown["payments_net_total"],
            "payments_total": breakdown["payments_net_total"],
            "payment_status": status_info["status"],
            "balance": status_info["balance"],
            "remaining_balance": status_info["balance"],
        },
        status=201,
    )


@login_required
def api_tax_period_payment_detail(request, period_key: str, payment_id):
    """
    PATCH/DELETE /api/tax/periods/<period_key>/payments/<payment_id>/
    
    PATCH accepts:
        - kind: "PAYMENT" or "REFUND"
        - bank_account_id: bank account FK
        - bank_account_label: fallback label
        - amount: must be positive
        - payment_date, currency, method, reference, notes
    """
    import json
    from django.utils.dateparse import parse_date

    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    payment = (
        TaxPayment.objects.filter(business=business, period_key=period_key, id=payment_id)
        .select_related("bank_account")
        .first()
    )
    if not payment:
        return JsonResponse({"error": "Payment not found"}, status=404)

    snapshot = TaxPeriodSnapshot.objects.filter(business=business, period_key=period_key).first()
    net_tax = _net_tax_from_summary((snapshot.summary_by_jurisdiction or {}) if snapshot else {})

    if request.method == "DELETE":
        payment.delete()
        # Recompute breakdown after delete
        payments = list(
            TaxPayment.objects.filter(business=business, period_key=period_key)
            .select_related("bank_account")
        )
        breakdown = _compute_payment_breakdown(payments)
        pmt_total = Decimal(str(breakdown["payments_payment_total"]))
        ref_total = Decimal(str(breakdown["payments_refund_total"]))
        status_info = _compute_payment_status_v2(net_tax, pmt_total, ref_total) if snapshot else {"status": None, "balance": None}
        return JsonResponse({
            "status": "deleted",
            "payments_payment_total": breakdown["payments_payment_total"],
            "payments_refund_total": breakdown["payments_refund_total"],
            "payments_net_total": breakdown["payments_net_total"],
            "payments_total": breakdown["payments_net_total"],
            "payment_status": status_info["status"],
            "balance": status_info["balance"],
        })

    if request.method != "PATCH":
        return HttpResponseBadRequest("PATCH or DELETE required")

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}

    errors = {}
    updates = {}

    # Kind field
    if "kind" in payload:
        kind = (payload.get("kind") or "").strip().upper()
        if kind not in TaxPayment.Kind.values:
            errors["kind"] = f"kind must be one of: {', '.join(TaxPayment.Kind.values)}"
        else:
            updates["kind"] = kind

    if "amount" in payload:
        try:
            next_amount = Decimal(str(payload.get("amount")))
            if next_amount < 0:
                errors["amount"] = "amount must be positive. Use kind=REFUND for refunds."
            else:
                updates["amount"] = abs(next_amount)
        except Exception:
            errors["amount"] = "amount must be a valid number."

    if "payment_date" in payload:
        pd = parse_date(str(payload.get("payment_date") or ""))
        if not pd:
            errors["payment_date"] = "payment_date must be YYYY-MM-DD."
        else:
            updates["payment_date"] = pd

    if "currency" in payload:
        cur = (payload.get("currency") or "").strip().upper()
        if not cur or len(cur) != 3:
            errors["currency"] = "currency must be a 3-letter code."
        else:
            updates["currency"] = cur

    if "bank_account_id" in payload:
        raw = payload.get("bank_account_id")
        if raw in (None, ""):
            updates["bank_account"] = None
        else:
            try:
                bank_account_id = int(str(raw))
            except Exception:
                errors["bank_account_id"] = "bank_account_id must be a valid id."
            else:
                bank_account = BankAccount.objects.filter(business=business, id=bank_account_id).first()
                if not bank_account:
                    errors["bank_account_id"] = "Bank account not found for this business."
                else:
                    updates["bank_account"] = bank_account

    if "bank_account_label" in payload:
        updates["bank_account_label"] = (payload.get("bank_account_label") or "").strip()

    if "method" in payload:
        updates["method"] = (payload.get("method") or "").strip()
    if "reference" in payload:
        updates["reference"] = (payload.get("reference") or "").strip()
    if "notes" in payload:
        updates["notes"] = (payload.get("notes") or "").strip()

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    for k, v in updates.items():
        setattr(payment, k, v)
    if updates:
        payment.save(update_fields=list(updates.keys()))

    # Recompute breakdown
    payments = list(
        TaxPayment.objects.filter(business=business, period_key=period_key)
        .select_related("bank_account")
    )
    breakdown = _compute_payment_breakdown(payments)
    pmt_total = Decimal(str(breakdown["payments_payment_total"]))
    ref_total = Decimal(str(breakdown["payments_refund_total"]))
    status_info = _compute_payment_status_v2(net_tax, pmt_total, ref_total) if snapshot else {"status": None, "balance": None}
    
    return JsonResponse(
        {
            "payment": _serialize_payment(payment),
            "payments_payment_total": breakdown["payments_payment_total"],
            "payments_refund_total": breakdown["payments_refund_total"],
            "payments_net_total": breakdown["payments_net_total"],
            "payments_total": breakdown["payments_net_total"],
            "payment_status": status_info["status"],
            "balance": status_info["balance"],
            "remaining_balance": status_info["balance"],
        }
    )


@login_required
def api_tax_period_refresh(request, period_key: str):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    existing = TaxPeriodSnapshot.objects.filter(business=business, period_key=period_key).first()
    if existing and existing.status == TaxPeriodSnapshot.SnapshotStatus.FILED:
        return JsonResponse(
            {"detail": f"Tax period {period_key} is filed and cannot be refreshed."},
            status=409,
        )

    cache_key = f"tax_refresh_{business.id}_{period_key}"
    last_run = cache.get(cache_key)
    now = time.time()
    if last_run and (now - last_run) < 60:
        return JsonResponse({"error": "Refresh throttled; try again shortly."}, status=429)

    snapshot = compute_tax_period_snapshot(business, period_key)
    compute_tax_anomalies(business, period_key)

    cache.set(cache_key, now, timeout=60)
    return JsonResponse({"status": "ok", "snapshot_id": str(snapshot.id)})


@login_required
def api_tax_period_llm_enrich(request, period_key: str):
    """
    POST /api/tax/periods/<period_key>/llm-enrich/

    On-demand observer enrichment:
    - Uses DeepSeek via Companion LLM wrapper
    - Never computes/changes amounts; only summarizes deterministic snapshot/anomalies
    - Throttled to avoid accidental spam
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    snapshot = TaxPeriodSnapshot.objects.filter(business=business, period_key=period_key).first()
    if not snapshot:
        return JsonResponse({"error": "Snapshot not found for this period"}, status=404)

    cache_key = f"tax_llm_enrich_{business.id}_{period_key}"
    last_run = cache.get(cache_key)
    now = time.time()
    if last_run and (now - last_run) < 60:
        return JsonResponse({"error": "Enrichment throttled; try again shortly."}, status=429)

    from companion.llm import LLMProfile
    from taxes.llm_observer import enrich_tax_period_snapshot_llm

    anomalies = list(TaxAnomaly.objects.filter(business=business, period_key=period_key).order_by("-created_at")[:50])
    enrichment = enrich_tax_period_snapshot_llm(
        business=business,
        snapshot=snapshot,
        anomalies=anomalies,
        profile=LLMProfile.LIGHT_CHAT,
    )
    if not enrichment:
        return JsonResponse(
            {"detail": "LLM enrichment unavailable (disabled or failed)."},
            status=503,
        )

    snapshot.llm_summary = enrichment.summary
    snapshot.llm_notes = "\n".join([f"- {n}" for n in enrichment.notes])
    snapshot.save(update_fields=["llm_summary", "llm_notes"])

    cache.set(cache_key, now, timeout=60)
    return JsonResponse({"status": "ok", "llm_summary": snapshot.llm_summary, "llm_notes": snapshot.llm_notes})


@login_required
def api_tax_export_json(request, period_key: str):
    """Export tax period snapshot as JSON file."""
    from django.http import HttpResponse
    from django.utils import timezone
    import json

    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    snapshot = TaxPeriodSnapshot.objects.filter(business=business, period_key=period_key).first()
    if not snapshot:
        return JsonResponse({"error": "Snapshot not found for this period"}, status=404)

    export_data = {
        "business_id": str(business.id),
        "period_key": snapshot.period_key,
        "country": snapshot.country,
        "status": snapshot.status,
        "summary_by_jurisdiction": snapshot.summary_by_jurisdiction,
        "line_mappings": snapshot.line_mappings,
        "generated_at": timezone.now().isoformat(),
    }

    response = HttpResponse(
        json.dumps(export_data, indent=2, default=str),
        content_type="application/json",
    )
    business_label = _business_label(business)
    filename = f"tax_snapshot_{business_label}_{period_key}.json"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def api_tax_export_csv(request, period_key: str):
    """Export tax period snapshot jurisdiction breakdown as CSV file."""
    from django.http import HttpResponse
    import csv
    import io

    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    snapshot = TaxPeriodSnapshot.objects.filter(business=business, period_key=period_key).first()
    if not snapshot:
        return JsonResponse({"error": "Snapshot not found for this period"}, status=404)

    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header row
    writer.writerow([
        "jurisdiction_code",
        "country",
        "currency",
        "taxable_sales",
        "taxable_purchases",
        "tax_collected",
        "tax_on_purchases",
        "net_tax",
    ])
    
    # Data rows
    summary = snapshot.summary_by_jurisdiction or {}
    for code, data in summary.items():
        writer.writerow([
            code,
            snapshot.country,
            data.get("currency", ""),
            data.get("taxable_sales", 0),
            data.get("taxable_purchases", 0),
            data.get("tax_collected", 0),
            data.get("tax_on_purchases", 0),
            data.get("net_tax", 0),
        ])

    response = HttpResponse(output.getvalue(), content_type="text/csv")
    business_label = _business_label(business)
    filename = f"tax_snapshot_{business_label}_{period_key}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def api_tax_export_ser_csv(request, period_key: str):
    """Export US SER-style per-state summary as CSV file (draft, deterministic)."""
    from django.http import HttpResponse
    import csv
    import io

    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    snapshot = TaxPeriodSnapshot.objects.filter(business=business, period_key=period_key).first()
    if not snapshot:
        return JsonResponse({"error": "Snapshot not found for this period"}, status=404)

    us = (snapshot.line_mappings or {}).get("US") or {}
    states = us.get("states") if isinstance(us, dict) else None
    if not states:
        return JsonResponse({"error": "No US SER data for this period"}, status=404)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "state_code",
            "gross_sales",
            "exempt_sales",
            "taxable_sales",
            "tax_collected",
            "tax_on_purchases",
            "net_tax",
        ]
    )

    for state_code in sorted(states.keys()):
        row = states.get(state_code) or {}
        tax_collected = Decimal(str(row.get("tax_collected", 0)))
        tax_on_purchases = Decimal(str(row.get("tax_on_purchases", 0)))
        net_tax = row.get("net_tax")
        if net_tax is None:
            net_tax = float(tax_collected - tax_on_purchases)
        writer.writerow(
            [
                state_code,
                row.get("gross_sales", 0),
                row.get("exempt_sales", 0),
                row.get("taxable_sales", 0),
                row.get("tax_collected", 0),
                row.get("tax_on_purchases", 0),
                net_tax,
            ]
        )

    response = HttpResponse(output.getvalue(), content_type="text/csv")
    business_label = _business_label(business)
    filename = f"tax_ser_{business_label}_{period_key}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def api_tax_anomalies_export_csv(request, period_key: str):
    """Export anomalies for a period as CSV."""
    from django.http import HttpResponse
    import csv
    import io

    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    snapshot = TaxPeriodSnapshot.objects.filter(business=business, period_key=period_key).first()
    if not snapshot:
        return JsonResponse({"error": "Snapshot not found for this period"}, status=404)

    anomalies = TaxAnomaly.objects.filter(business=business, period_key=period_key).order_by("-created_at")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "period_key",
            "code",
            "severity",
            "status",
            "task_code",
            "description",
            "jurisdiction_code",
            "linked_model",
            "linked_id",
            "created_at",
            "resolved_at",
        ]
    )
    for anomaly in anomalies:
        ctx = _anomaly_context(anomaly, business)
        writer.writerow(
            [
                anomaly.period_key,
                anomaly.code,
                anomaly.severity,
                anomaly.status,
                anomaly.task_code,
                anomaly.description,
                ctx.get("jurisdiction_code") or "",
                ctx.get("linked_model_friendly") or (anomaly.linked_transaction_ct.model if anomaly.linked_transaction_ct else ""),
                anomaly.linked_transaction_id or "",
                anomaly.created_at.isoformat() if anomaly.created_at else "",
                anomaly.resolved_at.isoformat() if anomaly.resolved_at else "",
            ]
        )

    response = HttpResponse(output.getvalue(), content_type="text/csv")
    business_label = _business_label(business)
    filename = f"tax_anomalies_{business_label}_{period_key}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def api_tax_period_status(request, period_key: str):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")
    import json

    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    snapshot = TaxPeriodSnapshot.objects.filter(business=business, period_key=period_key).first()
    if not snapshot:
        return JsonResponse({"error": "Snapshot not found"}, status=404)

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}
    new_status = payload.get("status")
    allowed = {
        TaxPeriodSnapshot.SnapshotStatus.COMPUTED,
        TaxPeriodSnapshot.SnapshotStatus.REVIEWED,
        TaxPeriodSnapshot.SnapshotStatus.FILED,
    }
    if new_status not in allowed:
        return JsonResponse({"error": "Invalid status"}, status=400)

    current = snapshot.status
    forward_only = {
        TaxPeriodSnapshot.SnapshotStatus.COMPUTED: {
            TaxPeriodSnapshot.SnapshotStatus.REVIEWED,
            TaxPeriodSnapshot.SnapshotStatus.FILED,
        },
        TaxPeriodSnapshot.SnapshotStatus.REVIEWED: {TaxPeriodSnapshot.SnapshotStatus.FILED},
        TaxPeriodSnapshot.SnapshotStatus.FILED: set(),
    }
    if new_status == current or new_status in forward_only.get(current, set()):
        snapshot.status = new_status
        if new_status == TaxPeriodSnapshot.SnapshotStatus.FILED:
            now = timezone.now()
            snapshot.filed_at = now
            snapshot.last_filed_at = now
        snapshot.save(update_fields=["status", "filed_at", "last_filed_at"])
        return JsonResponse(
            {
                "period_key": snapshot.period_key,
                "status": snapshot.status,
                "filed_at": snapshot.filed_at.isoformat() if snapshot.filed_at else None,
            }
        )

    return JsonResponse({"error": "Invalid transition"}, status=400)


@login_required
def api_tax_period_reset(request, period_key: str):
    """
    POST /api/tax/periods/<period_key>/reset/

    QBO-style "delete return":
    - Only allowed for FILED snapshots.
    - Does not delete snapshot data; clears FILED status so the period can be refreshed.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")
    import json

    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    snapshot = TaxPeriodSnapshot.objects.filter(business=business, period_key=period_key).first()
    if not snapshot:
        return JsonResponse({"error": "Snapshot not found"}, status=404)

    if snapshot.status != TaxPeriodSnapshot.SnapshotStatus.FILED:
        return JsonResponse({"error": "Only FILED periods can be reset."}, status=400)

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}

    if payload.get("confirm_reset") is not True:
        return JsonResponse({"error": "confirm_reset=true is required to reset a filed period."}, status=400)

    reason = (payload.get("reason") or "").strip()
    prev_filed_at = snapshot.filed_at
    snapshot.status = TaxPeriodSnapshot.SnapshotStatus.REVIEWED
    snapshot.filed_at = None
    snapshot.last_filed_at = prev_filed_at or snapshot.last_filed_at
    snapshot.last_reset_at = timezone.now()
    snapshot.last_reset_reason = reason[:255]
    snapshot.save(update_fields=["status", "filed_at", "last_filed_at", "last_reset_at", "last_reset_reason"])

    return JsonResponse(
        {
            "period_key": snapshot.period_key,
            "status": snapshot.status,
            "filed_at": None,
            "last_filed_at": snapshot.last_filed_at.isoformat() if snapshot.last_filed_at else None,
            "last_reset_at": snapshot.last_reset_at.isoformat() if snapshot.last_reset_at else None,
            "last_reset_reason": snapshot.last_reset_reason or "",
        }
    )
