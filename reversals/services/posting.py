from __future__ import annotations

import uuid
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.accounting_defaults import ensure_default_accounts
from core.models import Account, Invoice, JournalEntry, JournalLine
from taxes.models import TransactionLineTaxDetail
from taxes.postings import add_sales_tax_lines

from reversals.models import Allocation, CustomerCreditMemo, CustomerDeposit, CustomerRefund
from reversals.services.allocations import (
    credit_memo_available_amount,
    deposit_available_amount,
    invoice_open_amount,
)
from reversals.services.tax_inheritance import (
    replace_credit_memo_tax_details_by_recompute,
    replace_credit_memo_tax_details_from_invoice,
)


def _get_account(business, code: str) -> Account:
    return Account.objects.get(business=business, code=code)


def _create_entry(*, business, source, date_value, description: str, allocation_operation_id: str | None = None) -> JournalEntry:
    ct = ContentType.objects.get_for_model(source.__class__)
    return JournalEntry.objects.create(
        business=business,
        date=date_value,
        description=description[:255],
        source_content_type=ct,
        source_object_id=source.pk,
        allocation_operation_id=allocation_operation_id,
    )


def _posting_queryset(*, business, source, description_contains: str):
    ct = ContentType.objects.get_for_model(source.__class__)
    return JournalEntry.objects.filter(
        business=business,
        source_content_type=ct,
        source_object_id=source.pk,
        description__icontains=description_contains,
    )


def _refresh_invoice_settlement_state(invoice: Invoice) -> None:
    """
    Recompute invoice `balance`/`status` after allocations change, without triggering tax sync
    or cash-receipt postings.
    """
    invoice._skip_tax_sync = True
    invoice._skip_paid_posting = True
    invoice.save()


@transaction.atomic
def post_customer_credit_memo(credit_memo: CustomerCreditMemo, *, user=None) -> JournalEntry:
    if credit_memo.status != CustomerCreditMemo.Status.DRAFT:
        raise ValidationError("Only draft credit memos can be posted.")
    if credit_memo.net_total <= 0:
        raise ValidationError("Credit memo amount must be positive.")

    defaults = ensure_default_accounts(credit_memo.business)
    ar_account = defaults.get("ar") or _get_account(credit_memo.business, "1200")
    sales_returns = defaults.get("sales_returns") or _get_account(credit_memo.business, "4020")

    if _posting_queryset(business=credit_memo.business, source=credit_memo, description_contains="Credit memo posted").exists():
        return _posting_queryset(business=credit_memo.business, source=credit_memo, description_contains="Credit memo posted").order_by("-date", "-id").first()

    source_invoice = credit_memo.source_invoice
    if source_invoice:
        if source_invoice.business_id != credit_memo.business_id:
            raise ValidationError("Source invoice does not belong to this business.")
        if source_invoice.customer_id != credit_memo.customer_id:
            raise ValidationError("Source invoice belongs to a different customer.")
        if not credit_memo.tax_group_id and getattr(source_invoice, "tax_group_id", None):
            credit_memo.tax_group = source_invoice.tax_group

    tax_total = Decimal("0.00")
    if source_invoice and getattr(source_invoice, "tax_group_id", None):
        tax_total = replace_credit_memo_tax_details_from_invoice(credit_memo=credit_memo, invoice=source_invoice)
    else:
        tax_total = replace_credit_memo_tax_details_by_recompute(credit_memo=credit_memo) if credit_memo.tax_group_id else Decimal("0.00")

    credit_memo.tax_total = tax_total
    credit_memo.grand_total = (credit_memo.net_total or Decimal("0.00")) + tax_total
    credit_memo.status = CustomerCreditMemo.Status.POSTED
    credit_memo.save(update_fields=["tax_total", "grand_total", "status"])

    entry = _create_entry(
        business=credit_memo.business,
        source=credit_memo,
        date_value=credit_memo.posting_date,
        description=f"Credit memo posted – {credit_memo.credit_memo_number or f'CM-{credit_memo.pk}'}",
    )

    JournalLine.objects.create(journal_entry=entry, account=ar_account, debit=Decimal("0.00"), credit=credit_memo.grand_total, description="Accounts receivable")
    JournalLine.objects.create(journal_entry=entry, account=sales_returns, debit=credit_memo.net_total, credit=Decimal("0.00"), description="Sales returns")

    credit_ct = ContentType.objects.get_for_model(CustomerCreditMemo)
    tax_details = list(
        TransactionLineTaxDetail.objects.filter(
            business=credit_memo.business,
            transaction_line_content_type=credit_ct,
            transaction_line_object_id=credit_memo.pk,
        )
    )
    if tax_details:
        total_tax_home, _ = add_sales_tax_lines(entry, tax_details)
        # Align A/R credit to persisted tax details (home currency).
        # total_tax_home is signed; for credit memos we expect it to be negative.
        recomputed_total = (credit_memo.net_total or Decimal("0.00")) + (-total_tax_home)
        if recomputed_total != credit_memo.grand_total:
            entry.lines.filter(account=ar_account).update(credit=recomputed_total)
    entry.check_balance()
    return entry


