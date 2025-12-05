"""
Audit Engine - Basic audit checks for anomaly detection.

Provides deterministic audit heuristics including:
- Unusual transaction scale detection
- Suspense/uncategorized account flagging
- Risk level assessment
"""

from typing import List, Optional
from statistics import mean
from pydantic import BaseModel


# =============================================================================
# AUDIT MODELS
# =============================================================================

AuditSeverity = str  # "info", "low", "medium", "high", "critical"


class AuditFinding(BaseModel):
    """A single audit finding from analysis."""

    code: str  # e.g. "UNUSUAL_AMOUNT"
    message: str
    severity: str  # AuditSeverity
    transaction_id: Optional[str] = None
    journal_entry_id: Optional[str] = None
    suggestion: Optional[str] = None

    class Config:
        frozen = True


class AuditReport(BaseModel):
    """Complete audit report with findings and risk assessment."""

    findings: List[AuditFinding] = []
    risk_level: str = "low"  # "low", "medium", "high"

    def model_dump(self) -> dict:
        return {
            "findings": [
                {
                    "code": f.code,
                    "message": f.message,
                    "severity": f.severity,
                    "transaction_id": f.transaction_id,
                    "journal_entry_id": f.journal_entry_id,
                    "suggestion": f.suggestion,
                }
                for f in self.findings
            ],
            "risk_level": self.risk_level,
        }


# =============================================================================
# AUDIT ENGINE
# =============================================================================

# Keywords indicating suspense/uncategorized accounts
SUSPICIOUS_KEYWORDS = ("suspense", "uncategorized", "other_misc", "clearing", "unknown")


def run_basic_audit_checks(
    transactions: List,
    journal_entries: List,
    *,
    scale_threshold_multiplier: float = 3.0,
) -> AuditReport:
    """
    Run deterministic audit heuristics on transactions and journal entries.

    Checks performed:
    - Flag transactions > 3x mean amount as unusual
    - Flag entries using suspense/uncategorized accounts

    Args:
        transactions: List of NormalizedTransaction or dicts.
        journal_entries: List of JournalEntryProposal/GeneratedEntry or dicts.
        scale_threshold_multiplier: Multiplier for unusual scale detection.

    Returns:
        AuditReport with findings and risk level.
    """
    findings: List[AuditFinding] = []

    # Extract amounts for statistical analysis
    amounts = []
    for txn in transactions:
        if hasattr(txn, "amount"):
            amount = float(txn.amount)
        elif isinstance(txn, dict):
            amount = float(txn.get("amount", 0))
        else:
            amount = 0
        amounts.append(abs(amount))

    # Check for unusual scale
    if amounts and len(amounts) > 1:
        avg = mean(amounts)
        threshold = scale_threshold_multiplier * avg

        for txn in transactions:
            if hasattr(txn, "model_dump"):
                txn_data = txn.model_dump() if hasattr(txn, "model_dump") else {}
                txn_id = getattr(txn, "id", "unknown")
                amount = float(getattr(txn, "amount", 0))
            elif hasattr(txn, "id"):
                txn_id = txn.id
                amount = float(getattr(txn, "amount", 0))
            elif isinstance(txn, dict):
                txn_id = txn.get("id", "unknown")
                amount = float(txn.get("amount", 0))
            else:
                continue

            if abs(amount) > threshold:
                findings.append(
                    AuditFinding(
                        code="UNUSUAL_SCALE",
                        message=f"Transaction {txn_id} is {abs(amount):.2f}, above 3x average {avg:.2f}.",
                        severity="medium",
                        transaction_id=txn_id,
                        suggestion="Confirm this isn't a mis-keyed amount.",
                    )
                )

    # Check for suspense/uncategorized accounts
    for entry in journal_entries:
        # Get entry ID
        if hasattr(entry, "entry_id"):
            entry_id = entry.entry_id
        elif hasattr(entry, "description"):
            entry_id = entry.description
        elif isinstance(entry, dict):
            entry_id = entry.get("entry_id") or entry.get("description", "unknown")
        else:
            entry_id = "unknown"

        # Get lines
        if hasattr(entry, "lines"):
            lines = entry.lines
        elif isinstance(entry, dict):
            lines = entry.get("lines", [])
        else:
            lines = []

        for line in lines:
            # Get account name
            if hasattr(line, "account_name"):
                account_name = line.account_name or ""
            elif isinstance(line, dict):
                account_name = line.get("account_name", "") or ""
            else:
                account_name = ""

            account_lower = account_name.lower()
            if any(kw in account_lower for kw in SUSPICIOUS_KEYWORDS):
                findings.append(
                    AuditFinding(
                        code="SUSPENSE_ACCOUNT",
                        message=f"Entry {entry_id} uses '{account_name}'.",
                        severity="high",
                        journal_entry_id=entry_id,
                        suggestion="Clear suspense/uncategorized accounts to proper categories.",
                    )
                )

    # Determine risk level
    risk_level = "low"
    if any(f.severity == "high" or f.severity == "critical" for f in findings):
        risk_level = "high"
    elif any(f.severity == "medium" for f in findings):
        risk_level = "medium"

    return AuditReport(findings=findings, risk_level=risk_level)


__all__ = [
    "AuditFinding",
    "AuditReport",
    "run_basic_audit_checks",
]
