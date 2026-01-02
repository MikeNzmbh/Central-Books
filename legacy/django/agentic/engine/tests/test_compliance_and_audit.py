"""
Tests for Compliance and Audit Engines

Covers:
- Compliance checks (currency mismatch, unusual amount, unbalanced entry)
- Audit checks (unusual scale, suspense accounts)
- Integration with receipts workflow
"""

import pytest
from decimal import Decimal

from agentic.engine.compliance import (
    run_basic_compliance_checks,
    ComplianceIssue,
    ComplianceCheckResult,
)
from agentic.engine.audit import (
    run_basic_audit_checks,
    AuditFinding,
    AuditReport,
)


# =============================================================================
# MOCK DATA MODELS FOR TESTING
# =============================================================================


class MockTransaction:
    """Mock transaction for testing."""

    def __init__(self, id: str, amount: float, currency: str = "USD"):
        self.id = id
        self.amount = Decimal(str(amount))
        self.currency = currency

    def model_dump(self):
        return {
            "id": self.id,
            "amount": str(self.amount),
            "currency": self.currency,
        }


class MockJournalLine:
    """Mock journal line for testing."""

    def __init__(self, account_code: str, account_name: str, side: str, amount: float):
        self.account_code = account_code
        self.account_name = account_name
        self.side = side
        self.amount = Decimal(str(amount))


class MockJournalEntry:
    """Mock journal entry for testing."""

    def __init__(self, entry_id: str, description: str, lines: list, is_balanced: bool = True):
        self.entry_id = entry_id
        self.description = description
        self.lines = lines
        self.is_balanced = is_balanced


# =============================================================================
# COMPLIANCE ENGINE TESTS
# =============================================================================


class TestComplianceEngine:
    """Tests for the compliance engine."""

    def test_no_issues_for_valid_transactions(self):
        """Valid transactions should pass compliance checks."""
        txns = [
            MockTransaction(id="txn-1", amount=100.0, currency="USD"),
            MockTransaction(id="txn-2", amount=50.0, currency="USD"),
        ]
        entries = [
            MockJournalEntry(
                entry_id="je-1",
                description="Test entry",
                lines=[],
                is_balanced=True,
            )
        ]

        result = run_basic_compliance_checks(txns, entries)

        assert result.is_compliant
        assert len(result.issues) == 0

    def test_flags_currency_mismatch(self):
        """Currency mismatch should be flagged."""
        txns = [
            MockTransaction(id="txn-1", amount=100.0, currency="EUR"),
        ]

        result = run_basic_compliance_checks(txns, [], expected_currency="USD")

        assert len(result.issues) == 1
        assert result.issues[0].code == "CURRENCY_MISMATCH"
        assert result.issues[0].severity == "low"

    def test_flags_unusual_amount(self):
        """Unusually large amounts should be flagged."""
        txns = [
            MockTransaction(id="txn-1", amount=200000.0, currency="USD"),
        ]

        result = run_basic_compliance_checks(txns, [], max_reasonable_amount=100000.0)

        assert len(result.issues) == 1
        assert result.issues[0].code == "UNUSUAL_AMOUNT"
        assert result.issues[0].severity == "medium"

    def test_flags_unbalanced_entry(self):
        """Unbalanced journal entries should be flagged."""
        entries = [
            MockJournalEntry(
                entry_id="je-1",
                description="Unbalanced test",
                lines=[],
                is_balanced=False,
            )
        ]

        result = run_basic_compliance_checks([], entries)

        assert len(result.issues) == 1
        assert result.issues[0].code == "UNBALANCED_ENTRY"
        assert result.issues[0].severity == "critical"

    def test_multiple_issues(self):
        """Multiple issues should all be detected."""
        txns = [
            MockTransaction(id="txn-1", amount=100.0, currency="USD"),
            MockTransaction(id="txn-2", amount=200000.0, currency="EUR"),
        ]
        entries = [
            MockJournalEntry("je-1", "Test", [], is_balanced=False),
        ]

        result = run_basic_compliance_checks(txns, entries)

        codes = {i.code for i in result.issues}
        assert "CURRENCY_MISMATCH" in codes
        assert "UNUSUAL_AMOUNT" in codes
        assert "UNBALANCED_ENTRY" in codes
        assert not result.is_compliant