@transaction.atomic
def post_customer_deposit(deposit: CustomerDeposit, *, user=None) -> JournalEntry:
    if deposit.status != CustomerDeposit.Status.DRAFT:
        raise ValidationError("Only draft deposits can be posted.")
    if deposit.amount <= 0:
        raise ValidationError("Deposit amount must be positive.")

    defaults = ensure_default_accounts(deposit.business)
    deposit_liability = defaults.get("customer_deposits") or _get_account(deposit.business, "2100")
    bank_gl = deposit.bank_account.account or defaults.get("cash")
    if bank_gl is None:
        raise ValidationError("Bank account is not linked to a ledger account.")

    if _posting_queryset(business=deposit.business, source=deposit, description_contains="Customer deposit posted").exists():
        return _posting_queryset(business=deposit.business, source=deposit, description_contains="Customer deposit posted").order_by("-date", "-id").first()

    deposit.status = CustomerDeposit.Status.POSTED
    deposit.save(update_fields=["status"])

    entry = _create_entry(
        business=deposit.business,
        source=deposit,
        date_value=deposit.posting_date,
        description=f"Customer deposit posted – DEP-{deposit.pk}",
    )
    JournalLine.objects.create(journal_entry=entry, account=bank_gl, debit=deposit.amount, credit=Decimal("0.00"), description="Bank")
    JournalLine.objects.create(journal_entry=entry, account=deposit_liability, debit=Decimal("0.00"), credit=deposit.amount, description="Customer deposits")
    entry.check_balance()
    return entry


@transaction.atomic
def apply_customer_deposit_to_invoices(
    *,
    deposit: CustomerDeposit,
    invoice_amounts: list[tuple[Invoice, Decimal]],
    user=None,
    apply_date=None,
) -> JournalEntry:
    if deposit.status != CustomerDeposit.Status.POSTED:
        raise ValidationError("Deposit must be posted before it can be applied.")
    if deposit.voided_at or deposit.status == CustomerDeposit.Status.VOIDED:
        raise ValidationError("Cannot apply a voided deposit.")

    apply_date = apply_date or timezone.localdate()
    total = sum((amount for _, amount in invoice_amounts), Decimal("0.00"))
    if total <= 0:
        raise ValidationError("Allocation total must be positive.")

    available = deposit_available_amount(deposit)
    if total > available:
        raise ValidationError("Allocation exceeds available deposit balance.")

    defaults = ensure_default_accounts(deposit.business)
    deposit_liability = defaults.get("customer_deposits") or _get_account(deposit.business, "2100")
    ar_account = defaults.get("ar") or _get_account(deposit.business, "1200")

    operation_id = uuid.uuid4()
    operation_id_str = str(operation_id)

    # Validate invoices and create allocations.
    for invoice, amount in invoice_amounts:
        if invoice.business_id != deposit.business_id:
            raise ValidationError("Invoice does not belong to this business.")
        if invoice.customer_id != deposit.customer_id:
            raise ValidationError("Invoice belongs to a different customer.")
        if amount <= 0:
            raise ValidationError("Allocation amounts must be positive.")
        if amount > invoice_open_amount(invoice):
            raise ValidationError("Allocation exceeds the invoice open balance.")

    source_ct = ContentType.objects.get_for_model(CustomerDeposit)
    invoice_ct = ContentType.objects.get_for_model(Invoice)
    for invoice, amount in invoice_amounts:
        Allocation.objects.create(
            business=deposit.business,
            ledger_side=Allocation.LedgerSide.CUSTOMER,
            status=Allocation.Status.ACTIVE,
            source_content_type=source_ct,
            source_object_id=deposit.pk,
            target_content_type=invoice_ct,
            target_object_id=invoice.pk,
            amount=amount,
            currency=deposit.currency,
            operation_id=operation_id,
            created_by=user,
        )

    for invoice, _amount in invoice_amounts:
        _refresh_invoice_settlement_state(invoice)

    entry = _create_entry(
        business=deposit.business,
        source=deposit,
        date_value=apply_date,
        description=f"Apply customer deposit – DEP-{deposit.pk}",
        allocation_operation_id=operation_id_str,
    )
    JournalLine.objects.create(journal_entry=entry, account=deposit_liability, debit=total, credit=Decimal("0.00"), description="Reduce deposits liability")
    JournalLine.objects.create(journal_entry=entry, account=ar_account, debit=Decimal("0.00"), credit=total, description="Reduce accounts receivable")
    entry.check_balance()
    return entry


