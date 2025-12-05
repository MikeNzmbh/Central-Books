"""
Receipts Pipeline - End-to-End Workflow with Compliance & Audit

Pipeline: uploaded files → RawDocument → ExtractedDocument → NormalizedTransaction 
         → JournalEntry → ComplianceCheck → AuditReport

This is the first Residency-style demo workflow using deterministic
mock data (no real OCR or LLM calls).
"""

from typing import Any, Dict, List
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date
from uuid import uuid4

from agentic.workflows.graph import WorkflowGraph
from agentic.engine.entry_generation.double_entry_generator import (
    generate_journal_entries_for_transactions,
)
from agentic.engine.compliance import run_basic_compliance_checks
from agentic.engine.audit import run_basic_audit_checks


# =============================================================================
# SIMPLE DATA MODELS FOR PIPELINE
# =============================================================================


@dataclass
class RawDocument:
    """A raw uploaded document."""

    id: str
    filename: str
    content: str = ""
    source: str = "upload"
    mime_type: str = "application/pdf"

    def model_dump(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "content": self.content,
            "source": self.source,
            "mime_type": self.mime_type,
        }


@dataclass
class ExtractedDocument:
    """Extracted data from a document."""

    id: str
    raw_document_id: str
    vendor_name: str = "Unknown Vendor"
    total_amount: Decimal = Decimal("0")
    currency: str = "USD"
    txn_date: str = ""
    category_code: str = "6000"
    line_items: List[dict] = field(default_factory=list)

    def model_dump(self) -> dict:
        return {
            "id": self.id,
            "raw_document_id": self.raw_document_id,
            "vendor_name": self.vendor_name,
            "total_amount": str(self.total_amount),
            "currency": self.currency,
            "txn_date": self.txn_date,
            "category_code": self.category_code,
            "line_items": self.line_items,
        }


@dataclass
class NormalizedTransaction:
    """A normalized transaction ready for journal entry generation."""

    id: str
    description: str
    amount: Decimal
    currency: str = "USD"
    date: str = ""
    category_code: str = "6000"
    source_document_id: str = ""

    def model_dump(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "amount": str(self.amount),
            "currency": self.currency,
            "date": self.date,
            "category_code": self.category_code,
            "source_document_id": self.source_document_id,
        }


# =============================================================================
# DEMO DATA GENERATORS
# =============================================================================

# Vendor/amount mapping for deterministic demo
DEMO_VENDORS = {
    "office": ("Office Depot", Decimal("89.99"), "6100"),
    "coffee": ("Starbucks", Decimal("15.50"), "6200"),
    "software": ("GitHub", Decimal("49.00"), "6300"),
    "travel": ("Delta Airlines", Decimal("450.00"), "6200"),
    "supplies": ("Amazon", Decimal("125.75"), "6100"),
}


def _get_demo_extraction(filename: str, doc_id: str) -> dict:
    """Get deterministic demo extraction based on filename."""
    filename_lower = filename.lower()

    for keyword, (vendor, amount, category) in DEMO_VENDORS.items():
        if keyword in filename_lower:
            return {
                "vendor_name": vendor,
                "total_amount": amount,
                "category_code": category,
            }

    # Default fallback
    return {
        "vendor_name": "Demo Vendor",
        "total_amount": Decimal("100.00"),
        "category_code": "6000",
    }


# =============================================================================
# WORKFLOW STEPS
# =============================================================================


def ingest_step(context: Dict[str, Any]) -> None:
    """
    Convert uploaded files to RawDocument objects.

    Input: context["uploaded_files"]: list of {"filename": str, "content": str}
    Output: context["documents"]: list of RawDocument
    """
    uploaded = context.get("uploaded_files", [])
    docs: List[RawDocument] = []

    for idx, f in enumerate(uploaded):
        if isinstance(f, dict):
            filename = f.get("filename", f"receipt-{idx + 1}.pdf")
            content = f.get("content", "")
        else:
            filename = getattr(f, "name", f"receipt-{idx + 1}.pdf")
            content = ""

        docs.append(
            RawDocument(
                id=f"doc-{idx + 1}",
                filename=filename,
                content=content,
                source="upload",
            )
        )

    context["documents"] = docs


