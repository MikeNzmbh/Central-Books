"""
Tests for Bank Reconciliation Service
"""

from decimal import Decimal
from datetime import date

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import (
    Business,
    BankAccount,
    BankTransaction,
    Invoice,
    JournalEntry,
    JournalLine,
    Account,
    BankReconciliationMatch,
    Customer,
)
from core.services.bank_reconciliation import BankReconciliationService

User = get_user_model()


class BankReconciliationServiceTest(TestCase):
    """Test suite for BankReconciliationService"""

    def setUp(self):
        """Set up test data"""
        # Create user and business
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.business = Business.objects.create(
            name="Test Business", currency="CAD", owner_user=self.user
        )

        # Create customer (needed for invoices)
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

    def test_confirm_match(self):
        """Test confirming a match"""
        # Create bank transaction
        bank_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=date.today(),
            description="Payment received",
            amount=Decimal("500.00"),
        )

        # Create journal entry
        journal_entry = JournalEntry.objects.create(
            business=self.business,
            date=date.today(),
            description="Invoice payment",
        )
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

        # Confirm match
        match = BankReconciliationService.confirm_match(
            bank_transaction=bank_tx,
            journal_entry=journal_entry,
            match_confidence=Decimal("0.95"),
            user=self.user,
        )

        # Assert
        self.assertIsInstance(match, BankReconciliationMatch)
        self.assertEqual(match.bank_transaction, bank_tx)
        self.assertEqual(match.journal_entry, journal_entry)
        self.assertEqual(match.match_confidence, Decimal("0.95"))
        self.assertEqual(match.matched_amount, Decimal("500.00"))
        self.assertEqual(match.reconciled_by, self.user)
        
        # Verify bank transaction updated
        bank_tx.refresh_from_db()
        self.assertEqual(bank_tx.status, "MATCHED_SINGLE")
        self.assertEqual(bank_tx.allocated_amount, Decimal("500.00"))
        self.assertEqual(bank_tx.posted_journal_entry, journal_entry)

    def test_create_split_entry_balanced(self):
        """Test creating a balanced split entry"""
        # Create bank transaction (Expense)
        bank_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=date.today(),
            description="Office supplies and software",
            amount=Decimal("-100.00"),
        )

        splits = [
            {
                "account_id": self.expense_account.id,
                "amount": Decimal("60.00"),
                "description": "Office supplies",
            },
            {
                "account_id": self.expense_account.id,
                "amount": Decimal("40.00"),
                "description": "Software",
            },
        ]

        # Create split
        journal_entry, match = BankReconciliationService.create_split_entry(
            bank_transaction=bank_tx,
            splits=splits,
            user=self.user,
            description="Split expense",
        )

        # Assert
        self.assertIsInstance(journal_entry, JournalEntry)
        self.assertIsInstance(match, BankReconciliationMatch)
        
        # Verify journal lines
        lines = journal_entry.lines.all()
        self.assertEqual(lines.count(), 3)  # 2 splits + 1 bank line
        
        # Verify bank line
        bank_line = lines.filter(account=self.bank_coa_account).first()
        self.assertIsNotNone(bank_line)
        self.assertEqual(bank_line.credit, Decimal("100.00"))
        
        # Verify expense lines
        expense_lines = lines.filter(account=self.expense_account)
        self.assertEqual(expense_lines.count(), 2)
        self.assertEqual(sum(l.debit for l in expense_lines), Decimal("100.00"))

        # Verify bank transaction updated
        bank_tx.refresh_from_db()
        self.assertEqual(bank_tx.status, "MATCHED_MULTI")
        self.assertEqual(bank_tx.allocated_amount, Decimal("-100.00"))

    def test_create_split_entry_unbalanced(self):
        """Test that unbalanced splits raise ValueError"""
        bank_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=date.today(),
            description="Unbalanced split",
            amount=Decimal("-100.00"),
        )

        splits = [
            {
                "account_id": self.expense_account.id,
                "amount": Decimal("60.00"),  # Total 60 != 100
            },
        ]

        with self.assertRaises(ValueError):
            BankReconciliationService.create_split_entry(
                bank_transaction=bank_tx,
                splits=splits,
                user=self.user,
            )

    def test_unmatch(self):
        """Test unmatching a transaction"""
        # Setup: Create match first
        bank_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=date.today(),
            description="To be unmatched",
            amount=Decimal("500.00"),
        )
        journal_entry = JournalEntry.objects.create(
            business=self.business,
            date=date.today(),
            description="JE",
        )
        match = BankReconciliationService.confirm_match(
            bank_transaction=bank_tx,
            journal_entry=journal_entry,
            match_confidence=Decimal("1.00"),
            user=self.user,
        )

        # Verify matched state
        bank_tx.refresh_from_db()
        self.assertEqual(bank_tx.status, "MATCHED_SINGLE")

        # Unmatch
        BankReconciliationService.unmatch(match, user=self.user)

        # Verify unmatched state
        bank_tx.refresh_from_db()
        self.assertEqual(bank_tx.status, "NEW")
        self.assertEqual(bank_tx.allocated_amount, Decimal("0.00"))
        self.assertIsNone(bank_tx.posted_journal_entry)
        
        # Verify match record deleted
        self.assertFalse(BankReconciliationMatch.objects.filter(id=match.id).exists())

    def test_get_reconciliation_progress(self):
        """Test progress statistics"""
        # Create 1 matched and 1 unmatched transaction
        
        # Matched
        tx1 = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=date.today(),
            amount=Decimal("100.00"),
            status="MATCHED_SINGLE",
            allocated_amount=Decimal("100.00"),
        )
        
        # Unmatched
        tx2 = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=date.today(),
            amount=Decimal("200.00"),
            status="NEW",
            allocated_amount=Decimal("0.00"),
        )

        stats = BankReconciliationService.get_reconciliation_progress(self.bank_account)

        self.assertEqual(stats["total_transactions"], 2)
        self.assertEqual(stats["reconciled"], 1)
        self.assertEqual(stats["unreconciled"], 1)
        self.assertEqual(stats["total_reconciled_amount"], Decimal("100.00"))
        self.assertEqual(stats["total_unreconciled_amount"], Decimal("200.00"))
        self.assertEqual(stats["progress_percent"], 50.0)
