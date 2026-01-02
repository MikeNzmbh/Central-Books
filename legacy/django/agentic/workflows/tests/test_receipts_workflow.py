"""
Tests for Receipts Workflow

Covers:
- Workflow builds and runs successfully
- Each step populates expected context keys
- WorkflowRunResult serialization
"""

import pytest
from decimal import Decimal

from agentic.workflows.steps.receipts_pipeline import (
    build_receipts_workflow,
    RawDocument,
    ExtractedDocument,
    NormalizedTransaction,
    ingest_step,
    extract_step,
    normalize_step,
    generate_entries_step,
)
from agentic.workflows.graph import WorkflowGraph, WorkflowRunResult


class TestReceiptsWorkflowBasic:
    """Basic workflow execution tests."""

    def test_workflow_builds_successfully(self):
        """Workflow can be built without errors."""
        wf = build_receipts_workflow()
        assert isinstance(wf, WorkflowGraph)
        assert wf.name == "receipts_to_journal_entries"
        assert wf.step_count == 4

    def test_workflow_runs_with_sample_data(self):
        """Workflow runs successfully with sample data."""
        wf = build_receipts_workflow()
        context = {
            "uploaded_files": [
                {"filename": "test1.pdf", "content": "x"},
                {"filename": "test2.pdf", "content": "y"},
            ]
        }

        result = wf.run(context)

        assert result.status in ("success", "partial")
        assert len(result.steps) == 4
        assert "journal_entries" in result.artifacts
        assert len(result.artifacts["journal_entries"]) == 2

    def test_workflow_runs_with_empty_input(self):
        """Workflow handles empty input gracefully."""
        wf = build_receipts_workflow()
        result = wf.run({"uploaded_files": []})

        assert result.status == "success"
        assert len(result.artifacts.get("journal_entries", [])) == 0

    def test_all_steps_succeed(self):
        """All workflow steps complete successfully."""
        wf = build_receipts_workflow()
        result = wf.run({
            "uploaded_files": [{"filename": "office_receipt.pdf"}]
        })

        for step in result.steps:
            assert step.status == "success", f"Step {step.step_name} failed"


class TestWorkflowSteps:
    """Tests for individual workflow steps."""

    def test_ingest_step_creates_documents(self):
        """Ingest step creates RawDocument objects."""
        context = {
            "uploaded_files": [
                {"filename": "receipt1.pdf", "content": "data1"},
                {"filename": "receipt2.pdf", "content": "data2"},
            ]
        }

        ingest_step(context)

        assert "documents" in context
        assert len(context["documents"]) == 2
        assert all(isinstance(d, RawDocument) for d in context["documents"])
        assert context["documents"][0].filename == "receipt1.pdf"

    def test_extract_step_creates_extracted_documents(self):
        """Extract step creates ExtractedDocument objects."""
        context = {
            "documents": [
                RawDocument(id="doc-1", filename="office_test.pdf"),
                RawDocument(id="doc-2", filename="coffee_test.pdf"),
            ]
        }

        extract_step(context)

        assert "extracted_documents" in context
        assert len(context["extracted_documents"]) == 2
        assert all(isinstance(e, ExtractedDocument) for e in context["extracted_documents"])
        # Should use demo vendor mapping
        assert context["extracted_documents"][0].vendor_name == "Office Depot"
        assert context["extracted_documents"][1].vendor_name == "Starbucks"

    def test_normalize_step_creates_transactions(self):
        """Normalize step creates NormalizedTransaction objects."""
        context = {
            "extracted_documents": [
                ExtractedDocument(
                    id="ext-1",
                    raw_document_id="doc-1",
                    vendor_name="Test Vendor",
                    total_amount=Decimal("50.00"),
                    txn_date="2024-01-01",
                ),
            ]
        }

        normalize_step(context)

        assert "transactions" in context
        assert len(context["transactions"]) == 1
        txn = context["transactions"][0]
        assert isinstance(txn, NormalizedTransaction)
        assert "Test Vendor" in txn.description
        assert txn.amount == Decimal("50.00")

    def test_generate_entries_step_creates_balanced_entries(self):
        """Generate entries step creates balanced journal entries."""
        context = {
            "transactions": [
                NormalizedTransaction(
                    id="txn-1",
                    description="Test Transaction",
                    amount=Decimal("100.00"),
                    date="2024-01-01",
                    category_code="6000",
                ),
            ]
        }

        generate_entries_step(context)

        assert "journal_entries" in context
        assert len(context["journal_entries"]) == 1

        entry = context["journal_entries"][0]
        assert entry.is_balanced
        assert len(entry.lines) == 2
        assert entry.total_debits == entry.total_credits


class TestWorkflowRunResult:
    """Tests for WorkflowRunResult serialization."""

    def test_result_serializable(self):
        """WorkflowRunResult can be serialized to dict."""
        wf = build_receipts_workflow()
        result = wf.run({"uploaded_files": []})

        d = result.model_dump()

        assert d["workflow_name"] == "receipts_to_journal_entries"
        assert "status" in d
        assert "started_at" in d
        assert "finished_at" in d
        assert "steps" in d
        assert "artifacts" in d

    def test_result_has_duration(self):
        """WorkflowRunResult includes duration."""
        wf = build_receipts_workflow()
        result = wf.run({
            "uploaded_files": [{"filename": "test.pdf"}]
        })

        assert result.duration_ms >= 0
        for step in result.steps:
            assert step.duration_ms >= 0


class TestDemoVendorMapping:
    """Tests for deterministic demo vendor extraction."""

    def test_office_keyword_maps_to_office_depot(self):
        """'office' keyword maps to Office Depot."""
        context = {"documents": [RawDocument(id="doc-1", filename="office_supplies.pdf")]}
        extract_step(context)
        assert context["extracted_documents"][0].vendor_name == "Office Depot"
        assert context["extracted_documents"][0].category_code == "6100"

    def test_coffee_keyword_maps_to_starbucks(self):
        """'coffee' keyword maps to Starbucks."""
        context = {"documents": [RawDocument(id="doc-1", filename="coffee_meeting.pdf")]}
        extract_step(context)
        assert context["extracted_documents"][0].vendor_name == "Starbucks"

    def test_software_keyword_maps_to_github(self):
        """'software' keyword maps to GitHub."""
        context = {"documents": [RawDocument(id="doc-1", filename="software_license.pdf")]}
        extract_step(context)
        assert context["extracted_documents"][0].vendor_name == "GitHub"

    def test_unknown_keyword_uses_default(self):
        """Unknown keywords use default vendor."""
        context = {"documents": [RawDocument(id="doc-1", filename="random_receipt.pdf")]}
        extract_step(context)
        assert context["extracted_documents"][0].vendor_name == "Demo Vendor"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
