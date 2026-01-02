from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from core.models import Business, Account
from taxes.models import TaxJurisdiction, TaxComponent, TaxRate, TaxProductRule

User = get_user_model()


class TaxCatalogApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="catalog", password="pass", is_staff=True)
        self.business = Business.objects.create(
            name="Catalog Biz",
            currency="CAD",
            owner_user=self.user,
            tax_country="CA",
            tax_region="ON",
        )
        self.client = Client()
        self.client.force_login(self.user)

        self.non_staff = User.objects.create_user(username="nostaff", password="pass")
        self.client_non_staff = Client()
        self.client_non_staff.force_login(self.non_staff)

    def test_requires_staff(self):
        Business.objects.create(
            name="NoStaff Biz",
            currency="CAD",
            owner_user=self.non_staff,
        )
        resp = self.client_non_staff.get("/api/tax/catalog/jurisdictions/")
        self.assertEqual(resp.status_code, 403)

    def test_staff_without_business_can_access_global_catalog_endpoints(self):
        staff = User.objects.create_user(username="staff_nobiz", password="pass", is_staff=True)
        client = Client()
        client.force_login(staff)

        resp = client.get("/api/tax/catalog/jurisdictions/?limit=5")
        self.assertEqual(resp.status_code, 200)

        resp = client.get("/api/tax/catalog/product-rules/?limit=5")
        self.assertEqual(resp.status_code, 200)

    def test_jurisdiction_list_filters(self):
        TaxJurisdiction.objects.get_or_create(
            code="US-CA",
            defaults={"name": "California", "jurisdiction_type": "STATE", "country_code": "US", "region_code": "CA"},
        )
        resp = self.client.get("/api/tax/catalog/jurisdictions/?country_code=US&jurisdiction_type=STATE&limit=50")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("results", data)
        self.assertTrue(all(j["country_code"] == "US" for j in data["results"]))
        self.assertTrue(all(j["jurisdiction_type"] == "STATE" for j in data["results"]))

    def test_jurisdiction_create_and_patch_guardrails(self):
        TaxJurisdiction.objects.get_or_create(
            code="US-CA",
            defaults={"name": "California", "jurisdiction_type": "STATE", "country_code": "US", "region_code": "CA"},
        )

        payload = {
            "code": "US-CA-TST",
            "name": "Test District",
            "jurisdiction_type": "DISTRICT",
            "country_code": "US",
            "region_code": "CA",
            "sourcing_rule": "DESTINATION",
            "parent_code": "US-CA",
        }
        resp = self.client.post("/api/tax/catalog/jurisdictions/", data=payload, content_type="application/json")
        self.assertEqual(resp.status_code, 201)
        created = resp.json()
        self.assertEqual(created["code"], "US-CA-TST")
        self.assertTrue(created["is_custom"])

        # Custom jurisdiction can edit sourcing_rule
        resp = self.client.patch(
            "/api/tax/catalog/jurisdictions/US-CA-TST/",
            data={"sourcing_rule": "ORIGIN"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["sourcing_rule"], "ORIGIN")

        # Seeded jurisdiction cannot edit sourcing_rule
        seeded = TaxJurisdiction.objects.get(code="US-CA")
        resp = self.client.patch(
            f"/api/tax/catalog/jurisdictions/{seeded.code}/",
            data={"sourcing_rule": "ORIGIN"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

        # Attempt to change locked fields is rejected
        resp = self.client.patch(
            f"/api/tax/catalog/jurisdictions/{seeded.code}/",
            data={"country_code": "CA"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_rates_create_and_overlap_rejected(self):
        ca_on, _ = TaxJurisdiction.objects.get_or_create(
            code="CA-ON",
            defaults={"name": "Ontario", "jurisdiction_type": "PROVINCIAL", "country_code": "CA", "region_code": "ON"},
        )
        account = Account.objects.get(business=self.business, code="2300")
        component = TaxComponent.objects.create(
            business=self.business,
            name="Catalog Test Rate",
            rate_percentage=Decimal("0.10"),
            authority="CRA",
            is_recoverable=False,
            effective_start_date=date(2025, 1, 1),
            default_coa_account=account,
            jurisdiction=ca_on,
        )

        payload = {
            "jurisdiction_code": "CA-ON",
            "tax_name": component.name,
            "rate_decimal": "0.10",
            "valid_from": "2025-01-01",
            "valid_to": "2025-12-31",
            "product_category": TaxRate.ProductCategory.STANDARD,
        }
        resp = self.client.post("/api/tax/catalog/rates/", data=payload, content_type="application/json")
        self.assertEqual(resp.status_code, 201)

        # Overlapping range rejected
        overlap = {
            **payload,
            "rate_decimal": "0.11",
            "valid_from": "2025-06-01",
            "valid_to": "2025-12-31",
        }
        resp = self.client.post("/api/tax/catalog/rates/", data=overlap, content_type="application/json")
        self.assertEqual(resp.status_code, 400)

        # Listing by jurisdiction returns our rate
        resp = self.client.get("/api/tax/catalog/rates/?jurisdiction_code=CA-ON")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["results"]
        self.assertTrue(any(r["tax_name"] == component.name for r in data))

    def test_product_rules_non_overlap(self):
        ca_on, _ = TaxJurisdiction.objects.get_or_create(
            code="CA-ON",
            defaults={"name": "Ontario", "jurisdiction_type": "PROVINCIAL", "country_code": "CA", "region_code": "ON"},
        )

        payload = {
            "jurisdiction_code": "CA-ON",
            "product_code": "FOOD",
            "rule_type": "EXEMPT",
            "ssuta_code": "FOOD_GROCERY",
            "valid_from": "2025-01-01",
            "valid_to": "2025-12-31",
            "notes": "Basic groceries",
        }
        resp = self.client.post("/api/tax/catalog/product-rules/", data=payload, content_type="application/json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json().get("ssuta_code"), "FOOD_GROCERY")
        self.assertTrue(TaxProductRule.objects.filter(jurisdiction=ca_on, product_code="FOOD").exists())

        created_id = resp.json()["id"]
        resp = self.client.patch(
            f"/api/tax/catalog/product-rules/{created_id}/",
            data={"ssuta_code": "FOOD_GROCERY_V2"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("ssuta_code"), "FOOD_GROCERY_V2")

        # Overlapping rule rejected
        resp = self.client.post(
            "/api/tax/catalog/product-rules/",
            data={**payload, "rule_type": "ZERO_RATED", "valid_from": "2025-06-01"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

        # Non-overlapping rule allowed
        resp = self.client.post(
            "/api/tax/catalog/product-rules/",
            data={**payload, "rule_type": "ZERO_RATED", "valid_from": "2026-01-01", "valid_to": None},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
