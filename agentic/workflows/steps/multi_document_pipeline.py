"""
Multi-Document Processing Pipeline - Unified Workflow

This workflow handles mixed document uploads by:
1. Detecting document types (receipt, invoice, bank statement)
2. Routing to appropriate sub-pipelines
3. Aggregating results across document types
4. Running unified compliance and audit checks

Pipeline: documents → detect_type → route → process → aggregate → compliance → audit
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from enum import Enum

from agentic.workflows.graph import WorkflowGraph
from agentic.workflows.steps.receipts_pipeline import build_receipts_workflow
from agentic.workflows.steps.invoice_pipeline import build_invoice_workflow
from agentic.workflows.steps.bank_statement_pipeline import build_bank_statement_workflow
from agentic.engine.compliance import run_basic_compliance_checks
from agentic.engine.audit import run_basic_audit_checks


# =============================================================================
# DOCUMENT TYPE DETECTION
# =============================================================================


class DocumentType(str, Enum):
    """Supported document types."""
    RECEIPT = "receipt"
    INVOICE = "invoice"
    BANK_STATEMENT = "bank_statement"
    UNKNOWN = "unknown"


@dataclass
class ClassifiedDocument:
    """Document with detected type."""
    
    id: str
    filename: str
    content: str
    document_type: DocumentType
    confidence: float
    
    def model_dump(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "content": self.content,
            "document_type": self.document_type.value,
            "confidence": self.confidence,
        }


@dataclass
class AggregatedResults:
    """Combined results from multiple pipelines."""
    
    total_documents: int = 0
    receipts_processed: int = 0
    invoices_processed: int = 0
    statements_processed: int = 0
    unknown_skipped: int = 0
    
    journal_entries: List[dict] = field(default_factory=list)
    transactions: List[dict] = field(default_factory=list)
    reconciliation_reports: List[dict] = field(default_factory=list)
    payment_matches: List[dict] = field(default_factory=list)
    
    def model_dump(self) -> dict:
        return {
            "total_documents": self.total_documents,
            "receipts_processed": self.receipts_processed,
            "invoices_processed": self.invoices_processed,
            "statements_processed": self.statements_processed,
            "unknown_skipped": self.unknown_skipped,
            "journal_entries": self.journal_entries,
            "transactions": self.transactions,
            "reconciliation_reports": self.reconciliation_reports,
            "payment_matches": self.payment_matches,
        }


# =============================================================================
# TYPE DETECTION LOGIC
# =============================================================================


# Keywords for document type detection
RECEIPT_KEYWORDS = [
    "receipt", "rcpt", "pos", "sale", "purchase", "store",
    "coffee", "lunch", "dinner", "uber", "lyft", "amazon",
]

INVOICE_KEYWORDS = [
    "invoice", "inv", "bill", "due_date", "payment_terms",
    "net_30", "acme", "vendor", "supplier", "po_number",
]

STATEMENT_KEYWORDS = [
    "statement", "bank", "account", "balance", "transaction",
    "checking", "savings", "deposit", "withdrawal", "csv",
]


def _detect_document_type(filename: str, content: str) -> tuple:
    """
    Detect document type from filename and content.
    
    Returns: (DocumentType, confidence)
    """
    text = f"{filename} {content}".lower()
    
    # Count keyword matches
    receipt_score = sum(1 for kw in RECEIPT_KEYWORDS if kw in text)
    invoice_score = sum(1 for kw in INVOICE_KEYWORDS if kw in text)
    statement_score = sum(1 for kw in STATEMENT_KEYWORDS if kw in text)
    
    # File extension hints
    if filename.lower().endswith(".csv"):
        statement_score += 3
    elif "invoice" in filename.lower():
        invoice_score += 3
    elif "receipt" in filename.lower():
        receipt_score += 3
    elif "statement" in filename.lower():
        statement_score += 3
    
    # Determine winner
    scores = {
        DocumentType.RECEIPT: receipt_score,
        DocumentType.INVOICE: invoice_score,
        DocumentType.BANK_STATEMENT: statement_score,
    }
    
    max_score = max(scores.values())
    if max_score == 0:
        return DocumentType.UNKNOWN, 0.0
    
    # Get type with highest score
    doc_type = max(scores, key=scores.get)
    
    # Calculate confidence (normalized)
    total_score = sum(scores.values())
    confidence = max_score / total_score if total_score > 0 else 0.0
    
    return doc_type, min(confidence, 1.0)


# =============================================================================
# WORKFLOW STEPS
# =============================================================================


def ingest_multi_step(context: Dict[str, Any]) -> None:
    """
    Ingest uploaded files for multi-document processing.
    
    Input: context["uploaded_files"]
    Output: context["raw_documents"]
    """
    uploaded = context.get("uploaded_files", [])
    docs = []
    
    for idx, f in enumerate(uploaded):
        if isinstance(f, dict):
            filename = f.get("filename", f"document-{idx + 1}.pdf")
            content = f.get("content", "")
        else:
            filename = getattr(f, "name", f"document-{idx + 1}.pdf")
            content = ""
        
        docs.append({
            "id": f"multi-doc-{idx + 1}",
            "filename": filename,
            "content": content,
        })
    
    context["raw_documents"] = docs


def detect_types_step(context: Dict[str, Any]) -> None:
    """
    Detect document types for routing.
    
    Input: context["raw_documents"]
    Output: context["classified_documents"]
    """
    docs = context.get("raw_documents", [])
    classified = []
    
    for doc in docs:
        doc_type, confidence = _detect_document_type(
            doc["filename"],
            doc["content"],
        )
        
        classified.append(ClassifiedDocument(
            id=doc["id"],
            filename=doc["filename"],
            content=doc["content"],
            document_type=doc_type,
            confidence=confidence,
        ))
    
    context["classified_documents"] = classified


def route_documents_step(context: Dict[str, Any]) -> None:
    """
    Route documents to appropriate pipelines.
    
    Input: context["classified_documents"]
    Output: context["routed_documents"] (dict by type)
    """
    classified = context.get("classified_documents", [])
    
    routed = {
        DocumentType.RECEIPT: [],
        DocumentType.INVOICE: [],
        DocumentType.BANK_STATEMENT: [],
        DocumentType.UNKNOWN: [],
    }
    
    for doc in classified:
        routed[doc.document_type].append({
            "filename": doc.filename,
            "content": doc.content,
        })
    
    context["routed_documents"] = routed


def process_receipts_step(context: Dict[str, Any]) -> None:
    """
    Process receipt documents through receipts pipeline.
    
    Input: context["routed_documents"][RECEIPT]
    Output: context["receipt_results"]
    """
    routed = context.get("routed_documents", {})
    receipt_docs = routed.get(DocumentType.RECEIPT, [])
    
    if not receipt_docs:
        context["receipt_results"] = None
        return
    
    # Run receipts workflow
    wf = build_receipts_workflow()
    result = wf.run({"uploaded_files": receipt_docs})
    
    context["receipt_results"] = {
        "status": result.status,
        "steps": [s.model_dump() for s in result.steps],
        "artifacts": result.artifacts,
    }


def process_invoices_step(context: Dict[str, Any]) -> None:
    """
    Process invoice documents through invoice pipeline.
    
    Input: context["routed_documents"][INVOICE]
    Output: context["invoice_results"]
    """
    routed = context.get("routed_documents", {})
    invoice_docs = routed.get(DocumentType.INVOICE, [])
    
    if not invoice_docs:
        context["invoice_results"] = None
        return
    
    # Run invoice workflow
    wf = build_invoice_workflow()
    result = wf.run({"uploaded_files": invoice_docs})
    
    context["invoice_results"] = {
        "status": result.status,
        "steps": [s.model_dump() for s in result.steps],
        "artifacts": result.artifacts,
    }


def process_statements_step(context: Dict[str, Any]) -> None:
    """
    Process bank statement documents through bank statement pipeline.
    
    Input: context["routed_documents"][BANK_STATEMENT]
    Output: context["statement_results"]
    """
    routed = context.get("routed_documents", {})
    statement_docs = routed.get(DocumentType.BANK_STATEMENT, [])
    
    if not statement_docs:
        context["statement_results"] = None
        return
    
    # Run bank statement workflow
    wf = build_bank_statement_workflow()
    result = wf.run({"uploaded_files": statement_docs})
    
    context["statement_results"] = {
        "status": result.status,
        "steps": [s.model_dump() for s in result.steps],
        "artifacts": result.artifacts,
    }


def aggregate_results_step(context: Dict[str, Any]) -> None:
    """
    Aggregate results from all sub-pipelines.
    
    Input: context["receipt_results"], context["invoice_results"], context["statement_results"]
    Output: context["aggregated_results"]
    """
    routed = context.get("routed_documents", {})
    receipt_res = context.get("receipt_results")
    invoice_res = context.get("invoice_results")
    statement_res = context.get("statement_results")
    
    aggregated = AggregatedResults()
    
    # Count documents
    aggregated.receipts_processed = len(routed.get(DocumentType.RECEIPT, []))
    aggregated.invoices_processed = len(routed.get(DocumentType.INVOICE, []))
    aggregated.statements_processed = len(routed.get(DocumentType.BANK_STATEMENT, []))
    aggregated.unknown_skipped = len(routed.get(DocumentType.UNKNOWN, []))
    aggregated.total_documents = (
        aggregated.receipts_processed +
        aggregated.invoices_processed +
        aggregated.statements_processed +
        aggregated.unknown_skipped
    )
    
    # Collect journal entries from all pipelines
    if receipt_res and "artifacts" in receipt_res:
        entries = receipt_res["artifacts"].get("journal_entries", [])
        for entry in entries:
            if hasattr(entry, "model_dump"):
                aggregated.journal_entries.append(entry.model_dump())
            elif isinstance(entry, dict):
                aggregated.journal_entries.append(entry)
    
    if invoice_res and "artifacts" in invoice_res:
        entries = invoice_res["artifacts"].get("journal_entries", [])
        for entry in entries:
            if hasattr(entry, "model_dump"):
                aggregated.journal_entries.append(entry.model_dump())
            elif isinstance(entry, dict):
                aggregated.journal_entries.append(entry)
        
        # Collect payment matches
        matches = invoice_res["artifacts"].get("payment_matches", [])
        for match in matches:
            if hasattr(match, "model_dump"):
                aggregated.payment_matches.append(match.model_dump())
            elif isinstance(match, dict):
                aggregated.payment_matches.append(match)
    
    if statement_res and "artifacts" in statement_res:
        entries = statement_res["artifacts"].get("journal_entries", [])
        for entry in entries:
            if hasattr(entry, "model_dump"):
                aggregated.journal_entries.append(entry.model_dump())
            elif isinstance(entry, dict):
                aggregated.journal_entries.append(entry)
        
        # Collect reconciliation reports
        reports = statement_res["artifacts"].get("reconciliation_reports", [])
        for report in reports:
            if hasattr(report, "model_dump"):
                aggregated.reconciliation_reports.append(report.model_dump())
            elif isinstance(report, dict):
                aggregated.reconciliation_reports.append(report)
    
    context["aggregated_results"] = aggregated


def multi_compliance_step(context: Dict[str, Any]) -> None:
    """
    Run unified compliance checks on aggregated results.
    
    Input: context["aggregated_results"]
    Output: context["compliance_result"]
    """
    aggregated = context.get("aggregated_results")
    
    if not aggregated:
        context["compliance_result"] = {"issues": [], "is_compliant": True}
        return
    
    # Run compliance on all journal entries
    result = run_basic_compliance_checks(
        aggregated.transactions,
        aggregated.journal_entries,
    )
    
    context["compliance_result"] = result


def multi_audit_step(context: Dict[str, Any]) -> None:
    """
    Run unified audit checks on aggregated results.
    
    Input: context["aggregated_results"]
    Output: context["audit_report"]
    """
    aggregated = context.get("aggregated_results")
    
    if not aggregated:
        context["audit_report"] = {"findings": [], "risk_level": "low"}
        return
    
    report = run_basic_audit_checks(
        aggregated.transactions,
        aggregated.journal_entries,
    )
    
    context["audit_report"] = report


# =============================================================================
# WORKFLOW BUILDER
# =============================================================================


def build_multi_document_workflow() -> WorkflowGraph:
    """
    Build the multi-document processing workflow.
    
    Pipeline:
    1. ingest: uploaded_files → raw_documents
    2. detect_types: raw_documents → classified_documents
    3. route: classified_documents → routed_documents
    4. process_receipts: (parallel) routed_documents → receipt_results
    5. process_invoices: (parallel) routed_documents → invoice_results
    6. process_statements: (parallel) routed_documents → statement_results
    7. aggregate: all results → aggregated_results
    8. compliance: Run compliance checks
    9. audit: Run audit checks
    
    Returns:
        Configured WorkflowGraph ready to run.
    """
    wf = WorkflowGraph("multi_document_processing")
    
    # Register steps
    wf.add_step("ingest", ingest_multi_step)
    wf.add_step("detect_types", detect_types_step)
    wf.add_step("route", route_documents_step)
    wf.add_step("process_receipts", process_receipts_step)
    wf.add_step("process_invoices", process_invoices_step)
    wf.add_step("process_statements", process_statements_step)
    wf.add_step("aggregate", aggregate_results_step)
    wf.add_step("compliance", multi_compliance_step)
    wf.add_step("audit", multi_audit_step)
    
    # Define dependencies
    wf.add_edge("ingest", "detect_types")
    wf.add_edge("detect_types", "route")
    wf.add_edge("route", "process_receipts")
    wf.add_edge("route", "process_invoices")
    wf.add_edge("route", "process_statements")
    wf.add_edge("process_receipts", "aggregate")
    wf.add_edge("process_invoices", "aggregate")
    wf.add_edge("process_statements", "aggregate")
    wf.add_edge("aggregate", "compliance")
    wf.add_edge("compliance", "audit")
    
    return wf
