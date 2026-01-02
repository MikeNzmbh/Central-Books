from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Account, Business, JournalEntry, JournalLine


User = get_user_model()


class ProfitAndLossRenderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="pl-render-user",
            email="pl-render@example.com",
            password="testpass123",
        )
        self.business = Business.objects.create(
            name="P&L Render Biz",
            currency="USD",
            owner_user=self.user,
        )
        self.income_account = Account.objects.create(
            business=self.business,
            code="4100",
            name="Income",
            type=Account.AccountType.INCOME,
        )
        self.expense_account = Account.objects.create(
            business=self.business,
            code="5100",
            name="Expenses",
            type=Account.AccountType.EXPENSE,
        )
        self.cash_account = Account.objects.create(
            business=self.business,
            code="1100",
            name="Cash",
            type=Account.AccountType.ASSET,
        )

    def test_at_a_glance_uses_rendered_totals(self):
        today = date.today()

        # Income journal
        income_entry = JournalEntry.objects.create(
            business=self.business,
            date=today,
            description="Income entry",
        )
        JournalLine.objects.create(
            journal_entry=income_entry,
            account=self.cash_account,
            debit=Decimal("150.00"),
            credit=Decimal("0.00"),
        )
        JournalLine.objects.create(
            journal_entry=income_entry,
            account=self.income_account,
            debit=Decimal("0.00"),
            credit=Decimal("150.00"),
        )

        # Expense journal
        expense_entry = JournalEntry.objects.create(
            business=self.business,
            date=today,
            description="Expense entry",
        )
        JournalLine.objects.create(
            journal_entry=expense_entry,
            account=self.expense_account,
            debit=Decimal("40.00"),
            credit=Decimal("0.00"),
        )
        JournalLine.objects.create(
            journal_entry=expense_entry,
            account=self.cash_account,
            debit=Decimal("0.00"),
            credit=Decimal("40.00"),
        )

        self.client.force_login(self.user)
        response = self.client.get("/profit-loss/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")

        # Ensure rendered values appear and template expressions are not leaked.
        self.assertIn("$150.00", html)
        self.assertIn("$40.00", html)
        self.assertIn("$110.00", html)  # Net profit
        self.assertNotIn("${{ total_income|floatformat:2 }}", html)
        self.assertNotIn("${{ total_expenses|floatformat:2 }}", html)
        self.assertNotIn("${{ net_profit|floatformat:2 }}", html)
