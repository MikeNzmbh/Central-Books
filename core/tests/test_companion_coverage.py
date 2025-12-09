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
    
    def test_returns_three_domains(self):
        """Coverage should return 3 domains (books is omitted until real metrics available)."""
        coverage = build_companion_coverage(self.business)
        
        self.assertIn("receipts", coverage)
        self.assertIn("invoices", coverage)
        self.assertIn("banking", coverage)
        # books is intentionally omitted - no fake coverage
        self.assertNotIn("books", coverage)
    
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
    
    def test_unreconciled_below_threshold_does_not_block(self):
        """Less than 5 unreconciled with ratio below 2% should NOT block period close."""
        # Create 3 unreconciled transactions
        for i in range(3):
            BankTransaction.objects.create(
                bank_account=self.bank_account,
                date=timezone.now().date(),
                description=f"Unreconciled transaction {i}",
                amount=100.00,
                status=BankTransaction.TransactionStatus.NEW,
            )
        # Create 197 reconciled transactions to make ratio = 3/200 = 1.5% (< 2% threshold)
        for i in range(197):
            BankTransaction.objects.create(
                bank_account=self.bank_account,
                date=timezone.now().date(),
                description=f"Reconciled transaction {i}",
                amount=100.00,
                status=BankTransaction.TransactionStatus.RECONCILED,
            )
        
        result = evaluate_period_close_readiness(self.business)
        
        # Should NOT block because count < 5 AND ratio < 2%
        self.assertEqual(result["status"], "ready")
    
    def test_unreconciled_at_threshold_blocks_close(self):
        """At least 5 unreconciled bank transactions should block period close."""
        # Create 5 unreconciled - at the threshold
        for i in range(5):
            BankTransaction.objects.create(
                bank_account=self.bank_account,
                date=timezone.now().date(),
                description=f"Test transaction {i}",
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


class TestBankingCoverageSemantics(TestCase):
    """Tests for banking coverage status semantics (item 7)."""
    
    def setUp(self):
        self.user = User.objects.create_user(username="coveragesemuser", password="test123")
        self.business = Business.objects.create(
            name="Coverage Sem Test Co",
            currency="USD",
            owner_user=self.user,
        )
        defaults = ensure_default_accounts(self.business)
        self.bank_account = BankAccount.objects.create(
            business=self.business,
            name="Operating",
            account=defaults["cash"],
        )
    
    def test_new_status_is_not_covered(self):
        """NEW status should NOT be counted as covered."""
        BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=timezone.now().date(),
            description="New transaction",
            amount=100.00,
            status=BankTransaction.TransactionStatus.NEW,
        )
        
        coverage = build_companion_coverage(self.business)
        
        self.assertEqual(coverage["banking"]["total_items"], 1)
        self.assertEqual(coverage["banking"]["covered_items"], 0)
        self.assertEqual(coverage["banking"]["coverage_percent"], 0.0)
    
    def test_matched_single_status_is_covered(self):
        """MATCHED_SINGLE status should be counted as covered."""
        BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=timezone.now().date(),
            description="Matched single transaction",
            amount=100.00,
            status=BankTransaction.TransactionStatus.MATCHED_SINGLE,
        )
        
        coverage = build_companion_coverage(self.business)
        
        self.assertEqual(coverage["banking"]["covered_items"], 1)
        self.assertEqual(coverage["banking"]["coverage_percent"], 100.0)
    
    def test_matched_status_is_covered(self):
        """MATCHED status should be counted as covered."""
        BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=timezone.now().date(),
            description="Matched transaction",
            amount=100.00,
            status=BankTransaction.TransactionStatus.MATCHED,
        )
        
        coverage = build_companion_coverage(self.business)
        
        self.assertEqual(coverage["banking"]["covered_items"], 1)
    
    def test_reconciled_status_is_covered(self):
        """RECONCILED status should be counted as covered."""
        BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=timezone.now().date(),
            description="Reconciled transaction",
            amount=100.00,
            status=BankTransaction.TransactionStatus.RECONCILED,
        )
        
        coverage = build_companion_coverage(self.business)
        
        self.assertEqual(coverage["banking"]["covered_items"], 1)
    
    def test_excluded_status_is_covered(self):
        """EXCLUDED status should be counted as covered (intentional exclusion is a decision)."""
        BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=timezone.now().date(),
            description="Excluded transaction",
            amount=100.00,
            status=BankTransaction.TransactionStatus.EXCLUDED,
        )
        
        coverage = build_companion_coverage(self.business)
        
        self.assertEqual(coverage["banking"]["covered_items"], 1)


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
