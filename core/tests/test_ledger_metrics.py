"""
Tests for ledger-based metric calculations.
"""
from decimal import Decimal
from datetime import date, timedelta

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import Business, Account, JournalEntry, JournalLine
from core.services import (
    calculate_ledger_income,
    calculate_ledger_expenses,
    calculate_ledger_activity_date,
    calculate_ledger_expense_by_account_name,
)

User = get_user_model()


class LedgerMetricsTestCase(TestCase):
    """Test ledger aggregation helpers."""

    def setUp(self):
        """Create test business and accounts."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.business = Business.objects.create(
            name="Test Business",
            currency="USD",
            owner_user=self.user,
        )
        self.income_account = Account.objects.create(
            business=self.business,
            code="4000",
            name="Revenue",
            type=Account.AccountType.INCOME,
        )
        self.expense_account = Account.objects.create(
            business=self.business,
            code="5000",
            name="Expenses",
            type=Account.AccountType.EXPENSE,
        )
        self.expense_subscriptions = Account.objects.create(
            business=self.business,
            code="5100",
            name="Subscriptions",
            type=Account.AccountType.EXPENSE,
        )
        self.asset_account = Account.objects.create(
            business=self.business,
            code="1000",
            name="Cash",
            type=Account.AccountType.ASSET,
        )

    def test_calculate_ledger_income_single_entry(self):
        """Test income calculation with a single journal entry."""
        today = timezone.now().date()
        
        journal_entry = JournalEntry.objects.create(
            business=self.business,
            date=today,
            description="Test sale",
            is_void=False,
        )
        JournalLine.objects.create(
            journal_entry=journal_entry,
            account=self.asset_account,
            debit=Decimal("100.00"),
            credit=Decimal("0"),
        )
        JournalLine.objects.create(
            journal_entry=journal_entry,
            account=self.income_account,
            debit=Decimal("0"),
            credit=Decimal("100.00"),
        )

        income = calculate_ledger_income(
            self.business,
            today,
            today,
        )
        self.assertEqual(income, Decimal("100.00"))

    def test_calculate_ledger_expenses_single_entry(self):
        """Test expense calculation with a single journal entry."""
        today = timezone.now().date()
        
        journal_entry = JournalEntry.objects.create(
            business=self.business,
            date=today,
            description="Test expense",
            is_void=False,
        )
        JournalLine.objects.create(
            journal_entry=journal_entry,
            account=self.expense_account,
            debit=Decimal("50.00"),
            credit=Decimal("0"),
        )
        JournalLine.objects.create(
            journal_entry=journal_entry,
            account=self.asset_account,
            debit=Decimal("0"),
            credit=Decimal("50.00"),
        )

        expenses = calculate_ledger_expenses(
            self.business,
            today,
            today,
        )
        self.assertEqual(expenses, Decimal("50.00"))

    def test_void_entries_excluded(self):
        """Test that void journal entries are excluded from calculations."""
        today = timezone.now().date()
        
        # Create void entry
        void_entry = JournalEntry.objects.create(
            business=self.business,
            date=today,
            description="Void entry",
            is_void=True,
        )
        JournalLine.objects.create(
            journal_entry=void_entry,
            account=self.asset_account,
            debit=Decimal("200.00"),
            credit=Decimal("0"),
        )
        JournalLine.objects.create(
            journal_entry=void_entry,
            account=self.income_account,
            debit=Decimal("0"),
            credit=Decimal("200.00"),
        )

        income = calculate_ledger_income(self.business, today, today)
        self.assertEqual(income, Decimal("0"))

    def test_date_range_filtering(self):
        """Test that date ranges are correctly applied."""
        base_date = date(2024, 1, 1)
        
        # Income in January
        jan_entry = JournalEntry.objects.create(
            business=self.business,
            date=base_date,
            description="January income",
            is_void=False,
        )
        JournalLine.objects.create(
            journal_entry=jan_entry,
            account=self.asset_account,
            debit=Decimal("100.00"),
            credit=Decimal("0"),
        )
        JournalLine.objects.create(
            journal_entry=jan_entry,
            account=self.income_account,
            debit=Decimal("0"),
            credit=Decimal("100.00"),
        )

        # Income in February
        feb_date = date(2024, 2, 1)
        feb_entry = JournalEntry.objects.create(
            business=self.business,
            date=feb_date,
            description="February income",
            is_void=False,
        )
        JournalLine.objects.create(
            journal_entry=feb_entry,
            account=self.asset_account,
            debit=Decimal("200.00"),
            credit=Decimal("0"),
        )
        JournalLine.objects.create(
            journal_entry=feb_entry,
            account=self.income_account,
            debit=Decimal("0"),
            credit=Decimal("200.00"),
        )

        # Query only January
        jan_income = calculate_ledger_income(
            self.business,
            date(2024, 1, 1),
            date(2024, 1, 31),
        )
        self.assertEqual(jan_income, Decimal("100.00"))

        # Query only February
        feb_income = calculate_ledger_income(
            self.business,
            date(2024, 2, 1),
            date(2024, 2, 29),
        )
        self.assertEqual(feb_income, Decimal("200.00"))

    def test_calculate_ledger_activity_date(self):
        """Test finding most recent journal entry date."""
        old_date = date(2024, 1, 1)
        new_date = date(2024, 6, 1)
        
        # Create old entry
        JournalEntry.objects.create(
            business=self.business,
            date=old_date,
            description="Old entry",
            is_void=False,
        )

        # Create new entry
        JournalEntry.objects.create(
            business=self.business,
            date=new_date,
            description="New entry",
            is_void=False,
        )

        # Create void entry with even newer date (should be ignored)
        void_date = date(2024, 12, 1)
        JournalEntry.objects.create(
            business=self.business,
            date=void_date,
            description="Void entry",
            is_void=True,
        )

        latest = calculate_ledger_activity_date(self.business)
        self.assertEqual(latest, new_date)

    def test_calculate_ledger_expense_by_account_name(self):
        """Test expense calculation filtered by account name."""
        today = timezone.now().date()
        
        # Create subscription expense
        sub_entry = JournalEntry.objects.create(
            business=self.business,
            date=today,
            description="Subscription",
            is_void=False,
        )
        JournalLine.objects.create(
            journal_entry=sub_entry,
            account=self.expense_subscriptions,
            debit=Decimal("25.00"),
            credit=Decimal("0"),
        )
        JournalLine.objects.create(
            journal_entry=sub_entry,
            account=self.asset_account,
            debit=Decimal("0"),
            credit=Decimal("25.00"),
        )

        # Create other expense
        other_entry = JournalEntry.objects.create(
            business=self.business,
            date=today,
            description="Other expense",
            is_void=False,
        )
        JournalLine.objects.create(
            journal_entry=other_entry,
            account=self.expense_account,
            debit=Decimal("75.00"),
            credit=Decimal("0"),
        )
        JournalLine.objects.create(
            journal_entry=other_entry,
            account=self.asset_account,
            debit=Decimal("0"),
            credit=Decimal("75.00"),
        )

        # Query by account name (case-insensitive)
        sub_total = calculate_ledger_expense_by_account_name(
            self.business,
            today,
            today,
            "subscriptions",
        )
        self.assertEqual(sub_total, Decimal("25.00"))

        # Total expenses should be sum of both
        total_expenses = calculate_ledger_expenses(self.business, today, today)
        self.assertEqual(total_expenses, Decimal("100.00"))

    def test_no_activity_returns_zero(self):
        """Test that empty ledger returns zero."""
        today = timezone.now().date()
        
        income = calculate_ledger_income(self.business, today, today)
        expenses = calculate_ledger_expenses(self.business, today, today)
        
        self.assertEqual(income, Decimal("0"))
        self.assertEqual(expenses, Decimal("0"))

    def test_no_activity_returns_none_for_date(self):
        """Test that empty ledger returns None for activity date."""
        latest = calculate_ledger_activity_date(self.business)
        self.assertIsNone(latest)
