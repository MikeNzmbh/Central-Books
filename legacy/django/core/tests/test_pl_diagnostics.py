from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from core.accounting_defaults import ensure_default_accounts
from core.models import Account, BankAccount, BankTransaction, Business, JournalEntry, JournalLine
from core.services.ledger_metrics import build_pl_diagnostics
from django.contrib.auth import get_user_model


class PLDiagnosticsTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="diag-user", email="diag@example.com", password="pass12345")
        self.business = Business.objects.create(name="DiagCo", currency="USD", owner_user=user)
        self.defaults = ensure_default_accounts(self.business)
        self.bank_account = BankAccount.objects.create(
            business=self.business,
            name="Operating",
            account_number_mask="0001",
            bank_name="DiagBank",
        )
        self.bank_account.account = self.defaults["cash"]
        self.bank_account.save()
        self.today = date.today()
        self.start = self.today.replace(day=1)
        self.end = self.today

    def test_no_activity_reason(self):
        diag = build_pl_diagnostics(self.business, self.start, self.end)
        self.assertEqual(diag["reason_code"], "no_activity")

    def test_bank_activity_without_pl_lines(self):
        BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=self.today,
            description="Deposit",
            amount=Decimal("100.00"),
        )
        diag = build_pl_diagnostics(self.business, self.start, self.end)
        self.assertEqual(diag["reason_code"], "bank_only")

    def test_non_pl_accounts_reason(self):
        entry = JournalEntry.objects.create(
            business=self.business,
            date=self.today,
            description="Asset move",
        )
        JournalLine.objects.create(
            journal_entry=entry,
            account=self.defaults["cash"],
            debit=Decimal("50.00"),
            credit=Decimal("0.00"),
        )
        JournalLine.objects.create(
            journal_entry=entry,
            account=self.defaults["ar"],
            debit=Decimal("0.00"),
            credit=Decimal("50.00"),
        )

        diag = build_pl_diagnostics(self.business, self.start, self.end)
        self.assertEqual(diag["reason_code"], "non_pl_accounts")

    def test_has_pl_activity_returns_empty_reason(self):
        """When there are income/expense lines, diagnostics should be empty."""
        income_account = Account.objects.create(
            business=self.business,
            name="Revenue",
            code="4001",
            type=Account.AccountType.INCOME,
        )
        entry = JournalEntry.objects.create(
            business=self.business,
            date=self.today,
            description="Revenue entry",
        )
        JournalLine.objects.create(
            journal_entry=entry,
            account=self.defaults["cash"],
            debit=Decimal("100.00"),
            credit=Decimal("0.00"),
        )
        JournalLine.objects.create(
            journal_entry=entry,
            account=income_account,
            debit=Decimal("0.00"),
            credit=Decimal("100.00"),
        )

        diag = build_pl_diagnostics(self.business, self.start, self.end)
        self.assertEqual(diag["reason_code"], "")
        self.assertEqual(diag["reason_message"], "")
        self.assertTrue(diag["has_ledger_activity"])
