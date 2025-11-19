import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .accounting_defaults import ensure_default_accounts
from .models import (
    Account,
    BankAccount,
    BankTransaction,
    Business,
    Category,
    Customer,
    Expense,
    Invoice,
    JournalEntry,
    JournalLine,
    Supplier,
    TaxRate,
)
from .accounting_posting import post_invoice_sent
from .accounting_posting_expenses import post_expense_paid
from .reconciliation import (
    Allocation,
    add_bank_match,
    allocate_bank_transaction,
    recompute_bank_transaction_status,
)


class ReconciliationModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass")
        self.business = Business.objects.create(
            name="Central Books",
            currency="USD",
            owner_user=self.owner,
        )
        self.cash_account = Account.objects.create(
            business=self.business,
            code="1010",
            name="Cash",
            type=Account.AccountType.ASSET,
        )
        self.income_account = Account.objects.create(
            business=self.business,
            code="4010",
            name="Sales",
            type=Account.AccountType.INCOME,
        )
        self.bank_account = BankAccount.objects.create(
            business=self.business,
            name="Operating",
            bank_name="Central",
            usage_role=BankAccount.UsageRole.OPERATING,
        )
        self.bank_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=timezone.localdate(),
            description="Customer payment",
            amount=Decimal("100.00"),
        )
        self.journal_entry = JournalEntry.objects.create(
            business=self.business,
            date=timezone.localdate(),
            description="Invoice paid",
        )
        JournalLine.objects.create(
            journal_entry=self.journal_entry,
            account=self.cash_account,
            debit=Decimal("100.00"),
            credit=Decimal("0.00"),
        )
        JournalLine.objects.create(
            journal_entry=self.journal_entry,
            account=self.income_account,
            debit=Decimal("0.00"),
            credit=Decimal("100.00"),
        )

    def test_add_bank_match_updates_status(self):
        add_bank_match(self.bank_tx, self.journal_entry)
        self.bank_tx.refresh_from_db()
        self.assertEqual(self.bank_tx.status, BankTransaction.TransactionStatus.MATCHED_SINGLE)
        self.assertEqual(self.bank_tx.allocated_amount, Decimal("100.00"))

    def test_partial_match_marks_partial_status(self):
        add_bank_match(self.bank_tx, self.journal_entry, amount=Decimal("40.00"))
        self.bank_tx.refresh_from_db()
        self.assertEqual(self.bank_tx.status, BankTransaction.TransactionStatus.PARTIAL)
        self.assertEqual(self.bank_tx.allocated_amount, Decimal("40.00"))

    def test_recompute_keeps_excluded_status(self):
        self.bank_tx.status = BankTransaction.TransactionStatus.EXCLUDED
        self.bank_tx.save(update_fields=["status"])
        add_bank_match(self.bank_tx, self.journal_entry)
        self.bank_tx.refresh_from_db()
        self.assertEqual(self.bank_tx.status, BankTransaction.TransactionStatus.EXCLUDED)
        recompute_bank_transaction_status(self.bank_tx)
        self.bank_tx.refresh_from_db()
        self.assertEqual(self.bank_tx.allocated_amount, Decimal("100.00"))


class InvoicePaymentStateTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass")
        self.business = Business.objects.create(
            name="Central Books",
            currency="USD",
            owner_user=self.owner,
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="Acme Corp",
            email="billing@example.com",
        )

    def test_paid_invoice_sets_amount_paid(self):
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number="INV-100",
            total_amount=Decimal("500.00"),
            status=Invoice.Status.SENT,
        )
        invoice.status = Invoice.Status.PAID
        invoice.save()
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, Decimal("500.00"))
        self.assertEqual(invoice.balance, Decimal("0.00"))
        self.assertEqual(invoice.status, Invoice.Status.PAID)

    def test_partial_invoice_updates_balance(self):
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number="INV-200",
            total_amount=Decimal("300.00"),
            amount_paid=Decimal("120.00"),
            status=Invoice.Status.SENT,
        )
        invoice.save()
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, Decimal("120.00"))
        self.assertEqual(invoice.balance, Decimal("180.00"))
        self.assertEqual(invoice.status, Invoice.Status.PARTIAL)


class ExpensePaymentStateTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass")
        self.business = Business.objects.create(
            name="Central Books",
            currency="USD",
            owner_user=self.owner,
        )
        self.supplier = Supplier.objects.create(
            business=self.business,
            name="Supplies Inc.",
        )
        self.category = Category.objects.create(
            business=self.business,
            name="Office",
            type=Category.CategoryType.EXPENSE,
        )

    def test_mark_paid_sets_amount_fields(self):
        expense = Expense.objects.create(
            business=self.business,
            supplier=self.supplier,
            category=self.category,
            description="Office supplies",
            amount=Decimal("75.00"),
        )
        expense.mark_paid()
        expense.save()
        expense.refresh_from_db()
        self.assertEqual(expense.amount_paid, Decimal("75.00"))
        self.assertEqual(expense.balance, Decimal("0.00"))
        self.assertEqual(expense.status, Expense.Status.PAID)

    def test_partial_expense_sets_partial_status(self):
        expense = Expense.objects.create(
            business=self.business,
            supplier=self.supplier,
            category=self.category,
            description="Consulting",
            amount=Decimal("200.00"),
            amount_paid=Decimal("50.00"),
        )
        expense.save()
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.PARTIAL)
        self.assertEqual(expense.balance, Decimal("150.00"))


class AllocationEngineTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass")
        self.business = Business.objects.create(
            name="Central Books",
            currency="USD",
            owner_user=self.owner,
        )
        self.defaults = ensure_default_accounts(self.business)
        self.bank_cash = self.defaults["cash"]
        self.bank_account = BankAccount.objects.create(
            business=self.business,
            name="Operating",
            bank_name="Central",
            usage_role=BankAccount.UsageRole.OPERATING,
            account=self.bank_cash,
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="Acme Corp",
            email="billing@example.com",
        )
        self.supplier = Supplier.objects.create(
            business=self.business,
            name="Supply Co",
        )
        self.income_account = Account.objects.create(
            business=self.business,
            code="4100",
            name="Consulting Income",
            type=Account.AccountType.INCOME,
        )
        self.expense_account = Account.objects.create(
            business=self.business,
            code="6100",
            name="Professional Fees",
            type=Account.AccountType.EXPENSE,
        )
        self.fee_account = Account.objects.create(
            business=self.business,
            code="6120",
            name="Processor Fees",
            type=Account.AccountType.EXPENSE,
        )
        self.rounding_account = Account.objects.create(
            business=self.business,
            code="9998",
            name="Rounding",
            type=Account.AccountType.EXPENSE,
        )
        self.credit_account = Account.objects.create(
            business=self.business,
            code="2300",
            name="Customer Credits",
            type=Account.AccountType.LIABILITY,
        )

    def _make_invoice(self, amount: str) -> Invoice:
        return Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number=f"INV-{timezone.now().timestamp()}",
            total_amount=Decimal(amount),
            status=Invoice.Status.SENT,
        )

    def _make_bill(self, amount: str) -> Expense:
        return Expense.objects.create(
            business=self.business,
            supplier=self.supplier,
            category=None,
            description="Vendor bill",
            amount=Decimal(amount),
            status=Expense.Status.UNPAID,
        )

    def _make_tx(self, amount: str, description: str = "Bank txn") -> BankTransaction:
        return BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=timezone.localdate(),
            description=description,
            amount=Decimal(amount),
        )

    def test_allocate_single_invoice_payment(self):
        invoice = self._make_invoice("100.00")
        bank_tx = self._make_tx("100.00")

        entry = allocate_bank_transaction(
            bank_tx=bank_tx,
            allocations=[Allocation(kind="INVOICE", id=invoice.id, amount=Decimal("100.00"))],
            user=self.owner,
        )

        bank_tx.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, Decimal("100.00"))
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertEqual(bank_tx.status, BankTransaction.TransactionStatus.MATCHED_SINGLE)
        self.assertEqual(entry.lines.count(), 2)

    def test_allocate_multiple_invoices(self):
        inv1 = self._make_invoice("500.00")
        inv2 = self._make_invoice("700.00")
        inv3 = self._make_invoice("300.00")
        bank_tx = self._make_tx("1500.00")

        allocate_bank_transaction(
            bank_tx=bank_tx,
            allocations=[
                Allocation(kind="INVOICE", id=inv1.id, amount=Decimal("500.00")),
                Allocation(kind="INVOICE", id=inv2.id, amount=Decimal("700.00")),
                Allocation(kind="INVOICE", id=inv3.id, amount=Decimal("300.00")),
            ],
            user=self.owner,
        )

        bank_tx.refresh_from_db()
        self.assertEqual(bank_tx.status, BankTransaction.TransactionStatus.MATCHED_MULTI)
        self.assertEqual(bank_tx.matches.count(), 3)

    def test_allocate_partial_invoice_payment(self):
        invoice = self._make_invoice("1000.00")
        bank_tx = self._make_tx("300.00")

        allocate_bank_transaction(
            bank_tx=bank_tx,
            allocations=[Allocation(kind="INVOICE", id=invoice.id, amount=Decimal("300.00"))],
            user=self.owner,
        )

        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, Decimal("300.00"))
        self.assertEqual(invoice.status, Invoice.Status.PARTIAL)

    def test_allocate_overpayment_creates_credit_line(self):
        invoice = self._make_invoice("1000.00")
        bank_tx = self._make_tx("1200.00")

        entry = allocate_bank_transaction(
            bank_tx=bank_tx,
            allocations=[Allocation(kind="INVOICE", id=invoice.id, amount=Decimal("1000.00"))],
            overpayment=Allocation(
                kind="CREDIT_NOTE",
                account_id=self.credit_account.id,
                amount=Decimal("200.00"),
            ),
            user=self.owner,
        )

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertTrue(
            entry.lines.filter(account=self.credit_account, credit=Decimal("200.00")).exists()
        )

    def test_allocate_net_of_fee_payout(self):
        bank_tx = self._make_tx("97.00")

        entry = allocate_bank_transaction(
            bank_tx=bank_tx,
            allocations=[
                Allocation(
                    kind="DIRECT_INCOME",
                    account_id=self.income_account.id,
                    amount=Decimal("100.00"),
                )
            ],
            fees=Allocation(
                kind="DIRECT_EXPENSE",
                account_id=self.fee_account.id,
                amount=Decimal("3.00"),
            ),
            user=self.owner,
        )

        lines = list(entry.lines.all())
        self.assertTrue(
            any(line.account == self.fee_account and line.debit == Decimal("3.00") for line in lines)
        )
        self.assertTrue(
            any(line.account == self.income_account and line.credit == Decimal("100.00") for line in lines)
        )

    def test_allocate_rounding_difference(self):
        invoice = self._make_invoice("500.00")
        bank_tx = self._make_tx("499.98")

        allocate_bank_transaction(
            bank_tx=bank_tx,
            allocations=[Allocation(kind="INVOICE", id=invoice.id, amount=Decimal("500.00"))],
            rounding=Allocation(
                kind="DIRECT_EXPENSE",
                account_id=self.rounding_account.id,
                amount=Decimal("0.02"),
            ),
            user=self.owner,
        )

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)

    def test_allocate_bill_payment(self):
        bill = self._make_bill("250.00")
        bank_tx = self._make_tx("-250.00", description="Bill payment")

        allocate_bank_transaction(
            bank_tx=bank_tx,
            allocations=[Allocation(kind="BILL", id=bill.id, amount=Decimal("250.00"))],
            user=self.owner,
        )

        bill.refresh_from_db()
        self.assertEqual(bill.status, Expense.Status.PAID)

    def test_allocate_validation_invoice_over_allocation(self):
        invoice = self._make_invoice("100.00")
        bank_tx = self._make_tx("100.00")

        with self.assertRaises(ValidationError):
            allocate_bank_transaction(
                bank_tx=bank_tx,
                allocations=[Allocation(kind="INVOICE", id=invoice.id, amount=Decimal("120.00"))],
                user=self.owner,
            )

    def test_allocate_validation_bank_mismatch(self):
        invoice = self._make_invoice("100.00")
        bank_tx = self._make_tx("100.00")

        with self.assertRaises(ValidationError):
            allocate_bank_transaction(
                bank_tx=bank_tx,
                allocations=[Allocation(kind="INVOICE", id=invoice.id, amount=Decimal("80.00"))],
                user=self.owner,
            )

    def test_allocate_idempotent(self):
        invoice = self._make_invoice("100.00")
        bank_tx = self._make_tx("100.00")

        entry1 = allocate_bank_transaction(
            bank_tx=bank_tx,
            allocations=[Allocation(kind="INVOICE", id=invoice.id, amount=Decimal("100.00"))],
            user=self.owner,
            operation_id="tx-1",
        )
        entry2 = allocate_bank_transaction(
            bank_tx=bank_tx,
            allocations=[Allocation(kind="INVOICE", id=invoice.id, amount=Decimal("100.00"))],
            user=self.owner,
            operation_id="tx-1",
        )
        self.assertEqual(entry1.pk, entry2.pk)


class TaxCalculationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="taxer", password="pass")
        self.business = Business.objects.create(
            name="Taxable Co",
            currency="CAD",
            owner_user=self.owner,
        )
        self.defaults = ensure_default_accounts(self.business)
        self.customer = Customer.objects.create(
            business=self.business,
            name="Tax Customer",
            email="tax@example.com",
        )
        self.supplier = Supplier.objects.create(
            business=self.business,
            name="Tax Supplier",
        )

    def test_invoice_tax_rate_computation_and_posting(self):
        rate = TaxRate.objects.create(
            business=self.business,
            name="GST/HST 13%",
            code="GST13",
            percentage=Decimal("13.00"),
            is_recoverable=True,
            is_default_sales=True,
        )
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number="INV-TAX-1",
            total_amount=Decimal("100.00"),
            tax_amount=Decimal("0.00"),
            tax_rate=rate,
            status=Invoice.Status.SENT,
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.net_total, Decimal("100.00"))
        self.assertEqual(invoice.tax_total, Decimal("13.00"))
        self.assertEqual(invoice.grand_total, Decimal("113.00"))

        post_invoice_sent(invoice)
        entry = JournalEntry.objects.filter(
            business=self.business,
            source_object_id=invoice.id,
            description__icontains="Invoice sent",
        ).first()
        self.assertIsNotNone(entry)
        lines = { (line.account.code, line.account.type): line for line in entry.lines.all() }
        self.assertEqual(lines[("1200", Account.AccountType.ASSET)].debit, Decimal("113.00"))
        self.assertEqual(lines[("4010", Account.AccountType.INCOME)].credit, Decimal("100.00"))
        self.assertEqual(lines[("2200", Account.AccountType.LIABILITY)].credit, Decimal("13.00"))

    def test_expense_recoverable_tax_split(self):
        rate = TaxRate.objects.create(
            business=self.business,
            name="Input GST 13%",
            code="GSTIN13",
            percentage=Decimal("13.00"),
            is_recoverable=True,
            is_default_purchases=True,
        )
        expense = Expense.objects.create(
            business=self.business,
            supplier=self.supplier,
            description="Supplies",
            amount=Decimal("200.00"),
            tax_amount=Decimal("0.00"),
            tax_rate=rate,
            status=Expense.Status.PAID,
        )
        expense.refresh_from_db()
        self.assertEqual(expense.net_total, Decimal("200.00"))
        self.assertEqual(expense.tax_total, Decimal("26.00"))
        self.assertEqual(expense.grand_total, Decimal("226.00"))
        entry = post_expense_paid(expense)
        self.assertIsNotNone(entry)
        lines = list(entry.lines.all())
        expense_debit = next(line for line in lines if line.account == self.defaults["opex"])
        tax_debit = next(line for line in lines if line.account == self.defaults["tax_recoverable"])
        bank_credit = next(line for line in lines if line.account == self.defaults["cash"])
        self.assertEqual(expense_debit.debit, Decimal("200.00"))
        self.assertEqual(tax_debit.debit, Decimal("26.00"))
        self.assertEqual(bank_credit.credit, Decimal("226.00"))

    def test_expense_non_recoverable_tax_rolls_into_expense(self):
        rate = TaxRate.objects.create(
            business=self.business,
            name="Non recoverable",
            code="NONREC",
            percentage=Decimal("5.00"),
            is_recoverable=False,
        )
        expense = Expense.objects.create(
            business=self.business,
            supplier=self.supplier,
            description="Meals",
            amount=Decimal("100.00"),
            tax_amount=Decimal("0.00"),
            tax_rate=rate,
            status=Expense.Status.PAID,
        )
        entry = post_expense_paid(expense)
        lines = list(entry.lines.all())
        expense_debit = next(line for line in lines if line.account == self.defaults["opex"])
        bank_credit = next(line for line in lines if line.account == self.defaults["cash"])
        self.assertEqual(expense_debit.debit, Decimal("105.00"))
        self.assertEqual(bank_credit.credit, Decimal("105.00"))


class AllocationAPITests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass")
        self.business = Business.objects.create(
            name="Central Books",
            currency="USD",
            owner_user=self.owner,
        )
        defaults = ensure_default_accounts(self.business)
        self.cash = defaults["cash"]
        self.bank_account = BankAccount.objects.create(
            business=self.business,
            name="Operating",
            bank_name="Central",
            usage_role=BankAccount.UsageRole.OPERATING,
            account=self.cash,
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="API Customer",
            email="api@example.com",
        )
        self.invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number="API-100",
            total_amount=Decimal("100.00"),
            status=Invoice.Status.SENT,
        )
        self.bank_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=timezone.localdate(),
            description="API allocation",
            amount=Decimal("100.00"),
        )
        self.client.force_login(self.owner)

    def test_allocate_invoice_via_api(self):
        url = reverse("api_allocate_bank_transaction", args=[self.bank_tx.id])
        payload = {
            "allocations": [
                {"type": "INVOICE", "id": self.invoice.id, "amount": "100.00"},
            ],
            "tolerance_cents": 2,
            "operation_id": "api-op-1",
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("ok"))
        self.invoice.refresh_from_db()
        self.bank_tx.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.assertEqual(
            self.bank_tx.status,
            BankTransaction.TransactionStatus.MATCHED_SINGLE,
        )
