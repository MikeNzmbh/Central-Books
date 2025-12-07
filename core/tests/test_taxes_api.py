"""
Tests for Tax Settings and TaxRate CRUD APIs.
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from core.models import Business, TaxRate

User = get_user_model()


class TaxSettingsAPITest(TestCase):
    """Test the tax settings GET/PUT endpoint."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.business = Business.objects.create(
            name="Test Business",
            owner_user=self.user,
            currency="USD"
        )
        self.client.login(username="testuser", password="testpass123")

    def test_get_tax_settings_authenticated(self):
        """Authenticated user can read tax settings."""
        response = self.client.get("/api/taxes/settings/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("is_tax_registered", data)
        self.assertIn("tax_country", data)
        self.assertIn("tax_rates", data)

    def test_get_tax_settings_unauthenticated(self):
        """Unauthenticated user gets 302 redirect to login."""
        self.client.logout()
        response = self.client.get("/api/taxes/settings/")
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_update_tax_settings(self):
        """User can update their business tax settings."""
        response = self.client.post(
            "/api/taxes/settings/",
            data={
                "is_tax_registered": True,
                "tax_country": "CA",
                "tax_region": "ON"
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.business.refresh_from_db()
        self.assertTrue(self.business.is_tax_registered)
        self.assertEqual(self.business.tax_country, "CA")
        self.assertEqual(self.business.tax_region, "ON")

    def test_update_tax_settings_wrong_business(self):
        """User cannot update another business's tax settings."""
        # Create another user and business
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="otherpass123"
        )
        other_business = Business.objects.create(
            name="Other Business",
            owner_user=other_user,
            currency="CAD"
        )
        
        # First user cannot affect second business
        response = self.client.post(
            "/api/taxes/settings/",
            data={"is_tax_registered": True, "tax_country": "US"},
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify other business unchanged
        other_business.refresh_from_db()
        self.assertFalse(other_business.is_tax_registered)


class TaxRatesAPITest(TestCase):
    """Test the tax rates list/create endpoints."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.business = Business.objects.create(
            name="Test Business",
            owner_user=self.user,
            currency="CAD",
            is_tax_registered=True,
            tax_country="CA"
        )
        self.client.login(username="testuser", password="testpass123")

    def test_list_tax_rates(self):
        """User can list their tax rates."""
        TaxRate.objects.create(
            business=self.business,
            name="GST",
            code="GST",
            percentage=Decimal("5.00")  # Stored as 5% not 0.05
        )
        response = self.client.get("/api/taxes/rates/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["tax_rates"]), 1)
        self.assertEqual(data["tax_rates"][0]["name"], "GST")

    def test_create_tax_rate_valid(self):
        """User can create a valid tax rate."""
        response = self.client.post(
            "/api/taxes/rates/",
            data={
                "name": "HST Ontario",
                "code": "HST_ON",
                "rate": 0.13,
                "country": "CA",
                "region": "ON",
                "applies_to_sales": True,
                "applies_to_purchases": True
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(TaxRate.objects.filter(business=self.business, name="HST Ontario").exists())

    def test_create_tax_rate_invalid_percentage_negative(self):
        """Cannot create tax rate with negative percentage."""
        response = self.client.post(
            "/api/taxes/rates/",
            data={
                "name": "Invalid Tax",
                "rate": -0.05
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.json())

    def test_create_tax_rate_invalid_percentage_over_one(self):
        """Cannot create tax rate with percentage > 1000."""
        response = self.client.post(
            "/api/taxes/rates/",
            data={
                "name": "Invalid Tax",
                "rate": 1500  # >1000% should be rejected
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_create_tax_rate_invalid_percentage_too_large(self):
        """Cannot create tax rate with percentage > 1000."""
        response = self.client.post(
            "/api/taxes/rates/",
            data={
                "name": "Invalid Tax",
                "rate": 1500  # > 1000% is rejected
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_create_tax_rate_missing_name(self):
        """Cannot create tax rate without a name."""
        response = self.client.post(
            "/api/taxes/rates/",
            data={"rate": 0.10},
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json()["detail"].lower())

    def test_update_tax_rate(self):
        """User can update their own tax rate."""
        rate = TaxRate.objects.create(
            business=self.business,
            name="Test Rate",
            code="TEST",
            percentage=Decimal("10.00")  # 10%
        )
        response = self.client.patch(
            f"/api/taxes/rates/{rate.id}/",
            data={"name": "Updated Rate", "rate": 0.12},
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        rate.refresh_from_db()
        self.assertEqual(rate.name, "Updated Rate")
        self.assertEqual(rate.percentage, Decimal("12.00"))  # Stored as percentage (12%)

    def test_delete_tax_rate(self):
        """User can delete (deactivate) their tax rate."""
        rate = TaxRate.objects.create(
            business=self.business,
            name="Test Rate",
            code="TEST",
            percentage=Decimal("10.00"),  # 10%
            is_active=True
        )
        response = self.client.delete(f"/api/taxes/rates/{rate.id}/")
        self.assertEqual(response.status_code, 200)
        rate.refresh_from_db()
        self.assertFalse(rate.is_active)

    def test_cross_tenant_isolation(self):
        """User cannot see or modify another business's tax rates."""
        # Create another business with a tax rate
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="otherpass123"
        )
        other_business = Business.objects.create(
            name="Other Business",
            owner_user=other_user,
            currency="USD"
        )
        other_rate = TaxRate.objects.create(
            business=other_business,
            name="Other Rate",
            code="OTHER",
            percentage=Decimal("8.00")  # 8%
        )
        
        # First user's list should not include other business's rate
        response = self.client.get("/api/taxes/rates/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["tax_rates"]), 0)
        
        # First user cannot access other rate by ID
        response = self.client.patch(
            f"/api/taxes/rates/{other_rate.id}/",
            data={"name": "Hacked"},
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 404)
        
        # Verify other rate unchanged
        other_rate.refresh_from_db()
        self.assertEqual(other_rate.name, "Other Rate")
