"""
Centralized ledger-based metric calculations.

These helpers aggregate from JournalEntry/JournalLine to ensure consistency
across dashboard, P&L reports, and Companion health metrics.
"""
from decimal import Decimal
from datetime import date
from typing import Optional

from django.db.models import Sum, Q
from django.db.models.functions import Coalesce

from core.models import Account, JournalEntry, JournalLine


def calculate_ledger_income(
    business, 
    start_date: date, 
    end_date: date
) -> Decimal:
    """
    Calculate total income from the ledger for a given date range.
    
    Income accounts are credited, so we sum credits for INCOME accounts.
    Excludes void journal entries.
    """
    total = (
        JournalLine.objects.filter(
            journal_entry__business=business,
            journal_entry__date__gte=start_date,
            journal_entry__date__lte=end_date,
            journal_entry__is_void=False,
            account__type=Account.AccountType.INCOME,
        )
        .aggregate(total=Coalesce(Sum("credit"), Decimal("0")))["total"]
    )
    return total or Decimal("0")


def calculate_ledger_expenses(
    business, 
    start_date: date, 
    end_date: date
) -> Decimal:
    """
    Calculate total expenses from the ledger for a given date range.
    
    Expense accounts are debited, so we sum debits for EXPENSE accounts.
    Excludes void journal entries.
    """
    total = (
        JournalLine.objects.filter(
            journal_entry__business=business,
            journal_entry__date__gte=start_date,
            journal_entry__date__lte=end_date,
            journal_entry__is_void=False,
            account__type=Account.AccountType.EXPENSE,
        )
        .aggregate(total=Coalesce(Sum("debit"), Decimal("0")))["total"]
    )
    return total or Decimal("0")


def calculate_ledger_activity_date(business) -> Optional[date]:
    """
    Find the most recent non-void journal entry date for a business.
    
    Returns None if no journal entries exist.
    Used for calculating "last activity days ago" in health metrics.
    """
    latest_entry = (
        JournalEntry.objects.filter(
            business=business,
            is_void=False,
        )
        .order_by("-date")
        .values_list("date", flat=True)
        .first()
    )
    return latest_entry


def calculate_ledger_expense_by_account_name(
    business,
    start_date: date,
    end_date: date,
    account_name: str,
) -> Decimal:
    """
    Calculate expenses for a specific account name (case-insensitive).
    
    Used for category-specific expense tracking (e.g., "Subscriptions", "Taxes").
    """
    total = (
        JournalLine.objects.filter(
            journal_entry__business=business,
            journal_entry__date__gte=start_date,
            journal_entry__date__lte=end_date,
            journal_entry__is_void=False,
            account__type=Account.AccountType.EXPENSE,
            account__name__iexact=account_name,
        )
        .aggregate(total=Coalesce(Sum("debit"), Decimal("0")))["total"]
    )
    return total or Decimal("0")
