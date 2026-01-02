"""
Compliance Engine - Basic compliance checks for transactions and journal entries.

Provides deterministic compliance validation including:
- Currency mismatch detection
- Unusual amount flagging
- Journal entry balance verification
"""

from typing import List, Optional
from decimal import Decimal
from dataclasses import dataclass, field
from pydantic import BaseModel


# =============================================================================
# COMPLIANCE MODELS
# =============================================================================

ComplianceSeverity = str  # "info", "low", "medium", "high", "critical"


class ComplianceIssue(BaseModel):
    """A single compliance issue found during checks."""

    code: str  # e.g. "TAX_RATE_MISMATCH"
    message: str  # human-readable
    severity: str  # ComplianceSeverity
    transaction_id: Optional[str] = None
    suggestion: Optional[str] = None

    class Config:
        frozen = True


class ComplianceCheckResult(BaseModel):
    """Result of running compliance checks."""

    issues: List[ComplianceIssue] = []
    is_compliant: bool = True

    def model_dump(self) -> dict:
        return {
            "issues": [
                {
                    "code": i.code,
                    "message": i.message,
                    "severity": i.severity,
                    "transaction_id": i.transaction_id,
                    "suggestion": i.suggestion,
                }
                for i in self.issues
            ],
            "is_compliant": self.is_compliant,
        }


# =============================================================================
# COMPLIANCE ENGINE
# =============================================================================


def run_basic_compliance_checks(
    transactions: List,
    journal_entries: List,
    *,
    expected_currency: str = "USD",
    max_reasonable_amount: float = 100000.0,
) -> ComplianceCheckResult:
    """
    Run deterministic compliance checks on transactions and journal entries.

    Checks performed:
    - Currency mismatch vs expected_currency
    - Transaction amounts > max_reasonable_amount
    - Journal entries not balanced

    Args:
        transactions: List of NormalizedTransaction or dicts.
        journal_entries: List of JournalEntryProposal/GeneratedEntry or dicts.
        expected_currency: Expected currency code.
        max_reasonable_amount: Maximum reasonable transaction amount.

    Returns:
        ComplianceCheckResult with any issues found.
    """
    issues: List[ComplianceIssue] = []

    for txn in transactions:
        # Handle both object and dict access
        if hasattr(txn, "model_dump"):
            txn_data = txn.model_dump()
        elif hasattr(txn, "__dict__"):
            txn_data = {
                "id": getattr(txn, "id", "unknown"),
                "currency": getattr(txn, "currency", "USD"),
                "amount": getattr(txn, "amount", 0),
            }
        else:
            txn_data = txn

        txn_id = txn_data.get("id", "unknown")
        currency = txn_data.get("currency", "USD")
        amount = float(txn_data.get("amount", 0))

        # Check currency mismatch
        if currency != expected_currency:
            issues.append(
                ComplianceIssue(
                    code="CURRENCY_MISMATCH",
                    message=f"Transaction {txn_id} in {currency}, expected {expected_currency}.",
                    severity="low",
                    transaction_id=txn_id,
                    suggestion="Confirm if multi-currency is intended or convert to base currency.",
                )
            )

        # Check unusual amount
        if abs(amount) > max_reasonable_amount:
            issues.append(
                ComplianceIssue(
                    code="UNUSUAL_AMOUNT",
                    message=f"Transaction {txn_id} has unusually large amount {amount}.",
                    severity="medium",
                    transaction_id=txn_id,
                    suggestion="Verify the source document and approval.",
                )
            )

    for entry in journal_entries:
        # Handle both object and dict access
        if hasattr(entry, "is_balanced"):
            is_balanced = entry.is_balanced
            entry_id = getattr(entry, "entry_id", None) or getattr(entry, "description", "unknown")
        elif isinstance(entry, dict):
            is_balanced = entry.get("is_balanced", True)
            entry_id = entry.get("entry_id") or entry.get("description", "unknown")
        else:
            is_balanced = True
            entry_id = "unknown"

        if not is_balanced:
            issues.append(
                ComplianceIssue(
                    code="UNBALANCED_ENTRY",
                    message=f"Journal entry {entry_id} is not balanced.",
                    severity="critical",
                    suggestion="Investigate generator or manual edits to restore balance.",
                )
            )

    # Determine overall compliance
    blocking_severities = ("medium", "high", "critical")
    has_blocking = any(i.severity in blocking_severities for i in issues)

    return ComplianceCheckResult(
        issues=issues,
        is_compliant=not has_blocking,
    )


__all__ = [
    "ComplianceIssue",
    "ComplianceCheckResult",
    "run_basic_compliance_checks",
]
