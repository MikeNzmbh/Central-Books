from datetime import date
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from core.accounting_defaults import ensure_default_accounts
from core.models import (
    Account,
    BankAccount,
    Business,
    Category,
    Expense,
    Supplier,
)
from core.views import _post_income_entry
from core.accounting_posting_expenses import post_expense_paid
from core.services.ledger_metrics import calculate_ledger_income, calculate_ledger_expenses
from django.contrib.auth import get_user_model


class BankFeedPnlIntegrationTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="owner", email="owner@example.com", password="pass")
        self.business = Business.objects.create(name="P&L Co", currency="USD", owner_user=user)
        self.defaults = ensure_default_accounts(self.business)
        self.bank_account = BankAccount.objects.create(
            business=self.business,
            name="Operating",
            account_number_mask="0001",
            bank_name="TestBank",
        )
        self.bank_account.account = self.defaults["cash"]
        self.bank_account.save()

    def test_income_posts_to_income_account_even_if_category_is_misconfigured(self):
        wrong_income_account = Account.objects.create(
            business=self.business,
            name="Asset Bucket",
            code="1500",
            type=Account.AccountType.ASSET,
        )
        income_category = Category.objects.create(
            business=self.business,
            name="Bank Sales",
            type=Category.CategoryType.INCOME,
            account=wrong_income_account,
        )

        entry = _post_income_entry(
            self.business,
            self.bank_account,
            income_category,
            Decimal("120.00"),
            "Deposit",
            date.today(),
        )
        income_lines = entry.lines.filter(account__type=Account.AccountType.INCOME)
        self.assertEqual(income_lines.count(), 1)
        self.assertEqual(income_lines.first().account, self.defaults["sales"])

        total_income = calculate_ledger_income(self.business, date.today(), date.today())
        self.assertEqual(total_income, Decimal("120.00"))

    def test_expense_posts_to_expense_account_even_if_category_is_misconfigured(self):
        wrong_expense_account = Account.objects.create(
            business=self.business,
            name="Liability Bucket",
            code="2600",
            type=Account.AccountType.LIABILITY,
        )
        expense_category = Category.objects.create(
            business=self.business,
            name="Bank Expense",
            type=Category.CategoryType.EXPENSE,
            account=wrong_expense_account,
        )
        supplier = Supplier.objects.create(business=self.business, name="Acme")
        expense = Expense.objects.create(
            business=self.business,
            supplier=supplier,
            category=expense_category,
            description="Misc",
            amount=Decimal("75.00"),
            net_total=Decimal("75.00"),
            tax_total=Decimal("0.00"),
            grand_total=Decimal("75.00"),
        )

        entry = post_expense_paid(expense)
        expense_lines = entry.lines.filter(account__type=Account.AccountType.EXPENSE)
        self.assertEqual(expense_lines.count(), 1)
        self.assertEqual(expense_lines.first().account, self.defaults["opex"])

        total_expense = calculate_ledger_expenses(self.business, date.today(), date.today())
        self.assertEqual(total_expense, Decimal("75.00"))


class FixCategoryAccountAlignmentCommandTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="fixer", email="fix@example.com", password="pass")
        self.business = Business.objects.create(name="FixCo", currency="USD", owner_user=user)
        self.defaults = ensure_default_accounts(self.business)
        self.income_default = self.defaults["sales"]
        self.expense_default = self.defaults["opex"]

    def test_command_realigns_category_accounts(self):
        asset_account = Account.objects.create(
            business=self.business,
            name="Asset",
            code="1500",
            type=Account.AccountType.ASSET,
        )
        liability_account = Account.objects.create(
            business=self.business,
            name="Liability",
            code="2500",
            type=Account.AccountType.LIABILITY,
        )
        bad_income = Category.objects.create(
            business=self.business,
            name="Bad Income",
            type=Category.CategoryType.INCOME,
            account=asset_account,
        )
        bad_expense = Category.objects.create(
            business=self.business,
            name="Bad Expense",
            type=Category.CategoryType.EXPENSE,
            account=liability_account,
        )
        missing_income = Category.objects.create(
            business=self.business,
            name="Missing Income",
            type=Category.CategoryType.INCOME,
            account=None,
        )

        call_command("fix_category_account_alignment")

        for category in Category.objects.filter(id__in=[bad_income.id, missing_income.id]):
            category.refresh_from_db()
            self.assertEqual(category.account, self.income_default)
            self.assertEqual(category.account.type, Account.AccountType.INCOME)

        bad_expense.refresh_from_db()
        self.assertEqual(bad_expense.account, self.expense_default)
        self.assertEqual(bad_expense.account.type, Account.AccountType.EXPENSE)
