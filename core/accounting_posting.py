from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from core.models import Account, JournalEntry, JournalLine, Invoice, Expense
from core.accounting_defaults import ensure_default_accounts
from taxes.models import TransactionLineTaxDetail
from taxes.postings import add_sales_tax_lines
from .accounting_posting_expenses import (
    post_expense_paid as _post_expense_paid_impl,
    remove_expense_entry as _remove_expense_entry_impl,
)


class MissingAccount(Exception):
    pass


def _get_account(business, code):
    return Account.objects.get(business=business, code=code)


def _create_entry(business, source, date, description):
    content_type = ContentType.objects.get_for_model(source)
    return JournalEntry.objects.create(
        business=business,
        date=date,
        description=description,
        source_content_type=content_type,
        source_object_id=source.pk,
    )


def _posting_queryset(model_cls, source, description_contains):
    content_type = ContentType.objects.get_for_model(model_cls)
    return JournalEntry.objects.filter(
        business=source.business,
        source_content_type=content_type,
        source_object_id=source.pk,
        description__icontains=description_contains,
    )


def _remove_postings(model_cls, source, description_contains):
    _posting_queryset(model_cls, source, description_contains).delete()


@transaction.atomic
def post_invoice_sent(invoice):
    ensure_default_accounts(invoice.business)
    if _posting_queryset(Invoice, invoice, "Invoice sent").exists():
        return

    business = invoice.business
    net = invoice.net_total or invoice.total_amount or Decimal("0.00")
    tax = invoice.tax_total or invoice.tax_amount or Decimal("0.00")
    total = invoice.grand_total or (net + tax)

    ar_account = _get_account(business, "1200")
    income_account = None
    if getattr(invoice, "item", None) and invoice.item.income_account_id:
        income_account = invoice.item.income_account
    if income_account is None:
        income_account = _get_account(business, "4010")

    entry = _create_entry(
        business,
        invoice,
        invoice.issue_date,
        f"Invoice sent – {invoice.invoice_number}",
    )

    JournalLine.objects.create(journal_entry=entry, account=ar_account, debit=total, credit=0)
    JournalLine.objects.create(journal_entry=entry, account=income_account, debit=0, credit=net)

    tax_details = []
    if invoice.tax_group_id and invoice.pk:
        ct = ContentType.objects.get_for_model(Invoice)
        tax_details = list(
            TransactionLineTaxDetail.objects.filter(
                business=invoice.business,
                transaction_line_content_type=ct,
                transaction_line_object_id=invoice.pk,
            )
        )

    if tax_details:
        total_tax_home, _ = add_sales_tax_lines(entry, tax_details)
        # Adjust A/R debit if tax_details totals differ from invoice.grand_total
        recomputed_total = net + total_tax_home
        if recomputed_total != total:
            entry.lines.filter(account=ar_account).update(debit=recomputed_total)
    elif tax > 0:
        tax_account = _get_account(business, "2200")
        JournalLine.objects.create(journal_entry=entry, account=tax_account, debit=0, credit=tax)

    entry.check_balance()


@transaction.atomic
def post_invoice_paid(invoice, bank_account_code="1010"):
    ensure_default_accounts(invoice.business)
    if _posting_queryset(Invoice, invoice, "Invoice paid").exists():
        return

    business = invoice.business
    total = invoice.grand_total or (invoice.net_total + invoice.tax_total)
    ar_account = _get_account(business, "1200")
    bank_account = _get_account(business, bank_account_code)

    entry = _create_entry(
        business,
        invoice,
        getattr(invoice, "paid_date", invoice.issue_date),
        f"Invoice paid – {invoice.invoice_number}",
    )

    JournalLine.objects.create(journal_entry=entry, account=bank_account, debit=total, credit=0)
    JournalLine.objects.create(journal_entry=entry, account=ar_account, debit=0, credit=total)

    entry.check_balance()


@transaction.atomic
def post_expense_paid(expense, bank_account_code="1010"):
    return _post_expense_paid_impl(expense, bank_account_code=bank_account_code)


def remove_invoice_sent_entry(invoice):
    _remove_postings(Invoice, invoice, "Invoice sent")


def remove_invoice_paid_entry(invoice):
    _remove_postings(Invoice, invoice, "Invoice paid")


def remove_expense_entry(expense):
    return _remove_expense_entry_impl(expense)
