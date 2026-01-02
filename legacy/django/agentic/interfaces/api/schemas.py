"""
API Schemas for Agentic System

Pydantic models for API request/response serialization.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# WORKFLOW API SCHEMAS
# =============================================================================


class WorkflowStepResult(BaseModel):
    """Result of a single workflow step."""

    name: str
    status: str  # "success" | "failed" | "skipped"
    duration_ms: float = 0.0
    error: Optional[str] = None


class ExtractedDocumentSchema(BaseModel):
    """Extracted document data."""

    id: str
    raw_document_id: str
    vendor_name: str
    total_amount: str
    currency: str
    txn_date: str
    category_code: str


class TransactionSchema(BaseModel):
    """Normalized transaction data."""

    id: str
    description: str
    amount: str
    currency: str
    date: str
    category_code: str


class JournalLineSchema(BaseModel):
    """Journal entry line."""

    account_code: str
    account_name: str
    side: str
    amount: str


class JournalEntrySchema(BaseModel):
    """Journal entry proposal."""

    entry_id: str
    date: str
    description: str
    lines: List[JournalLineSchema]
    is_balanced: bool
    total_debits: str
    total_credits: str


class ComplianceIssueSchema(BaseModel):
    """Compliance issue."""

    code: str
    message: str
    severity: str
    transaction_id: Optional[str] = None
    suggestion: Optional[str] = None


class ComplianceResultSchema(BaseModel):
    """Compliance check result."""

    issues: List[ComplianceIssueSchema] = Field(default_factory=list)
    is_compliant: bool = True


class AuditFindingSchema(BaseModel):
    """Audit finding."""

    code: str
    message: str
    severity: str
    transaction_id: Optional[str] = None
    journal_entry_id: Optional[str] = None
    suggestion: Optional[str] = None


class AuditReportSchema(BaseModel):
    """Audit report."""

    findings: List[AuditFindingSchema] = Field(default_factory=list)
    risk_level: str = "low"


class ReceiptsDemoResponse(BaseModel):
    """
    Complete response for the receipts demo endpoint.

    Contains all workflow artifacts including documents, transactions,
    journal entries, compliance results, and audit findings.
    """

    workflow_name: str
    status: str  # "success" | "partial" | "failed"
    duration_ms: float = 0.0
    steps: List[WorkflowStepResult] = Field(default_factory=list)

    # Core artifacts
    extracted_documents: List[Dict[str, Any]] = Field(default_factory=list)
    transactions: List[Dict[str, Any]] = Field(default_factory=list)
    journal_entries: List[Dict[str, Any]] = Field(default_factory=list)

    # Compliance & Audit
    compliance: Optional[Dict[str, Any]] = None
    audit: Optional[Dict[str, Any]] = None

    # Summary for Residency demo
    summary: Optional[str] = None
    notes: Optional[List[str]] = None

    class Config:
        extra = "allow"


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================


class DocumentInput(BaseModel):
    """Input document for processing."""

    filename: str
    content: str = ""


class ReceiptsDemoRequest(BaseModel):
    """Request body for receipts demo endpoint."""

    documents: List[DocumentInput]
