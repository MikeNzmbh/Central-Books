from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum
from django.http import HttpResponseBadRequest, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST

from core.models import Customer, Invoice
from core.utils import get_current_business
from reversals.models import Allocation, CustomerCreditMemo, CustomerDeposit, CustomerRefund
from reversals.services.allocations import (
    credit_memo_available_amount,
    deposit_available_amount,
    invoice_open_amount,
    sum_posted_refunds_for_credit_memo,
    sum_posted_refunds_for_deposit,
)
from reversals.services.posting import (
    allocate_credit_memo_to_invoices,
    apply_customer_deposit_to_invoices,
    post_customer_credit_memo,
    post_customer_deposit,
    post_customer_refund,
)
from reversals.services.voiding import (
    void_customer_credit_memo,
    void_customer_deposit,
    void_customer_refund,
)


def _json_from_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return None


def _as_decimal(value, *, field: str) -> Decimal:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {field}.") from exc
    return d


def _serialize_money(value: Decimal | None) -> str:
    return f"{Decimal(value or Decimal('0.00')):.2f}"


def _serialize_credit_memo(business, memo: CustomerCreditMemo) -> dict:
    available = credit_memo_available_amount(memo)
    refunded = sum_posted_refunds_for_credit_memo(credit_memo=memo)

    invoice_ct = ContentType.objects.get_for_model(Invoice)
    memo_ct = ContentType.objects.get_for_model(CustomerCreditMemo)
    allocations_by_invoice = (
        Allocation.objects.filter(
            business=business,
            status=Allocation.Status.ACTIVE,
            source_content_type=memo_ct,
            source_object_id=memo.pk,
            target_content_type=invoice_ct,
        )
        .values("target_object_id")
        .annotate(total=Sum("amount"))
    )
    invoice_ids = [row["target_object_id"] for row in allocations_by_invoice]
    invoices = {
        inv.id: inv
        for inv in Invoice.objects.filter(business=business, id__in=invoice_ids).only("id", "invoice_number")
    }
    linked = [
        {
            "invoice_id": row["target_object_id"],
            "invoice_number": getattr(invoices.get(row["target_object_id"]), "invoice_number", ""),
            "amount": _serialize_money(row["total"]),
        }
        for row in allocations_by_invoice
    ]

    return {
        "id": memo.id,
        "credit_memo_number": memo.credit_memo_number,
        "posting_date": memo.posting_date.isoformat() if memo.posting_date else None,
        "status": memo.status,
        "memo": memo.memo or "",
        "net_total": _serialize_money(memo.net_total),
        "tax_total": _serialize_money(memo.tax_total),
        "grand_total": _serialize_money(memo.grand_total),
        "available_amount": _serialize_money(max(Decimal("0.00"), available)),
        "refunded_total": _serialize_money(refunded),
        "source_invoice_id": memo.source_invoice_id,
        "source_invoice_number": getattr(memo.source_invoice, "invoice_number", None) if memo.source_invoice_id else None,
        "linked_invoices": linked,
    }


def _serialize_deposit(business, deposit: CustomerDeposit) -> dict:
    available = deposit_available_amount(deposit)
    refunded = sum_posted_refunds_for_deposit(deposit=deposit)

    invoice_ct = ContentType.objects.get_for_model(Invoice)
    deposit_ct = ContentType.objects.get_for_model(CustomerDeposit)
    allocations_by_invoice = (
        Allocation.objects.filter(
            business=business,
            status=Allocation.Status.ACTIVE,
            source_content_type=deposit_ct,
            source_object_id=deposit.pk,
            target_content_type=invoice_ct,
        )
        .values("target_object_id")
        .annotate(total=Sum("amount"))
    )
    invoice_ids = [row["target_object_id"] for row in allocations_by_invoice]
    invoices = {
        inv.id: inv
        for inv in Invoice.objects.filter(business=business, id__in=invoice_ids).only("id", "invoice_number")
    }
    linked = [
        {
            "invoice_id": row["target_object_id"],
            "invoice_number": getattr(invoices.get(row["target_object_id"]), "invoice_number", ""),
            "amount": _serialize_money(row["total"]),
        }
        for row in allocations_by_invoice
    ]

    return {
        "id": deposit.id,
        "posting_date": deposit.posting_date.isoformat() if deposit.posting_date else None,
        "status": deposit.status,
        "memo": deposit.memo or "",
        "amount": _serialize_money(deposit.amount),
        "currency": deposit.currency,
        "available_amount": _serialize_money(max(Decimal("0.00"), available)),
        "refunded_total": _serialize_money(refunded),
        "bank_account_id": deposit.bank_account_id,
        "bank_account_name": getattr(deposit.bank_account, "name", ""),
        "linked_invoices": linked,
    }


