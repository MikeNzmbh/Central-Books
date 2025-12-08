"""
Tests for Companion Coverage, Close-Readiness, and Playbook.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import (
    Business,
    CompanionIssue,
    ReceiptRun,
    ReceiptDocument,
    Invoice,
    BankAccount,
    BankTransaction,
)
from core.companion_issues import (
    build_companion_coverage,
    evaluate_period_close_readiness,
    build_companion_playbook,
)
from core.accounting_defaults import ensure_default_accounts


User = get_user_model()


class TestBuildCompanionCoverage(TestCase):
    """Tests for build_companion_coverage function."""
    
    def setUp(self):
        self.user = User.objects.create_user(username="coverageuser", password="test123")
        self.business = Business.objects.create(
            name="Coverage Test Co",
            currency="USD",
            owner_user=self.user,
        )
        defaults = ensure_default_accounts(self.business)
        self.bank_account = BankAccount.objects.create(
            business=self.business,
            name="Operating",
            account=defaults["cash"],
        )
    
    def test_returns_all_four_domains(self):
        """Coverage should return all 4 domains."""
        coverage = build_companion_coverage(self.business)
        
        self.assertIn("receipts", coverage)
        self.assertIn("invoices", coverage)
        self.assertIn("banking", coverage)
        self.assertIn("books", coverage)
    
    def test_each_domain_has_required_fields(self):
        """Each domain should have coverage_percent, total_items, covered_items."""
        coverage = build_companion_coverage(self.business)
        
        for domain_name, domain in coverage.items():
            self.assertIn("coverage_percent", domain, f"{domain_name} missing coverage_percent")
            self.assertIn("total_items", domain, f"{domain_name} missing total_items")
            self.assertIn("covered_items", domain, f"{domain_name} missing covered_items")
    
    def test_empty_business_has_zero_items(self):
        """Empty business should have 0 total_items for receipts/invoices/banking."""
        coverage = build_companion_coverage(self.business)
        
        self.assertEqual(coverage["receipts"]["total_items"], 0)
        self.assertEqual(coverage["invoices"]["total_items"], 0)
        self.assertEqual(coverage["banking"]["total_items"], 0)


class TestEvaluatePeriodCloseReadiness(TestCase):
    """Tests for evaluate_period_close_readiness function."""
    
    def setUp(self):
        self.user = User.objects.create_user(username="readinessuser", password="test123")
        self.business = Business.objects.create(
            name="Readiness Test Co",
            currency="USD",
            owner_user=self.user,
        )
        defaults = ensure_default_accounts(self.business)
        self.bank_account = BankAccount.objects.create(
            business=self.business,
            name="Operating",
            account=defaults["cash"],
        )
    
    def test_empty_business_is_ready(self):
        """Empty business with no issues should be ready to close."""
        result = evaluate_period_close_readiness(self.business)
        
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["blocking_reasons"], [])
    
    def test_unreconciled_transactions_blocks_close(self):
        """Unreconciled bank transactions should block period close."""
        BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=timezone.now().date(),
            description="Test transaction",
            amount=100.00,
            status=BankTransaction.TransactionStatus.NEW,
        )
        
        result = evaluate_period_close_readiness(self.business)
        
        self.assertEqual(result["status"], "not_ready")
        self.assertTrue(any("unreconciled" in r.lower() for r in result["blocking_reasons"]))
    
    def test_high_severity_issue_blocks_close(self):
        """High severity CompanionIssue in books/bank should block close."""
        CompanionIssue.objects.create(
            business=self.business,
            surface="books",
            severity=CompanionIssue.Severity.HIGH,
            status=CompanionIssue.Status.OPEN,
            title="High risk journal entry",
        )
        
        result = evaluate_period_close_readiness(self.business)
        
        self.assertEqual(result["status"], "not_ready")
        self.assertTrue(any("high-severity" in r.lower() for r in result["blocking_reasons"]))


class TestBuildCompanionPlaybook(TestCase):
    """Tests for build_companion_playbook function."""
    
    def setUp(self):
        self.user = User.objects.create_user(username="playbookuser", password="test123")
        self.business = Business.objects.create(
            name="Playbook Test Co",
            currency="USD",
            owner_user=self.user,
        )
    
    def test_returns_list(self):
        """Playbook should return a list."""
        playbook = build_companion_playbook(self.business)
        
        self.assertIsInstance(playbook, list)
    
    def test_max_four_steps(self):
        """Playbook should have at most 4 steps."""
        # Create 10 issues
        for i in range(10):
            CompanionIssue.objects.create(
                business=self.business,
                surface="bank",
                severity=CompanionIssue.Severity.MEDIUM,
                status=CompanionIssue.Status.OPEN,
                title=f"Issue {i}",
            )
        
        playbook = build_companion_playbook(self.business)
        
        self.assertLessEqual(len(playbook), 4)
    
    def test_steps_have_required_fields(self):
        """Each playbook step should have required fields."""
        CompanionIssue.objects.create(
            business=self.business,
            surface="receipts",
            severity=CompanionIssue.Severity.HIGH,
            status=CompanionIssue.Status.OPEN,
            title="Review receipts",
        )
        
        playbook = build_companion_playbook(self.business)
        
        self.assertGreater(len(playbook), 0)
        step = playbook[0]
        self.assertIn("label", step)
        self.assertIn("surface", step)
        self.assertIn("severity", step)
        self.assertIn("url", step)
    
    def test_high_severity_issues_first(self):
        """High severity issues should appear before low severity."""
        CompanionIssue.objects.create(
            business=self.business,
            surface="receipts",
            severity=CompanionIssue.Severity.LOW,
            status=CompanionIssue.Status.OPEN,
            title="Low priority",
        )
        CompanionIssue.objects.create(
            business=self.business,
            surface="bank",
            severity=CompanionIssue.Severity.HIGH,
            status=CompanionIssue.Status.OPEN,
            title="High priority",
        )
        
        playbook = build_companion_playbook(self.business)
        
        self.assertEqual(playbook[0]["title" if "title" in playbook[0] else "label"], "High priority")
