from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase

from core.models import Business, Customer, Supplier, Invoice, Expense
from taxes.bootstrap import seed_canadian_defaults
from taxes.models import TaxAnomaly, TaxGroup

User = get_user_model()


class TaxDocumentApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="taxdoc", password="pass")
        self.business = Business.objects.create(name="Doc Biz", currency="CAD", owner_user=self.user)
        seed_canadian_defaults(self.business)
        self.customer = Customer.objects.create(business=self.business, name="Cust")
        self.supplier = Supplier.objects.create(business=self.business, name="Supp")

        self.client = Client()
        self.client.force_login(self.user)

        self.other_user = User.objects.create_user(username="taxdoc2", password="pass")
        self.other_business = Business.objects.create(name="Other Biz", currency="CAD", owner_user=self.other_user)

    def test_invoice_tax_drilldown_basic(self):
        tax_group = TaxGroup.objects.get(business=self.business, display_name="CA-ON HST 13%")
        inv = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number="INV-100",
            issue_date=date(2025, 4, 15),
            due_date=date(2025, 5, 15),
            total_amount=Decimal("100.00"),
            status=Invoice.Status.SENT,
            tax_group=tax_group,
        )
        resp = self.client.get(f"/api/tax/document/invoice/{inv.id}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], inv.id)
        self.assertEqual(data["period_key"], "2025-04")
        self.assertEqual(data["totals"]["tax_total"], "13.00")
        self.assertTrue(data["line_level_available"])
        self.assertEqual(len(data["lines"]), 1)
        self.assertEqual(len(data["lines"][0]["tax_details"]), 1)
        juris = [r["jurisdiction_code"] for r in data["breakdown"]["by_jurisdiction"]]
        self.assertIn("CA-ON", juris)
        self.assertEqual(data["anomalies"], [])

    def test_invoice_tax_drilldown_with_linked_anomaly_and_link(self):
        tax_group = TaxGroup.objects.get(business=self.business, display_name="CA-ON HST 13%")
        inv = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number="INV-101",
            issue_date=date(2025, 4, 15),
            total_amount=Decimal("100.00"),
            status=Invoice.Status.SENT,
            tax_group=tax_group,
        )
        ct = ContentType.objects.get_for_model(Invoice)
        TaxAnomaly.objects.create(
            business=self.business,
            period_key="2025-04",
            code="T1_RATE_MISMATCH",
            severity=TaxAnomaly.AnomalySeverity.HIGH,
            status=TaxAnomaly.AnomalyStatus.OPEN,
            description="Rate mismatch",
            linked_transaction_ct=ct,
            linked_transaction_id=inv.id,
            task_code="T1",
        )
        resp = self.client.get(f"/api/tax/document/invoice/{inv.id}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["anomalies"]), 1)
        self.assertIn("severity=high", data["tax_guardian_link"])
        self.assertIn("period=2025-04", data["tax_guardian_link"])

    def test_expense_tax_drilldown_and_wrong_business_404(self):
        tax_group = TaxGroup.objects.get(business=self.business, display_name="CA-ON HST 13%")
        exp = Expense.objects.create(
            business=self.business,
            supplier=self.supplier,
            description="Office supplies",
            date=date(2025, 4, 20),
            amount=Decimal("100.00"),
            status=Expense.Status.PAID,
            tax_group=tax_group,
        )
        resp = self.client.get(f"/api/tax/document/expense/{exp.id}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["period_key"], "2025-04")
        self.assertEqual(data["totals"]["tax_total"], "13.00")

        other_exp = Expense.objects.create(
            business=self.other_business,
            supplier=Supplier.objects.create(business=self.other_business, name="Other Supp"),
            description="Other",
            date=date(2025, 4, 1),
            amount=Decimal("10.00"),
            status=Expense.Status.UNPAID,
        )
        resp = self.client.get(f"/api/tax/document/expense/{other_exp.id}/")
        self.assertEqual(resp.status_code, 404)