def _serialize_refund(refund: CustomerRefund) -> dict:
    return {
        "id": refund.id,
        "posting_date": refund.posting_date.isoformat() if refund.posting_date else None,
        "status": refund.status,
        "memo": refund.memo or "",
        "amount": _serialize_money(refund.amount),
        "currency": refund.currency,
        "bank_account_id": refund.bank_account_id,
        "bank_account_name": getattr(refund.bank_account, "name", ""),
        "credit_memo_id": refund.credit_memo_id,
        "deposit_id": refund.deposit_id,
    }


@login_required
@require_GET
def api_customer_reversals_summary(request, customer_id: int):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    customer = Customer.objects.filter(business=business, pk=customer_id).first()
    if not customer:
        return JsonResponse({"error": "Customer not found"}, status=404)

    invoices = list(
        Invoice.objects.filter(business=business, customer=customer)
        .only("id", "balance", "grand_total", "net_total", "tax_total", "amount_paid", "status")
        .order_by("-issue_date")[:200]
    )
    open_ar = sum((invoice_open_amount(inv) for inv in invoices if inv.status in (Invoice.Status.SENT, Invoice.Status.PARTIAL)), Decimal("0.00"))

    credit_memos = list(
        CustomerCreditMemo.objects.filter(
            business=business, customer=customer, status=CustomerCreditMemo.Status.POSTED
        ).only("id", "grand_total", "customer_id", "status")
    )
    open_credits = sum((max(Decimal("0.00"), credit_memo_available_amount(cm)) for cm in credit_memos), Decimal("0.00"))

    deposits = list(
        CustomerDeposit.objects.filter(
            business=business, customer=customer, status=CustomerDeposit.Status.POSTED
        ).only("id", "amount", "currency", "customer_id", "status")
    )
    deposit_balance = sum((max(Decimal("0.00"), deposit_available_amount(dep)) for dep in deposits), Decimal("0.00"))

    return JsonResponse(
        {
            "customer_id": customer.id,
            "currency": business.currency,
            "open_ar": _serialize_money(open_ar),
            "open_credits": _serialize_money(open_credits),
            "deposit_balance": _serialize_money(deposit_balance),
        }
    )


@login_required
@require_GET
def api_customer_credit_memos(request, customer_id: int):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    customer = Customer.objects.filter(business=business, pk=customer_id).first()
    if not customer:
        return JsonResponse({"error": "Customer not found"}, status=404)

    memos = (
        CustomerCreditMemo.objects.filter(business=business, customer=customer)
        .select_related("source_invoice")
        .order_by("-posting_date", "-id")[:200]
    )
    return JsonResponse(
        {
            "credit_memos": [_serialize_credit_memo(business, m) for m in memos],
            "currency": business.currency,
        }
    )


