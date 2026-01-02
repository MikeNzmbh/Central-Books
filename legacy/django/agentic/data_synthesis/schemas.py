"""
Data Synthesis Schemas - Pydantic Models for Synthetic Scenarios

Models:
- SyntheticDocument: Raw document with content
- GroundTruthTransaction: Expected normalized transaction
- ExpectedJournalEntry: Expected journal entry
- ExpectedComplianceResult: Expected compliance outcome
- ExpectedAuditFinding: Expected audit finding
- SyntheticScenario: Complete scenario with all components
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import date, datetime
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================


class DocumentCategory(str, Enum):
    """Document categories for synthesis."""
    RECEIPT = "receipt"
    INVOICE = "invoice"
    BANK_STATEMENT = "bank_statement"


class ExpenseCategory(str, Enum):
    """Standard expense categories."""
    OFFICE_SUPPLIES = "6100"
    TRAVEL = "6200"
    SOFTWARE = "6300"
    RENT = "6400"
    UTILITIES = "6500"
    BANK_FEES = "6600"
    PAYROLL = "6000"
    COGS = "5000"
    RAW_MATERIALS = "5100"
    SHIPPING = "5200"


# =============================================================================
# DOCUMENT MODELS
# =============================================================================


class SyntheticDocument(BaseModel):
    """A synthetic document for testing."""
    
    id: str
    filename: str
    category: DocumentCategory
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Ground truth for extraction
    expected_vendor: str = ""
    expected_amount: Decimal = Decimal("0")
    expected_currency: str = "USD"
    expected_date: Optional[str] = None
    expected_category_code: str = ""


class GroundTruthTransaction(BaseModel):
    """Expected normalized transaction."""
    
    id: str
    source_document_id: str
    description: str
    amount: Decimal
    currency: str = "USD"
    date: str
    category_code: str
    vendor_name: Optional[str] = None
    
    # For bank statements
    transaction_type: str = "debit"  # debit or credit
    is_recurring: bool = False


class ExpectedJournalLine(BaseModel):
    """Expected line in a journal entry."""
    
    account_code: str
    account_name: str
    side: str  # debit or credit
    amount: Decimal


class ExpectedJournalEntry(BaseModel):
    """Expected journal entry."""
    
    entry_id: str
    source_transaction_id: str
    date: str
    description: str
    lines: List[ExpectedJournalLine]
    is_balanced: bool = True
    total_debits: Decimal = Decimal("0")
    total_credits: Decimal = Decimal("0")


class ExpectedComplianceIssue(BaseModel):
    """Expected compliance issue."""
    
    code: str
    severity: str
    message: str
    transaction_id: Optional[str] = None


class ExpectedComplianceResult(BaseModel):
    """Expected compliance check result."""
    
    is_compliant: bool = True
    issues: List[ExpectedComplianceIssue] = Field(default_factory=list)


class ExpectedAuditFinding(BaseModel):
    """Expected audit finding."""
    
    code: str
    severity: str
    message: str
    transaction_id: Optional[str] = None
    journal_entry_id: Optional[str] = None


class ExpectedAuditResult(BaseModel):
    """Expected audit result."""
    
    risk_level: str = "low"
    findings: List[ExpectedAuditFinding] = Field(default_factory=list)


# =============================================================================
# SCENARIO MODEL
# =============================================================================


class SyntheticScenario(BaseModel):
    """
    Complete synthetic scenario for testing.
    
    Contains:
    - Raw documents (receipts, invoices, bank statements)
    - Ground truth transactions
    - Expected journal entries
    - Expected compliance results
    - Expected audit findings
    """
    
    id: str
    name: str
    description: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    seed: int = 0
    
    # Input documents
    documents: List[SyntheticDocument] = Field(default_factory=list)
    
    # Ground truth outputs
    transactions: List[GroundTruthTransaction] = Field(default_factory=list)
    journal_entries: List[ExpectedJournalEntry] = Field(default_factory=list)
    
    # Expected results
    compliance: ExpectedComplianceResult = Field(default_factory=ExpectedComplianceResult)
    audit: ExpectedAuditResult = Field(default_factory=ExpectedAuditResult)
    
    # Scenario metadata
    total_revenue: Decimal = Decimal("0")
    total_expenses: Decimal = Decimal("0")
    net_income: Decimal = Decimal("0")
    
    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }
    
    def summary(self) -> Dict[str, Any]:
        """Generate scenario summary."""
        return {
            "id": self.id,
            "name": self.name,
            "documents": len(self.documents),
            "transactions": len(self.transactions),
            "journal_entries": len(self.journal_entries),
            "is_compliant": self.compliance.is_compliant,
            "audit_risk": self.audit.risk_level,
            "total_expenses": str(self.total_expenses),
        }


# =============================================================================
# SCENARIO TEMPLATES
# =============================================================================


class ScenarioTemplate(str, Enum):
    """Pre-defined scenario templates."""
    
    MONTHLY_BOOKKEEPING = "monthly_bookkeeping"
    QUARTERLY_REVIEW = "quarterly_review"
    AUDIT_STRESS_TEST = "audit_stress_test"
    COMPLIANCE_EDGE_CASES = "compliance_edge_cases"
    MULTI_CURRENCY = "multi_currency"
