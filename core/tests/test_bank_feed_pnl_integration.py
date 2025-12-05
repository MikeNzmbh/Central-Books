from datetime import date, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from core.accounting_defaults import ensure_default_accounts
from core.models import (
    Account,
    BankAccount,
    BankTransaction,
    Business,
    Category,
    Customer,
    Expense,
    Invoice,
    JournalLine,
    Supplier,
)
from core.views import _post_income_entry
from core.accounting_posting_expenses import post_expense_paid
from core.services.ledger_metrics import calculate_ledger_income, calculate_ledger_expenses
from core.reconciliation import Allocation, allocate_bank_transaction
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

    def test_direct_income_allocation_falls_back_to_income_account(self):
        wrong_account = Account.objects.create(
            business=self.business,
            name="Asset Holding",
            code="1600",
            type=Account.AccountType.ASSET,
        )
        bank_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=date.today(),
            description="Client deposit",
            amount=Decimal("200.00"),
        )

        entry = allocate_bank_transaction(
            bank_tx=bank_tx,
            allocations=[
                Allocation(kind="DIRECT_INCOME", amount=Decimal("200.00"), account_id=wrong_account.id)
            ],
            user=None,
        )

        income_lines = JournalLine.objects.filter(
            journal_entry=entry, account__type=Account.AccountType.INCOME
        )
        self.assertEqual(income_lines.count(), 1)
        self.assertEqual(income_lines.first().account, self.defaults["sales"])

    def test_direct_expense_allocation_falls_back_to_expense_account(self):
        wrong_account = Account.objects.create(
            business=self.business,
            name="Random Liability",
            code="2601",
            type=Account.AccountType.LIABILITY,
        )
        bank_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=date.today(),
            description="Vendor payment",
            amount=Decimal("-150.00"),
        )

        entry = allocate_bank_transaction(
            bank_tx=bank_tx,
            allocations=[
                Allocation(kind="DIRECT_EXPENSE", amount=Decimal("150.00"), account_id=wrong_account.id)
            ],
            user=None,
        )

        expense_lines = JournalLine.objects.filter(
            journal_entry=entry, account__type=Account.AccountType.EXPENSE
        )
        self.assertEqual(expense_lines.count(), 1)
        self.assertEqual(expense_lines.first().account, self.defaults["opex"])

    def test_invoice_allocation_does_not_create_income_line(self):
        customer = Customer.objects.create(business=self.business, name="Alice")
        invoice = Invoice.objects.create(
            business=self.business,
            customer=customer,
            invoice_number="INV-001",
            issue_date=date.today(),
            due_date=date.today(),
            status=Invoice.Status.SENT,
            total_amount=Decimal("100.00"),
            net_total=Decimal("100.00"),
            tax_total=Decimal("0.00"),
            grand_total=Decimal("100.00"),
        )
        bank_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=date.today(),
            description="Invoice payment",
            amount=Decimal("100.00"),
        )

        entry = allocate_bank_transaction(
            bank_tx=bank_tx,
            allocations=[Allocation(kind="INVOICE", amount=Decimal("100.00"), id=invoice.id)],
            user=None,
        )

        income_lines = JournalLine.objects.filter(
            journal_entry=entry, account__type=Account.AccountType.INCOME
        )
        self.assertEqual(income_lines.count(), 0)
        ar_lines = JournalLine.objects.filter(journal_entry=entry, account=self.defaults["ar"])
        self.assertEqual(ar_lines.count(), 1)


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


class BankOnlyPLFlowTests(TestCase):
    """
    Tests that a bank-only workflow produces correct P&L numbers.
    Simulates a workspace where user allocates bank transactions without creating
    invoices/expenses first.
    """

    def setUp(self):
        user = get_user_model().objects.create_user(
            username="bankonly", email="bank@example.com", password="pass"
        )
        self.business = Business.objects.create(name="BankOnlyCo", currency="USD", owner_user=user)
        self.defaults = ensure_default_accounts(self.business)
        self.bank_account = BankAccount.objects.create(
            business=self.business,
            name="Main Account",
            account_number_mask="0001",
            bank_name="TestBank",
        )
        self.bank_account.account = self.defaults["cash"]
        self.bank_account.save()
        self.today = date.today()
        self.month_start = self.today.replace(day=1)

    def test_full_bank_only_workflow_produces_correct_pl(self):
        """
        Scenario:
        - Deposit $1000 categorized as direct income
        - Withdrawal $300 categorized as direct expense
        - Invoice paid (issued prior month, paid this month) - should NOT add to P&L

        Expected:
        - Income = $1000
        - Expenses = $300
        - Net = $700
        - Invoice payment does not create extra income
        """
        # 1. Direct income via bank allocation
        deposit_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=self.today,
            description="Client payment",
            amount=Decimal("1000.00"),
        )
        income_entry = allocate_bank_transaction(
            bank_tx=deposit_tx,
            allocations=[
                Allocation(kind="DIRECT_INCOME", amount=Decimal("1000.00"), account_id=self.defaults["sales"].id)
            ],
            user=None,
        )

        # 2. Direct expense via bank allocation
        expense_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=self.today,
            description="Vendor payment",
            amount=Decimal("-300.00"),
        )
        expense_entry = allocate_bank_transaction(
            bank_tx=expense_tx,
            allocations=[
                Allocation(kind="DIRECT_EXPENSE", amount=Decimal("300.00"), account_id=self.defaults["opex"].id)
            ],
            user=None,
        )

        # 3. Invoice from prior month, paid this month
        customer = Customer.objects.create(business=self.business, name="OldClient")
        prior_month = self.month_start - timedelta(days=15)
        invoice = Invoice.objects.create(
            business=self.business,
            customer=customer,
            invoice_number="INV-OLD-001",
            issue_date=prior_month,
            due_date=self.today,
            status=Invoice.Status.SENT,
            total_amount=Decimal("500.00"),
            net_total=Decimal("500.00"),
            tax_total=Decimal("0.00"),
            grand_total=Decimal("500.00"),
        )
        payment_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=self.today,
            description="Invoice INV-OLD-001 payment",
            amount=Decimal("500.00"),
        )
        payment_entry = allocate_bank_transaction(
            bank_tx=payment_tx,
            allocations=[Allocation(kind="INVOICE", amount=Decimal("500.00"), id=invoice.id)],
            user=None,
        )

        # Verify P&L for this month using the existing functions
        total_income = calculate_ledger_income(self.business, self.month_start, self.today)
        total_expense = calculate_ledger_expenses(self.business, self.month_start, self.today)
        net = total_income - total_expense

        # Income should be $1000 (from direct income), NOT $1500 (no invoice income)
        self.assertEqual(total_income, Decimal("1000.00"))
        # Expenses should be $300
        self.assertEqual(total_expense, Decimal("300.00"))
        # Net should be $700
        self.assertEqual(net, Decimal("700.00"))

        # The invoice payment should NOT have created any income lines for this month
        income_lines_this_month = JournalLine.objects.filter(
            journal_entry=payment_entry,
            account__type=Account.AccountType.INCOME,
        )
        self.assertEqual(income_lines_this_month.count(), 0)
