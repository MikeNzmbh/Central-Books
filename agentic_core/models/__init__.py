"""
Agentic Core Data Models

This subpackage contains all Pydantic models used throughout the agentic
accounting system. Models are organized by domain:

- base: Core tracing and metadata models (AgentTrace, LLMCallMetadata)
- documents: Document ingestion models (RawDocument, ExtractedDocument)
- ledger: Accounting transaction models (NormalizedTransaction, JournalEntryProposal)
- compliance: Compliance checking models (ComplianceIssue, ComplianceCheckResult)
- audit: Audit trail models (AuditFinding, AuditReport)
- reporting: Financial reporting models (PlAccountRow, PlReport)
"""

from agentic_core.models.base import AgentTrace, LLMCallMetadata
from agentic_core.models.documents import (
    RawDocument,
    ExtractedDocument,
    ExtractedLineItem,
)
from agentic_core.models.ledger import (
    NormalizedTransaction,
    JournalLineProposal,
    JournalEntryProposal,
)
from agentic_core.models.compliance import ComplianceIssue, ComplianceCheckResult
from agentic_core.models.audit import AuditFinding, AuditReport
from agentic_core.models.reporting import PlAccountRow, PlReport

__all__ = [
    # Base
    "AgentTrace",
    "LLMCallMetadata",
    # Documents
    "RawDocument",
    "ExtractedDocument",
    "ExtractedLineItem",
    # Ledger
    "NormalizedTransaction",
    "JournalLineProposal",
    "JournalEntryProposal",
    # Compliance
    "ComplianceIssue",
    "ComplianceCheckResult",
    # Audit
    "AuditFinding",
    "AuditReport",
    # Reporting
    "PlAccountRow",
    "PlReport",
]
