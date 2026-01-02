from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from core.models import Business

User = get_user_model()


class TaxSettingsApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="taxsettings", password="pass")
        self.client = Client()
        self.client.force_login(self.user)
        self.business = Business.objects.create(
            name="Settings Biz",
            currency="CAD",
            owner_user=self.user,
            tax_country="CA",
            tax_region="ON",
        )

    def test_get_tax_settings_returns_values(self):
        self.business.gst_hst_number = "123456789RT0001"
        self.business.qst_number = "1234567890TQ0001"
        self.business.us_sales_tax_id = "CA-12345"
        self.business.default_nexus_jurisdictions = ["US-CA", "US-NY"]
        self.business.tax_regime_ca = Business.TaxRegimeCA.GST_ONLY
        self.business.save()
        resp = self.client.get("/api/tax/settings/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["tax_country"], "CA")
        self.assertEqual(data["tax_regime_ca"], "GST_ONLY")
        self.assertEqual(data["gst_hst_number"], "123456789RT0001")
        self.assertEqual(data["default_nexus_jurisdictions"], ["US-CA", "US-NY"])
        self.assertTrue(data["is_country_locked"])

    def test_patch_tax_settings_updates_allowed_fields(self):
        payload = {
            "tax_filing_frequency": "MONTHLY",
            "tax_filing_due_day": 15,
            "gst_hst_number": "111222333RT0001",
            "qst_number": "444555666TQ0001",
            "us_sales_tax_id": "NY-999",
            "default_nexus_jurisdictions": ["US-NY", "US-NJ"],
            "tax_regime_ca": "HST_ONLY",
        }
        resp = self.client.patch(
            "/api/tax/settings/",
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.business.refresh_from_db()
        self.assertEqual(self.business.tax_filing_frequency, "MONTHLY")
        self.assertEqual(self.business.tax_filing_due_day, 15)
        self.assertEqual(self.business.gst_hst_number, "111222333RT0001")
        self.assertEqual(self.business.default_nexus_jurisdictions, ["US-NY", "US-NJ"])
        self.assertEqual(self.business.tax_regime_ca, Business.TaxRegimeCA.HST_ONLY)

    def test_patch_tax_country_locked(self):
        resp = self.client.patch(
            "/api/tax/settings/",
            data={"tax_country": "US"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.business.refresh_from_db()
        self.assertEqual(self.business.tax_country, "CA")

    def test_patch_tax_country_allowed_when_blank(self):
        user = User.objects.create_user(username="blank", password="pass")
        client = Client()
        client.force_login(user)
        biz = Business.objects.create(
            name="Blank Country",
            currency="CAD",
            owner_user=user,
            tax_country="",
            tax_region="",
        )
        resp = client.patch(
            "/api/tax/settings/",
            data={"tax_country": "US", "tax_region": "CA"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        biz.refresh_from_db()
        self.assertEqual(biz.tax_country, "US")
        self.assertEqual(biz.tax_region, "CA")

    def test_patch_tax_regime_ca_ignored_when_not_canada(self):
        user = User.objects.create_user(username="us_taxsettings", password="pass")
        client = Client()
        client.force_login(user)
        biz = Business.objects.create(
            name="US Settings Biz",
            currency="USD",
            owner_user=user,
            tax_country="US",
            tax_region="CA",
        )
        resp = client.patch(
            "/api/tax/settings/",
            data={"tax_regime_ca": "GST_ONLY"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        biz.refresh_from_db()
        self.assertIsNone(biz.tax_regime_ca)
        self.assertIsNone(resp.json().get("tax_regime_ca"))
