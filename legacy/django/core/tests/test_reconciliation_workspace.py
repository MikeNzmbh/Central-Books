from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.accounting_defaults import ensure_default_accounts
from core.models import (
    Account,
    BankAccount,
    BankTransaction,
    Business,
    JournalEntry,
    JournalLine,
)
from core.services.reconciliation_engine import ReconciliationEngine


class ReconciliationEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reco", password="pass")
        self.business = Business.objects.create(
            name="Reco Co",
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

    def _make_bank_tx(self, amount: Decimal) -> BankTransaction:
        tx_date = timezone.localdate()
        return BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=tx_date,
            description="Deposit",
            amount=amount,
        )

    def _make_journal_line(self, amount: Decimal) -> JournalLine:
        entry = JournalEntry.objects.create(
            business=self.business,
            date=timezone.localdate(),
            description="Bank entry",
        )
        return JournalLine.objects.create(
            journal_entry=entry,
            account=self.bank_account.account,
            debit=amount if amount > 0 else Decimal("0.00"),
            credit=abs(amount) if amount < 0 else Decimal("0.00"),
            description="Bank side",
        )

    def test_candidate_match_found(self):
        tx = self._make_bank_tx(Decimal("100.00"))
        line = self._make_journal_line(Decimal("100.00"))
        engine = ReconciliationEngine(self.business, self.bank_account)
        candidates = engine.get_candidate_matches(tx)
        self.assertIn(line, candidates)

    def test_reconcile_marks_flags(self):
        tx = self._make_bank_tx(Decimal("100.00"))
        line = self._make_journal_line(Decimal("100.00"))
        engine = ReconciliationEngine(self.business, self.bank_account)
        engine.reconcile(tx, [line])
        tx.refresh_from_db()
        line.refresh_from_db()
        self.assertTrue(tx.is_reconciled)
        self.assertTrue(line.is_reconciled)
        self.assertIsNotNone(tx.reconciled_at)
        self.assertIsNotNone(line.reconciled_at)

    def test_reconcile_view_flow(self):
        tx = self._make_bank_tx(Decimal("50.00"))
        line = self._make_journal_line(Decimal("50.00"))
        client = Client()
        client.force_login(self.user)

        url = reverse("reconcile_bank_account", args=[self.bank_account.id])
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, tx.description)

        resp = client.post(
            url,
            {
                "bank_line_id": tx.id,
                "journal_line_id": line.id,
            },
        )
        self.assertEqual(resp.status_code, 302)
        tx.refresh_from_db()
        self.assertTrue(tx.is_reconciled)
