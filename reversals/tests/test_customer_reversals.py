from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from core.accounting_defaults import ensure_default_accounts
from core.models import BankAccount, BankTransaction, Business, Customer, Invoice, JournalEntry
from core.reconciliation import Allocation as BankAllocation
from core.reconciliation import allocate_bank_transaction
from reversals.models import CustomerCreditMemo, CustomerDeposit, CustomerRefund
from reversals.services.posting import (
    apply_customer_deposit_to_invoices,
    post_customer_credit_memo,
    post_customer_deposit,
    post_customer_refund,
)
from reversals.services.voiding import (
    void_customer_credit_memo,
    void_customer_deposit,
    void_customer_refund,
)
from taxes.models import TaxGroup, TransactionLineTaxDetail
from taxes.services import compute_tax_period_snapshot

User = get_user_model()


class CustomerReversalsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rev", password="pass")
        self.business = Business.objects.create(name="RevCo", currency="CAD", owner_user=self.user)
        self.defaults = ensure_default_accounts(self.business)
        self.customer = Customer.objects.create(business=self.business, name="Acme")
        self.tax_group = TaxGroup.objects.get(business=self.business, display_name="CA-ON HST 13%")

    def _create_invoice(self, *, invoice_number: str, net: Decimal) -> Invoice:
        return Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number=invoice_number,
            issue_date=timezone.localdate(),
            status=Invoice.Status.SENT,
            description="Test",
            total_amount=net,
            tax_group=self.tax_group,
        )

    def test_credit_memo_creates_negative_tax_details_and_affects_snapshot(self):
        invoice = self._create_invoice(invoice_number="INV-1", net=Decimal("100.00"))

        invoice_ct = ContentType.objects.get_for_model(Invoice)
        inv_details = list(
            TransactionLineTaxDetail.objects.filter(
                business=self.business,
                transaction_line_content_type=invoice_ct,
                transaction_line_object_id=invoice.id,
            )
        )
        self.assertTrue(inv_details)
        self.assertTrue(all(d.document_side == TransactionLineTaxDetail.DocumentSide.SALE for d in inv_details))

        credit = CustomerCreditMemo.objects.create(
            business=self.business,
            customer=self.customer,
            source_invoice=invoice,
            posting_date=timezone.localdate(),
            status=CustomerCreditMemo.Status.DRAFT,
            net_total=Decimal("50.00"),
            tax_total=Decimal("0.00"),
            grand_total=Decimal("50.00"),
            tax_group=self.tax_group,
        )
        post_customer_credit_memo(credit)
        credit.refresh_from_db()
        self.assertEqual(credit.status, CustomerCreditMemo.Status.POSTED)
        self.assertEqual(credit.tax_total, Decimal("6.50"))
        self.assertEqual(credit.grand_total, Decimal("56.50"))

        credit_ct = ContentType.objects.get_for_model(CustomerCreditMemo)
        credit_details = list(
            TransactionLineTaxDetail.objects.filter(
                business=self.business,
                transaction_line_content_type=credit_ct,
                transaction_line_object_id=credit.id,
            )
        )
        self.assertTrue(credit_details)
        self.assertTrue(all(d.tax_amount_txn_currency < 0 for d in credit_details))
        self.assertTrue(all(d.document_side == TransactionLineTaxDetail.DocumentSide.SALE for d in credit_details))

        period_key = f"{timezone.localdate():%Y-%m}"
        snapshot = compute_tax_period_snapshot(self.business, period_key)
        summary = snapshot.summary_by_jurisdiction or {}
        on = summary.get("CA-ON") or {}
        self.assertAlmostEqual(on.get("taxable_sales", 0), 50.0)
        self.assertAlmostEqual(on.get("tax_collected", 0), 6.5)

    def test_bank_reconciliation_invoice_allocation_does_not_post_invoice_paid_entry(self):
        bank_account = BankAccount.objects.create(
            business=self.business,
            name="Main",
            usage_role=BankAccount.UsageRole.OPERATING,
            account=self.defaults["cash"],
        )
        invoice = self._create_invoice(invoice_number="INV-2", net=Decimal("500.00"))
        bank_tx = BankTransaction.objects.create(
            bank_account=bank_account,
            date=timezone.localdate(),
            description="Invoice payment",
            amount=Decimal("565.00"),
        )

        allocate_bank_transaction(
            bank_tx=bank_tx,
            allocations=[BankAllocation(kind="INVOICE", amount=Decimal("565.00"), id=invoice.id)],
            user=None,
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)

        invoice_ct = ContentType.objects.get_for_model(Invoice)
        paid_entries = JournalEntry.objects.filter(
            business=self.business,
            source_content_type=invoice_ct,
            source_object_id=invoice.id,
            description__icontains="Invoice paid",
        )
        self.assertEqual(paid_entries.count(), 0)

    def test_deposit_apply_creates_allocation_and_journal(self):
        bank_account = BankAccount.objects.create(
            business=self.business,
            name="Main",
            usage_role=BankAccount.UsageRole.OPERATING,
            account=self.defaults["cash"],
        )
        deposit = CustomerDeposit.objects.create(
            business=self.business,
            customer=self.customer,
            bank_account=bank_account,
            posting_date=timezone.localdate(),
            status=CustomerDeposit.Status.DRAFT,
            amount=Decimal("200.00"),
            currency=self.business.currency,
        )
        post_customer_deposit(deposit)
        deposit.refresh_from_db()
        self.assertEqual(deposit.status, CustomerDeposit.Status.POSTED)

        invoice = self._create_invoice(invoice_number="INV-3", net=Decimal("100.00"))
        entry = apply_customer_deposit_to_invoices(
            deposit=deposit,
            invoice_amounts=[(invoice, Decimal("50.00"))],
            user=self.user,
        )
        self.assertIsNotNone(entry.allocation_operation_id)
        self.assertEqual(entry.lines.count(), 2)

    def test_void_credit_memo_voids_journal_and_deletes_tax_details(self):
        invoice = self._create_invoice(invoice_number="INV-VOID-1", net=Decimal("100.00"))
        credit = CustomerCreditMemo.objects.create(
            business=self.business,
            customer=self.customer,
            source_invoice=invoice,
            posting_date=timezone.localdate(),
            status=CustomerCreditMemo.Status.DRAFT,
            net_total=Decimal("10.00"),
            tax_total=Decimal("0.00"),
            grand_total=Decimal("10.00"),
            tax_group=self.tax_group,
        )
        entry = post_customer_credit_memo(credit)
        self.assertFalse(entry.is_void)

        credit_ct = ContentType.objects.get_for_model(CustomerCreditMemo)
        self.assertTrue(
            TransactionLineTaxDetail.objects.filter(
                business=self.business,
                transaction_line_content_type=credit_ct,
                transaction_line_object_id=credit.id,
            ).exists()
        )

        void_customer_credit_memo(credit_memo=credit, user=self.user, reason="mistake")
        credit.refresh_from_db()
        entry.refresh_from_db()

        self.assertEqual(credit.status, CustomerCreditMemo.Status.VOIDED)
        self.assertTrue(entry.is_void)
        self.assertFalse(
            TransactionLineTaxDetail.objects.filter(
                business=self.business,
                transaction_line_content_type=credit_ct,
                transaction_line_object_id=credit.id,
            ).exists()
        )

    def test_void_deposit_and_refund_voids_journal(self):
        bank_account = BankAccount.objects.create(
            business=self.business,
            name="Main",
            usage_role=BankAccount.UsageRole.OPERATING,
            account=self.defaults["cash"],
        )
        deposit = CustomerDeposit.objects.create(
            business=self.business,
            customer=self.customer,
            bank_account=bank_account,
            posting_date=timezone.localdate(),
            status=CustomerDeposit.Status.DRAFT,
            amount=Decimal("200.00"),
            currency=self.business.currency,
        )
        dep_entry = post_customer_deposit(deposit)
        self.assertFalse(dep_entry.is_void)

        refund = CustomerRefund.objects.create(
            business=self.business,
            customer=self.customer,
            bank_account=bank_account,
            posting_date=timezone.localdate(),
            status=CustomerRefund.Status.DRAFT,
            amount=Decimal("50.00"),
            currency=self.business.currency,
            deposit=deposit,
        )
        ref_entry = post_customer_refund(refund)
        self.assertFalse(ref_entry.is_void)

        void_customer_refund(refund=refund, user=self.user, reason="duplicate")
        refund.refresh_from_db()
        ref_entry.refresh_from_db()
        self.assertEqual(refund.status, CustomerRefund.Status.VOIDED)
        self.assertTrue(ref_entry.is_void)

        void_customer_deposit(deposit=deposit, user=self.user, reason="duplicate deposit")
        deposit.refresh_from_db()
        dep_entry.refresh_from_db()
        self.assertEqual(deposit.status, CustomerDeposit.Status.VOIDED)
        self.assertTrue(dep_entry.is_void)
