from datetime import date

from django.test import TestCase

from core.services.periods import resolve_comparison, resolve_period


class PeriodResolverTests(TestCase):
    def test_last_month_bounds(self):
        today = date(2025, 5, 15)
        period = resolve_period("last_month", today=today)
        self.assertEqual(period["start"], date(2025, 4, 1))
        self.assertEqual(period["end"], date(2025, 4, 30))
        self.assertIn("Last Month", period["label"])

    def test_custom_range_from_strings(self):
        period = resolve_period("custom", "2024-01-15", "2024-02-02")
        self.assertEqual(period["start"], date(2024, 1, 15))
        self.assertEqual(period["end"], date(2024, 2, 2))
        self.assertEqual(period["preset"], "custom")

    def test_month_span_comparison_respects_calendar_month(self):
        start = date(2025, 10, 1)
        end = date(2025, 10, 31)
        comparison = resolve_comparison(start, end, "previous_period")
        self.assertEqual(comparison["compare_start"], date(2025, 9, 1))
        self.assertEqual(comparison["compare_end"], date(2025, 9, 30))

    def test_previous_year_comparison(self):
        start = date(2024, 3, 1)
        end = date(2024, 3, 31)
        comparison = resolve_comparison(start, end, "previous_year")
        self.assertEqual(comparison["compare_start"], date(2023, 3, 1))
        self.assertEqual(comparison["compare_end"], date(2023, 3, 31))

    def test_same_period_last_year_comparison_alias(self):
        start = date(2024, 10, 1)
        end = date(2024, 10, 31)
        comparison = resolve_comparison(start, end, "same_period_last_year")
        self.assertEqual(comparison["compare_start"], date(2023, 10, 1))
        self.assertEqual(comparison["compare_end"], date(2023, 10, 31))
