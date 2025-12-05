from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Account, Business, JournalEntry, JournalLine


User = get_user_model()


class ProfitAndLossPeriodParamTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pl-period-user", password="testpass123")
        self.business = Business.objects.create(
            name="PL Period Biz",
            currency="USD",
            owner_user=self.user,
        )
        self.cash = Account.objects.create(
            business=self.business,
            code="1000",
            name="Cash",
            type=Account.AccountType.ASSET,
        )
        self.income = Account.objects.create(
            business=self.business,
            code="4000",
            name="Income",
            type=Account.AccountType.INCOME,
        )
        self.expense = Account.objects.create(
            business=self.business,
            code="5000",
            name="Expense",
            type=Account.AccountType.EXPENSE,
        )

    def _add_income(self, amount: Decimal, tx_date: date):
        entry = JournalEntry.objects.create(business=self.business, date=tx_date, description="Income")
        JournalLine.objects.create(journal_entry=entry, account=self.cash, debit=amount, credit=Decimal("0.00"))
        JournalLine.objects.create(journal_entry=entry, account=self.income, debit=Decimal("0.00"), credit=amount)

    def _add_expense(self, amount: Decimal, tx_date: date):
        entry = JournalEntry.objects.create(business=self.business, date=tx_date, description="Expense")
        JournalLine.objects.create(journal_entry=entry, account=self.expense, debit=amount, credit=Decimal("0.00"))
        JournalLine.objects.create(journal_entry=entry, account=self.cash, debit=Decimal("0.00"), credit=amount)

    def test_custom_range_filters_entries(self):
        self._add_income(Decimal("200.00"), date(2024, 4, 10))
        self._add_income(Decimal("150.00"), date(2024, 5, 5))  # outside range

        self.client.force_login(self.user)
        response = self.client.get(
            "/profit-loss/",
            {
                "start_date": "2024-04-01",
                "end_date": "2024-04-30",
                "period_preset": "custom",
                "compare_to": "none",
            },
        )
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertEqual(ctx["total_income"], Decimal("200.00"))
        self.assertEqual(ctx["prev_total_income"], Decimal("0.00"))

    def test_previous_period_uses_prior_month(self):
        self._add_income(Decimal("300.00"), date(2025, 10, 10))
        self._add_income(Decimal("120.00"), date(2025, 9, 12))
        self._add_expense(Decimal("40.00"), date(2025, 9, 15))

        self.client.force_login(self.user)
        response = self.client.get(
            "/profit-loss/",
            {
                "start_date": "2025-10-01",
                "end_date": "2025-10-31",
                "period_preset": "last_month",
                "compare_to": "previous_period",
            },
        )
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertEqual(ctx["total_income"], Decimal("300.00"))
        self.assertEqual(ctx["prev_total_income"], Decimal("120.00"))
        # Ensure prior period does not bleed in older months
        self.assertEqual(ctx["income_change_pct"].quantize(Decimal("1")), Decimal("150"))
