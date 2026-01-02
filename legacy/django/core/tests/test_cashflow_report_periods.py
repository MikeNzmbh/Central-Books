import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import BankAccount, BankTransaction, Business


User = get_user_model()


class CashflowReportPeriodTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cf-user", password="testpass123")
        self.business = Business.objects.create(
            owner_user=self.user,
            name="Cashflow Biz",
            currency="USD",
        )
        self.bank_account = BankAccount.objects.create(
            business=self.business,
            name="Operating",
            account_number_mask="****1111",
        )

    def test_custom_range_filters_transactions(self):
        BankTransaction.objects.create(
            bank_account=self.bank_account,
            amount=Decimal("150.00"),
            date=date(2024, 1, 15),
            description="January inflow",
        )
        BankTransaction.objects.create(
            bank_account=self.bank_account,
            amount=Decimal("-50.00"),
            date=date(2024, 2, 10),
            description="February outflow",
        )

        self.client.force_login(self.user)
        response = self.client.get(
            "/reports/cashflow/",
            {"start_date": "2024-02-01", "end_date": "2024-02-28", "period_preset": "custom"},
        )
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.context["cashflow_data_json"])

        self.assertEqual(payload["period"]["start"], "2024-02-01")
        self.assertEqual(payload["period"]["end"], "2024-02-28")
        self.assertEqual(payload["summary"]["totalInflows"], 0.0)
        self.assertEqual(payload["summary"]["totalOutflows"], 50.0)
        # Trend should only include the in-range month
        self.assertTrue(all("Feb" in point["periodLabel"] for point in payload["trend"]))
