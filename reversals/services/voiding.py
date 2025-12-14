from __future__ import annotations

from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import JournalEntry
from taxes.models import TransactionLineTaxDetail

from reversals.models import CustomerCreditMemo, CustomerDeposit, CustomerRefund
from reversals.services.allocations import (
    sum_active_allocations_for_source,
    sum_posted_refunds_for_credit_memo,
    sum_posted_refunds_for_deposit,
)


def _void_related_journal_entries(*, business, source_obj) -> int:
    ct = ContentType.objects.get_for_model(source_obj.__class__)
    return JournalEntry.objects.filter(
        business=business,
        source_content_type=ct,
        source_object_id=source_obj.pk,
        is_void=False,
    ).update(is_void=True)


def _delete_tax_details(*, business, source_obj) -> None:
    ct = ContentType.objects.get_for_model(source_obj.__class__)
    TransactionLineTaxDetail.objects.filter(
        business=business,
        transaction_line_content_type=ct,
        transaction_line_object_id=source_obj.pk,
    ).delete()


@transaction.atomic
def void_customer_credit_memo(*, credit_memo: CustomerCreditMemo, user=None, reason: str = "") -> CustomerCreditMemo:
    if credit_memo.status == CustomerCreditMemo.Status.VOIDED:
        raise ValidationError("Credit memo is already voided.")
    if credit_memo.status != CustomerCreditMemo.Status.POSTED:
        raise ValidationError("Only posted credit memos can be voided.")

    allocated = sum_active_allocations_for_source(business=credit_memo.business, source_obj=credit_memo)
    refunded = sum_posted_refunds_for_credit_memo(credit_memo=credit_memo)
    if allocated > Decimal("0.00") or refunded > Decimal("0.00"):
        raise ValidationError("Cannot void a credit memo that has been applied or refunded.")

    _void_related_journal_entries(business=credit_memo.business, source_obj=credit_memo)
    _delete_tax_details(business=credit_memo.business, source_obj=credit_memo)

    credit_memo.status = CustomerCreditMemo.Status.VOIDED
    credit_memo.voided_at = timezone.now()
    credit_memo.void_reason = (reason or "").strip()
    credit_memo.save(update_fields=["status", "voided_at", "void_reason"])
    return credit_memo


@transaction.atomic
def void_customer_deposit(*, deposit: CustomerDeposit, user=None, reason: str = "") -> CustomerDeposit:
    if deposit.status == CustomerDeposit.Status.VOIDED:
        raise ValidationError("Deposit is already voided.")
    if deposit.status != CustomerDeposit.Status.POSTED:
        raise ValidationError("Only posted deposits can be voided.")

    allocated = sum_active_allocations_for_source(business=deposit.business, source_obj=deposit)
    refunded = sum_posted_refunds_for_deposit(deposit=deposit)
    if allocated > Decimal("0.00") or refunded > Decimal("0.00"):
        raise ValidationError("Cannot void a deposit that has been applied or refunded.")

    _void_related_journal_entries(business=deposit.business, source_obj=deposit)

    deposit.status = CustomerDeposit.Status.VOIDED
    deposit.voided_at = timezone.now()
    deposit.void_reason = (reason or "").strip()
    deposit.save(update_fields=["status", "voided_at", "void_reason"])
    return deposit


@transaction.atomic
def void_customer_refund(*, refund: CustomerRefund, user=None, reason: str = "") -> CustomerRefund:
    if refund.status == CustomerRefund.Status.VOIDED:
        raise ValidationError("Refund is already voided.")
    if refund.status != CustomerRefund.Status.POSTED:
        raise ValidationError("Only posted refunds can be voided.")

    _void_related_journal_entries(business=refund.business, source_obj=refund)

    refund.status = CustomerRefund.Status.VOIDED
    refund.voided_at = timezone.now()
    refund.void_reason = (reason or "").strip()
    refund.save(update_fields=["status", "voided_at", "void_reason"])
    return refund
