from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.accounting_defaults import ensure_default_accounts
from core.models import Business, Customer, Invoice

User = get_user_model()


class InvoiceDraftPaymentTransitionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="draftpay", password="pass")
        self.business = Business.objects.create(name="Biz", currency="CAD", owner_user=self.user)
        ensure_default_accounts(self.business)
        self.customer = Customer.objects.create(business=self.business, name="Cust")

    def test_draft_invoice_promotes_to_partial_when_payment_applied(self):
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number="INV-DRAFT-PART",
            issue_date=timezone.localdate(),
            status=Invoice.Status.DRAFT,
            total_amount=Decimal("100.00"),
        )

        invoice.amount_paid = Decimal("60.00")
        invoice.save()

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PARTIAL)
        self.assertEqual(invoice.balance, Decimal("40.00"))
        self.assertTrue(invoice.posted_journal_entry.filter(description__icontains="Invoice sent").exists())
        self.assertFalse(invoice.posted_journal_entry.filter(description__icontains="Invoice paid").exists())

    def test_draft_invoice_promotes_to_paid_when_fully_settled(self):
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number="INV-DRAFT-PAID",
            issue_date=timezone.localdate(),
            status=Invoice.Status.DRAFT,
            total_amount=Decimal("100.00"),
        )

        invoice.amount_paid = Decimal("100.00")
        invoice.save()

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertEqual(invoice.balance, Decimal("0.00"))
        self.assertTrue(invoice.posted_journal_entry.filter(description__icontains="Invoice sent").exists())
        self.assertTrue(invoice.posted_journal_entry.filter(description__icontains="Invoice paid").exists())

