from decimal import Decimal
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Business, Customer, Invoice, TaxRate


class InvoiceTaxCalculationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="taxuser", password="pass")
        self.business = Business.objects.create(
            name="Taxable Co",
            currency="CAD",
            owner_user=self.user,
        )
        self.tax_rate = TaxRate.ensure_defaults(self.business) or TaxRate.objects.get(
            business=self.business, code="GST13"
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="Acme Corp",
            email="acme@example.com",
        )

    def test_invoice_saved_uses_tax_rate_percentage(self):
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number="INV-1",
            issue_date=date.today(),
            total_amount=Decimal("100.00"),
            tax_rate=TaxRate.objects.filter(business=self.business, code="GST13").first(),
            description="Test",
            status=Invoice.Status.SENT,
            notes="",
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.tax_total, Decimal("13.00"))
        self.assertEqual(invoice.grand_total, Decimal("113.00"))