@login_required
@require_POST
def api_customer_credit_memo_create(request):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    payload = _json_from_body(request)
    if not isinstance(payload, dict):
        return HttpResponseBadRequest("Invalid JSON")

    customer_id = payload.get("customer_id")
    if not customer_id:
        return JsonResponse({"error": "customer_id is required"}, status=400)
    customer = Customer.objects.filter(business=business, pk=customer_id).first()
    if not customer:
        return JsonResponse({"error": "Customer not found"}, status=404)

    try:
        net_total = _as_decimal(payload.get("net_total"), field="net_total")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    if net_total <= 0:
        return JsonResponse({"error": "net_total must be > 0"}, status=400)

    posting_date = parse_date(payload.get("posting_date")) or timezone.localdate()
    memo_text = (payload.get("memo") or "").strip()
    credit_memo_number = (payload.get("credit_memo_number") or "").strip()

    source_invoice = None
    source_invoice_id = payload.get("source_invoice_id") or None
    if source_invoice_id:
        source_invoice = (
            Invoice.objects.filter(business=business, pk=source_invoice_id)
            .select_related("tax_group", "customer")
            .first()
        )
        if not source_invoice:
            return JsonResponse({"error": "Source invoice not found"}, status=404)
        if source_invoice.customer_id != customer.id:
            return JsonResponse({"error": "Source invoice belongs to a different customer"}, status=400)

    tax_group_id = payload.get("tax_group_id")
    tax_group = None
    if tax_group_id:
        from taxes.models import TaxGroup

        tax_group = TaxGroup.objects.filter(business=business, pk=tax_group_id).first()
        if not tax_group:
            return JsonResponse({"error": "tax_group_id not found"}, status=404)
    elif source_invoice and getattr(source_invoice, "tax_group_id", None):
        tax_group = source_invoice.tax_group

    credit_memo = CustomerCreditMemo.objects.create(
        business=business,
        customer=customer,
        source_invoice=source_invoice,
        credit_memo_number=credit_memo_number,
        posting_date=posting_date,
        status=CustomerCreditMemo.Status.DRAFT,
        memo=memo_text,
        net_total=net_total,
        tax_total=Decimal("0.00"),
        grand_total=net_total,
        tax_group=tax_group,
    )

    return JsonResponse({"credit_memo": _serialize_credit_memo(business, credit_memo)})


@login_required
@require_POST
def api_customer_credit_memo_post(request, credit_memo_id: int):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    credit_memo = (
        CustomerCreditMemo.objects.filter(business=business, pk=credit_memo_id)
        .select_related("customer", "source_invoice", "tax_group")
        .first()
    )
    if not credit_memo:
        return JsonResponse({"error": "Not found"}, status=404)

    if credit_memo.status == CustomerCreditMemo.Status.POSTED:
        return JsonResponse({"credit_memo": _serialize_credit_memo(business, credit_memo)})

    try:
        entry = post_customer_credit_memo(credit_memo, user=request.user)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "journal_entry_id": entry.id,
            "credit_memo": _serialize_credit_memo(business, credit_memo),
        }
    )


@login_required
@require_POST
def api_customer_credit_memo_void(request, credit_memo_id: int):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    credit_memo = CustomerCreditMemo.objects.filter(business=business, pk=credit_memo_id).first()
    if not credit_memo:
        return JsonResponse({"error": "Not found"}, status=404)

    payload = _json_from_body(request)
    reason = ""
    if isinstance(payload, dict):
        reason = payload.get("reason") or ""

    try:
        void_customer_credit_memo(credit_memo=credit_memo, user=request.user, reason=reason)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"ok": True, "credit_memo": _serialize_credit_memo(business, credit_memo)})


@login_required
@require_POST
def api_customer_credit_memo_allocate(request, credit_memo_id: int):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    credit_memo = (
        CustomerCreditMemo.objects.filter(business=business, pk=credit_memo_id)
        .select_related("customer")
        .first()
    )
    if not credit_memo:
        return JsonResponse({"error": "Not found"}, status=404)

    payload = _json_from_body(request)
    if not isinstance(payload, dict) or not isinstance(payload.get("allocations"), list):
        return HttpResponseBadRequest("Invalid JSON")

    invoice_amounts: list[tuple[Invoice, Decimal]] = []
    for row in payload["allocations"]:
        if not isinstance(row, dict):
            return JsonResponse({"error": "Invalid allocations payload"}, status=400)
        invoice_id = row.get("invoice_id")
        if not invoice_id:
            return JsonResponse({"error": "invoice_id is required"}, status=400)
        try:
            amount = _as_decimal(row.get("amount"), field="amount")
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        invoice = Invoice.objects.filter(business=business, pk=invoice_id).select_related("customer").first()
        if not invoice:
            return JsonResponse({"error": f"Invoice {invoice_id} not found"}, status=404)
        invoice_amounts.append((invoice, amount))

    try:
        allocations = allocate_credit_memo_to_invoices(credit_memo=credit_memo, invoice_amounts=invoice_amounts, user=request.user)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "allocations_created": len(allocations),
            "credit_memo": _serialize_credit_memo(business, credit_memo),
        }
    )


