from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import Business, Account, JournalEntry, JournalLine, BankAccount, BankTransaction
from core.ledger_services import compute_ledger_pl


class DashboardPnLTests(TestCase):
    """Test that dashboard P&L uses ledger-based calculations correctly."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        
        # Create user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        
        # Create business
        self.business = Business.objects.create(
            name="Test Business",
            owner_user=self.user,
            currency="USD",
        )
        
        # Create income and expense accounts
        self.income_account = Account.objects.create(
            business=self.business,
            name="Revenue",
            code="4000",
            type=Account.AccountType.INCOME,
        )
        
        self.expense_account = Account.objects.create(
            business=self.business,
            name="Office Expenses",
            code="6100",
            type=Account.AccountType.EXPENSE,
        )
        
        self.bank_account_ledger = Account.objects.create(
            business=self.business,
            name="Checking Account",
            code="1000",
            type=Account.AccountType.ASSET,
        )
        
        # Log in
        self.client.login(username="testuser", password="testpass123")

    def test_manual_journal_entry_appears_in_dashboard(self):
        """Test Case 1: Manual journal entry shows in dashboard P&L."""
        today = date.today()
        
        # Create a manual journal entry with income and expense
        je = JournalEntry.objects.create(
            business=self.business,
            date=today,
            description="Manual Entry",
            is_void=False,
        )
        
        # Income: Credit $1000
        JournalLine.objects.create(
            journal_entry=je,
            account=self.income_account,
            credit=Decimal("1000.00"),
            debit=Decimal("0.00"),
        )
        
        # Cash: Debit $1000 (balancing entry)
        JournalLine.objects.create(
            journal_entry=je,
            account=self.bank_account_ledger,
            debit=Decimal("1000.00"),
            credit=Decimal("0.00"),
        )
        
        # Create expense journal entry
        je2 = JournalEntry.objects.create(
            business=self.business,
            date=today,
            description="Expense Entry",
            is_void=False,
        )
        
        # Expense: Debit $400
        JournalLine.objects.create(
            journal_entry=je2,
            account=self.expense_account,
            debit=Decimal("400.00"),
            credit=Decimal("0.00"),
        )
        
        # Cash: Credit $400 (balancing entry)
        JournalLine.objects.create(
            journal_entry=je2,
            account=self.bank_account_ledger,
            credit=Decimal("400.00"),
            debit=Decimal("0.00"),
        )
        
        # Call dashboard view
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        
        context = response.context
        
        # Assert totals match journal entries
        self.assertEqual(context["total_income_month"], Decimal("1000.00"))
        self.assertEqual(context["total_expenses_month"], Decimal("400.00"))
        self.assertEqual(context["net_income_month"], Decimal("600.00"))

    def test_bank_matched_entry_appears_in_dashboard(self):
        """Test Case 2: Bank-matched transaction creates JE that shows in dashboard."""
        today = date.today()
        
        # Create bank account
        bank_account = BankAccount.objects.create(
            business=self.business,
            name="Business Checking",
            account_number_mask="****1234",
            account=self.bank_account_ledger,
        )
        
        # Create bank transaction
        bank_tx = BankTransaction.objects.create(
            bank_account=bank_account,
            date=today,
            description="Customer Payment",
            amount=Decimal("500.00"),
        )
        
        # Simulate matching: create journal entry
        je = JournalEntry.objects.create(
            business=self.business,
            date=today,
            description=f"Bank match: {bank_tx.description}",
            is_void=False,
        )
        
        # Bank debit (cash in)
        JournalLine.objects.create(
            journal_entry=je,
            account=self.bank_account_ledger,
            debit=Decimal("500.00"),
            credit=Decimal("0.00"),
        )
        
        # Income credit
        JournalLine.objects.create(
            journal_entry=je,
            account=self.income_account,
            credit=Decimal("500.00"),
            debit=Decimal("0.00"),
        )
        
        # Call dashboard
        response = self.client.get(reverse("dashboard"))
        context = response.context
        
        # Assert bank-matched entry shows in P&L
        self.assertEqual(context["total_income_month"], Decimal("500.00"))

    def test_unmatched_bank_transaction_not_in_pnl(self):
        """Test Case 3: Unmatched bank transaction does NOT affect P&L."""
        today = date.today()
        
        # Create bank account
        bank_account = BankAccount.objects.create(
            business=self.business,
            name="Business Checking",
            account_number_mask="****1234",
            account=self.bank_account_ledger,
        )
        
        # Create unmatched bank transaction (no journal entry)
        BankTransaction.objects.create(
            bank_account=bank_account,
            date=today,
            description="Unmatched Transaction",
            amount=Decimal("300.00"),
        )
        
        # Call dashboard
        response = self.client.get(reverse("dashboard"))
        context = response.context
        
        # Assert unmatched transaction does NOT affect P&L
        self.assertEqual(context["total_income_month"], Decimal("0.00"))
        self.assertEqual(context["total_expenses_month"], Decimal("0.00"))

    def test_void_journal_entries_excluded(self):
        """Test Case 4: Void journal entries are excluded from P&L."""
        today = date.today()
        
        # Create void journal entry
        je = JournalEntry.objects.create(
            business=self.business,
            date=today,
            description="Void Entry",
            is_void=True,  # Marked as void
        )
        
        JournalLine.objects.create(
            journal_entry=je,
            account=self.income_account,
            credit=Decimal("999.00"),
            debit=Decimal("0.00"),
        )
        
        JournalLine.objects.create(
            journal_entry=je,
            account=self.bank_account_ledger,
            debit=Decimal("999.00"),
            credit=Decimal("0.00"),
        )
        
        # Call dashboard
        response = self.client.get(reverse("dashboard"))
        context = response.context
        
        # Assert void entry is excluded
        self.assertEqual(context["total_income_month"], Decimal("0.00"))

    def test_date_filtering_multi_period(self):
        """Test Case 5: Date filtering works correctly across periods."""
        today = date.today()
        last_month = today - timedelta(days=40)
        
        # Create entry in current month
        je_current = JournalEntry.objects.create(
            business=self.business,
            date=today,
            description="Current Month",
            is_void=False,
        )
        
        JournalLine.objects.create(
            journal_entry=je_current,
            account=self.income_account,
            credit=Decimal("100.00"),
            debit=Decimal("0.00"),
        )
        
        JournalLine.objects.create(
            journal_entry=je_current,
            account=self.bank_account_ledger,
            debit=Decimal("100.00"),
            credit=Decimal("0.00"),
        )
        
        # Create entry in previous month
        je_past = JournalEntry.objects.create(
            business=self.business,
            date=last_month,
            description="Past Month",
            is_void=False,
        )
        
        JournalLine.objects.create(
            journal_entry=je_past,
            account=self.income_account,
            credit=Decimal("500.00"),
            debit=Decimal("0.00"),
        )
        
        JournalLine.objects.create(
            journal_entry=je_past,
            account=self.bank_account_ledger,
            debit=Decimal("500.00"),
            credit=Decimal("0.00"),
        )
        
        # Call dashboard
        response = self.client.get(reverse("dashboard"))
        context = response.context
        
        # Assert only current month shows in month total
        self.assertEqual(context["total_income_month"], Decimal("100.00"))
        
        # Assert 30-day total includes both if within 30 days
        # (depends on exact dates, so just verify it's a positive number)
        self.assertGreaterEqual(context["revenue_30"], Decimal("100.00"))

    def test_dashboard_matches_pnl_report(self):
        """Test Case 6: Dashboard totals match P&L report totals."""
        today = date.today()
        month_start = date(today.year, today.month, 1)
        
        # Calculate next month start
        if today.month == 12:
            next_month_start = date(today.year + 1, 1, 1)
        else:
            next_month_start = date(today.year, today.month + 1, 1)
        
        month_end = next_month_start - timedelta(days=1)
        
        # Create some journal entries
        je = JournalEntry.objects.create(
            business=self.business,
            date=today,
            description="Test Entry",
            is_void=False,
        )
        
        JournalLine.objects.create(
            journal_entry=je,
            account=self.income_account,
            credit=Decimal("750.00"),
            debit=Decimal("0.00"),
        )
        
        JournalLine.objects.create(
            journal_entry=je,
            account=self.expense_account,
            debit=Decimal("250.00"),
            credit=Decimal("0.00"),
        )
        
        JournalLine.objects.create(
            journal_entry=je,
            account=self.bank_account_ledger,
            debit=Decimal("500.00"),
            credit=Decimal("0.00"),
        )
        
        # Get dashboard totals
        response = self.client.get(reverse("dashboard"))
        dashboard_income = response.context["total_income_month"]
        dashboard_expense = response.context["total_expenses_month"]
        
        # Get P&L report totals using compute_ledger_pl
        pl_report = compute_ledger_pl(self.business, month_start, month_end)
        
        # Assert they match
        self.assertEqual(dashboard_income, pl_report["total_income"])
        self.assertEqual(dashboard_expense, pl_report["total_expense"])

    def test_empty_ledger_returns_zero(self):
        """Test Case 7: Empty ledger returns zero totals, not None."""
        # No journal entries created
        
        # Call dashboard
        response = self.client.get(reverse("dashboard"))
        context = response.context
        
        # Assert totals are zero (not None, not error)
        self.assertEqual(context["total_income_month"], Decimal("0.00"))
        self.assertEqual(context["total_expenses_month"], Decimal("0.00"))
        self.assertEqual(context["net_income_month"], Decimal("0.00"))
        self.assertEqual(context["revenue_30"], Decimal("0.00"))
        self.assertEqual(context["expenses_30"], Decimal("0.00"))