@transaction.atomic
def allocate_credit_memo_to_invoices(
    *,
    credit_memo: CustomerCreditMemo,
    invoice_amounts: list[tuple[Invoice, Decimal]],
    user=None,
) -> list[Allocation]:
    if credit_memo.status != CustomerCreditMemo.Status.POSTED:
        raise ValidationError("Credit memo must be posted before it can be applied.")
    if credit_memo.voided_at or credit_memo.status == CustomerCreditMemo.Status.VOIDED:
        raise ValidationError("Cannot apply a voided credit memo.")

    total = sum((amount for _, amount in invoice_amounts), Decimal("0.00"))
    if total <= 0:
        raise ValidationError("Allocation total must be positive.")

    available = credit_memo_available_amount(credit_memo)
    if total > available:
        raise ValidationError("Allocation exceeds available credit memo balance.")

    operation_id = uuid.uuid4()
    created: list[Allocation] = []
    source_ct = ContentType.objects.get_for_model(CustomerCreditMemo)
    invoice_ct = ContentType.objects.get_for_model(Invoice)
    for invoice, amount in invoice_amounts:
        if invoice.business_id != credit_memo.business_id:
            raise ValidationError("Invoice does not belong to this business.")
        if invoice.customer_id != credit_memo.customer_id:
            raise ValidationError("Invoice belongs to a different customer.")
        if amount <= 0:
            raise ValidationError("Allocation amounts must be positive.")
        if amount > invoice_open_amount(invoice):
            raise ValidationError("Allocation exceeds the invoice open balance.")
        created.append(
            Allocation.objects.create(
                business=credit_memo.business,
                ledger_side=Allocation.LedgerSide.CUSTOMER,
                status=Allocation.Status.ACTIVE,
                source_content_type=source_ct,
                source_object_id=credit_memo.pk,
                target_content_type=invoice_ct,
                target_object_id=invoice.pk,
                amount=amount,
                currency=getattr(credit_memo.business, "currency", "CAD") or "CAD",
                operation_id=operation_id,
                created_by=user,
            )
        )

    for invoice, _amount in invoice_amounts:
        _refresh_invoice_settlement_state(invoice)
    return created


@transaction.atomic
def post_customer_refund(refund: CustomerRefund, *, user=None) -> JournalEntry:
    if refund.status != CustomerRefund.Status.DRAFT:
        raise ValidationError("Only draft refunds can be posted.")
    if refund.amount <= 0:
        raise ValidationError("Refund amount must be positive.")

    if refund.credit_memo_id and refund.deposit_id:
        raise ValidationError("Refund cannot reference both a credit memo and a deposit.")

    defaults = ensure_default_accounts(refund.business)
    ar_account = defaults.get("ar") or _get_account(refund.business, "1200")
    deposit_liability = defaults.get("customer_deposits") or _get_account(refund.business, "2100")
    bank_gl = refund.bank_account.account or defaults.get("cash")
    if bank_gl is None:
        raise ValidationError("Bank account is not linked to a ledger account.")

    if _posting_queryset(business=refund.business, source=refund, description_contains="Customer refund posted").exists():
        return _posting_queryset(business=refund.business, source=refund, description_contains="Customer refund posted").order_by("-date", "-id").first()

    if refund.credit_memo_id:
        if refund.credit_memo.business_id != refund.business_id or refund.credit_memo.customer_id != refund.customer_id:
            raise ValidationError("Credit memo does not belong to this customer/business.")
        if refund.amount > credit_memo_available_amount(refund.credit_memo):
            raise ValidationError("Refund exceeds available credit memo balance.")
        debit_account = ar_account
    elif refund.deposit_id:
        if refund.deposit.business_id != refund.business_id or refund.deposit.customer_id != refund.customer_id:
            raise ValidationError("Deposit does not belong to this customer/business.")
        if refund.amount > deposit_available_amount(refund.deposit):
            raise ValidationError("Refund exceeds available deposit balance.")
        debit_account = deposit_liability
    else:
        debit_account = ar_account

    refund.status = CustomerRefund.Status.POSTED
    refund.save(update_fields=["status"])

    entry = _create_entry(
        business=refund.business,
        source=refund,
        date_value=refund.posting_date,
        description=f"Customer refund posted – REF-{refund.pk}",
    )
    JournalLine.objects.create(journal_entry=entry, account=debit_account, debit=refund.amount, credit=Decimal("0.00"), description="Refund debit")
    JournalLine.objects.create(journal_entry=entry, account=bank_gl, debit=Decimal("0.00"), credit=refund.amount, description="Bank")
    entry.check_balance()
    return entry
