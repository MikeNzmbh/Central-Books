from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from core.models import Account, Business
from taxes.models import TaxComponent, TaxJurisdiction, TaxProductRule, TaxRate

User = get_user_model()


class TaxImportApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="importer", password="pass", is_staff=True)
        self.business = Business.objects.create(
            name="Import Biz",
            currency="CAD",
            owner_user=self.user,
            tax_country="CA",
            tax_region="ON",
        )
        self.client = Client()
        self.client.force_login(self.user)

        self.non_staff = User.objects.create_user(username="nostaff_import", password="pass")
        self.business_non_staff = Business.objects.create(name="NonStaff Biz", currency="CAD", owner_user=self.non_staff)
        self.client_non_staff = Client()
        self.client_non_staff.force_login(self.non_staff)

    def test_requires_staff(self):
        content = b"code,name,jurisdiction_type,country_code\nCA-ON,Ontario,PROVINCIAL,CA\n"
        upload = SimpleUploadedFile("jur.csv", content, content_type="text/csv")
        resp = self.client_non_staff.post(
            "/api/tax/catalog/import/preview/",
            data={"import_type": "jurisdictions", "file": upload},
        )
        self.assertEqual(resp.status_code, 403)

    def test_preview_jurisdictions_csv_valid_and_invalid(self):
        TaxJurisdiction.objects.get_or_create(
            code="CA",
            defaults={"name": "Canada", "jurisdiction_type": "FEDERAL", "country_code": "CA", "region_code": ""},
        )
        content = b"code,name,jurisdiction_type,country_code,parent_code\nCA-ON,Ontario,PROVINCIAL,CA,CA\nBAD,,STATE,CA,\n"
        upload = SimpleUploadedFile("jur.csv", content, content_type="text/csv")
        resp = self.client.post(
            "/api/tax/catalog/import/preview/",
            data={"import_type": "jurisdictions", "file": upload},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["import_type"], "jurisdictions")
        self.assertEqual(data["summary"]["total_rows"], 2)
        self.assertGreaterEqual(data["summary"]["errors"], 1)

    def test_apply_jurisdictions_does_not_modify_seeded_protected_fields(self):
        seeded, _ = TaxJurisdiction.objects.get_or_create(
            code="US-CA",
            defaults={
                "name": "California",
                "jurisdiction_type": "STATE",
                "country_code": "US",
                "region_code": "CA",
                "sourcing_rule": "HYBRID",
                "metadata": {},
            },
        )
        # Ensure it is treated as seeded (non-custom).
        seeded.metadata = seeded.metadata or {}
        seeded.metadata.pop("is_custom", None)
        seeded.save(update_fields=["metadata"])
        # Attempt to change seeded country_code/jurisdiction_type (should error and not apply).
        content = b"code,name,jurisdiction_type,country_code,region_code\nUS-CA,California Updated,PROVINCIAL,CA,CA\n"
        upload = SimpleUploadedFile("jur.csv", content, content_type="text/csv")
        resp = self.client.post(
            "/api/tax/catalog/import/apply/",
            data={"import_type": "jurisdictions", "file": upload},
        )
        self.assertEqual(resp.status_code, 400)
        seeded.refresh_from_db()
        self.assertEqual(seeded.country_code, "US")
        self.assertEqual(seeded.jurisdiction_type, "STATE")

    def test_preview_rates_detects_overlap(self):
        ca_on, _ = TaxJurisdiction.objects.get_or_create(
            code="CA-ON",
            defaults={"name": "Ontario", "jurisdiction_type": "PROVINCIAL", "country_code": "CA", "region_code": "ON"},
        )
        account = Account.objects.get(business=self.business, code="2300")
        component = TaxComponent.objects.create(
            business=self.business,
            name="HST",
            rate_percentage=Decimal("0.13"),
            authority="CRA",
            is_recoverable=False,
            effective_start_date=date(2025, 1, 1),
            default_coa_account=account,
            jurisdiction=ca_on,
        )
        TaxRate.objects.create(
            component=component,
            rate_decimal=Decimal("0.13"),
            effective_from=date(2025, 1, 1),
            effective_to=date(2025, 12, 31),
            product_category=TaxRate.ProductCategory.STANDARD,
        )

        # Overlaps existing
        content = b"jurisdiction_code,tax_name,rate_decimal,valid_from,valid_to\nCA-ON,HST,0.12,2025-06-01,2025-12-31\n"
        upload = SimpleUploadedFile("rates.csv", content, content_type="text/csv")
        resp = self.client.post("/api/tax/catalog/import/preview/", data={"import_type": "rates", "file": upload})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["summary"]["errors"], 1)

    def test_apply_rates_valid_creates_rows(self):
        ca_on, _ = TaxJurisdiction.objects.get_or_create(
            code="CA-ON",
            defaults={"name": "Ontario", "jurisdiction_type": "PROVINCIAL", "country_code": "CA", "region_code": "ON"},
        )
        account = Account.objects.get(business=self.business, code="2300")
        TaxComponent.objects.create(
            business=self.business,
            name="HST_IMPORT",
            rate_percentage=Decimal("0.13"),
            authority="CRA",
            is_recoverable=False,
            effective_start_date=date(2025, 1, 1),
            default_coa_account=account,
            jurisdiction=ca_on,
        )
        content = b"jurisdiction_code,tax_name,rate_decimal,valid_from,valid_to,product_category\nCA-ON,HST_IMPORT,0.13,2025-01-01,2025-12-31,STANDARD\n"
        upload = SimpleUploadedFile("rates.csv", content, content_type="text/csv")
        resp = self.client.post("/api/tax/catalog/import/apply/", data={"import_type": "rates", "file": upload})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["created"], 1)

    def test_apply_product_rules_errors_block_transaction(self):
        ca_on, _ = TaxJurisdiction.objects.get_or_create(
            code="CA-ON",
            defaults={"name": "Ontario", "jurisdiction_type": "PROVINCIAL", "country_code": "CA", "region_code": "ON"},
        )
        # invalid rule_type should block and create nothing
        content = b"jurisdiction_code,product_code,rule_type,valid_from\nCA-ON,FOOD,NOT_A_RULE,2025-01-01\n"
        upload = SimpleUploadedFile("rules.csv", content, content_type="text/csv")
        resp = self.client.post("/api/tax/catalog/import/apply/", data={"import_type": "product_rules", "file": upload})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(TaxProductRule.objects.filter(jurisdiction=ca_on, product_code="FOOD").exists())