@login_required
@require_GET
def api_customer_deposits(request, customer_id: int):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    customer = Customer.objects.filter(business=business, pk=customer_id).first()
    if not customer:
        return JsonResponse({"error": "Customer not found"}, status=404)

    deposits = (
        CustomerDeposit.objects.filter(business=business, customer=customer)
        .select_related("bank_account")
        .order_by("-posting_date", "-id")[:200]
    )
    return JsonResponse(
        {
            "deposits": [_serialize_deposit(business, d) for d in deposits],
            "currency": business.currency,
        }
    )


@login_required
@require_POST
def api_customer_deposit_create(request):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    payload = _json_from_body(request)
    if not isinstance(payload, dict):
        return HttpResponseBadRequest("Invalid JSON")

    customer_id = payload.get("customer_id")
    if not customer_id:
        return JsonResponse({"error": "customer_id is required"}, status=400)
    customer = Customer.objects.filter(business=business, pk=customer_id).first()
    if not customer:
        return JsonResponse({"error": "Customer not found"}, status=404)

    bank_account_id = payload.get("bank_account_id")
    if not bank_account_id:
        return JsonResponse({"error": "bank_account_id is required"}, status=400)
    from core.models import BankAccount

    bank_account = BankAccount.objects.filter(business=business, pk=bank_account_id).select_related("account").first()
    if not bank_account:
        return JsonResponse({"error": "Bank account not found"}, status=404)

    try:
        amount = _as_decimal(payload.get("amount"), field="amount")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    if amount <= 0:
        return JsonResponse({"error": "amount must be > 0"}, status=400)

    currency = (payload.get("currency") or business.currency or "CAD").upper()
    posting_date = parse_date(payload.get("posting_date")) or timezone.localdate()
    memo_text = (payload.get("memo") or "").strip()

    deposit = CustomerDeposit.objects.create(
        business=business,
        customer=customer,
        bank_account=bank_account,
        posting_date=posting_date,
        status=CustomerDeposit.Status.DRAFT,
        amount=amount,
        currency=currency,
        memo=memo_text,
    )

    try:
        entry = post_customer_deposit(deposit, user=request.user)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"ok": True, "journal_entry_id": entry.id, "deposit": _serialize_deposit(business, deposit)})


@login_required
@require_POST
def api_customer_deposit_apply(request, deposit_id: int):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    deposit = (
        CustomerDeposit.objects.filter(business=business, pk=deposit_id)
        .select_related("customer")
        .first()
    )
    if not deposit:
        return JsonResponse({"error": "Not found"}, status=404)

    payload = _json_from_body(request)
    if not isinstance(payload, dict) or not isinstance(payload.get("allocations"), list):
        return HttpResponseBadRequest("Invalid JSON")

    invoice_amounts: list[tuple[Invoice, Decimal]] = []
    for row in payload["allocations"]:
        if not isinstance(row, dict):
            return JsonResponse({"error": "Invalid allocations payload"}, status=400)
        invoice_id = row.get("invoice_id")
        if not invoice_id:
            return JsonResponse({"error": "invoice_id is required"}, status=400)
        try:
            amount = _as_decimal(row.get("amount"), field="amount")
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        invoice = Invoice.objects.filter(business=business, pk=invoice_id).select_related("customer").first()
        if not invoice:
            return JsonResponse({"error": f"Invoice {invoice_id} not found"}, status=404)
        invoice_amounts.append((invoice, amount))

    try:
        entry = apply_customer_deposit_to_invoices(deposit=deposit, invoice_amounts=invoice_amounts, user=request.user)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "journal_entry_id": entry.id,
            "deposit": _serialize_deposit(business, deposit),
        }
    )


