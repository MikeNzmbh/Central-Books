from decimal import Decimal
from io import StringIO
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.models import (
    Business,
    Account,
    Invoice,
    Customer,
    Item,
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
from .models import (
    TaxComponent,
    TaxGroup,
    TaxGroupComponent,
    TaxRate,
    TaxJurisdiction,
    TaxProductRule,
    TaxPeriodSnapshot,
    TaxAnomaly,
    TransactionLineTaxDetail,
)
from .services import TaxEngine, compute_tax_anomalies, compute_tax_period_snapshot
from .services import compute_tax_due_date


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


class TaxEngineV1DeterministicTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="taxuser", password="pass")
        self.business = Business.objects.create(
            name="Tax Biz",
            currency="CAD",
            owner_user=self.user,
            tax_country="CA",
            tax_region="ON",
        )
        self.customer = Customer.objects.create(business=self.business, name="ACME")

    def test_jurisdiction_and_product_rule_creation(self):
        ca_on, _ = TaxJurisdiction.objects.get_or_create(
            code="CA-ON",
            defaults={
                "name": "Ontario",
                "jurisdiction_type": TaxJurisdiction.JurisdictionType.PROVINCIAL,
                "country_code": "CA",
                "region_code": "ON",
            },
        )
        rule = TaxProductRule.objects.create(
            jurisdiction=ca_on,
            product_code="GENERAL",
            rule_type=TaxProductRule.RuleType.TAXABLE,
            valid_from=timezone.localdate(),
        )
        self.assertGreaterEqual(TaxJurisdiction.objects.count(), 1)
        self.assertEqual(TaxProductRule.objects.count(), 1)
        self.assertEqual(rule.jurisdiction.code, "CA-ON")

    def _create_invoice_and_expense(self, period="2025-04", invoice_tax=Decimal("13.00"), expense_tax=Decimal("5.00")):
        issue_date = timezone.datetime.strptime(period + "-01", "%Y-%m-%d").date()
        Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number="INV-1",
            issue_date=issue_date,
            due_date=issue_date,
            status=Invoice.Status.SENT,
            subtotal=Decimal("100.00"),
            tax_amount=invoice_tax,
            tax_total=invoice_tax,
            net_total=Decimal("100.00"),
            grand_total=Decimal("113.00"),
            total_amount=Decimal("113.00"),
            balance=Decimal("113.00"),
        )
        Expense.objects.create(
            business=self.business,
            supplier=None,
            category=None,
            date=issue_date,
            description="Supplies",
            amount=Decimal("50.00"),
            subtotal=Decimal("50.00"),
            tax_amount=expense_tax,
            tax_total=expense_tax,
            net_total=Decimal("50.00"),
            grand_total=Decimal("55.00"),
            balance=Decimal("55.00"),
        )

    def test_compute_snapshot(self):
        self._create_invoice_and_expense()
        snapshot = compute_tax_period_snapshot(self.business, "2025-04")
        self.assertIsInstance(snapshot, TaxPeriodSnapshot)
        summary = snapshot.summary_by_jurisdiction
        self.assertTrue(summary)
        jurisdiction_code = list(summary.keys())[0]
        self.assertIn("taxable_sales", summary[jurisdiction_code])
        self.assertEqual(summary[jurisdiction_code]["tax_collected"], 13.0)

    def test_us_line_mapping_avoids_double_counting_local_components(self):
        self.business.tax_country = "US"
        self.business.tax_region = "CA"
        self.business.save(update_fields=["tax_country", "tax_region"])

        us_root = TaxJurisdiction.objects.get(code="US")
        us_ca = TaxJurisdiction.objects.get(code="US-CA")
        us_ca_la, _ = TaxJurisdiction.objects.get_or_create(
            code="US-CA-LA",
            defaults={
                "name": "Los Angeles County",
                "jurisdiction_type": TaxJurisdiction.JurisdictionType.COUNTY,
                "country_code": "US",
                "region_code": "CA",
                "sourcing_rule": TaxJurisdiction.SourcingRule.DESTINATION,
                "parent": us_ca,
            },
        )
        if us_ca_la.parent_id != us_ca.id:
            us_ca_la.parent = us_ca
            us_ca_la.save(update_fields=["parent"])
        if us_ca.parent_id != us_root.id:
            us_ca.parent = us_root
            us_ca.save(update_fields=["parent"])

        liability = Account.objects.create(
            business=self.business,
            code="2310",
            name="US Sales Tax Payable",
            type=Account.AccountType.LIABILITY,
        )
        state_component = TaxComponent.objects.create(
            business=self.business,
            name="CA State Sales Tax 5%",
            rate_percentage=Decimal("0.05"),
            authority="US-CA",
            is_recoverable=False,
            effective_start_date=timezone.localdate(),
            default_coa_account=liability,
            jurisdiction=us_ca,
        )
        local_component = TaxComponent.objects.create(
            business=self.business,
            name="LA County Sales Tax 1%",
            rate_percentage=Decimal("0.01"),
            authority="US-CA-LA",
            is_recoverable=False,
            effective_start_date=timezone.localdate(),
            default_coa_account=liability,
            jurisdiction=us_ca_la,
        )
        group = TaxGroup.objects.create(
            business=self.business,
            display_name="US-CA Sales Tax 6%",
            calculation_method=TaxGroup.CalculationMethod.SIMPLE,
        )
        group.components.add(state_component, local_component)

        period = "2025-04"
        issue_date = timezone.datetime.strptime(period + "-10", "%Y-%m-%d").date()
        Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number="US-INV-1",
            issue_date=issue_date,
            due_date=issue_date,
            status=Invoice.Status.SENT,
            total_amount=Decimal("100.00"),
            tax_group=group,
            balance=Decimal("100.00"),
        )

        snapshot = compute_tax_period_snapshot(self.business, period)
        us = snapshot.line_mappings.get("US") or {}
        # Two components (state + local) should not double count taxable sales.
        self.assertEqual(us.get("gross_sales"), 100.0)
        self.assertEqual(us.get("taxable_sales"), 100.0)

    def test_compute_anomalies_negative_net(self):
        self._create_invoice_and_expense(invoice_tax=Decimal("1.00"), expense_tax=Decimal("5.00"))
        anomalies = compute_tax_anomalies(self.business, "2025-04")
        self.assertTrue(anomalies)
        self.assertEqual(anomalies[0].code, "T6_NEGATIVE_BALANCE")
        self.assertEqual(anomalies[0].severity, TaxAnomaly.AnomalySeverity.HIGH)

    def test_management_commands(self):
        self._create_invoice_and_expense()
        out = StringIO()
        call_command("tax_refresh_period", business_id=self.business.id, period="2025-04", stdout=out)
        self.assertIn("Computed snapshot", out.getvalue())

        out = StringIO()
        call_command("tax_watchdog_period", business_id=self.business.id, period="2025-04", stdout=out)
        self.assertIn("Watchdog complete", out.getvalue())

    def test_snapshot_uses_tax_details_and_jurisdiction_code(self):
        seed_canadian_defaults(self.business)
        tax_group = TaxGroup.objects.get(business=self.business, display_name="CA-ON HST 13%")
        txn_date = timezone.datetime.strptime("2025-04-15", "%Y-%m-%d").date()
        component = tax_group.components.first()

        TransactionLineTaxDetail.objects.create(
            business=self.business,
            tax_group=tax_group,
            tax_component=component,
            transaction_date=txn_date,
            taxable_amount_txn_currency=Decimal("100.00"),
            taxable_amount_home_currency_cad=Decimal("100.00"),
            tax_amount_txn_currency=Decimal("13.00"),
            tax_amount_home_currency_cad=Decimal("13.00"),
            is_recoverable=False,
            jurisdiction_code="CA-ON",
        )

        snapshot = compute_tax_period_snapshot(self.business, "2025-04")
        self.assertIn("CA-ON", snapshot.summary_by_jurisdiction)
        self.assertEqual(snapshot.summary_by_jurisdiction["CA-ON"]["tax_collected"], 13.0)
        self.assertEqual(snapshot.summary_by_jurisdiction["CA-ON"]["source"], "tax_details")

    def test_ca_line_101_excludes_out_of_scope_tax_groups(self):
        ca_federal, _ = TaxJurisdiction.objects.get_or_create(
            code="CA",
            defaults={
                "name": "Canada",
                "jurisdiction_type": TaxJurisdiction.JurisdictionType.FEDERAL,
                "country_code": "CA",
                "region_code": "",
                "sourcing_rule": TaxJurisdiction.SourcingRule.DESTINATION,
            },
        )
        liability, _ = Account.objects.get_or_create(
            business=self.business,
            code="2300",
            defaults={
                "name": "Sales Tax Payable",
                "type": Account.AccountType.LIABILITY,
            },
        )
        gst_5 = TaxComponent.objects.create(
            business=self.business,
            name="GST 5% (test)",
            rate_percentage=Decimal("0.05"),
            authority="CRA",
            is_recoverable=True,
            effective_start_date=timezone.localdate(),
            default_coa_account=liability,
            jurisdiction=ca_federal,
        )
        gst_0 = TaxComponent.objects.create(
            business=self.business,
            name="GST 0% (test)",
            rate_percentage=Decimal("0.00"),
            authority="CRA",
            is_recoverable=True,
            effective_start_date=timezone.localdate(),
            default_coa_account=liability,
            jurisdiction=ca_federal,
        )

        taxable_group = TaxGroup.objects.create(
            business=self.business,
            display_name="CA GST 5% (Taxable)",
            calculation_method=TaxGroup.CalculationMethod.SIMPLE,
            reporting_category=TaxGroup.ReportingCategory.TAXABLE,
        )
        taxable_group.components.add(gst_5)
        zero_group = TaxGroup.objects.create(
            business=self.business,
            display_name="CA GST 0% (Zero-rated)",
            calculation_method=TaxGroup.CalculationMethod.SIMPLE,
            reporting_category=TaxGroup.ReportingCategory.ZERO_RATED,
        )
        zero_group.components.add(gst_0)
        exempt_group = TaxGroup.objects.create(
            business=self.business,
            display_name="CA GST 0% (Exempt)",
            calculation_method=TaxGroup.CalculationMethod.SIMPLE,
            reporting_category=TaxGroup.ReportingCategory.EXEMPT,
        )
        exempt_group.components.add(gst_0)
        out_of_scope_group = TaxGroup.objects.create(
            business=self.business,
            display_name="CA Out of scope (test)",
            calculation_method=TaxGroup.CalculationMethod.SIMPLE,
            reporting_category=TaxGroup.ReportingCategory.OUT_OF_SCOPE,
        )
        out_of_scope_group.components.add(gst_0)

        txn_date = date(2025, 4, 15)
        invoice_ct = ContentType.objects.get_for_model(Invoice)
        expense_ct = ContentType.objects.get_for_model(Expense)

        def _make_invoice(number: str, group: TaxGroup) -> Invoice:
            inv = Invoice(
                business=self.business,
                customer=self.customer,
                invoice_number=number,
                issue_date=txn_date,
                status=Invoice.Status.SENT,
                total_amount=Decimal("1.00"),
                tax_group=group,
                balance=Decimal("1.00"),
            )
            inv._skip_tax_sync = True
            inv.save()
            return inv

        inv_taxable = _make_invoice("INV-TAXABLE", taxable_group)
        inv_zero = _make_invoice("INV-ZERO", zero_group)
        inv_exempt = _make_invoice("INV-EXEMPT", exempt_group)
        inv_oos = _make_invoice("INV-OOS", out_of_scope_group)

        TransactionLineTaxDetail.objects.create(
            business=self.business,
            tax_group=taxable_group,
            tax_component=gst_5,
            transaction_line_content_type=invoice_ct,
            transaction_line_object_id=inv_taxable.id,
            transaction_date=txn_date,
            taxable_amount_txn_currency=Decimal("100.00"),
            taxable_amount_home_currency_cad=Decimal("100.00"),
            tax_amount_txn_currency=Decimal("5.00"),
            tax_amount_home_currency_cad=Decimal("5.00"),
            is_recoverable=True,
            jurisdiction_code="CA",
        )
        TransactionLineTaxDetail.objects.create(
            business=self.business,
            tax_group=zero_group,
            tax_component=gst_0,
            transaction_line_content_type=invoice_ct,
            transaction_line_object_id=inv_zero.id,
            transaction_date=txn_date,
            taxable_amount_txn_currency=Decimal("200.00"),
            taxable_amount_home_currency_cad=Decimal("200.00"),
            tax_amount_txn_currency=Decimal("0.00"),
            tax_amount_home_currency_cad=Decimal("0.00"),
            is_recoverable=True,
            jurisdiction_code="CA",
        )
        TransactionLineTaxDetail.objects.create(
            business=self.business,
            tax_group=exempt_group,
            tax_component=gst_0,
            transaction_line_content_type=invoice_ct,
            transaction_line_object_id=inv_exempt.id,
            transaction_date=txn_date,
            taxable_amount_txn_currency=Decimal("300.00"),
            taxable_amount_home_currency_cad=Decimal("300.00"),
            tax_amount_txn_currency=Decimal("0.00"),
            tax_amount_home_currency_cad=Decimal("0.00"),
            is_recoverable=True,
            jurisdiction_code="CA",
        )
        TransactionLineTaxDetail.objects.create(
            business=self.business,
            tax_group=out_of_scope_group,
            tax_component=gst_0,
            transaction_line_content_type=invoice_ct,
            transaction_line_object_id=inv_oos.id,
            transaction_date=txn_date,
            taxable_amount_txn_currency=Decimal("400.00"),
            taxable_amount_home_currency_cad=Decimal("400.00"),
            tax_amount_txn_currency=Decimal("0.00"),
            tax_amount_home_currency_cad=Decimal("0.00"),
            is_recoverable=True,
            jurisdiction_code="CA",
        )

        exp = Expense(
            business=self.business,
            supplier=None,
            category=None,
            date=txn_date,
            description="Purchase",
            amount=Decimal("1.00"),
            status=Expense.Status.PAID,
            tax_group=taxable_group,
        )
        exp._skip_tax_sync = True
        exp.save()
        TransactionLineTaxDetail.objects.create(
            business=self.business,
            tax_group=taxable_group,
            tax_component=gst_5,
            transaction_line_content_type=expense_ct,
            transaction_line_object_id=exp.id,
            transaction_date=txn_date,
            taxable_amount_txn_currency=Decimal("40.00"),
            taxable_amount_home_currency_cad=Decimal("40.00"),
            tax_amount_txn_currency=Decimal("2.00"),
            tax_amount_home_currency_cad=Decimal("2.00"),
            is_recoverable=True,
            jurisdiction_code="CA",
        )

        snapshot = compute_tax_period_snapshot(self.business, "2025-04")
        ca = snapshot.line_mappings.get("CA") or {}
        self.assertEqual(ca.get("line_101"), 600.0)
        self.assertEqual(ca.get("line_105"), 5.0)
        self.assertEqual(ca.get("line_108"), 2.0)
        self.assertEqual(ca.get("line_109"), 3.0)

    def test_us_ser_and_line_mapping_excludes_out_of_scope_tax_groups(self):
        self.business.tax_country = "US"
        self.business.tax_region = "CA"
        self.business.save(update_fields=["tax_country", "tax_region"])

        us_root, _ = TaxJurisdiction.objects.get_or_create(
            code="US",
            defaults={
                "name": "United States",
                "jurisdiction_type": TaxJurisdiction.JurisdictionType.FEDERAL,
                "country_code": "US",
                "region_code": "",
                "sourcing_rule": TaxJurisdiction.SourcingRule.DESTINATION,
            },
        )
        us_ca, _ = TaxJurisdiction.objects.get_or_create(
            code="US-CA",
            defaults={
                "name": "California",
                "jurisdiction_type": TaxJurisdiction.JurisdictionType.STATE,
                "country_code": "US",
                "region_code": "CA",
                "sourcing_rule": TaxJurisdiction.SourcingRule.DESTINATION,
                "parent": us_root,
            },
        )
        liability, _ = Account.objects.get_or_create(
            business=self.business,
            code="2310",
            defaults={
                "name": "US Sales Tax Payable",
                "type": Account.AccountType.LIABILITY,
            },
        )
        ca_state_6 = TaxComponent.objects.create(
            business=self.business,
            name="US-CA State 6% (test)",
            rate_percentage=Decimal("0.06"),
            authority="US-CA",
            is_recoverable=False,
            effective_start_date=timezone.localdate(),
            default_coa_account=liability,
            jurisdiction=us_ca,
        )
        ca_state_0 = TaxComponent.objects.create(
            business=self.business,
            name="US-CA State 0% (test)",
            rate_percentage=Decimal("0.00"),
            authority="US-CA",
            is_recoverable=False,
            effective_start_date=timezone.localdate(),
            default_coa_account=liability,
            jurisdiction=us_ca,
        )
        taxable_group = TaxGroup.objects.create(
            business=self.business,
            display_name="US-CA Taxable (test)",
            calculation_method=TaxGroup.CalculationMethod.SIMPLE,
            reporting_category=TaxGroup.ReportingCategory.TAXABLE,
        )
        taxable_group.components.add(ca_state_6)
        out_of_scope_group = TaxGroup.objects.create(
            business=self.business,
            display_name="US-CA Out of scope (test)",
            calculation_method=TaxGroup.CalculationMethod.SIMPLE,
            reporting_category=TaxGroup.ReportingCategory.OUT_OF_SCOPE,
        )
        out_of_scope_group.components.add(ca_state_0)

        txn_date = date(2025, 4, 10)
        invoice_ct = ContentType.objects.get_for_model(Invoice)

        inv_taxable = Invoice(
            business=self.business,
            customer=self.customer,
            invoice_number="US-INV-TAXABLE",
            issue_date=txn_date,
            status=Invoice.Status.SENT,
            total_amount=Decimal("1.00"),
            tax_group=taxable_group,
            balance=Decimal("1.00"),
        )
        inv_taxable._skip_tax_sync = True
        inv_taxable.save()

        inv_oos = Invoice(
            business=self.business,
            customer=self.customer,
            invoice_number="US-INV-OOS",
            issue_date=txn_date,
            status=Invoice.Status.SENT,
            total_amount=Decimal("1.00"),
            tax_group=out_of_scope_group,
            balance=Decimal("1.00"),
        )
        inv_oos._skip_tax_sync = True
        inv_oos.save()

        TransactionLineTaxDetail.objects.create(
            business=self.business,
            tax_group=taxable_group,
            tax_component=ca_state_6,
            transaction_line_content_type=invoice_ct,
            transaction_line_object_id=inv_taxable.id,
            transaction_date=txn_date,
            taxable_amount_txn_currency=Decimal("100.00"),
            taxable_amount_home_currency_cad=Decimal("100.00"),
            tax_amount_txn_currency=Decimal("6.00"),
            tax_amount_home_currency_cad=Decimal("6.00"),
            is_recoverable=False,
            jurisdiction_code="US-CA",
        )
        TransactionLineTaxDetail.objects.create(
            business=self.business,
            tax_group=out_of_scope_group,
            tax_component=ca_state_0,
            transaction_line_content_type=invoice_ct,
            transaction_line_object_id=inv_oos.id,
            transaction_date=txn_date,
            taxable_amount_txn_currency=Decimal("50.00"),
            taxable_amount_home_currency_cad=Decimal("50.00"),
            tax_amount_txn_currency=Decimal("0.00"),
            tax_amount_home_currency_cad=Decimal("0.00"),
            is_recoverable=False,
            jurisdiction_code="US-CA",
        )

        snapshot = compute_tax_period_snapshot(self.business, "2025-04")
        us = snapshot.line_mappings.get("US") or {}
        self.assertEqual(us.get("gross_sales"), 100.0)
        self.assertEqual(us.get("taxable_sales"), 100.0)
        states = us.get("states") or {}
        self.assertIn("US-CA", states)
        self.assertEqual(states["US-CA"]["gross_sales"], 100.0)
        self.assertEqual(states["US-CA"]["taxable_sales"], 100.0)

    def test_rate_mismatch_anomaly_detected(self):
        seed_canadian_defaults(self.business)
        tax_group = TaxGroup.objects.get(business=self.business, display_name="CA-ON HST 13%")
        component = tax_group.components.first()
        txn_date = timezone.datetime.strptime("2025-04-10", "%Y-%m-%d").date()

        TransactionLineTaxDetail.objects.create(
            business=self.business,
            tax_group=tax_group,
            tax_component=component,
            transaction_date=txn_date,
            taxable_amount_txn_currency=Decimal("100.00"),
            taxable_amount_home_currency_cad=Decimal("100.00"),
            tax_amount_txn_currency=Decimal("20.00"),  # intentionally high to trigger mismatch
            tax_amount_home_currency_cad=Decimal("20.00"),
            is_recoverable=False,
            jurisdiction_code="CA-ON",
        )

        anomalies = compute_tax_anomalies(self.business, "2025-04")
        # Overcharge direction is classified as T2_POSSIBLE_OVERCHARGE.
        self.assertTrue(any(a.code in {"T1_RATE_MISMATCH", "T2_POSSIBLE_OVERCHARGE"} for a in anomalies))

    def test_missing_tax_anomaly_for_registered_business(self):
        self.business.is_tax_registered = True
        self.business.save(update_fields=["is_tax_registered"])
        tax_group = TaxGroup.objects.create(
            business=self.business,
            display_name="CA-ON HST 13% (Missing Tax)",
            calculation_method=TaxGroup.CalculationMethod.SIMPLE,
        )
        component = TaxComponent.objects.create(
            business=self.business,
            name="ON HST",
            rate_percentage=Decimal("0.13"),
            authority="CRA",
            is_recoverable=False,
            effective_start_date=timezone.localdate(),
            default_coa_account=Account.objects.create(
                business=self.business,
                code="9999",
                name="Temp",
                type=Account.AccountType.LIABILITY,
            ),
        )
        tax_group.components.add(component)
        txn_date = timezone.datetime.strptime("2025-04-05", "%Y-%m-%d").date()
        TransactionLineTaxDetail.objects.create(
            business=self.business,
            tax_group=tax_group,
            tax_component=component,
            transaction_date=txn_date,
            taxable_amount_txn_currency=Decimal("100.00"),
            taxable_amount_home_currency_cad=Decimal("100.00"),
            tax_amount_txn_currency=Decimal("0.00"),  # missing tax
            tax_amount_home_currency_cad=Decimal("0.00"),
            is_recoverable=False,
            jurisdiction_code="CA-ON",
        )

        anomalies = compute_tax_anomalies(self.business, "2025-04")
        self.assertTrue(any(a.code == "T3_MISSING_TAX" for a in anomalies))

    def test_rounding_anomaly_detected(self):
        invoice_ct = ContentType.objects.get_for_model(Invoice)
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number="INV-RND",
            issue_date=timezone.datetime(2025, 4, 5).date(),
            due_date=timezone.datetime(2025, 4, 20).date(),
            status=Invoice.Status.SENT,
            subtotal=Decimal("100.00"),
            tax_total=Decimal("10.00"),
            net_total=Decimal("100.00"),
            grand_total=Decimal("110.00"),
            total_amount=Decimal("110.00"),
            balance=Decimal("110.00"),
        )
        tax_group = TaxGroup.objects.create(
            business=self.business,
            display_name="CA-ON HST 13% (Rounding)",
            calculation_method=TaxGroup.CalculationMethod.SIMPLE,
        )
        invoice._skip_tax_sync = True
        invoice.tax_group = tax_group
        invoice.save(update_fields=["tax_group"])
        TaxComponent.objects.create(
            business=self.business,
            name="ON HST",
            rate_percentage=Decimal("0.13"),
            authority="CRA",
            is_recoverable=False,
            effective_start_date=timezone.localdate(),
            default_coa_account=Account.objects.create(
                business=self.business,
                code="9998",
                name="Temp2",
                type=Account.AccountType.LIABILITY,
            ),
        )
        TransactionLineTaxDetail.objects.create(
            business=self.business,
            tax_group=tax_group,
            tax_component=TaxComponent.objects.filter(business=self.business).first(),
            transaction_date=invoice.issue_date,
            transaction_line_content_type=invoice_ct,
            transaction_line_object_id=invoice.id,
            taxable_amount_txn_currency=Decimal("100.00"),
            taxable_amount_home_currency_cad=Decimal("100.00"),
            tax_amount_txn_currency=Decimal("9.50"),  # sum detail tax < invoice tax_total
            tax_amount_home_currency_cad=Decimal("9.50"),
            is_recoverable=False,
            jurisdiction_code="CA-ON",
        )
        anomalies = compute_tax_anomalies(self.business, "2025-04")
        self.assertTrue(any(a.code == "T4_ROUNDING_ANOMALY" for a in anomalies))

    def test_exempt_product_taxed_anomaly(self):
        jurisdiction = TaxJurisdiction.objects.create(
            code="CA-EX",
            name="Example",
            jurisdiction_type=TaxJurisdiction.JurisdictionType.PROVINCIAL,
            country_code="CA",
        )
        txn_date = timezone.datetime.strptime("2025-04-06", "%Y-%m-%d").date()
        TaxProductRule.objects.create(
            jurisdiction=jurisdiction,
            product_code="GENERAL",
            rule_type=TaxProductRule.RuleType.EXEMPT,
            valid_from=txn_date,
        )
        tax_group = TaxGroup.objects.create(
            business=self.business,
            display_name="CA-EX EXEMPT",
            calculation_method=TaxGroup.CalculationMethod.SIMPLE,
        )
        component = TaxComponent.objects.create(
            business=self.business,
            name="EX TAX",
            rate_percentage=Decimal("0.05"),
            authority="CRA",
            is_recoverable=False,
            effective_start_date=timezone.localdate(),
            default_coa_account=Account.objects.create(
                business=self.business,
                code="9997",
                name="Temp3",
                type=Account.AccountType.LIABILITY,
            ),
            jurisdiction=jurisdiction,
        )
        TransactionLineTaxDetail.objects.create(
            business=self.business,
            tax_group=tax_group,
            tax_component=component,
            transaction_date=txn_date,
            taxable_amount_txn_currency=Decimal("100.00"),
            taxable_amount_home_currency_cad=Decimal("100.00"),
            tax_amount_txn_currency=Decimal("5.00"),
            tax_amount_home_currency_cad=Decimal("5.00"),
            is_recoverable=False,
            jurisdiction_code=jurisdiction.code,
        )
        anomalies = compute_tax_anomalies(self.business, "2025-04")
        self.assertTrue(any(a.code == "T5_EXEMPT_TAXED" for a in anomalies))

    def test_qst_line_mappings(self):
        jurisdiction, _ = TaxJurisdiction.objects.get_or_create(
            code="CA-QC",
            defaults={
                "name": "Quebec",
                "jurisdiction_type": TaxJurisdiction.JurisdictionType.PROVINCIAL,
                "country_code": "CA",
                "region_code": "QC",
            },
        )
        txn_date = timezone.datetime.strptime("2025-04-10", "%Y-%m-%d").date()
        tax_group = TaxGroup.objects.create(
            business=self.business,
            display_name="QC Group",
            calculation_method=TaxGroup.CalculationMethod.SIMPLE,
        )
        TransactionLineTaxDetail.objects.create(
            business=self.business,
            tax_group=tax_group,
            tax_component=TaxComponent.objects.create(
                business=self.business,
                name="QST Component",
                rate_percentage=Decimal("0.09975"),
                authority="RQ",
                is_recoverable=False,
                effective_start_date=txn_date,
                default_coa_account=Account.objects.create(
                    business=self.business,
                    code="9996",
                    name="Temp4",
                    type=Account.AccountType.LIABILITY,
                ),
                jurisdiction=jurisdiction,
            ),
            transaction_date=txn_date,
            taxable_amount_txn_currency=Decimal("1000.00"),
            taxable_amount_home_currency_cad=Decimal("1000.00"),
            tax_amount_txn_currency=Decimal("50.00"),
            tax_amount_home_currency_cad=Decimal("50.00"),
            is_recoverable=False,
            jurisdiction_code=jurisdiction.code,
        )
        recoverable_component = TaxComponent.objects.create(
            business=self.business,
            name="QST Recoverable",
            rate_percentage=Decimal("0.09975"),
            authority="RQ",
            is_recoverable=True,
            effective_start_date=txn_date,
            default_coa_account=Account.objects.create(
                business=self.business,
                code="9995",
                name="Temp5",
                type=Account.AccountType.ASSET,
            ),
            jurisdiction=jurisdiction,
        )
        TransactionLineTaxDetail.objects.create(
            business=self.business,
            tax_group=tax_group,
            tax_component=recoverable_component,
            transaction_date=txn_date,
            taxable_amount_txn_currency=Decimal("200.00"),
            taxable_amount_home_currency_cad=Decimal("200.00"),
            tax_amount_txn_currency=Decimal("10.00"),
            tax_amount_home_currency_cad=Decimal("10.00"),
            is_recoverable=True,
            jurisdiction_code=jurisdiction.code,
        )
        snapshot = compute_tax_period_snapshot(self.business, "2025-04")
        qc = snapshot.line_mappings.get("CA_QC", {})
        self.assertEqual(qc.get("line_205"), 50.0)
        self.assertEqual(qc.get("line_206"), 10.0)
        self.assertEqual(qc.get("line_209"), 40.0)


class TaxDueDateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="due", password="pass")
        self.business = Business.objects.create(
            name="Due Biz",
            currency="CAD",
            owner_user=self.user,
            tax_country="CA",
            tax_region="ON",
            tax_filing_due_day=30,
            tax_filing_frequency=Business.TaxFilingFrequency.MONTHLY,
        )

    def test_compute_tax_due_date_monthly_simple(self):
        due_date = compute_tax_due_date(self.business, "2025-04")
        self.assertEqual(due_date, date(2025, 5, 30))

    def test_compute_tax_due_date_clamps_end_of_month(self):
        self.business.tax_filing_due_day = 31
        self.business.save()
        due_date = compute_tax_due_date(self.business, "2025-01")
        self.assertEqual(due_date, date(2025, 2, 28))


class TaxJurisdictionSeedTests(TestCase):
    def test_core_jurisdictions_seeded(self):
        codes = ["CA", "CA-ON", "CA-QC", "US", "US-CA", "US-TX", "US-IL", "US-AZ"]
        for code in codes:
            self.assertTrue(TaxJurisdiction.objects.filter(code=code).exists(), f"{code} not seeded")
        self.assertEqual(
            TaxJurisdiction.objects.get(code="US-IL").sourcing_rule,
            TaxJurisdiction.SourcingRule.ORIGIN,
        )

    def test_all_us_states_seeded_with_expected_sourcing_rules(self):
        origin_states = {"AZ", "IL", "MO", "OH", "PA", "TX", "UT", "VA"}
        all_states = {
            "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
            "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
            "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY",
        }
        for abbr in all_states:
            code = f"US-{abbr}"
            self.assertTrue(
                TaxJurisdiction.objects.filter(code=code, jurisdiction_type=TaxJurisdiction.JurisdictionType.STATE).exists(),
                f"{code} not seeded",
            )
        self.assertEqual(TaxJurisdiction.objects.get(code="US-CA").sourcing_rule, TaxJurisdiction.SourcingRule.HYBRID)
        for abbr in origin_states:
            self.assertEqual(
                TaxJurisdiction.objects.get(code=f"US-{abbr}").sourcing_rule,
                TaxJurisdiction.SourcingRule.ORIGIN,
            )
        self.assertEqual(
            TaxJurisdiction.objects.get(code="US-NY").sourcing_rule,
            TaxJurisdiction.SourcingRule.DESTINATION,
        )

    def test_seeded_components_have_jurisdiction(self):
        user = User.objects.create_user(username="seeded", password="pass")
        business = Business.objects.create(
            name="Jur Biz",
            currency="CAD",
            owner_user=user,
            tax_country="CA",
            tax_region="ON",
        )
        seed_canadian_defaults(business)
        self.assertTrue(TaxComponent.objects.filter(business=business, jurisdiction__isnull=False).exists())

    def test_sample_us_locals_seeded_with_parent(self):
        expected = {
            "US-CA-LA": (TaxJurisdiction.JurisdictionType.COUNTY, "US-CA"),
            "US-CA-SF": (TaxJurisdiction.JurisdictionType.CITY, "US-CA"),
            "US-CA-DIST-1": (TaxJurisdiction.JurisdictionType.DISTRICT, "US-CA"),
            "US-NY-NYC": (TaxJurisdiction.JurisdictionType.CITY, "US-NY"),
            "US-TX-TRV": (TaxJurisdiction.JurisdictionType.COUNTY, "US-TX"),
        }
        for code, (jtype, parent_code) in expected.items():
            row = TaxJurisdiction.objects.filter(code=code).select_related("parent").first()
            self.assertIsNotNone(row, f"{code} not seeded")
            self.assertEqual(row.jurisdiction_type, jtype)
            self.assertIsNotNone(row.parent, f"{code} missing parent")
            self.assertEqual(row.parent.code, parent_code)


class TaxSourcingResolutionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sourcing", password="pass")

    def _make_business(self, *, name: str, tax_country: str, tax_region: str, currency: str):
        return Business.objects.create(
            name=name,
            currency=currency,
            owner_user=self.user,
            tax_country=tax_country,
            tax_region=tax_region,
        )

    def _make_customer(self, business: Business):
        return Customer.objects.create(business=business, name="Customer")

    def _make_generic_tax_group(self, business: Business, *, name: str, authority: str, rate: Decimal):
        liability = Account.objects.create(
            business=business,
            code="2310",
            name="Sales Tax Payable",
            type=Account.AccountType.LIABILITY,
        )
        component = TaxComponent.objects.create(
            business=business,
            name=name,
            rate_percentage=rate,
            authority=authority,
            is_recoverable=False,
            effective_start_date=timezone.localdate(),
            default_coa_account=liability,
            jurisdiction=None,
        )
        group = TaxGroup.objects.create(
            business=business,
            display_name=f"{authority} Generic {rate}",
            calculation_method=TaxGroup.CalculationMethod.SIMPLE,
        )
        group.components.add(component)
        return group

    def test_ca_tpp_uses_ship_to_province(self):
        business = self._make_business(name="CA Biz", tax_country="CA", tax_region="ON", currency="CAD")
        customer = self._make_customer(business)
        group = self._make_generic_tax_group(business, name="Generic CA tax", authority="CRA", rate=Decimal("0.05"))

        item = Item.objects.create(
            business=business,
            name="Widget",
            type=Item.ItemType.PRODUCT,
            unit_price=Decimal("10.00"),
        )
        invoice = Invoice.objects.create(
            business=business,
            customer=customer,
            invoice_number="CA-TPP-1",
            issue_date=date(2025, 4, 10),
            status=Invoice.Status.SENT,
            item=item,
            total_amount=Decimal("100.00"),
            tax_group=group,
            balance=Decimal("100.00"),
            ship_from_jurisdiction_code="CA-ON",
            ship_to_jurisdiction_code="CA-NS",
            place_of_supply_hint="AUTO",  # should infer TPP from item type
        )

        ct = ContentType.objects.get_for_model(Invoice)
        detail = TransactionLineTaxDetail.objects.filter(
            business=business,
            transaction_line_content_type=ct,
            transaction_line_object_id=invoice.id,
        ).first()
        self.assertIsNotNone(detail)
        self.assertEqual(detail.jurisdiction_code, "CA-NS")

        snapshot = compute_tax_period_snapshot(business, "2025-04")
        self.assertIn("CA-NS", snapshot.summary_by_jurisdiction)

    def test_ca_services_uses_customer_location(self):
        business = self._make_business(name="CA Biz 2", tax_country="CA", tax_region="ON", currency="CAD")
        customer = self._make_customer(business)
        group = self._make_generic_tax_group(business, name="Generic CA tax 2", authority="CRA", rate=Decimal("0.05"))

        invoice = Invoice.objects.create(
            business=business,
            customer=customer,
            invoice_number="CA-SVC-1",
            issue_date=date(2025, 4, 12),
            status=Invoice.Status.SENT,
            total_amount=Decimal("200.00"),
            tax_group=group,
            balance=Decimal("200.00"),
            customer_location_jurisdiction_code="CA-QC",
            place_of_supply_hint="SERVICE",
        )

        ct = ContentType.objects.get_for_model(Invoice)
        detail = TransactionLineTaxDetail.objects.filter(
            business=business,
            transaction_line_content_type=ct,
            transaction_line_object_id=invoice.id,
        ).first()
        self.assertIsNotNone(detail)
        self.assertEqual(detail.jurisdiction_code, "CA-QC")

    def test_us_origin_state_intrastate_uses_ship_from(self):
        business = self._make_business(name="US Biz", tax_country="US", tax_region="TX", currency="USD")
        customer = self._make_customer(business)
        group = self._make_generic_tax_group(business, name="Generic US tax", authority="US", rate=Decimal("0.05"))

        invoice = Invoice.objects.create(
            business=business,
            customer=customer,
            invoice_number="US-TX-1",
            issue_date=date(2025, 4, 10),
            status=Invoice.Status.SENT,
            total_amount=Decimal("100.00"),
            tax_group=group,
            balance=Decimal("100.00"),
            ship_from_jurisdiction_code="US-TX",
            ship_to_jurisdiction_code="US-TX",
        )

        ct = ContentType.objects.get_for_model(Invoice)
        detail = TransactionLineTaxDetail.objects.filter(
            business=business,
            transaction_line_content_type=ct,
            transaction_line_object_id=invoice.id,
        ).first()
        self.assertIsNotNone(detail)
        self.assertEqual(detail.jurisdiction_code, "US-TX")

    def test_us_destination_state_uses_ship_to(self):
        business = self._make_business(name="US Biz 2", tax_country="US", tax_region="TX", currency="USD")
        customer = self._make_customer(business)
        group = self._make_generic_tax_group(business, name="Generic US tax 2", authority="US", rate=Decimal("0.05"))

        invoice = Invoice.objects.create(
            business=business,
            customer=customer,
            invoice_number="US-NY-1",
            issue_date=date(2025, 4, 10),
            status=Invoice.Status.SENT,
            total_amount=Decimal("100.00"),
            tax_group=group,
            balance=Decimal("100.00"),
            ship_from_jurisdiction_code="US-TX",
            ship_to_jurisdiction_code="US-NY",
        )

        ct = ContentType.objects.get_for_model(Invoice)
        detail = TransactionLineTaxDetail.objects.filter(
            business=business,
            transaction_line_content_type=ct,
            transaction_line_object_id=invoice.id,
        ).first()
        self.assertIsNotNone(detail)
        self.assertEqual(detail.jurisdiction_code, "US-NY")

    def test_us_california_hybrid_returns_state_level_code(self):
        business = self._make_business(name="US Biz 3", tax_country="US", tax_region="CA", currency="USD")
        customer = self._make_customer(business)
        group = self._make_generic_tax_group(business, name="Generic US tax 3", authority="US", rate=Decimal("0.05"))

        invoice = Invoice.objects.create(
            business=business,
            customer=customer,
            invoice_number="US-CA-1",
            issue_date=date(2025, 4, 10),
            status=Invoice.Status.SENT,
            total_amount=Decimal("100.00"),
            tax_group=group,
            balance=Decimal("100.00"),
            ship_from_jurisdiction_code="US-CA",
            ship_to_jurisdiction_code="US-CA",
        )

        ct = ContentType.objects.get_for_model(Invoice)
        detail = TransactionLineTaxDetail.objects.filter(
            business=business,
            transaction_line_content_type=ct,
            transaction_line_object_id=invoice.id,
        ).first()
        self.assertIsNotNone(detail)
        self.assertEqual(detail.jurisdiction_code, "US-CA")

    def test_us_california_hybrid_assigns_local_component_to_destination_local(self):
        business = self._make_business(name="US Biz Local", tax_country="US", tax_region="CA", currency="USD")
        customer = self._make_customer(business)

        liability = Account.objects.create(
            business=business,
            code="2310",
            name="US Sales Tax Payable",
            type=Account.AccountType.LIABILITY,
        )
        state_component = TaxComponent.objects.create(
            business=business,
            name="CA State Sales Tax 5%",
            rate_percentage=Decimal("0.05"),
            authority="US",
            is_recoverable=False,
            effective_start_date=timezone.localdate(),
            default_coa_account=liability,
            jurisdiction=None,
        )
        local_component = TaxComponent.objects.create(
            business=business,
            name="CA Local Sales Tax 1%",
            rate_percentage=Decimal("0.01"),
            authority="US",
            is_recoverable=False,
            effective_start_date=timezone.localdate(),
            default_coa_account=liability,
            jurisdiction=None,
        )
        group = TaxGroup.objects.create(
            business=business,
            display_name="US-CA State+Local 6%",
            calculation_method=TaxGroup.CalculationMethod.SIMPLE,
        )
        TaxGroupComponent.objects.create(group=group, component=state_component, calculation_order=1)
        TaxGroupComponent.objects.create(group=group, component=local_component, calculation_order=2)

        invoice = Invoice.objects.create(
            business=business,
            customer=customer,
            invoice_number="US-CA-LOCAL-1",
            issue_date=date(2025, 4, 10),
            status=Invoice.Status.DRAFT,
            total_amount=Decimal("100.00"),
            tax_group=group,
            balance=Decimal("100.00"),
            ship_from_jurisdiction_code="US-CA-LA",
            ship_to_jurisdiction_code="US-CA-SF",
        )

        ct = ContentType.objects.get_for_model(Invoice)
        details = list(
            TransactionLineTaxDetail.objects.filter(
                business=business,
                transaction_line_content_type=ct,
                transaction_line_object_id=invoice.id,
            ).order_by("tax_component__name")
        )
        self.assertEqual(len(details), 2)
        jurisdictions = {d.jurisdiction_code for d in details}
        self.assertIn("US-CA", jurisdictions)
        self.assertIn("US-CA-SF", jurisdictions)

        us_ca = TaxJurisdiction.objects.get(code="US-CA")
        TaxProductRule.objects.create(
            jurisdiction=us_ca,
            product_code="GENERAL",
            rule_type=TaxProductRule.RuleType.EXEMPT,
            valid_from=date(2020, 1, 1),
            valid_to=None,
            notes="Exempt for testing",
        )

        snapshot = compute_tax_period_snapshot(business, "2025-04")
        self.assertIn("US-CA", snapshot.summary_by_jurisdiction)
        self.assertIn("US-CA-SF", snapshot.summary_by_jurisdiction)

        us_mapping = snapshot.line_mappings.get("US") or {}
        self.assertEqual(us_mapping.get("taxable_sales"), 100.0)
        locals_mapping = us_mapping.get("locals") or {}
        self.assertIn("US-CA-SF", locals_mapping)
        self.assertEqual(locals_mapping["US-CA-SF"]["tax_collected"], 1.0)

        states_mapping = us_mapping.get("states") or {}
        self.assertIn("US-CA", states_mapping)
        self.assertEqual(states_mapping["US-CA"]["gross_sales"], 100.0)
        self.assertEqual(states_mapping["US-CA"]["exempt_sales"], 100.0)
        self.assertEqual(states_mapping["US-CA"]["taxable_sales"], 0.0)
        self.assertEqual(states_mapping["US-CA"]["tax_collected"], 6.0)


class TaxObserverPipelineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="taxobserver", password="pass")
        self.business = Business.objects.create(
            name="Observer Biz",
            currency="CAD",
            owner_user=self.user,
            tax_country="CA",
            tax_region="ON",
            tax_filing_due_day=30,
            tax_filing_frequency=Business.TaxFilingFrequency.MONTHLY,
        )

    @patch("taxes.management.commands.tax_nudge_notifications.timezone.localdate")
    def test_tax_nudge_notifications_creates_due_soon_insight(self, mock_localdate):
        from companion.models import CompanionInsight

        mock_localdate.return_value = date(2025, 5, 25)  # due for 2025-04 is 2025-05-30
        TaxPeriodSnapshot.objects.create(
            business=self.business,
            period_key="2025-04",
            country="CA",
            status=TaxPeriodSnapshot.SnapshotStatus.COMPUTED,
            summary_by_jurisdiction={},
            line_mappings={},
        )

        call_command("tax_nudge_notifications", business_id=self.business.id, stdout=StringIO())
        insight = CompanionInsight.objects.filter(
            workspace=self.business,
            domain="tax_filing",
            title__contains="due soon",
            is_dismissed=False,
        ).first()
        self.assertIsNotNone(insight)
        self.assertEqual(insight.context, CompanionInsight.CONTEXT_TAX_FX)

    @patch("taxes.management.commands.tax_nudge_notifications.timezone.localdate")
    def test_tax_nudge_notifications_creates_overdue_insight(self, mock_localdate):
        from companion.models import CompanionInsight

        mock_localdate.return_value = date(2025, 6, 5)  # overdue for 2025-04 (due 2025-05-30)
        TaxPeriodSnapshot.objects.create(
            business=self.business,
            period_key="2025-04",
            country="CA",
            status=TaxPeriodSnapshot.SnapshotStatus.COMPUTED,
            summary_by_jurisdiction={},
            line_mappings={},
        )

        call_command("tax_nudge_notifications", business_id=self.business.id, stdout=StringIO())
        insight = CompanionInsight.objects.filter(
            workspace=self.business,
            domain="tax_filing",
            title__contains="overdue",
            is_dismissed=False,
        ).first()
        self.assertIsNotNone(insight)
        self.assertEqual(insight.severity, "critical")

    @patch("taxes.llm_observer._invoke_llm")
    def test_tax_llm_enrich_period_command_updates_snapshot(self, mock_llm):
        mock_llm.return_value = '{"summary":"Stable net tax position.","notes":["Review open anomalies before filing."]}'
        snap = TaxPeriodSnapshot.objects.create(
            business=self.business,
            period_key="2025-04",
            country="CA",
            status=TaxPeriodSnapshot.SnapshotStatus.COMPUTED,
            summary_by_jurisdiction={
                "CA-ON": {
                    "taxable_sales": 1000.0,
                    "tax_collected": 130.0,
                    "tax_on_purchases": 20.0,
                    "net_tax": 110.0,
                    "currency": "CAD",
                }
            },
            line_mappings={"CA": {"line_101": 1000.0, "line_105": 130.0, "line_108": 20.0, "line_109": 110.0}},
        )
        call_command("tax_llm_enrich_period", business_id=self.business.id, period="2025-04", stdout=StringIO())
        snap.refresh_from_db()
        self.assertIn("Stable net tax", snap.llm_summary)
        self.assertIn("Review open anomalies", snap.llm_notes)
