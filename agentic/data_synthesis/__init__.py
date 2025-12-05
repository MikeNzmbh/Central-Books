"""
Data Synthesis Package - Synthetic Scenario Generation

Provides:
- SyntheticScenario: Complete test scenario with documents and ground truth
- Generator functions for receipts, invoices, bank statements
- CLI for generating sample data
"""

from .schemas import (
    SyntheticScenario,
    SyntheticDocument,
    GroundTruthTransaction,
    ExpectedJournalEntry,
    ExpectedComplianceResult,
    ExpectedAuditFinding,
)
from .generator import (
    generate_scenario_monthly_bookkeeping,
    generate_receipt_docs_for_scenario,
    generate_invoice_docs_for_scenario,
    generate_bank_statement_docs_for_scenario,
)

__all__ = [
    "SyntheticScenario",
    "SyntheticDocument",
    "GroundTruthTransaction",
    "ExpectedJournalEntry",
    "ExpectedComplianceResult",
    "ExpectedAuditFinding",
    "generate_scenario_monthly_bookkeeping",
    "generate_receipt_docs_for_scenario",
    "generate_invoice_docs_for_scenario",
    "generate_bank_statement_docs_for_scenario",
]
