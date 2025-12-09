"""
Tests for Companion Risk Radar - 4-axis stability scoring.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import Business, CompanionIssue
from core.companion_issues import build_companion_radar


User = get_user_model()


class TestBuildCompanionRadar(TestCase):
    """Tests for build_companion_radar function."""
    
    def setUp(self):
        self.user = User.objects.create_user(username="radaruser", password="test123")
        self.business = Business.objects.create(
            name="Radar Test Co",
            currency="USD",
            owner_user=self.user,
        )
    
    def test_returns_all_four_axes(self):
        """Radar should return all 4 axes."""
        radar = build_companion_radar(self.business)
        
        self.assertIn("cash_reconciliation", radar)
        self.assertIn("revenue_invoices", radar)
        self.assertIn("expenses_receipts", radar)
        self.assertIn("tax_compliance", radar)
    
    def test_each_axis_has_score_and_open_issues(self):
        """Each axis should have score and open_issues keys."""
        radar = build_companion_radar(self.business)
        
        for axis_name, axis in radar.items():
            self.assertIn("score", axis, f"{axis_name} missing score")
            self.assertIn("open_issues", axis, f"{axis_name} missing open_issues")
    
    def test_perfect_score_with_no_issues(self):
        """All axes should have score 100 when no issues exist."""
        radar = build_companion_radar(self.business)
        
        for axis_name, axis in radar.items():
            self.assertEqual(axis["score"], 100, f"{axis_name} should be 100 with no issues")
            self.assertEqual(axis["open_issues"], 0, f"{axis_name} should have 0 open issues")
    
    def test_score_decreases_with_high_severity_issue(self):
        """Score should decrease when high severity issues are added."""
        # Add a high severity bank issue
        CompanionIssue.objects.create(
            business=self.business,
            surface="bank",
            run_type="bank_review",
            severity=CompanionIssue.Severity.HIGH,
            status=CompanionIssue.Status.OPEN,
            title="Unreconciled transactions",
        )
        
        radar = build_companion_radar(self.business)
        
        # cash_reconciliation axis should be affected
        self.assertLess(radar["cash_reconciliation"]["score"], 100)
        self.assertEqual(radar["cash_reconciliation"]["open_issues"], 1)
        
        # Other axes should remain at 100
        self.assertEqual(radar["revenue_invoices"]["score"], 100)
        self.assertEqual(radar["expenses_receipts"]["score"], 100)
        self.assertEqual(radar["tax_compliance"]["score"], 100)
    
    def test_multiple_issues_reduce_score_more(self):
        """Multiple issues should reduce score more than a single issue."""
        # Add 3 medium severity invoice issues
        for i in range(3):
            CompanionIssue.objects.create(
                business=self.business,
                surface="invoices",
                run_type="invoices",
                severity=CompanionIssue.Severity.MEDIUM,
                status=CompanionIssue.Status.OPEN,
                title=f"Issue {i}",
            )
        
        radar = build_companion_radar(self.business)
        
        # revenue_invoices should have 3 open issues
        self.assertEqual(radar["revenue_invoices"]["open_issues"], 3)
        # Score should be 100 - (3 * 8) = 76
        self.assertEqual(radar["revenue_invoices"]["score"], 76)
    
    def test_resolved_issues_not_counted(self):
        """Resolved issues should not affect the score."""
        CompanionIssue.objects.create(
            business=self.business,
            surface="receipts",
            run_type="receipts",
            severity=CompanionIssue.Severity.HIGH,
            status=CompanionIssue.Status.RESOLVED,  # Resolved!
            title="Old resolved issue",
        )
        
        radar = build_companion_radar(self.business)
        
        # expenses_receipts should still be perfect
        self.assertEqual(radar["expenses_receipts"]["score"], 100)
        self.assertEqual(radar["expenses_receipts"]["open_issues"], 0)
    
    def test_age_penalty_applied(self):
        """Older issues should have additional point deductions (1 point per week, max 5)."""
        # Create an issue 14 days ago (2 weeks = +2 age penalty with new 1pt/week rule)
        old_issue = CompanionIssue.objects.create(
            business=self.business,
            surface="books",
            run_type="books_review",
            severity=CompanionIssue.Severity.LOW,  # base: 3 points
            status=CompanionIssue.Status.OPEN,
            title="Old books issue",
        )
        old_issue.created_at = timezone.now() - timedelta(days=14)
        old_issue.save()
        
        radar = build_companion_radar(self.business)
        
        # tax_compliance should be 100 - 3 (base) - 2 (age: 2 weeks * 1pt) = 95
        self.assertEqual(radar["tax_compliance"]["score"], 95)
    
    def test_age_penalty_four_weeks(self):
        """28-day-old issue should add 4 points age penalty (softened from 8 points)."""
        # Create an issue 28 days ago (4 weeks, still within 30-day window)
        # With new 1pt/week: 4 * 1 = 4 points (previously was 4 * 2 = 8 points)
        old_issue = CompanionIssue.objects.create(
            business=self.business,
            surface="books",
            run_type="books_review",
            severity=CompanionIssue.Severity.LOW,  # base: 3 points
            status=CompanionIssue.Status.OPEN,
            title="Old books issue",
        )
        old_issue.created_at = timezone.now() - timedelta(days=28)
        old_issue.save()
        
        radar = build_companion_radar(self.business)
        
        # tax_compliance should be 100 - 3 (base) - 4 (age: 4 weeks * 1pt) = 93
        self.assertEqual(radar["tax_compliance"]["score"], 93)
