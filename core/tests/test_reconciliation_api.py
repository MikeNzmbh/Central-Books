from decimal import Decimal
from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from core.accounting_defaults import ensure_default_accounts
from core.models import (
    Account,
    BankAccount,
    BankTransaction,
    Business,
    JournalEntry,
    JournalLine,
)


class ReconciliationAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="apiuser", password="pass")
        self.business = Business.objects.create(
            name="API Co",
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

    def _make_bank_tx(self, amount: Decimal) -> BankTransaction:
        return BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=date.today(),
            description="Deposit",
            amount=amount,
        )

    def _make_journal_entry(self, amount: Decimal) -> JournalEntry:
        je = JournalEntry.objects.create(
            business=self.business,
            date=date.today(),
            description="Bank entry",
        )
        JournalLine.objects.create(
            journal_entry=je,
            account=self.bank_account.account,
            debit=amount if amount > 0 else Decimal("0.00"),
            credit=abs(amount) if amount < 0 else Decimal("0.00"),
            description="Bank side",
        )
        return je

    def test_overview_and_transactions_endpoints(self):
        tx = self._make_bank_tx(Decimal("100.00"))
        url_overview = reverse("api_reco_overview", args=[self.bank_account.id])
        resp = self.client.get(url_overview)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_transactions"], 1)
        url_tx = reverse("api_reco_transactions", args=[self.bank_account.id])
        resp = self.client.get(url_tx, {"status": "UNRECONCILED"})
        self.assertEqual(resp.status_code, 200)
        tx_list = resp.json()
        self.assertEqual(len(tx_list), 1)
        self.assertEqual(tx_list[0]["id"], tx.id)

    def test_confirm_match_marks_reconciled(self):
        tx = self._make_bank_tx(Decimal("50.00"))
        je = self._make_journal_entry(Decimal("50.00"))
        resp = self.client.post(
            reverse("api_reco_confirm_match"),
            data={
                "bank_transaction_id": tx.id,
                "journal_entry_id": je.id,
                "match_confidence": "1.0",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        tx.refresh_from_db()
        self.assertTrue(tx.is_reconciled)
        self.assertIsNotNone(tx.reconciled_at)

    def test_create_split(self):
        tx = self._make_bank_tx(Decimal("120.00"))
        expense_account = (
            Account.objects.filter(business=self.business, type=Account.AccountType.EXPENSE)
            .first()
        )
        resp = self.client.post(
            reverse("api_reco_create_split"),
            data={
                "bank_transaction_id": tx.id,
                "splits": [
                    {"account_id": expense_account.id, "amount": "70.00", "description": "Part A"},
                    {"account_id": expense_account.id, "amount": "50.00", "description": "Part B"},
                ],
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        tx.refresh_from_db()
        self.assertTrue(tx.is_reconciled)
