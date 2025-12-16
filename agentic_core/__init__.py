"""
Agentic Accounting Core - A subsystem for AI-powered automated accounting.

This package provides the foundational architecture for building an agentic
accounting operating system, including:

- Pydantic data models for documents, ledger entries, compliance, and audit
- Agent base classes with tracing and LLM call logging
- Specialized accounting agents with deterministic double-entry logic
- Workflow orchestration for end-to-end processing pipelines

This is a parallel subsystem that does not integrate with Django models yet.
It is designed to be extended with additional agents and workflows in future phases.
"""

__version__ = "0.1.0"
__author__ = "Clover Books / CloverBooks Team"

# Re-export key classes for convenient imports
from agentic_core.models import (
    AgentTrace,
    LLMCallMetadata,
    RawDocument,
    ExtractedDocument,
    ExtractedLineItem,
    NormalizedTransaction,
    JournalLineProposal,
    JournalEntryProposal,
    ComplianceIssue,
    ComplianceCheckResult,
    AuditFinding,
    AuditReport,
    PlAccountRow,
    PlReport,
)
from agentic_core.agents import BaseAgent, AccountingAgent
from agentic_core.workflows import ReceiptsWorkflow

__all__ = [
    # Version
    "__version__",
    # Models
    "AgentTrace",
    "LLMCallMetadata",
    "RawDocument",
    "ExtractedDocument",
    "ExtractedLineItem",
    "NormalizedTransaction",
    "JournalLineProposal",
    "JournalEntryProposal",
    "ComplianceIssue",
    "ComplianceCheckResult",
    "AuditFinding",
    "AuditReport",
    "PlAccountRow",
    "PlReport",
    # Agents
    "BaseAgent",
    "AccountingAgent",
    # Workflows
    "ReceiptsWorkflow",
]