# =============================================================================
# AUDIT ENGINE TESTS
# =============================================================================


class TestAuditEngine:
    """Tests for the audit engine."""

    def test_no_findings_for_normal_transactions(self):
        """Normal transactions should have no audit findings."""
        txns = [
            MockTransaction(id="txn-1", amount=100.0),
            MockTransaction(id="txn-2", amount=120.0),
            MockTransaction(id="txn-3", amount=80.0),
        ]
        entries = [
            MockJournalEntry(
                "je-1", "Test",
                [MockJournalLine("6000", "Office Supplies", "debit", 100)],
            )
        ]

        report = run_basic_audit_checks(txns, entries)

        assert report.risk_level == "low"
        assert len(report.findings) == 0

    def test_flags_unusual_scale(self):
        """Transactions with unusual scale should be flagged."""
        txns = [
            MockTransaction(id="txn-1", amount=100.0),
            MockTransaction(id="txn-2", amount=100.0),
            MockTransaction(id="txn-3", amount=1000.0),  # 10x average = unusual
        ]

        report = run_basic_audit_checks(txns, [])

        assert len(report.findings) == 1
        assert report.findings[0].code == "UNUSUAL_SCALE"
        assert report.risk_level == "medium"

    def test_flags_suspense_account(self):
        """Entries using suspense accounts should be flagged."""
        entries = [
            MockJournalEntry(
                "je-1", "Test",
                [MockJournalLine("9999", "Suspense Clearing", "debit", 100)],
            )
        ]

        report = run_basic_audit_checks([], entries)

        assert len(report.findings) == 1
        assert report.findings[0].code == "SUSPENSE_ACCOUNT"
        assert report.risk_level == "high"

    def test_flags_uncategorized_account(self):
        """Entries using uncategorized accounts should be flagged."""
        entries = [
            MockJournalEntry(
                "je-1", "Test",
                [MockJournalLine("0000", "Uncategorized Expense", "debit", 100)],
            )
        ]

        report = run_basic_audit_checks([], entries)

        assert len(report.findings) == 1
        assert report.findings[0].code == "SUSPENSE_ACCOUNT"

    def test_multiple_findings(self):
        """Multiple audit findings should all be detected."""
        txns = [
            MockTransaction(id="txn-1", amount=100.0),
            MockTransaction(id="txn-2", amount=1000.0),  # Unusual scale
        ]
        entries = [
            MockJournalEntry(
                "je-1", "Test",
                [MockJournalLine("9999", "Suspense", "debit", 100)],
            )
        ]

        report = run_basic_audit_checks(txns, entries)

        codes = {f.code for f in report.findings}
        assert "UNUSUAL_SCALE" in codes
        assert "SUSPENSE_ACCOUNT" in codes
        assert report.risk_level == "high"


# =============================================================================
# WORKFLOW INTEGRATION TESTS
# =============================================================================


class TestWorkflowIntegration:
    """Tests for compliance and audit integration with workflow."""

    def test_receipts_workflow_includes_compliance_and_audit(self):
        """Workflow should include compliance and audit artifacts."""
        from agentic.workflows.steps.receipts_pipeline import build_receipts_workflow

        wf = build_receipts_workflow()
        result = wf.run({"uploaded_files": [{"filename": "test.pdf", "content": "x"}]})

        assert "compliance_result" in result.artifacts
        assert "audit_report" in result.artifacts

    def test_workflow_has_six_steps(self):
        """Workflow should have all 6 steps."""
        from agentic.workflows.steps.receipts_pipeline import build_receipts_workflow

        wf = build_receipts_workflow()

        assert wf.step_count == 6
        step_names = wf.get_step_names()
        assert "ingest" in step_names
        assert "extract" in step_names
        assert "normalize" in step_names
        assert "generate_entries" in step_names
        assert "compliance" in step_names
        assert "audit" in step_names

    def test_all_steps_succeed(self):
        """All workflow steps should succeed."""
        from agentic.workflows.steps.receipts_pipeline import build_receipts_workflow

        wf = build_receipts_workflow()
        result = wf.run({
            "uploaded_files": [{"filename": "office_test.pdf"}]
        })

        for step in result.steps:
            assert step.status == "success", f"Step {step.step_name} failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
