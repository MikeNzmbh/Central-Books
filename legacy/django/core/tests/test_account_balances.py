from decimal import Decimal
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from core.accounting_defaults import ensure_default_accounts
from core.ledger_reports import account_balances_for_business
from core.models import Account, Business, JournalEntry, JournalLine


class AccountBalanceVisibilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ledgeruser", password="pass")
        self.business = Business.objects.create(
            name="Ledger Co",
            currency="USD",
            owner_user=self.user,
        )
        self.defaults = ensure_default_accounts(self.business)

    def test_cash_account_shows_without_activity(self):
        cash = self.defaults["cash"]
        data = account_balances_for_business(self.business)
        account_ids = {row["id"] for row in data["accounts"]}
        self.assertIn(cash.id, account_ids)
        self.assertEqual(data["totals_by_type"].get(Account.AccountType.ASSET, Decimal("0.00")), Decimal("0.00"))

    def test_cash_account_balance_included_with_journal_lines(self):
        cash = self.defaults["cash"]
        je = JournalEntry.objects.create(
            business=self.business,
            date=date.today(),
            description="Deposit",
        )
        JournalLine.objects.create(
            journal_entry=je,
            account=cash,
            debit=Decimal("150.00"),
            credit=Decimal("0.00"),
        )

        data = account_balances_for_business(self.business)
        cash_row = next(row for row in data["accounts"] if row["id"] == cash.id)
        self.assertEqual(cash_row["balance"], Decimal("150.00"))
