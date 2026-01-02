"""
Tests for P&L month selector functionality.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model

from core.models import Business, Account, JournalEntry, JournalLine
from core.services.ledger_metrics import get_pl_period_dates, PLPeriod

User = get_user_model()


class PLMonthSelectorTestCase(TestCase):
    """Test P&L month selection and period date calculation."""

    def setUp(self):
        """Create test business and journal activity."""
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
        
        # Create accounts
        self.income_account = Account.objects.create(
            business=self.business,
            code="4000",
            name="Revenue",
            type=Account.AccountType.INCOME,
        )
        self.cash_account = Account.objects.create(
            business=self.business,
            code="1000",
            name="Cash",
            type=Account.AccountType.ASSET,
        )

    def test_explicit_month_selection(self):
        """Test selecting a specific month in YYYY-MM format."""
        start_date, end_date, label, normalized = get_pl_period_dates("2025-11")
        
        self.assertEqual(start_date, date(2025, 11, 1))
        self.assertEqual(end_date, date(2025, 11, 30))
        self.assertEqual(label, "November 2025")
        self.assertEqual(normalized, "2025-11")

    def test_explicit_month_december(self):
        """Test December specifically (edge case for month calculation)."""
        start_date, end_date, label, normalized = get_pl_period_dates("2025-12")
        
        self.assertEqual(start_date, date(2025, 12, 1))
        self.assertEqual(end_date, date(2025, 12, 31))
        self.assertEqual(label, "December 2025")
        self.assertEqual(normalized, "2025-12")

    def test_explicit_month_january(self):
        """Test January specifically (edge case for month calculation)."""
        start_date, end_date, label, normalized = get_pl_period_dates("2026-01")
        
        self.assertEqual(start_date, date(2026, 1, 1))
        self.assertEqual(end_date, date(2026, 1, 31))
        self.assertEqual(label, "January 2026")
        self.assertEqual(normalized, "2026-01")

    def test_invalid_explicit_month_falls_back(self):
        """Test that invalid month format falls back to default."""
        start_date, end_date, label, normalized = get_pl_period_dates("invalid-month")
        
        # Should fall back to "this month" behavior
        self.assertEqual(normalized, PLPeriod.THIS_MONTH.value)

    def test_explicit_month_with_journal_activity(self):
        """Test that explicit month selection works with actual journal data."""
        # Create journal entry in November 2024
        nov_entry = JournalEntry.objects.create(
            business=self.business,
            date=date(2024, 11, 15),
            description="November sale",
        )
        JournalLine.objects.create(
            journal_entry=nov_entry,
            account=self.cash_account,
            debit=Decimal("1000.00"),
            credit=Decimal("0.00"),
            description="Cash",
        )
        JournalLine.objects.create(
            journal_entry=nov_entry,
            account=self.income_account,
            debit=Decimal("0.00"),
            credit=Decimal("1000.00"),
            description="Revenue",
        )
        
        # Select November 2024
        start_date, end_date, label, normalized = get_pl_period_dates("2024-11")
        
        # Verify the entry date falls within this range
        self.assertTrue(start_date <= nov_entry.date <= end_date)
        self.assertEqual(label, "November 2024")
