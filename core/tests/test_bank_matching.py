"""
Tests for Bank Matching Engine

Tests the 3-tier automatic matching logic:
- Tier 1: ID matching
- Tier 2: Reference parsing
- Tier 3: Amount + date heuristics
"""

from decimal import Decimal
from datetime import date, timedelta

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from core.models import (
    Business,
    BankAccount,
    BankTransaction,
    Invoice,
    Expense,
    JournalEntry,
    JournalLine,
    Account,
    Customer,
)
from core.services.bank_matching import BankMatchingEngine

User = get_user_model()


class BankMatchingEngineTest(TestCase):
    """Test suite for BankMatchingEngine"""

    def setUp(self):
        """Set up test data"""
        # Create user and business
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.business = Business.objects.create(
            name="Test Business", currency="CAD", owner_user=self.user
        )

        # Create customer
        self.customer = Customer.objects.create(
            business=self.business,
            name="Test Customer",
        )

        # Create bank account with linked COA account
        self.bank_coa_account = Account.objects.create(
            code="1000",
            name="Bank Account",
            business=self.business,
            type=Account.AccountType.ASSET,
        )

        self.bank_account = BankAccount.objects.create(
            business=self.business,
            name="Test Bank",
            bank_name="RBC",
            account=self.bank_coa_account,
        )

        # Create revenue and expense accounts
        self.revenue_account = Account.objects.create(
            code="4000",
            name="Revenue",
            business=self.business,
            type=Account.AccountType.INCOME,
        )

        self.expense_account = Account.objects.create(
            code="5000",
            name="Expenses",
            business=self.business,
            type=Account.AccountType.EXPENSE,
        )

    def test_tier1_invoice_match_by_external_id(self):
        """Test Tier 1: Match invoice by external_id"""
        # Create invoice with journal entry
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number="INV-1001",
            total_amount=Decimal("500.00"),
        )

        journal_entry = JournalEntry.objects.create(
            business=self.business,
            date=timezone.now().date(),
            description="Invoice #1234",
            source_object=invoice,
        )

        # Link invoice to journal entry
        # invoice.posted_journal_entry = journal_entry
        # invoice.save()
        JournalLine.objects.create(
            journal_entry=journal_entry,
            account=self.bank_coa_account,
            debit=Decimal("500.00"),
            credit=Decimal("0"),
        )

        JournalLine.objects.create(
            journal_entry=journal_entry,
            account=self.revenue_account,
            debit=Decimal("0"),
            credit=Decimal("500.00"),
        )



        # Create bank transaction with matching external_id
        bank_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=date.today(),
            description="Payment received",
            amount=Decimal("500.00"),
            external_id="INV-1001",
        )

        # Run matching
        matches = BankMatchingEngine.find_matches(bank_tx)

        # Assert
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["journal_entry"].id, journal_entry.id)
        self.assertEqual(matches[0]["confidence"], Decimal("1.00"))
        self.assertEqual(matches[0]["match_type"], "ONE_TO_ONE")
        self.assertIn("INV-1001", matches[0]["reason"])

    def test_tier2_invoice_reference_in_description(self):
        """Test Tier 2: Parse invoice reference from description"""
        # Create invoice
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number="1234",
            total_amount=Decimal("750.00"),
        )

        journal_entry = JournalEntry.objects.create(
            business=self.business,
            date=date.today(),
            description="Invoice 1234",
            source_object=invoice,
        )

        JournalLine.objects.create(
            journal_entry=journal_entry,
            account=self.bank_coa_account,
            debit=Decimal("750.00"),
            credit=Decimal("0"),
        )

        JournalLine.objects.create(
            journal_entry=journal_entry,
            account=self.revenue_account,
            debit=Decimal("0"),
            credit=Decimal("750.00"),
        )



        # Create bank transaction with invoice reference in description
        bank_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=date.today(),
            description="Payment for invoice INV-1234",
            amount=Decimal("750.00"),
        )

        # Run matching
        matches = BankMatchingEngine.find_matches(bank_tx)

        # Assert
        self.assertGreater(len(matches), 0)
        match_found = any(m["journal_entry"].id == journal_entry.id for m in matches)
        self.assertTrue(match_found)

        matched = [m for m in matches if m["journal_entry"].id == journal_entry.id][0]
        self.assertEqual(matched["confidence"], Decimal("0.95"))

    def test_tier3_amount_date_match_single(self):
        """Test Tier 3: Match by amount + date (single clear match)"""
        # Create journal entry
        journal_entry = JournalEntry.objects.create(
            business=self.business,
            date=date.today(),
            description="Test expense",
        )

        JournalLine.objects.create(
            journal_entry=journal_entry,
            account=self.expense_account,
            debit=Decimal("123.45"),
            credit=Decimal("0"),
        )

        JournalLine.objects.create(
            journal_entry=journal_entry,
            account=self.bank_coa_account,
            debit=Decimal("0"),
            credit=Decimal("123.45"),
        )

        # Create bank transaction matching amount within date window
        bank_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=date.today() + timedelta(days=1),
            description="Some expense",
            amount=Decimal("-123.45"),
        )

        # Run matching
        matches = BankMatchingEngine.find_matches(bank_tx)

        # Assert: should find single match with 0.80 confidence
        self.assertGreater(len(matches), 0)
        match_found = any(
            m["journal_entry"].id == journal_entry.id and m["confidence"] == Decimal("0.80")
            for m in matches
        )
        self.assertTrue(match_found)

    def test_tier3_amount_date_match_multiple_ambiguous(self):
        """Test Tier 3: Multiple matches result in lower confidence"""
        # Create two journal entries with same amount on same day
        je1 = JournalEntry.objects.create(
            business=self.business,
            date=date.today(),
            description="Expense 1",
        )

        JournalLine.objects.create(
            journal_entry=je1,
            account=self.expense_account,
            debit=Decimal("100.00"),
            credit=Decimal("0"),
        )

        JournalLine.objects.create(
            journal_entry=je1,
            account=self.bank_coa_account,
            debit=Decimal("0"),
            credit=Decimal("100.00"),
        )

        je2 = JournalEntry.objects.create(
            business=self.business,
            date=date.today(),
            description="Expense 2",
        )

        JournalLine.objects.create(
            journal_entry=je2,
            account=self.expense_account,
            debit=Decimal("100.00"),
            credit=Decimal("0"),
        )

        JournalLine.objects.create(
            journal_entry=je2,
            account=self.bank_coa_account,
            debit=Decimal("0"),
            credit=Decimal("100.00"),
        )

        # Create bank transaction
        bank_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=date.today(),
            description="Payment",
            amount=Decimal("-100.00"),
        )

        # Run matching
        matches = BankMatchingEngine.find_matches(bank_tx)

        # Assert: both should be found with lower confidence (0.50)
        self.assertGreaterEqual(len(matches), 2)
        for match in matches:
            if match["journal_entry"].id in [je1.id, je2.id]:
                self.assertEqual(match["confidence"], Decimal("0.50"))

    def test_no_match(self):
        """Test case with no matching entries"""
        # Create bank transaction with no corresponding journal entry
        bank_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=date.today(),
            description="Random transaction",
            amount=Decimal("999.99"),
        )

        # Run matching
        matches = BankMatchingEngine.find_matches(bank_tx)

        # Assert: should return empty list
        self.assertEqual(len(matches), 0)

    def test_match_limit(self):
        """Test that find_matches respects the limit parameter"""
        # Create 10 journal entries with same amount
        for i in range(10):
            je = JournalEntry.objects.create(
                business=self.business,
                date=date.today(),
                description=f"Entry {i}",
            )

            JournalLine.objects.create(
                journal_entry=je,
                account=self.expense_account,
                debit=Decimal("50.00"),
                credit=Decimal("0"),
            )

            JournalLine.objects.create(
                journal_entry=je,
                account=self.bank_coa_account,
                debit=Decimal("0"),
                credit=Decimal("50.00"),
            )

        # Create bank transaction
        bank_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=date.today(),
            description="Payment",
            amount=Decimal("-50.00"),
        )

        # Run matching with limit=3
        matches = BankMatchingEngine.find_matches(bank_tx, limit=3)

        # Assert: should return max 3 results
        self.assertLessEqual(len(matches), 3)
