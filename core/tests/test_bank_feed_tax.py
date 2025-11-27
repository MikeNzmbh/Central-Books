from decimal import Decimal
from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.accounting_defaults import ensure_default_accounts
from core.models import (
    Account,
    BankAccount,
    BankReconciliationMatch,
    BankTransaction,
    Business,
    Category,
    JournalEntry,
    TaxRate,
)

User = get_user_model()


class BankFeedTaxTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass1234")
        self.business = Business.objects.create(
            name="Tax Biz",
            currency="USD",
            owner_user=self.user,
        )
        self.defaults = ensure_default_accounts(self.business)
        self.bank_account = BankAccount.objects.create(
            business=self.business,
            name="Operating",
            usage_role=BankAccount.UsageRole.OPERATING,
            account=self.defaults["cash"],
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.tax_rate = TaxRate.objects.create(
            business=self.business,
            name="Standard 15",
            code="GST15",
            percentage=Decimal("15.00"),
        )
        self.income_account = self.defaults["sales"]
        self.expense_account = self.defaults["opex"]
        self.income_category = Category.objects.create(
            business=self.business,
            name="Sales",
            type=Category.CategoryType.INCOME,
            account=self.income_account,
        )
        self.expense_category = Category.objects.create(
            business=self.business,
            name="Expenses",
            type=Category.CategoryType.EXPENSE,
            account=self.expense_account,
        )

    def _make_tx(self, amount: Decimal) -> BankTransaction:
        return BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=date.today(),
            description="Bank line",
            amount=amount,
        )

    def test_add_entry_no_tax(self):
        tx = self._make_tx(Decimal("100.00"))
        resp = self.client.post(
            reverse("api_banking_feed_add_entry", args=[tx.id]),
            data={
                "account_id": self.income_account.id,
                "direction": "IN",
                "amount": "100.00",
                "tax_treatment": "NONE",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        entry = JournalEntry.objects.order_by("-id").first()
        self.assertIsNotNone(entry)
        lines = {line.account_id: line for line in entry.lines.all()}
        self.assertEqual(lines[self.defaults["cash"].id].debit, Decimal("100.00"))
        self.assertEqual(lines[self.income_account.id].credit, Decimal("100.00"))
        tx.refresh_from_db()
        self.assertEqual(tx.status, BankTransaction.TransactionStatus.MATCHED_SINGLE)
        self.assertTrue(
            BankReconciliationMatch.objects.filter(
                bank_transaction=tx, journal_entry=entry
            ).exists()
        )

    def test_add_entry_tax_included(self):
        tx = self._make_tx(Decimal("115.00"))
        resp = self.client.post(
            reverse("api_banking_feed_add_entry", args=[tx.id]),
            data={
                "account_id": self.income_account.id,
                "direction": "IN",
                "amount": "115.00",
                "tax_treatment": "INCLUDED",
                "tax_rate_id": self.tax_rate.id,
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        entry = JournalEntry.objects.order_by("-id").first()
        lines = {line.account_id: line for line in entry.lines.all()}
        self.assertEqual(lines[self.defaults["cash"].id].debit, Decimal("115.00"))
        self.assertAlmostEqual(lines[self.income_account.id].credit, Decimal("100.00"))
        self.assertAlmostEqual(lines[self.defaults["tax"].id].credit, Decimal("15.00"))

    def test_add_entry_tax_on_top_withdrawal(self):
        tx = self._make_tx(Decimal("-115.00"))
        resp = self.client.post(
            reverse("api_banking_feed_add_entry", args=[tx.id]),
            data={
                "account_id": self.expense_account.id,
                "direction": "OUT",
                "amount": "100.00",
                "tax_treatment": "ON_TOP",
                "tax_rate_id": self.tax_rate.id,
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        entry = JournalEntry.objects.order_by("-id").first()
        lines = {line.account_id: line for line in entry.lines.all()}
        self.assertEqual(lines[self.expense_account.id].debit, Decimal("100.00"))
        self.assertEqual(lines[self.defaults["tax_recoverable"].id].debit, Decimal("15.00"))
        self.assertEqual(lines[self.defaults["cash"].id].credit, Decimal("115.00"))

    def test_allocate_direct_with_tax(self):
        tx = self._make_tx(Decimal("-115.00"))
        resp = self.client.post(
            reverse("api_allocate_bank_transaction", args=[tx.id]),
            data={
                "allocations": [
                    {
                        "type": "DIRECT_EXPENSE",
                        "account_id": self.expense_account.id,
                        "amount": "100.00",
                        "tax_treatment": "ON_TOP",
                        "tax_rate_id": self.tax_rate.id,
                    }
                ]
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("ok"))
        entry = JournalEntry.objects.order_by("-id").first()
        lines = {line.account_id: line for line in entry.lines.all()}
        self.assertEqual(lines[self.expense_account.id].debit, Decimal("100.00"))
        self.assertEqual(lines[self.defaults["tax_recoverable"].id].debit, Decimal("15.00"))
        self.assertEqual(lines[self.defaults["cash"].id].credit, Decimal("115.00"))
        tx.refresh_from_db()
        self.assertEqual(tx.status, BankTransaction.TransactionStatus.MATCHED_SINGLE)

    def test_create_entry_with_tax(self):
        tx = self._make_tx(Decimal("115.00"))
        resp = self.client.post(
            reverse("api_banking_feed_create_entry", args=[tx.id]),
            data={
                "category_id": self.income_category.id,
                "tax_treatment": "INCLUDED",
                "tax_rate_id": self.tax_rate.id,
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        entry = JournalEntry.objects.order_by("-id").first()
        lines = {line.account_id: line for line in entry.lines.all()}
        self.assertEqual(lines[self.defaults["cash"].id].debit, Decimal("115.00"))
        self.assertAlmostEqual(lines[self.income_account.id].credit, Decimal("100.00"))
        self.assertAlmostEqual(lines[self.defaults["tax"].id].credit, Decimal("15.00"))
        tx.refresh_from_db()
        self.assertTrue(tx.posted_journal_entry)
        self.assertTrue(
            BankReconciliationMatch.objects.filter(bank_transaction=tx).exists()
        )
