from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from core.accounting_defaults import ensure_default_accounts
from core.models import BankAccount, BankTransaction, Business


class CoaBankTransactionsAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="coauser", password="pass")
        self.business = Business.objects.create(
            name="COA Co",
            currency="USD",
            owner_user=self.user,
        )
        defaults = ensure_default_accounts(self.business)
        self.bank_account = BankAccount.objects.create(
            business=self.business,
            name="Operating",
            usage_role=BankAccount.UsageRole.OPERATING,
            account=defaults["cash"],
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_transactions_include_reconciliation_status(self):
        # Default should be unreconciled
        tx1 = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=date.today(),
            description="Deposit",
            amount=Decimal("100.00"),
        )
        # Explicit reconciled
        tx2 = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=date.today(),
            description="Matched",
            amount=Decimal("50.00"),
            reconciliation_status=BankTransaction.RECO_STATUS_RECONCILED,
        )

        resp = self.client.get(
            reverse("api_banking_feed_transactions"),
            {"account_id": self.bank_account.id},
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        txs = {str(row["id"]): row for row in payload.get("transactions", [])}
        self.assertIn(str(tx1.id), txs)
        self.assertIn(str(tx2.id), txs)
        self.assertEqual(
            txs[str(tx1.id)]["reconciliation_status"],
            BankTransaction.RECO_STATUS_UNRECONCILED,
        )
        self.assertEqual(
            txs[str(tx2.id)]["reconciliation_status"],
            BankTransaction.RECO_STATUS_RECONCILED,
        )
