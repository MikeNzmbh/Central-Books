from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.ledger_services import compute_ledger_pl
from core.models import Account, Business, JournalEntry, JournalLine
from core.services.ledger_metrics import PLPeriod, get_pl_period_dates


class DashboardPLAlignmentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="align", email="align@example.com", password="pass")
        self.business = Business.objects.create(name="AlignCo", owner_user=self.user, currency="USD")
        self.income_account = Account.objects.create(
            business=self.business,
            name="Sales",
            code="4010",
            type=Account.AccountType.INCOME,
        )
        self.expense_account = Account.objects.create(
            business=self.business,
            name="Office",
            code="5010",
            type=Account.AccountType.EXPENSE,
        )
        self.cash_account = Account.objects.create(
            business=self.business,
            name="Cash",
            code="1010",
            type=Account.AccountType.ASSET,
        )
        self.client.login(username="align", password="pass")
        self.today = date(2025, 12, 15)

    def _patch_today(self):
        return mock.patch("core.views.timezone.localdate", return_value=self.today), mock.patch(
            "core.services.ledger_metrics.timezone.localdate", return_value=self.today
        )

    def _create_entry(self, entry_date: date, income: Decimal = Decimal("0"), expense: Decimal = Decimal("0")):
        je = JournalEntry.objects.create(
            business=self.business,
            date=entry_date,
            description="Test entry",
            is_void=False,
        )
        if income:
            JournalLine.objects.create(journal_entry=je, account=self.cash_account, debit=income, credit=0)
            JournalLine.objects.create(journal_entry=je, account=self.income_account, debit=0, credit=income)
        if expense:
            JournalLine.objects.create(journal_entry=je, account=self.expense_account, debit=expense, credit=0)
            JournalLine.objects.create(journal_entry=je, account=self.cash_account, debit=0, credit=expense)

    def test_dashboard_totals_match_compute_ledger_pl_current_period(self):
        with mock.patch.multiple(
            "core.views.timezone",
            localdate=mock.Mock(return_value=self.today),
        ), mock.patch.multiple(
            "core.services.ledger_metrics.timezone",
            localdate=mock.Mock(return_value=self.today),
        ):
            self._create_entry(self.today, income=Decimal("500.00"), expense=Decimal("200.00"))
            response = self.client.get(reverse("dashboard"))
            metrics = response.context["metrics"]

            start, end, _, _ = get_pl_period_dates(PLPeriod.THIS_MONTH, today=self.today)
            expected = compute_ledger_pl(self.business, start, end)

            self.assertEqual(metrics["total_income_month"], expected["total_income"])
            self.assertEqual(metrics["total_expenses_month"], expected["total_expense"])

    def test_dashboard_prev_period_uses_last_month(self):
        prev_start, prev_end, _, _ = get_pl_period_dates(PLPeriod.LAST_MONTH, today=self.today)
        prev_mid = prev_start + timedelta(days=5)
        with mock.patch.multiple(
            "core.views.timezone",
            localdate=mock.Mock(return_value=self.today),
        ), mock.patch.multiple(
            "core.services.ledger_metrics.timezone",
            localdate=mock.Mock(return_value=self.today),
        ):
            self._create_entry(prev_mid, income=Decimal("300.00"), expense=Decimal("100.00"))
            response = self.client.get(reverse("dashboard"))
            metrics = response.context["metrics"]

            expected_prev = compute_ledger_pl(self.business, prev_start, prev_end)
            self.assertEqual(metrics["pl_prev_income"], expected_prev["total_income"])
            self.assertEqual(metrics["pl_prev_expenses"], expected_prev["total_expense"])

    def test_no_activity_flag_true_when_no_income_or_expense_lines(self):
        with mock.patch.multiple(
            "core.views.timezone",
            localdate=mock.Mock(return_value=self.today),
        ), mock.patch.multiple(
            "core.services.ledger_metrics.timezone",
            localdate=mock.Mock(return_value=self.today),
        ):
            response = self.client.get(reverse("dashboard"))
            metrics = response.context["metrics"]
            debug = metrics["pl_debug"]
            self.assertTrue(debug["no_ledger_activity_for_period"])
            self.assertEqual(metrics["total_income_month"], Decimal("0.00"))
            self.assertEqual(metrics["total_expenses_month"], Decimal("0.00"))

    def test_no_activity_flag_false_when_income_present(self):
        with mock.patch.multiple(
            "core.views.timezone",
            localdate=mock.Mock(return_value=self.today),
        ), mock.patch.multiple(
            "core.services.ledger_metrics.timezone",
            localdate=mock.Mock(return_value=self.today),
        ):
            self._create_entry(self.today, income=Decimal("50.00"))
            response = self.client.get(reverse("dashboard"))
            debug = response.context["metrics"]["pl_debug"]
            self.assertFalse(debug["no_ledger_activity_for_period"])
