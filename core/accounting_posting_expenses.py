from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from .accounting_defaults import ensure_default_accounts
from .models import Account, JournalEntry, JournalLine, Expense


def _get_expense_account(expense, defaults):
    category = getattr(expense, "category", None)
    if category and category.account_id:
        return category.account
    fallback = defaults.get("opex")
    if fallback:
        return fallback
    return (
        Account.objects.filter(
            business=expense.business,
            type=Account.AccountType.EXPENSE,
        )
        .order_by("code")
        .first()
    )


def _posting_queryset(expense):
    content_type = ContentType.objects.get_for_model(Expense)
    return JournalEntry.objects.filter(
        business=expense.business,
        source_content_type=content_type,
        source_object_id=expense.pk,
        description__icontains="Expense paid",
    )


def remove_expense_entry(expense):
    _posting_queryset(expense).delete()


def post_expense_paid(expense, bank_account_code="1010"):
    """Create a ledger entry when an expense is marked as paid."""
    defaults = ensure_default_accounts(expense.business)
    cash_account = defaults.get("cash") or Account.objects.get(
        business=expense.business,
        code=bank_account_code,
    )

    expense_account = _get_expense_account(expense, defaults)
    if expense_account is None:
        raise ValueError("No expense account available for posting.")

    net = expense.net_total or expense.amount or Decimal("0.00")
    tax = expense.tax_total or expense.tax_amount or Decimal("0.00")
    total = expense.grand_total or (net + tax)

    existing_entry = _posting_queryset(expense).first()
    if existing_entry:
        return existing_entry

    content_type = ContentType.objects.get_for_model(Expense)

    with transaction.atomic():
        entry = JournalEntry.objects.create(
            business=expense.business,
            date=expense.date,
            description=f"Expense paid – {expense.description[:40] if expense.description else expense.pk}",
            source_content_type=content_type,
            source_object_id=expense.pk,
        )

        JournalLine.objects.create(
            journal_entry=entry,
            account=expense_account,
            debit=net + (Decimal("0.00") if (expense.tax_rate and expense.tax_rate.is_recoverable) else tax),
            credit=0,
            description="Expense posted",
        )
        if tax > 0 and expense.tax_rate and expense.tax_rate.is_recoverable:
            tax_account = defaults.get("tax_recoverable")
            if not tax_account:
                raise ValueError("No tax recoverable account available.")
            JournalLine.objects.create(
                journal_entry=entry,
                account=tax_account,
                debit=tax,
                credit=0,
                description="Recoverable tax",
            )
        JournalLine.objects.create(
            journal_entry=entry,
            account=cash_account,
            debit=0,
            credit=total,
            description="Cash/Bank",
        )

        entry.check_balance()
        return entry
