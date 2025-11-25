from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from core.models import (
    Business,
    Account,
    Invoice,
    Customer,
    Expense,
    Supplier,
    JournalEntry,
    JournalLine,
)
from taxes.reporting import (
    gst_hst_summary,
    net_tax_position,
    get_us_sales_tax_summary,
)
from .bootstrap import seed_canadian_defaults
from .models import TaxComponent, TaxGroup, TaxRate, TransactionLineTaxDetail
from .services import TaxEngine


class TaxSeedingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="seeduser", password="pass")
        self.business = Business.objects.create(
            name="Seeded Co",
            currency="CAD",
            owner_user=self.user,
        )
        # Re-run explicitly to ensure deterministic state even if signal skipped in fixtures.
        seed_canadian_defaults(self.business)

    def test_accounts_exist_and_typed(self):
        tax_payable = Account.objects.get(business=self.business, code="2300")
        recoverable = Account.objects.get(business=self.business, code="1400")
        self.assertEqual(tax_payable.type, Account.AccountType.LIABILITY)
        self.assertEqual(recoverable.type, Account.AccountType.ASSET)

    def test_on_hst_group_and_rate(self):
        group = TaxGroup.objects.get(business=self.business, display_name="CA-ON HST 13%")
        self.assertTrue(group.is_system_locked)
        components = list(group.group_components.select_related("component"))
        self.assertEqual(len(components), 1)
        comp = components[0].component
        self.assertAlmostEqual(comp.rate_percentage, Decimal("0.13"))
        rate = TaxRate.objects.filter(component=comp).first()
        self.assertIsNotNone(rate)
        self.assertEqual(rate.rate_decimal, Decimal("0.13"))

    def test_quebec_group_has_two_components(self):
        group = TaxGroup.objects.get(
            business=self.business,
            display_name="CA-QC GST 5% + QST 9.975% (14.975%)",
        )
        comps = list(group.group_components.select_related("component"))
        self.assertEqual(len(comps), 2)
        rates = {c.component.name: c.component.rate_percentage for c in comps}
        self.assertEqual(rates["Federal GST 5%"], Decimal("0.05"))
        self.assertEqual(rates["Quebec QST 9.975%"], Decimal("0.09975"))


class TaxEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="engineuser", password="pass")
        self.business = Business.objects.create(
            name="Engine Co",
            currency="CAD",
            owner_user=self.user,
        )
        seed_canadian_defaults(self.business)

    def test_calculate_for_line_simple_group(self):
        tax_group = TaxGroup.objects.get(business=self.business, display_name="CA-ON HST 13%")
        txn_date = timezone.localdate()

        class DummyLine:
            net_amount = Decimal("100.00")
            product_category = "STANDARD"

        result = TaxEngine.calculate_for_line(
            business=self.business,
            transaction_line=DummyLine(),
            tax_group=tax_group,
            txn_date=txn_date,
            currency="CAD",
        )

        self.assertEqual(result["total_tax_txn_currency"], Decimal("13.00"))
        self.assertEqual(result["total_tax_home_currency_cad"], Decimal("13.00"))

    def test_calculate_for_line_with_fx_and_multiple_components(self):
        tax_group = TaxGroup.objects.get(business=self.business, display_name="CA-BC GST 5% + PST 7%")
        txn_date = timezone.localdate()

        class DummyLine:
            net_amount = Decimal("100.00")
            product_category = "STANDARD"

        result = TaxEngine.calculate_for_line(
            business=self.business,
            transaction_line=DummyLine(),
            tax_group=tax_group,
            txn_date=txn_date,
            currency="USD",
            fx_rate=Decimal("1.30"),
        )

        # Two components: 5% and 7% on base -> 12.00 tax in txn currency.
        self.assertEqual(result["total_tax_txn_currency"], Decimal("12.00"))
        # Converted at 1.30 -> 15.60 CAD.
        self.assertEqual(result["total_tax_home_currency_cad"], Decimal("15.60"))


class TaxLifecycleIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="flowuser", password="pass")
        self.business = Business.objects.create(
            name="Flow Co",
            currency="CAD",
            owner_user=self.user,
        )
        seed_canadian_defaults(self.business)
        self.customer = Customer.objects.create(business=self.business, name="Cust")
        self.supplier = Supplier.objects.create(business=self.business, name="Supp")

    def test_invoice_posts_liability_with_tax_group(self):
        tax_group = TaxGroup.objects.get(business=self.business, display_name="CA-ON HST 13%")
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number="INV-1",
            total_amount=Decimal("100.00"),
            status=Invoice.Status.SENT,
            tax_group=tax_group,
        )
        details = TransactionLineTaxDetail.objects.filter(tax_group=tax_group)
        self.assertEqual(details.count(), 1)
        self.assertEqual(details.first().tax_amount_home_currency_cad, Decimal("13.00"))

        entry = JournalEntry.objects.filter(
            business=self.business,
            source_object_id=invoice.pk,
            description__icontains="Invoice sent",
        ).first()
        self.assertIsNotNone(entry)
        liability_line = entry.lines.filter(account__code="2300").first()
        self.assertIsNotNone(liability_line)
        self.assertEqual(liability_line.credit, Decimal("13.00"))

    def test_expense_posts_recoverable_and_non_recoverable(self):
        tax_group = TaxGroup.objects.get(
            business=self.business,
            display_name="CA-BC GST 5% + PST 7%",
        )
        expense = Expense.objects.create(
            business=self.business,
            supplier=self.supplier,
            description="Office supplies",
            amount=Decimal("100.00"),
            status=Expense.Status.PAID,
            tax_group=tax_group,
        )
        details = TransactionLineTaxDetail.objects.filter(tax_group=tax_group)
        self.assertEqual(details.count(), 2)

        entry = JournalEntry.objects.filter(
            business=self.business,
            source_object_id=expense.pk,
            description__icontains="Expense paid",
        ).first()
        self.assertIsNotNone(entry)
        recoverable_line = entry.lines.filter(account__code="1400").first()
        self.assertIsNotNone(recoverable_line)
        self.assertEqual(recoverable_line.debit, Decimal("5.00"))
        # Expense line should include non-recoverable PST (7)
        expense_line = entry.lines.exclude(account__code__in=["1400", "1010"]).first()
        self.assertIsNotNone(expense_line)
        self.assertEqual(expense_line.debit, Decimal("107.00"))


class FilingAndNetPositionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="filing", password="pass")
        self.business = Business.objects.create(
            name="Report Co",
            currency="CAD",
            owner_user=self.user,
        )
        seed_canadian_defaults(self.business)
        self.customer = Customer.objects.create(business=self.business, name="Cust")
        self.supplier = Supplier.objects.create(business=self.business, name="Supp")

    def _create_invoice(self, amount, tax_group_name, date):
        tax_group = TaxGroup.objects.get(business=self.business, display_name=tax_group_name)
        return Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number=f"INV-{amount}-{tax_group_name}",
            total_amount=Decimal(str(amount)),
            status=Invoice.Status.SENT,
            issue_date=date,
            tax_group=tax_group,
        )

    def _create_expense(self, amount, tax_group_name, date):
        tax_group = TaxGroup.objects.get(business=self.business, display_name=tax_group_name)
        return Expense.objects.create(
            business=self.business,
            supplier=self.supplier,
            description="Expense",
            amount=Decimal(str(amount)),
            status=Expense.Status.PAID,
            date=date,
            tax_group=tax_group,
        )

    def test_gst_hst_summary_per_authority_and_legacy(self):
        on_date = timezone.datetime(2025, 1, 15).date()
        qc_date = timezone.datetime(2025, 1, 16).date()

        self._create_invoice(100, "CA-ON HST 13%", on_date)
        self._create_invoice(200, "CA-QC GST 5% + QST 9.975% (14.975%)", qc_date)
        self._create_expense(100, "CA-BC GST 5% + PST 7%", qc_date)

        # Legacy liability journal on 2200
        acc_2200, _ = Account.objects.get_or_create(
            business=self.business,
            code="2200",
            defaults={
                "name": "Legacy Tax Payable",
                "type": Account.AccountType.LIABILITY,
            },
        )
        je = JournalEntry.objects.create(
            business=self.business,
            date=on_date,
            description="Legacy tax",
        )
        JournalLine.objects.create(journal_entry=je, account=acc_2200, debit=Decimal("0.00"), credit=Decimal("50.00"))
        JournalLine.objects.create(
            journal_entry=je,
            account=Account.objects.filter(business=self.business, type=Account.AccountType.ASSET).first(),
            debit=Decimal("50.00"),
            credit=Decimal("0.00"),
        )

        summary_all = gst_hst_summary(self.business, on_date, qc_date, jurisdiction="ALL")
        self.assertEqual(summary_all["line_101_taxable_sales"], Decimal("300.00"))
        self.assertEqual(summary_all["line_105_tax_collected"], Decimal("42.95"))  # CRA 23 + RQ 19.95
        self.assertEqual(summary_all["line_108_itcs"], Decimal("5.00"))
        self.assertEqual(summary_all["line_109_net_tax"], Decimal("37.95"))
        self.assertGreater(summary_all["ledger_liability"], Decimal("0.00"))  # picks up legacy 2200

        summary_cra = gst_hst_summary(self.business, on_date, qc_date, jurisdiction="CRA")
        self.assertEqual(summary_cra["line_105_tax_collected"], Decimal("23.00"))  # ON 13 + QC GST 10

        summary_rq = gst_hst_summary(self.business, on_date, qc_date, jurisdiction="RQ")
        self.assertEqual(summary_rq["line_105_tax_collected"], Decimal("19.95"))  # QST only

    def test_net_tax_position_helper(self):
        acc_2300 = Account.objects.get(business=self.business, code="2300")
        acc_1400 = Account.objects.get(business=self.business, code="1400")
        je = JournalEntry.objects.create(
            business=self.business,
            date=timezone.localdate(),
            description="Tax balances",
        )
        JournalLine.objects.create(journal_entry=je, account=acc_2300, debit=Decimal("0.00"), credit=Decimal("200.00"))
        JournalLine.objects.create(journal_entry=je, account=acc_1400, debit=Decimal("50.00"), credit=Decimal("0.00"))
        pos = net_tax_position(self.business)
        self.assertEqual(pos["sales_tax_payable"], Decimal("200.00"))
        self.assertEqual(pos["recoverable_tax_asset"], Decimal("50.00"))
        self.assertEqual(pos["net_tax"], Decimal("150.00"))


class USSalesTaxSummaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ususer", password="pass")
        self.business = Business.objects.create(
            name="US Co",
            currency="CAD",
            owner_user=self.user,
        )
        seed_canadian_defaults(self.business)
        self.customer = Customer.objects.create(business=self.business, name="US Cust")
        self.default_account = Account.objects.get(business=self.business, code="2300")

        self.us_ny = TaxComponent.objects.create(
            business=self.business,
            name="US - New York 8.875%",
            rate_percentage=Decimal("0.08875"),
            authority="US-NY",
            is_recoverable=False,
            effective_start_date=timezone.localdate(),
            default_coa_account=self.default_account,
        )
        self.us_ca = TaxComponent.objects.create(
            business=self.business,
            name="US - California 7.25%",
            rate_percentage=Decimal("0.0725"),
            authority="US-CA",
            is_recoverable=False,
            effective_start_date=timezone.localdate(),
            default_coa_account=self.default_account,
        )
        self.ny_group = TaxGroup.objects.create(
            business=self.business,
            display_name="US-NY 8.875%",
            calculation_method=TaxGroup.CalculationMethod.SIMPLE,
            is_system_locked=False,
        )
        self.ny_group.components.add(self.us_ny)
        self.ca_group = TaxGroup.objects.create(
            business=self.business,
            display_name="US-CA 7.25%",
            calculation_method=TaxGroup.CalculationMethod.SIMPLE,
            is_system_locked=False,
        )
        self.ca_group.components.add(self.us_ca)

    def _create_invoice(self, amount, group):
        return Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number=f"US-{amount}-{group.display_name}",
            total_amount=Decimal(str(amount)),
            status=Invoice.Status.SENT,
            issue_date=timezone.localdate(),
            tax_group=group,
        )

    def test_us_sales_tax_summary_groups_by_jurisdiction(self):
        self._create_invoice(Decimal("100.00"), self.ny_group)
        self._create_invoice(Decimal("200.00"), self.ca_group)

        summary = get_us_sales_tax_summary(
            business=self.business,
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
        )

        jurisdictions = {j["code"]: j for j in summary["jurisdictions"]}
        self.assertIn("US-NY", jurisdictions)
        self.assertIn("US-CA", jurisdictions)

        ny = jurisdictions["US-NY"]
        ca = jurisdictions["US-CA"]

        self.assertEqual(ny["gross_taxable_sales_txn"], Decimal("100.00"))
        self.assertEqual(ny["tax_collected_txn"], Decimal("8.88"))  # 8.875 rounded

        self.assertEqual(ca["gross_taxable_sales_txn"], Decimal("200.00"))
        self.assertEqual(ca["tax_collected_txn"], Decimal("14.50"))

        totals = summary["totals"]
        self.assertEqual(totals["gross_taxable_sales_txn"], Decimal("300.00"))
        self.assertEqual(totals["tax_collected_txn"], Decimal("23.38"))