@login_required
@require_POST
def api_customer_deposit_void(request, deposit_id: int):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    deposit = CustomerDeposit.objects.filter(business=business, pk=deposit_id).select_related("bank_account").first()
    if not deposit:
        return JsonResponse({"error": "Not found"}, status=404)

    payload = _json_from_body(request)
    reason = ""
    if isinstance(payload, dict):
        reason = payload.get("reason") or ""

    try:
        void_customer_deposit(deposit=deposit, user=request.user, reason=reason)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"ok": True, "deposit": _serialize_deposit(business, deposit)})


@login_required
@require_GET
def api_customer_refunds(request, customer_id: int):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    customer = Customer.objects.filter(business=business, pk=customer_id).first()
    if not customer:
        return JsonResponse({"error": "Customer not found"}, status=404)

    refunds = (
        CustomerRefund.objects.filter(business=business, customer=customer)
        .select_related("bank_account")
        .order_by("-posting_date", "-id")[:200]
    )
    return JsonResponse(
        {
            "refunds": [_serialize_refund(r) for r in refunds],
            "currency": business.currency,
        }
    )


@login_required
@require_POST
def api_customer_refund_create(request):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    payload = _json_from_body(request)
    if not isinstance(payload, dict):
        return HttpResponseBadRequest("Invalid JSON")

    customer_id = payload.get("customer_id")
    if not customer_id:
        return JsonResponse({"error": "customer_id is required"}, status=400)
    customer = Customer.objects.filter(business=business, pk=customer_id).first()
    if not customer:
        return JsonResponse({"error": "Customer not found"}, status=404)

    bank_account_id = payload.get("bank_account_id")
    if not bank_account_id:
        return JsonResponse({"error": "bank_account_id is required"}, status=400)
    from core.models import BankAccount

    bank_account = BankAccount.objects.filter(business=business, pk=bank_account_id).select_related("account").first()
    if not bank_account:
        return JsonResponse({"error": "Bank account not found"}, status=404)

    try:
        amount = _as_decimal(payload.get("amount"), field="amount")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    if amount <= 0:
        return JsonResponse({"error": "amount must be > 0"}, status=400)

    currency = (payload.get("currency") or business.currency or "CAD").upper()
    posting_date = parse_date(payload.get("posting_date")) or timezone.localdate()
    memo_text = (payload.get("memo") or "").strip()

    credit_memo_id = payload.get("credit_memo_id") or None
    deposit_id = payload.get("deposit_id") or None

    credit_memo = None
    if credit_memo_id:
        credit_memo = CustomerCreditMemo.objects.filter(business=business, pk=credit_memo_id).first()
        if not credit_memo:
            return JsonResponse({"error": "Credit memo not found"}, status=404)
    deposit = None
    if deposit_id:
        deposit = CustomerDeposit.objects.filter(business=business, pk=deposit_id).first()
        if not deposit:
            return JsonResponse({"error": "Deposit not found"}, status=404)

    refund = CustomerRefund.objects.create(
        business=business,
        customer=customer,
        bank_account=bank_account,
        posting_date=posting_date,
        status=CustomerRefund.Status.DRAFT,
        amount=amount,
        currency=currency,
        memo=memo_text,
        credit_memo=credit_memo,
        deposit=deposit,
    )

    try:
        entry = post_customer_refund(refund, user=request.user)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"ok": True, "journal_entry_id": entry.id, "refund": _serialize_refund(refund)})


@login_required
@require_POST
def api_customer_refund_void(request, refund_id: int):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    refund = CustomerRefund.objects.filter(business=business, pk=refund_id).select_related("bank_account").first()
    if not refund:
        return JsonResponse({"error": "Not found"}, status=404)

    payload = _json_from_body(request)
    reason = ""
    if isinstance(payload, dict):
        reason = payload.get("reason") or ""

    try:
        void_customer_refund(refund=refund, user=request.user, reason=reason)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"ok": True, "refund": _serialize_refund(refund)})
