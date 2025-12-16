from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from core.models import Business
from taxes.models import TaxJurisdiction, TaxProductRule

User = get_user_model()


class TaxProductRulesApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rules", password="pass")
        self.client = Client()
        self.client.force_login(self.user)
        self.business = Business.objects.create(
            name="Rules Biz",
            currency="CAD",
            owner_user=self.user,
            tax_country="CA",
            tax_region="ON",
            default_nexus_jurisdictions=["CA-ON"],
        )
        self.ca_on, _ = TaxJurisdiction.objects.get_or_create(
            code="CA-ON",
            defaults={"name": "Ontario", "jurisdiction_type": "PROVINCIAL", "country_code": "CA", "region_code": "ON"},
        )
        self.us_ca, _ = TaxJurisdiction.objects.get_or_create(
            code="US-CA",
            defaults={"name": "California", "jurisdiction_type": "STATE", "country_code": "US", "region_code": "CA"},
        )

    def test_list_product_rules_filters_by_jurisdiction_and_product_code(self):
        TaxProductRule.objects.create(
            jurisdiction=self.ca_on,
            product_code="FOOD",
            rule_type=TaxProductRule.RuleType.EXEMPT,
            valid_from=date(2025, 1, 1),
        )
        TaxProductRule.objects.create(
            jurisdiction=self.us_ca,
            product_code="FOOD",
            rule_type=TaxProductRule.RuleType.TAXABLE,
            valid_from=date(2025, 1, 1),
        )
        # No filters -> default nexus subset (CA-ON only)
        resp = self.client.get("/api/tax/product-rules/")
        self.assertEqual(resp.status_code, 200)
        rules = resp.json()["rules"]
        self.assertTrue(all(r["jurisdiction_code"] == "CA-ON" for r in rules))

        resp = self.client.get("/api/tax/product-rules/?jurisdiction=US-CA")
        self.assertEqual(resp.status_code, 200)
        rules = resp.json()["rules"]
        self.assertTrue(all(r["jurisdiction_code"] == "US-CA" for r in rules))

        resp = self.client.get("/api/tax/product-rules/?product_code=FOOD")
        self.assertEqual(resp.status_code, 200)
        rules = resp.json()["rules"]
        self.assertTrue(all(r["product_code"] == "FOOD" for r in rules))

    def test_create_product_rule_valid(self):
        payload = {
            "jurisdiction_code": "CA-ON",
            "product_code": "SAAS",
            "rule_type": "TAXABLE",
            "valid_from": "2025-01-01",
            "notes": "Standard",
        }
        resp = self.client.post("/api/tax/product-rules/", data=payload, content_type="application/json")
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(TaxProductRule.objects.filter(jurisdiction=self.ca_on, product_code="SAAS").exists())

    def test_create_product_rule_requires_special_rate_for_reduced(self):
        payload = {
            "jurisdiction_code": "CA-ON",
            "product_code": "FOOD",
            "rule_type": "REDUCED",
            "valid_from": "2025-01-01",
        }
        resp = self.client.post("/api/tax/product-rules/", data=payload, content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("special_rate", resp.json().get("errors", {}))

    def test_update_product_rule_partial(self):
        rule = TaxProductRule.objects.create(
            jurisdiction=self.ca_on,
            product_code="FOOD",
            rule_type=TaxProductRule.RuleType.EXEMPT,
            valid_from=date(2025, 1, 1),
        )
        resp = self.client.patch(
            f"/api/tax/product-rules/{rule.id}/",
            data={"notes": "Updated", "valid_to": "2025-12-31"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        rule.refresh_from_db()
        self.assertEqual(rule.notes, "Updated")
        self.assertEqual(rule.valid_to, date(2025, 12, 31))

    def test_delete_product_rule(self):
        rule = TaxProductRule.objects.create(
            jurisdiction=self.ca_on,
            product_code="FOOD",
            rule_type=TaxProductRule.RuleType.EXEMPT,
            valid_from=date(2025, 1, 1),
        )
        resp = self.client.delete(f"/api/tax/product-rules/{rule.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(TaxProductRule.objects.filter(id=rule.id).exists())

