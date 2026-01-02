"""Tests for the P&L Report API endpoint."""
from datetime import date
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from core.models import Business, Account, JournalEntry, JournalLine


User = get_user_model()


class PlReportApiTests(TestCase):
    """Tests for /api/reports/pl/ endpoint."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.business = Business.objects.create(
            name="Test Business",
            owner_user=self.user,
            currency="USD",
        )
        self.user.current_business = self.business
        self.user.save()
        self.client.login(username="testuser", password="testpass123")

        # Create accounts for testing
        self.income_account = Account.objects.create(
            business=self.business,
            name="Sales Revenue",
            code="4000",
            type=Account.AccountType.INCOME,
        )
        self.cogs_account = Account.objects.create(
            business=self.business,
            name="Cost of Goods Sold",
            code="5000",
            type=Account.AccountType.EXPENSE,
        )
        self.expense_account = Account.objects.create(
            business=self.business,
            name="Office Supplies",
            code="6000",
            type=Account.AccountType.EXPENSE,
        )
        self.cash_account = Account.objects.create(
            business=self.business,
            name="Cash",
            code="1000",
            type=Account.AccountType.ASSET,
        )

    def _create_journal_entry(self, account, amount, is_income=False, entry_date=None):
        """Helper to create journal entry with given amount."""
        entry_date = entry_date or date.today()
        entry = JournalEntry.objects.create(
            business=self.business,
            date=entry_date,
            description=f"Test entry for {account.name}",
        )
        if is_income:
            # Income: credit the income account, debit cash
            JournalLine.objects.create(
                journal_entry=entry,
                account=account,
                debit=Decimal("0"),
                credit=amount,
            )
            JournalLine.objects.create(
                journal_entry=entry,
                account=self.cash_account,
                debit=amount,
                credit=Decimal("0"),
            )
        else:
            # Expense: debit the expense account, credit cash
            JournalLine.objects.create(
                journal_entry=entry,
                account=account,
                debit=amount,
                credit=Decimal("0"),
            )
            JournalLine.objects.create(
                journal_entry=entry,
                account=self.cash_account,
                debit=Decimal("0"),
                credit=amount,
            )
        return entry

    def test_pl_api_returns_kpi_with_cogs_and_gross_profit(self):
        """Test that the API returns COGS, gross profit, and margins."""
        # Create test data
        self._create_journal_entry(self.income_account, Decimal("10000"), is_income=True)
        self._create_journal_entry(self.cogs_account, Decimal("4000"))
        self._create_journal_entry(self.expense_account, Decimal("2000"))

        response = self.client.get(
            reverse("pl_report_api"),
            {"period_preset": "this_month", "compare_preset": "none"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Check KPI values
        self.assertEqual(data["kpi"]["income"], 10000.0)
        self.assertEqual(data["kpi"]["cogs"], 4000.0)
        self.assertEqual(data["kpi"]["gross_profit"], 6000.0)  # 10000 - 4000
        self.assertEqual(data["kpi"]["expenses"], 2000.0)
        self.assertEqual(data["kpi"]["net_income"], 4000.0)  # 6000 - 2000

        # Check margins
        self.assertEqual(data["kpi"]["gross_margin_pct"], 60.0)  # 6000/10000 * 100
        self.assertEqual(data["kpi"]["net_margin_pct"], 40.0)  # 4000/10000 * 100

    def test_pl_api_respects_period_preset(self):
        """Test that the API respects period preset parameter."""
        self._create_journal_entry(self.income_account, Decimal("5000"), is_income=True)

        response = self.client.get(
            reverse("pl_report_api"),
            {"period_preset": "this_month"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["period_preset"], "this_month")
        self.assertIn("period_label", data)
        self.assertIn("period_start", data)
        self.assertIn("period_end", data)

    def test_pl_api_respects_compare_preset(self):
        """Test that the API handles comparison preset."""
        self._create_journal_entry(self.income_account, Decimal("5000"), is_income=True)

        response = self.client.get(
            reverse("pl_report_api"),
            {"period_preset": "this_month", "compare_preset": "previous_period"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["compare_preset"], "previous_period")
        # Should have a compare_label when comparison is active
        self.assertIn("compare_label", data)

    def test_pl_api_empty_period_sets_has_activity_false(self):
        """Test that empty periods have has_activity = false."""
        # No journal entries created
        response = self.client.get(
            reverse("pl_report_api"),
            {"period_preset": "this_month", "compare_preset": "none"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["diagnostics"]["has_activity"])

    def test_pl_api_returns_rows_with_correct_groups(self):
        """Test that rows are grouped correctly as INCOME, COGS, or EXPENSE."""
        self._create_journal_entry(self.income_account, Decimal("1000"), is_income=True)
        self._create_journal_entry(self.cogs_account, Decimal("500"))
        self._create_journal_entry(self.expense_account, Decimal("200"))

        response = self.client.get(
            reverse("pl_report_api"),
            {"period_preset": "this_month", "compare_preset": "none"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        income_rows = [r for r in data["rows"] if r["group"] == "INCOME"]
        cogs_rows = [r for r in data["rows"] if r["group"] == "COGS"]
        expense_rows = [r for r in data["rows"] if r["group"] == "EXPENSE"]

        self.assertEqual(len(income_rows), 1)
        self.assertEqual(income_rows[0]["name"], "Sales Revenue")
        self.assertEqual(income_rows[0]["amount"], 1000.0)

        self.assertEqual(len(cogs_rows), 1)
        self.assertEqual(cogs_rows[0]["name"], "Cost of Goods Sold")
        self.assertEqual(cogs_rows[0]["amount"], 500.0)

        self.assertEqual(len(expense_rows), 1)
        self.assertEqual(expense_rows[0]["name"], "Office Supplies")
        self.assertEqual(expense_rows[0]["amount"], 200.0)

    def test_pl_api_requires_authentication(self):
        """Test that the API requires authentication."""
        self.client.logout()
        response = self.client.get(reverse("pl_report_api"))
        # Should redirect to login page
        self.assertEqual(response.status_code, 302)

    def test_pl_api_cogs_classification_by_code(self):
        """Test that accounts with code in 5xxx range are classified as COGS."""
        # Create more expense accounts with different codes
        cogs_account_2 = Account.objects.create(
            business=self.business,
            name="Direct Labor",
            code="5100",  # Should be COGS
            type=Account.AccountType.EXPENSE,
        )
        expense_account_2 = Account.objects.create(
            business=self.business,
            name="Marketing",
            code="6100",  # Should be EXPENSE
            type=Account.AccountType.EXPENSE,
        )

        self._create_journal_entry(cogs_account_2, Decimal("1000"))
        self._create_journal_entry(expense_account_2, Decimal("500"))

        response = self.client.get(
            reverse("pl_report_api"),
            {"period_preset": "this_month", "compare_preset": "none"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        cogs_rows = [r for r in data["rows"] if r["group"] == "COGS"]
        expense_rows = [r for r in data["rows"] if r["group"] == "EXPENSE"]

        # Direct Labor (5100) should be in COGS
        cogs_names = [r["name"] for r in cogs_rows]
        self.assertIn("Direct Labor", cogs_names)

        # Marketing (6100) should be in EXPENSE
        expense_names = [r["name"] for r in expense_rows]
        self.assertIn("Marketing", expense_names)
