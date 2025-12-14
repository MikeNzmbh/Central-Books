from datetime import date
from unittest.mock import patch
from decimal import Decimal
import csv
import io

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from core.models import Business, Account, BankAccount
from taxes.models import TaxPeriodSnapshot, TaxAnomaly, TaxPayment
from taxes.services import compute_tax_anomalies, compute_tax_period_snapshot
from taxes.models import TaxComponent, TaxGroup, TransactionLineTaxDetail

User = get_user_model()


class TaxGuardianApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="taxapi", password="pass")
        self.business = Business.objects.create(
            name="Tax API Biz",
            currency="CAD",
            owner_user=self.user,
            tax_country="CA",
            tax_region="ON",
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.period_key = f"{date.today().year}-{date.today().month:02d}"
        self.bank_account = BankAccount.objects.create(business=self.business, name="Operating")

    def _make_snapshot(self, *, net_tax: float = 110.0):
        tax_on_purchases = 20.0
        tax_collected = float(net_tax) + tax_on_purchases
        return TaxPeriodSnapshot.objects.create(
            business=self.business,
            period_key=self.period_key,
            country="CA",
            status=TaxPeriodSnapshot.SnapshotStatus.COMPUTED,
            summary_by_jurisdiction={
                "CA-ON": {
                    "taxable_sales": 1000.0,
                    "tax_collected": tax_collected,
                    "tax_on_purchases": tax_on_purchases,
                    "net_tax": float(net_tax),
                    "currency": "CAD",
                }
            },
            line_mappings={
                "CA": {
                    "line_101": 1000.0,
                    "line_105": tax_collected,
                    "line_108": tax_on_purchases,
                    "line_109": float(net_tax),
                }
            },
        )

    def test_list_periods(self):
        self._make_snapshot()
        resp = self.client.get("/api/tax/periods/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["periods"]
        self.assertTrue(any(p["period_key"] == self.period_key for p in data))

    def test_period_detail(self):
        self._make_snapshot()
        resp = self.client.get(f"/api/tax/periods/{self.period_key}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["period_key"], self.period_key)
        self.assertIn("summary_by_jurisdiction", data)
        self.assertIn("line_mappings", data)
        self.assertIn("llm_summary", data)
        self.assertIn("llm_notes", data)

    def test_anomalies_listing(self):
        self._make_snapshot()
        TaxAnomaly.objects.create(
            business=self.business,
            period_key=self.period_key,
            code="T6_NEGATIVE_BALANCE",
            severity=TaxAnomaly.AnomalySeverity.HIGH,
            status=TaxAnomaly.AnomalyStatus.OPEN,
            description="Negative",
            task_code="T2",
        )
        resp = self.client.get(f"/api/tax/periods/{self.period_key}/anomalies/?severity=high")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["anomalies"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["code"], "T6_NEGATIVE_BALANCE")

    def test_refresh_creates_snapshot(self):
        resp = self.client.post(f"/api/tax/periods/{self.period_key}/refresh/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(TaxPeriodSnapshot.objects.filter(business=self.business, period_key=self.period_key).exists())

    @patch("taxes.llm_observer._invoke_llm")
    def test_llm_enrich_endpoint_updates_snapshot(self, mock_llm):
        self._make_snapshot()
        mock_llm.return_value = '{"summary":"Net tax looks stable for this period.","notes":["Review high anomalies before filing."]}'
        resp = self.client.post(f"/api/tax/periods/{self.period_key}/llm-enrich/")
        self.assertEqual(resp.status_code, 200)
        snap = TaxPeriodSnapshot.objects.get(business=self.business, period_key=self.period_key)
        self.assertIn("Net tax looks stable", snap.llm_summary)

    def test_export_filenames(self):
        self._make_snapshot()
        json_resp = self.client.get(f"/api/tax/periods/{self.period_key}/export.json")
        self.assertEqual(json_resp.status_code, 200)
        disposition = json_resp["Content-Disposition"]
        self.assertIn("tax_snapshot_", disposition)
        self.assertIn(self.period_key, disposition)

        csv_resp = self.client.get(f"/api/tax/periods/{self.period_key}/export.csv")
        self.assertEqual(csv_resp.status_code, 200)
        disposition_csv = csv_resp["Content-Disposition"]
        self.assertIn("tax_snapshot_", disposition_csv)
        self.assertIn(self.period_key, disposition_csv)

    def test_export_json(self):
        """Test JSON export returns proper file structure."""
        self._make_snapshot()
        resp = self.client.get(f"/api/tax/periods/{self.period_key}/export.json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/json")
        self.assertIn("attachment", resp["Content-Disposition"])
        data = resp.json()
        self.assertIn("business_id", data)
        self.assertIn("period_key", data)
        self.assertIn("summary_by_jurisdiction", data)
        self.assertIn("line_mappings", data)
        self.assertIn("generated_at", data)
        self.assertEqual(data["period_key"], self.period_key)

    def test_export_csv(self):
        """Test CSV export returns proper header and data rows."""
        self._make_snapshot()
        resp = self.client.get(f"/api/tax/periods/{self.period_key}/export.csv")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        self.assertIn("attachment", resp["Content-Disposition"])
        content = resp.content.decode("utf-8")
        lines = content.strip().split("\n")
        # Header row
        self.assertIn("jurisdiction_code", lines[0])
        self.assertIn("taxable_sales", lines[0])
        self.assertIn("net_tax", lines[0])
        # Data row (CA-ON)
        self.assertTrue(len(lines) >= 2)
        self.assertIn("CA-ON", content)

    def test_export_json_not_found(self):
        """Test JSON export returns 404 for non-existent snapshots."""
        resp = self.client.get("/api/tax/periods/1999-01/export.json")
        self.assertEqual(resp.status_code, 404)

    def test_export_csv_not_found(self):
        """Test CSV export returns 404 for non-existent snapshots."""
        resp = self.client.get("/api/tax/periods/1999-01/export.csv")
        self.assertEqual(resp.status_code, 404)

    def test_export_ser_csv_not_found_without_snapshot(self):
        resp = self.client.get("/api/tax/periods/1999-01/export-ser.csv")
        self.assertEqual(resp.status_code, 404)

    def test_export_ser_csv_not_found_without_us_data(self):
        self._make_snapshot()
        resp = self.client.get(f"/api/tax/periods/{self.period_key}/export-ser.csv")
        self.assertEqual(resp.status_code, 404)

    def test_export_ser_csv_success(self):
        TaxPeriodSnapshot.objects.create(
            business=self.business,
            period_key=self.period_key,
            country="US",
            status=TaxPeriodSnapshot.SnapshotStatus.COMPUTED,
            summary_by_jurisdiction={},
            line_mappings={
                "US": {
                    "gross_sales": 100.0,
                    "taxable_sales": 90.0,
                    "tax_collected": 6.0,
                    "tax_on_purchases": 1.0,
                    "net_tax": 5.0,
                    "states": {
                        "US-CA": {
                            "gross_sales": 100.0,
                            "exempt_sales": 10.0,
                            "taxable_sales": 90.0,
                            "tax_collected": 6.0,
                            "tax_on_purchases": 1.0,
                            "net_tax": 5.0,
                        }
                    },
                }
            },
        )
        resp = self.client.get(f"/api/tax/periods/{self.period_key}/export-ser.csv")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        self.assertIn("tax_ser_", resp["Content-Disposition"])
        self.assertIn(self.period_key, resp["Content-Disposition"])
        content = resp.content.decode("utf-8")
        self.assertIn("state_code", content.splitlines()[0])
        self.assertIn("US-CA", content)

    def test_reset_filed_period_success(self):
        snap = self._make_snapshot()
        snap.status = TaxPeriodSnapshot.SnapshotStatus.FILED
        snap.filed_at = timezone.now()
        snap.save(update_fields=["status", "filed_at"])
        resp = self.client.post(
            f"/api/tax/periods/{self.period_key}/reset/",
            data='{"confirm_reset": true, "reason": "test"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        snap.refresh_from_db()
        self.assertEqual(snap.status, TaxPeriodSnapshot.SnapshotStatus.REVIEWED)
        self.assertIsNone(snap.filed_at)
        self.assertIsNotNone(snap.last_filed_at)
        self.assertIsNotNone(snap.last_reset_at)

    def test_reset_non_filed_period_rejected(self):
        snap = self._make_snapshot()
        self.assertNotEqual(snap.status, TaxPeriodSnapshot.SnapshotStatus.FILED)
        resp = self.client.post(
            f"/api/tax/periods/{self.period_key}/reset/",
            data='{"confirm_reset": true}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_reset_respects_business_scope(self):
        other_user = User.objects.create_user(username="taxapi2", password="pass")
        other_business = Business.objects.create(
            name="Other Biz",
            currency="CAD",
            owner_user=other_user,
            tax_country="CA",
            tax_region="ON",
        )
        TaxPeriodSnapshot.objects.create(
            business=other_business,
            period_key=self.period_key,
            country="CA",
            status=TaxPeriodSnapshot.SnapshotStatus.FILED,
            filed_at=timezone.now(),
            summary_by_jurisdiction={},
            line_mappings={},
        )
        resp = self.client.post(
            f"/api/tax/periods/{self.period_key}/reset/",
            data='{"confirm_reset": true}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_create_payment_updates_payment_total_and_status(self):
        self._make_snapshot()
        resp = self.client.post(
            f"/api/tax/periods/{self.period_key}/payments/",
            data=f'{{"amount":"60.00","payment_date":"2025-01-10","method":"EFT","bank_account_id":"{self.bank_account.id}"}}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        payload = resp.json()
        self.assertEqual(payload["payment"]["bank_account_id"], str(self.bank_account.id))
        self.assertEqual(payload["payment"]["bank_account_label"], str(self.bank_account))
        detail = self.client.get(f"/api/tax/periods/{self.period_key}/").json()
        self.assertEqual(detail["payment_status"], "PARTIALLY_PAID")
        self.assertAlmostEqual(detail["payments_total"], 60.0)

        resp = self.client.post(
            f"/api/tax/periods/{self.period_key}/payments/",
            data=f'{{"amount":"50.00","payment_date":"2025-01-11","method":"EFT","bank_account_id":"{self.bank_account.id}"}}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        detail = self.client.get(f"/api/tax/periods/{self.period_key}/").json()
        self.assertEqual(detail["payment_status"], "PAID")
        self.assertAlmostEqual(detail["payments_total"], 110.0)

    def test_payment_scoped_to_business(self):
        self._make_snapshot()
        payment = TaxPayment.objects.create(
            business=self.business,
            period_key=self.period_key,
            snapshot=TaxPeriodSnapshot.objects.get(business=self.business, period_key=self.period_key),
            amount=Decimal("10.00"),
            currency="CAD",
            payment_date=date(2025, 1, 1),
            created_by=self.user,
        )
        other_user = User.objects.create_user(username="taxapi3", password="pass")
        other_business = Business.objects.create(
            name="Other Biz 2",
            currency="CAD",
            owner_user=other_user,
            tax_country="CA",
            tax_region="ON",
        )
        client2 = Client()
        client2.force_login(other_user)
        resp = client2.get(f"/api/tax/periods/{self.period_key}/payments/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["payments"], [])
        resp = client2.patch(
            f"/api/tax/periods/{self.period_key}/payments/{payment.id}/",
            data='{"amount":"20.00"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_remaining_balance_and_statuses_liability(self):
        self._make_snapshot(net_tax=200.0)

        detail = self.client.get(f"/api/tax/periods/{self.period_key}/").json()
        self.assertEqual(detail["payment_status"], "UNPAID")
        self.assertAlmostEqual(detail["payments_total"], 0.0)
        self.assertAlmostEqual(detail["remaining_balance"], 200.0)

        self.client.post(
            f"/api/tax/periods/{self.period_key}/payments/",
            data=f'{{"amount":"100.00","payment_date":"2025-01-10","method":"EFT","bank_account_id":"{self.bank_account.id}"}}',
            content_type="application/json",
        )
        detail = self.client.get(f"/api/tax/periods/{self.period_key}/").json()
        self.assertEqual(detail["payment_status"], "PARTIALLY_PAID")
        self.assertAlmostEqual(detail["payments_total"], 100.0)
        self.assertAlmostEqual(detail["remaining_balance"], 100.0)

        self.client.post(
            f"/api/tax/periods/{self.period_key}/payments/",
            data=f'{{"amount":"100.00","payment_date":"2025-01-11","method":"EFT","bank_account_id":"{self.bank_account.id}"}}',
            content_type="application/json",
        )
        detail = self.client.get(f"/api/tax/periods/{self.period_key}/").json()
        self.assertEqual(detail["payment_status"], "PAID")
        self.assertAlmostEqual(detail["payments_total"], 200.0)
        self.assertAlmostEqual(detail["remaining_balance"], 0.0, places=2)

        self.client.post(
            f"/api/tax/periods/{self.period_key}/payments/",
            data=f'{{"amount":"50.00","payment_date":"2025-01-12","method":"EFT","bank_account_id":"{self.bank_account.id}"}}',
            content_type="application/json",
        )
        detail = self.client.get(f"/api/tax/periods/{self.period_key}/").json()
        self.assertEqual(detail["payment_status"], "OVERPAID")
        self.assertAlmostEqual(detail["payments_total"], 250.0)
        self.assertAlmostEqual(detail["remaining_balance"], -50.0)

        periods = self.client.get("/api/tax/periods/").json()["periods"]
        row = next(p for p in periods if p["period_key"] == self.period_key)
        self.assertIn("remaining_balance", row)
        self.assertEqual(row["payment_status"], "OVERPAID")

    def test_remaining_balance_and_statuses_refund(self):
        self._make_snapshot(net_tax=-200.0)

        detail = self.client.get(f"/api/tax/periods/{self.period_key}/").json()
        self.assertEqual(detail["payment_status"], "REFUND_DUE")
        self.assertAlmostEqual(detail["payments_total"], 0.0)
        self.assertAlmostEqual(detail["remaining_balance"], -200.0)

        self.client.post(
            f"/api/tax/periods/{self.period_key}/payments/",
            data=f'{{"amount":"200.00","payment_date":"2025-01-10","method":"EFT","bank_account_id":"{self.bank_account.id}"}}',
            content_type="application/json",
        )
        detail = self.client.get(f"/api/tax/periods/{self.period_key}/").json()
        self.assertEqual(detail["payment_status"], "REFUND_RECEIVED")
        self.assertAlmostEqual(detail["payments_total"], -200.0)
        self.assertAlmostEqual(detail["remaining_balance"], 0.0, places=2)

        self.client.post(
            f"/api/tax/periods/{self.period_key}/payments/",
            data=f'{{"amount":"50.00","payment_date":"2025-01-11","method":"EFT","bank_account_id":"{self.bank_account.id}"}}',
            content_type="application/json",
        )
        detail = self.client.get(f"/api/tax/periods/{self.period_key}/").json()
        self.assertEqual(detail["payment_status"], "REFUND_OVERRECEIVED")
        self.assertAlmostEqual(detail["payments_total"], -250.0)
        self.assertAlmostEqual(detail["remaining_balance"], 50.0)

        periods = self.client.get("/api/tax/periods/").json()["periods"]
        row = next(p for p in periods if p["period_key"] == self.period_key)
        self.assertEqual(row["payment_status"], "REFUND_OVERRECEIVED")
        self.assertIn("remaining_balance", row)

    def test_create_payment_rejects_cross_business_bank_account(self):
        self._make_snapshot(net_tax=200.0)

        other_user = User.objects.create_user(username="taxapi_other", password="pass")
        other_business = Business.objects.create(
            name="Other Biz",
            currency="CAD",
            owner_user=other_user,
            tax_country="CA",
            tax_region="ON",
        )
        other_bank = BankAccount.objects.create(business=other_business, name="Other Operating")

        resp = self.client.post(
            f"/api/tax/periods/{self.period_key}/payments/",
            data=f'{{"amount":"100.00","payment_date":"2025-01-10","method":"EFT","bank_account_id":"{other_bank.id}"}}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("bank_account_id", resp.json().get("errors", {}))

    def test_status_transition_valid(self):
        snap = self._make_snapshot()
        resp = self.client.post(f"/api/tax/periods/{self.period_key}/status/", data='{"status":"REVIEWED"}', content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        snap.refresh_from_db()
        self.assertEqual(snap.status, TaxPeriodSnapshot.SnapshotStatus.REVIEWED)

        resp = self.client.post(f"/api/tax/periods/{self.period_key}/status/", data='{"status":"FILED"}', content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        snap.refresh_from_db()
        self.assertEqual(snap.status, TaxPeriodSnapshot.SnapshotStatus.FILED)

    def test_status_transition_invalid_backwards(self):
        snap = self._make_snapshot()
        snap.status = TaxPeriodSnapshot.SnapshotStatus.FILED
        snap.save()
        resp = self.client.post(f"/api/tax/periods/{self.period_key}/status/", data='{"status":"REVIEWED"}', content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_refresh_blocked_for_filed(self):
        snap = self._make_snapshot()
        snap.status = TaxPeriodSnapshot.SnapshotStatus.FILED
        snap.save()
        resp = self.client.post(f"/api/tax/periods/{self.period_key}/refresh/")
        self.assertEqual(resp.status_code, 409)

    def test_update_anomaly_status(self):
        self._make_snapshot()
        anomaly = TaxAnomaly.objects.create(
            business=self.business,
            period_key=self.period_key,
            code="T6_NEGATIVE_BALANCE",
            severity=TaxAnomaly.AnomalySeverity.HIGH,
            status=TaxAnomaly.AnomalyStatus.OPEN,
            description="Negative",
            task_code="T2",
        )
        resp = self.client.patch(
            f"/api/tax/periods/{self.period_key}/anomalies/{anomaly.id}/",
            data='{"status":"ACKNOWLEDGED"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        anomaly.refresh_from_db()
        self.assertEqual(anomaly.status, TaxAnomaly.AnomalyStatus.ACKNOWLEDGED)

    def test_update_anomaly_wrong_business(self):
        other_user = User.objects.create_user(username="other", password="pass")
        other_business = Business.objects.create(
            name="Other",
            currency="CAD",
            owner_user=other_user,
            tax_country="CA",
            tax_region="QC",
        )
        anomaly = TaxAnomaly.objects.create(
            business=other_business,
            period_key=self.period_key,
            code="T6_NEGATIVE_BALANCE",
            severity=TaxAnomaly.AnomalySeverity.HIGH,
            status=TaxAnomaly.AnomalyStatus.OPEN,
            description="Negative",
            task_code="T2",
        )
        resp = self.client.patch(
            f"/api/tax/periods/{self.period_key}/anomalies/{anomaly.id}/",
            data='{"status":"ACKNOWLEDGED"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)

    def _create_rate_mismatch_anomaly(self):
        tax_group = TaxGroup.objects.create(
            business=self.business,
            display_name="Test Group",
            calculation_method=TaxGroup.CalculationMethod.SIMPLE,
        )
        account = Account.objects.create(
            business=self.business,
            code=f"23{Account.objects.filter(business=self.business).count()+1}",
            name="Tax Payable",
            type=Account.AccountType.LIABILITY,
        )
        component = TaxComponent.objects.create(
            business=self.business,
            name="GST 5%",
            rate_percentage=Decimal("0.05"),
            authority="CRA",
            is_recoverable=False,
            effective_start_date=date.today(),
            default_coa_account=account,
        )
        detail = TransactionLineTaxDetail.objects.create(
            business=self.business,
            tax_group=tax_group,
            tax_component=component,
            transaction_date=date.today(),
            taxable_amount_txn_currency=Decimal("100.00"),
            taxable_amount_home_currency_cad=Decimal("100.00"),
            tax_amount_txn_currency=Decimal("1.00"),  # should be 5.00 expected
            tax_amount_home_currency_cad=Decimal("1.00"),
            is_recoverable=False,
            jurisdiction_code="CA-ON",
            transaction_line_content_type=ContentType.objects.get_for_model(Business),
            transaction_line_object_id=self.business.id,
        )
        compute_tax_period_snapshot(self.business, self.period_key)
        anomalies = compute_tax_anomalies(self.business, self.period_key)
        return anomalies, detail

    def test_anomalies_export_csv_includes_expected_columns(self):
        anomalies, detail = self._create_rate_mismatch_anomaly()
        resp = self.client.get(f"/api/tax/periods/{self.period_key}/anomalies/export.csv")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("tax_anomalies_", resp["Content-Disposition"])
        decoded = resp.content.decode("utf-8")
        reader = csv.reader(io.StringIO(decoded))
        rows = list(reader)
        self.assertGreaterEqual(len(rows), 1)
        header = rows[0]
        self.assertIn("period_key", header)
        self.assertIn("jurisdiction_code", header)

    def test_anomalies_export_csv_404_without_snapshot(self):
        resp = self.client.get("/api/tax/periods/1999-01/anomalies/export.csv")
        self.assertEqual(resp.status_code, 404)

    def test_anomalies_list_includes_linked_model_and_difference(self):
        anomalies, detail = self._create_rate_mismatch_anomaly()
        resp = self.client.get(f"/api/tax/periods/{self.period_key}/anomalies/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["anomalies"]
        self.assertTrue(any(a.get("code") == "T1_RATE_MISMATCH" for a in data))
        target = next(a for a in data if a.get("code") == "T1_RATE_MISMATCH")
        # Should include expected/actual/difference fields
        self.assertIn("expected_tax_amount", target)
        self.assertIn("actual_tax_amount", target)
        self.assertIn("difference", target)

    @patch("core.views_tax_guardian.timezone.localdate")
    def test_period_list_includes_due_dates(self, mock_localdate):
        mock_localdate.return_value = date(2025, 5, 25)
        self.business.tax_filing_due_day = 30
        self.business.tax_filing_frequency = Business.TaxFilingFrequency.MONTHLY
        self.business.save()
        self.period_key = "2025-04"
        self._make_snapshot()
        resp = self.client.get("/api/tax/periods/")
        self.assertEqual(resp.status_code, 200)
        period = resp.json()["periods"][0]
        self.assertEqual(period["due_date"], "2025-05-30")
        self.assertTrue(period["is_due_soon"])
        self.assertFalse(period["is_overdue"])

    @patch("core.views_tax_guardian.timezone.localdate")
    def test_period_detail_includes_due_dates_and_overdue(self, mock_localdate):
        mock_localdate.return_value = date(2025, 6, 15)
        self.business.tax_filing_due_day = 30
        self.business.tax_filing_frequency = Business.TaxFilingFrequency.MONTHLY
        self.business.save()
        self.period_key = "2025-04"
        self._make_snapshot()
        resp = self.client.get(f"/api/tax/periods/{self.period_key}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["due_date"], "2025-05-30")
        self.assertTrue(data["is_overdue"])
        self.assertFalse(data["is_due_soon"])
