"""Tests for dashboard P&L period handling using unified resolver."""
from datetime import date, timedelta
from decimal import Decimal
import json

from django.test import TestCase, Client
from django.urls import reverse

from core.models import Business, Account, JournalEntry, JournalLine
from core.services.periods import resolve_period, resolve_comparison


class DashboardPeriodResolverTestCase(TestCase):
    """Test that dashboard uses unified period resolver correctly."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(username="test", password="test123")
        self.business = Business.objects.create(
            name="Test Biz",
            owner_user=self.user,
            currency="USD",
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_default_period_is_this_month(self):
        """Dashboard with no params defaults to this_month preset."""
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode()
        # Find the dashboard payload in the page
        self.assertIn('"pl_period_preset":', content)
        self.assertIn('"this_month"', content)

    def test_last_month_preset_resolves_correctly(self):
        """Dashboard with pl_period_preset=last_month returns correct dates."""
        response = self.client.get(
            reverse("dashboard"),
            {"pl_period_preset": "last_month"}
        )
        self.assertEqual(response.status_code, 200)

        content = response.content.decode()
        self.assertIn('"pl_period_preset":', content)
        self.assertIn('"last_month"', content)
        self.assertIn("Last Month", content)

    def test_custom_range_with_dates(self):
        """Dashboard with custom date range returns correct label."""
        response = self.client.get(
            reverse("dashboard"),
            {
                "pl_period_preset": "custom",
                "pl_start_date": "2025-01-01",
                "pl_end_date": "2025-01-31",
            }
        )
        self.assertEqual(response.status_code, 200)

        content = response.content.decode()
        self.assertIn('"pl_period_preset":', content)
        self.assertIn('"custom"', content)

    def test_comparison_fields_present(self):
        """Dashboard includes comparison fields when compare_to is set."""
        response = self.client.get(
            reverse("dashboard"),
            {"pl_compare_to": "previous_period"}
        )
        self.assertEqual(response.status_code, 200)

        content = response.content.decode()
        self.assertIn('"pl_compare_to":', content)
        self.assertIn('"pl_compare_label":', content)

    def test_comparison_none_returns_null_fields(self):
        """Dashboard with compare_to=none returns null comparison fields."""
        response = self.client.get(
            reverse("dashboard"),
            {"pl_compare_to": "none"}
        )
        self.assertEqual(response.status_code, 200)

        content = response.content.decode()
        self.assertIn('"pl_compare_to": "none"', content)

    def test_this_quarter_preset(self):
        """Dashboard with this_quarter preset works correctly."""
        response = self.client.get(
            reverse("dashboard"),
            {"pl_period_preset": "this_quarter"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('"this_quarter"', content)

    def test_this_year_preset(self):
        """Dashboard with this_year preset works correctly."""
        response = self.client.get(
            reverse("dashboard"),
            {"pl_period_preset": "this_year"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('"this_year"', content)
        self.assertIn("Year to Date", content)
