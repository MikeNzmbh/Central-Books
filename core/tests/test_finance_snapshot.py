from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.finance_snapshot import compute_finance_snapshot
from core.models import Business, Account, JournalEntry, JournalLine, Invoice, Customer, BankAccount, BankTransaction

User = get_user_model()


class FinanceSnapshotTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="finance", password="pass123")
        self.business = Business.objects.create(
            name="Finance Co",
            currency="USD",
            owner_user=self.user,
        )
        # Basic accounts
        self.cash = Account.objects.create(business=self.business, code="1000", name="Cash", type=Account.AccountType.ASSET)
        self.income = Account.objects.create(business=self.business, code="4000", name="Sales", type=Account.AccountType.INCOME)
        self.expense = Account.objects.create(business=self.business, code="6000", name="Expenses", type=Account.AccountType.EXPENSE)
        self.bank = BankAccount.objects.create(business=self.business, name="Operating", account=self.cash)

    def test_snapshot_returns_defaults(self):
        snap = compute_finance_snapshot(self.business)
        self.assertIn("cash_health", snap)
        self.assertIn("revenue_expense", snap)
        self.assertIn("ar_health", snap)

    def test_snapshot_uses_bank_transactions_for_burn(self):
        today = timezone.localdate()
        BankTransaction.objects.create(
            bank_account=self.bank,
            date=today - timedelta(days=10),
            description="Vendor payment",
            amount=Decimal("-900.00"),
        )
        snap = compute_finance_snapshot(self.business)
        self.assertGreaterEqual(snap["cash_health"]["monthly_burn"], 0)

    def test_snapshot_includes_ar_buckets(self):
        customer = Customer.objects.create(business=self.business, name="ACME")
        Invoice.objects.create(
            business=self.business,
            customer=customer,
            invoice_number="INV-1",
            issue_date=timezone.localdate() - timedelta(days=45),
            due_date=timezone.localdate() - timedelta(days=15),
            status=Invoice.Status.SENT,
            total_amount=Decimal("1000.00"),
            balance=Decimal("800.00"),
        )
        snap = compute_finance_snapshot(self.business)
        self.assertGreater(snap["ar_health"]["buckets"]["30"], 0)