def extract_step(context: Dict[str, Any]) -> None:
    """
    Extract structured data from documents.

    This is a deterministic mock for demo purposes.
    Real implementation would use OCR + LLM.

    Input: context["documents"]: list of RawDocument
    Output: context["extracted_documents"]: list of ExtractedDocument
    """
    docs: List[RawDocument] = context.get("documents", [])
    extracted: List[ExtractedDocument] = []

    today = str(date.today())

    for doc in docs:
        demo_data = _get_demo_extraction(doc.filename, doc.id)

        extracted.append(
            ExtractedDocument(
                id=doc.id.replace("doc", "ext"),
                raw_document_id=doc.id,
                vendor_name=demo_data["vendor_name"],
                total_amount=demo_data["total_amount"],
                currency="USD",
                txn_date=today,
                category_code=demo_data["category_code"],
            )
        )

    context["extracted_documents"] = extracted


def normalize_step(context: Dict[str, Any]) -> None:
    """
    Normalize extracted documents to transactions.

    Input: context["extracted_documents"]: list of ExtractedDocument
    Output: context["transactions"]: list of NormalizedTransaction
    """
    extracted: List[ExtractedDocument] = context.get("extracted_documents", [])
    txns: List[NormalizedTransaction] = []

    for ext in extracted:
        txns.append(
            NormalizedTransaction(
                id=f"txn-{ext.id}",
                description=f"Receipt from {ext.vendor_name}",
                amount=ext.total_amount,
                currency=ext.currency,
                date=ext.txn_date,
                category_code=ext.category_code,
                source_document_id=ext.raw_document_id,
            )
        )

    context["transactions"] = txns


def generate_entries_step(context: Dict[str, Any]) -> None:
    """
    Generate journal entry proposals from transactions.

    Uses the double_entry_generator module for balanced entries.

    Input: context["transactions"]: list of NormalizedTransaction
    Output: context["journal_entries"]: list of GeneratedEntry
    """
    txns: List[NormalizedTransaction] = context.get("transactions", [])

    entries = generate_journal_entries_for_transactions(txns)

    context["journal_entries"] = entries


def compliance_step(context: Dict[str, Any]) -> None:
    """
    Run compliance checks on transactions and journal entries.

    Input: context["transactions"], context["journal_entries"]
    Output: context["compliance_result"]: ComplianceCheckResult
    """
    txns = context.get("transactions", [])
    entries = context.get("journal_entries", [])

    result = run_basic_compliance_checks(txns, entries)
    context["compliance_result"] = result


def audit_step(context: Dict[str, Any]) -> None:
    """
    Run audit checks on transactions and journal entries.

    Input: context["transactions"], context["journal_entries"]
    Output: context["audit_report"]: AuditReport
    """
    txns = context.get("transactions", [])
    entries = context.get("journal_entries", [])

    report = run_basic_audit_checks(txns, entries)
    context["audit_report"] = report


# =============================================================================
# WORKFLOW BUILDER
# =============================================================================


def build_receipts_workflow() -> WorkflowGraph:
    """
    Build the complete receipts-to-journal-entries workflow with compliance & audit.

    Pipeline:
    1. ingest: uploaded_files → documents (RawDocument[])
    2. extract: documents → extracted_documents (ExtractedDocument[])
    3. normalize: extracted_documents → transactions (NormalizedTransaction[])
    4. generate_entries: transactions → journal_entries (GeneratedEntry[])
    5. compliance: Run compliance checks
    6. audit: Run audit checks

    Returns:
        Configured WorkflowGraph ready to run.
    """
    wf = WorkflowGraph("receipts_to_journal_entries")

    # Register steps
    wf.add_step("ingest", ingest_step)
    wf.add_step("extract", extract_step)
    wf.add_step("normalize", normalize_step)
    wf.add_step("generate_entries", generate_entries_step)
    wf.add_step("compliance", compliance_step)
    wf.add_step("audit", audit_step)

    # Define dependencies
    wf.add_edge("ingest", "extract")
    wf.add_edge("extract", "normalize")
    wf.add_edge("normalize", "generate_entries")
    wf.add_edge("generate_entries", "compliance")
    wf.add_edge("compliance", "audit")

    return wf
