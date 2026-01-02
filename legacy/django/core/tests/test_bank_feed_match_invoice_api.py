from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from core.accounting_defaults import ensure_default_accounts
from core.models import BankAccount, BankTransaction, Business, Customer, Invoice

User = get_user_model()


class BankFeedMatchInvoiceApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="bankmatch", password="pass")
        self.business = Business.objects.create(name="Biz", currency="CAD", owner_user=self.user)
        self.defaults = ensure_default_accounts(self.business)
        self.customer = Customer.objects.create(business=self.business, name="Cust")
        self.client = Client()
        self.client.force_login(self.user)

        self.bank_account = BankAccount.objects.create(
            business=self.business,
            name="Main",
            usage_role=BankAccount.UsageRole.OPERATING,
            account=self.defaults["cash"],
        )

    def test_match_invoice_sets_amount_paid_and_keeps_paid_status(self):
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number="INV-100",
            issue_date=timezone.localdate(),
            status=Invoice.Status.SENT,
            total_amount=Decimal("100.00"),
        )
        bank_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=timezone.localdate(),
            description="Customer payment",
            amount=Decimal("100.00"),
        )

        resp = self.client.post(
            f"/api/banking/feed/transactions/{bank_tx.id}/match-invoice/",
            data={"invoice_id": invoice.id},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertEqual(invoice.amount_paid, invoice.grand_total)
        self.assertEqual(invoice.balance, Decimal("0.00"))

