"""
Centralized ledger-based metric calculations.

These helpers aggregate from JournalEntry/JournalLine to ensure consistency
across dashboard, P&L reports, and Companion health metrics.
"""
from decimal import Decimal
from datetime import date, timedelta
from enum import Enum
from typing import Optional

from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.models import Account, JournalEntry, JournalLine


class PLPeriod(str, Enum):
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    THIS_YEAR = "this_year"
    LAST_YEAR = "last_year"
    THIS_QUARTER = "this_quarter"
    YTD = "ytd"


def _first_day_of_month(d: date) -> date:
    return d.replace(day=1)


def _add_months(d: date, months: int) -> date:
    month_index = (d.month - 1) + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _format_label(prefix: str, start_date: date, end_date: date) -> str:
    return f"{prefix} · {start_date:%b %d, %Y} – {end_date:%b %d, %Y}"


def get_pl_period_dates(period: str | PLPeriod, today: date | None = None) -> tuple[date, date, str, str]:
    """
    Shared P&L period helper used by dashboard and P&L report.
    Returns (start_date, end_date, label, normalized_period_key).
    
    Supports:
    - Enum values (PLPeriod.THIS_MONTH, etc.)
    - String period keys ("this_month", "last_month", etc.)
    - Explicit month in YYYY-MM format (e.g., "2025-11")
    """
    normalized = str(period) if isinstance(period, PLPeriod) else (period or "").strip()
    if not normalized:
        normalized = PLPeriod.THIS_MONTH.value

    ref_date = today or timezone.localdate()
    
    # Check if this is an explicit month (YYYY-MM format)
    if "-" in normalized and len(normalized) == 7:
        try:
            year, month = normalized.split("-")
            year_int = int(year)
            month_int = int(month)
            if 1 <= month_int <= 12:
                start_date = date(year_int, month_int, 1)
                # Get last day of the month
                if month_int == 12:
                    next_month = date(year_int + 1, 1, 1)
                else:
                    next_month = date(year_int, month_int + 1, 1)
                end_date = next_month - timedelta(days=1)
                label = start_date.strftime("%B %Y")
                return start_date, end_date, label, normalized
        except (ValueError, TypeError):
            # Fall through to default handling if parsing fails
            pass

    if normalized == PLPeriod.LAST_MONTH.value:
        first_of_this_month = _first_day_of_month(ref_date)
        end_date = first_of_this_month - timedelta(days=1)
        start_date = _first_day_of_month(end_date)
        label = _format_label("Last month", start_date, end_date)
        normalized = PLPeriod.LAST_MONTH.value
    elif normalized == PLPeriod.THIS_YEAR.value:
        start_date = ref_date.replace(month=1, day=1)
        end_date = ref_date
        label = _format_label("This year", start_date, end_date)
        normalized = PLPeriod.THIS_YEAR.value
    elif normalized == PLPeriod.LAST_YEAR.value:
        start_date = ref_date.replace(year=ref_date.year - 1, month=1, day=1)
        end_date = start_date.replace(month=12, day=31)
        label = _format_label("Last year", start_date, end_date)
        normalized = PLPeriod.LAST_YEAR.value
    elif normalized == PLPeriod.THIS_QUARTER.value:
        quarter_start_month = ((ref_date.month - 1) // 3) * 3 + 1
        start_date = ref_date.replace(month=quarter_start_month, day=1)
        next_quarter_start = _add_months(start_date, 3)
        end_date_candidate = next_quarter_start - timedelta(days=1)
        end_date = min(ref_date, end_date_candidate)
        label = _format_label("This quarter", start_date, end_date)
        normalized = PLPeriod.THIS_QUARTER.value
    elif normalized == PLPeriod.YTD.value:
        start_date = ref_date.replace(month=1, day=1)
        end_date = ref_date
        label = _format_label("Year to date", start_date, end_date)
        normalized = PLPeriod.YTD.value
    else:
        start_date = _first_day_of_month(ref_date)
        next_month = _add_months(start_date, 1)
        end_date_candidate = next_month - timedelta(days=1)
        end_date = min(ref_date, end_date_candidate)
        label = _format_label("This month", start_date, end_date)
        normalized = PLPeriod.THIS_MONTH.value

    return start_date, end_date, label, normalized


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
