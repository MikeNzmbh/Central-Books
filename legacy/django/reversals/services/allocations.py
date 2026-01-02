from __future__ import annotations

from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum

from reversals.models import Allocation, CustomerRefund


def sum_active_allocations_for_source(*, business, source_obj) -> Decimal:
    ct = ContentType.objects.get_for_model(source_obj.__class__)
    total = (
        Allocation.objects.filter(
            business=business,
            status=Allocation.Status.ACTIVE,
            source_content_type=ct,
            source_object_id=source_obj.pk,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )
    return Decimal(total)


def sum_active_allocations_for_target(*, business, target_obj) -> Decimal:
    ct = ContentType.objects.get_for_model(target_obj.__class__)
    total = (
        Allocation.objects.filter(
            business=business,
            status=Allocation.Status.ACTIVE,
            target_content_type=ct,
            target_object_id=target_obj.pk,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )
    return Decimal(total)


def sum_posted_refunds_for_credit_memo(*, credit_memo) -> Decimal:
    total = (
        CustomerRefund.objects.filter(
            business=credit_memo.business,
            credit_memo=credit_memo,
            status=CustomerRefund.Status.POSTED,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )
    return Decimal(total)


def sum_posted_refunds_for_deposit(*, deposit) -> Decimal:
    total = (
        CustomerRefund.objects.filter(
            business=deposit.business,
            deposit=deposit,
            status=CustomerRefund.Status.POSTED,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )
    return Decimal(total)


def credit_memo_available_amount(credit_memo) -> Decimal:
    allocated = sum_active_allocations_for_source(business=credit_memo.business, source_obj=credit_memo)
    refunded = sum_posted_refunds_for_credit_memo(credit_memo=credit_memo)
    return (credit_memo.grand_total or Decimal("0.00")) - allocated - refunded


def deposit_available_amount(deposit) -> Decimal:
    allocated = sum_active_allocations_for_source(business=deposit.business, source_obj=deposit)
    refunded = sum_posted_refunds_for_deposit(deposit=deposit)
    return (deposit.amount or Decimal("0.00")) - allocated - refunded


def invoice_open_amount(invoice) -> Decimal:
    """
    Returns invoice open amount after applying reversals allocations.

    In v1, allocations are treated as additional invoice settlement (alongside cash payments),
    so open amount is derived from invoice totals, amount_paid, and active allocations.
    """
    total = invoice.grand_total or (invoice.net_total + invoice.tax_total)
    base_open = (total or Decimal("0.00")) - (invoice.amount_paid or Decimal("0.00"))
    applied = sum_active_allocations_for_target(business=invoice.business, target_obj=invoice)
    remaining = (base_open or Decimal("0.00")) - applied
    return max(Decimal("0.00"), remaining)
