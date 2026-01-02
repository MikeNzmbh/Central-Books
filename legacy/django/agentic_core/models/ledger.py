"""
Ledger models for normalized transactions and journal entry proposals.

These models represent the core double-entry accounting structures:
- NormalizedTransaction: Standardized transaction ready for journaling
- JournalLineProposal: Single debit/credit line in a journal entry
- JournalEntryProposal: Complete balanced journal entry proposal
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class TransactionType(str, Enum):
    """Type of transaction for classification."""

    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"
    PAYROLL = "payroll"
    TAX = "tax"
    DEPRECIATION = "depreciation"
    OTHER = "other"


class JournalEntryStatus(str, Enum):
    """Status of a journal entry proposal."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    POSTED = "posted"
    REJECTED = "rejected"


class NormalizedTransaction(BaseModel):
    """
    A normalized transaction ready for accounting processing.

    This is the standardized representation of a financial transaction
    after extraction and normalization from various sources (documents,
    bank feeds, manual entry).

    Attributes:
        transaction_id: Unique identifier.
        source_type: Origin of this transaction ("document", "bank_feed", "manual").
        source_id: ID of the source record.
        transaction_type: Classification of the transaction.
        transaction_date: When the transaction occurred.
        amount: Transaction amount (always positive).
        currency: Currency code.
        description: Human-readable description.
        payee_name: Vendor/customer name.
        category_hint: Suggested category from source.
        account_code_hint: Suggested account code.
        tax_amount: Tax portion if applicable.
        tax_code: Tax code if applicable.
        reference_number: Invoice/check/reference number.
        metadata: Additional context.
        created_at: When this record was created.
    """

    transaction_id: str = Field(default_factory=lambda: str(uuid4()))
    source_type: str  # "document", "bank_feed", "manual"
    source_id: Optional[str] = None
    transaction_type: TransactionType = TransactionType.EXPENSE
    transaction_date: date
    amount: Decimal
    currency: str = "USD"
    description: str
    payee_name: Optional[str] = None
    category_hint: Optional[str] = None
    account_code_hint: Optional[str] = None
    tax_amount: Optional[Decimal] = None
    tax_code: Optional[str] = None
    reference_number: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            Decimal: lambda v: str(v),
        }


class JournalLineProposal(BaseModel):
    """
    A single line (debit or credit) in a journal entry proposal.

    Represents one side of a double-entry accounting transaction.

    Attributes:
        line_id: Unique identifier for this line.
        account_code: Chart of accounts code.
        account_name: Human-readable account name.
        debit: Debit amount (mutually exclusive with credit).
        credit: Credit amount (mutually exclusive with debit).
        description: Line-level description/memo.
        tax_code: Tax code if applicable.
        department: Department/cost center if applicable.
        project: Project code if applicable.
        confidence: Agent's confidence in this line (0-1).
        reasoning: Why the agent chose this account.
    """

    line_id: str = Field(default_factory=lambda: str(uuid4()))
    account_code: str
    account_name: Optional[str] = None
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    description: Optional[str] = None
    tax_code: Optional[str] = None
    department: Optional[str] = None
    project: Optional[str] = None
    confidence: float = 1.0
    reasoning: Optional[str] = None

    class Config:
        json_encoders = {Decimal: lambda v: str(v)}

    @model_validator(mode="after")
    def validate_debit_credit(self) -> "JournalLineProposal":
        """Ensure exactly one of debit/credit is non-zero."""
        if self.debit > 0 and self.credit > 0:
            raise ValueError("A journal line cannot have both debit and credit")
        if self.debit == 0 and self.credit == 0:
            raise ValueError("A journal line must have either debit or credit")
        return self

    @property
    def is_debit(self) -> bool:
        """Check if this is a debit line."""
        return self.debit > 0

    @property
    def is_credit(self) -> bool:
        """Check if this is a credit line."""
        return self.credit > 0

    @property
    def amount(self) -> Decimal:
        """Get the non-zero amount."""
        return self.debit if self.is_debit else self.credit


class JournalEntryProposal(BaseModel):
    """
    A complete journal entry proposal generated by an accounting agent.

    This represents a balanced double-entry set of debits and credits
    that can be reviewed and posted to the general ledger.

    Attributes:
        entry_id: Unique identifier for this proposal.
        source_transaction_id: ID of the NormalizedTransaction this was generated from.
        entry_date: Date for the journal entry.
        description: Entry-level description/memo.
        lines: List of debit/credit lines.
        status: Current status of the proposal.
        total_debits: Sum of all debit amounts.
        total_credits: Sum of all credit amounts.
        is_balanced: Whether debits equal credits.
        currency: Currency code.
        agent_name: Name of the agent that generated this.
        agent_confidence: Overall confidence score (0-1).
        reasoning: High-level reasoning for this entry.
        review_notes: Notes from human review.
        created_at: When this proposal was created.
        reviewed_at: When this was reviewed.
        reviewed_by: Who reviewed it.
    """

    entry_id: str = Field(default_factory=lambda: str(uuid4()))
    source_transaction_id: Optional[str] = None
    entry_date: date
    description: str
    lines: list[JournalLineProposal] = Field(default_factory=list)
    status: JournalEntryStatus = JournalEntryStatus.DRAFT
    currency: str = "USD"
    agent_name: Optional[str] = None
    agent_confidence: float = 1.0
    reasoning: Optional[str] = None
    review_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            Decimal: lambda v: str(v),
        }

    @property
    def total_debits(self) -> Decimal:
        """Sum of all debit amounts."""
        return sum((line.debit for line in self.lines), Decimal("0"))

    @property
    def total_credits(self) -> Decimal:
        """Sum of all credit amounts."""
        return sum((line.credit for line in self.lines), Decimal("0"))

    @property
    def is_balanced(self) -> bool:
        """Check if debits equal credits."""
        return self.total_debits == self.total_credits

    @property
    def imbalance(self) -> Decimal:
        """Get the imbalance amount (debits - credits)."""
        return self.total_debits - self.total_credits

    def add_debit(
        self,
        account_code: str,
        amount: Decimal,
        account_name: Optional[str] = None,
        description: Optional[str] = None,
        reasoning: Optional[str] = None,
    ) -> JournalLineProposal:
        """Add a debit line to this entry."""
        line = JournalLineProposal(
            account_code=account_code,
            account_name=account_name,
            debit=amount,
            credit=Decimal("0"),
            description=description,
            reasoning=reasoning,
        )
        self.lines.append(line)
        return line

    def add_credit(
        self,
        account_code: str,
        amount: Decimal,
        account_name: Optional[str] = None,
        description: Optional[str] = None,
        reasoning: Optional[str] = None,
    ) -> JournalLineProposal:
        """Add a credit line to this entry."""
        line = JournalLineProposal(
            account_code=account_code,
            account_name=account_name,
            debit=Decimal("0"),
            credit=amount,
            description=description,
            reasoning=reasoning,
        )
        self.lines.append(line)
        return line

    def validate_balance(self) -> tuple[bool, str]:
        """
        Validate that this entry is balanced.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.lines:
            return False, "Journal entry has no lines"
        if not self.is_balanced:
            return (
                False,
                f"Entry is not balanced: debits={self.total_debits}, "
                f"credits={self.total_credits}, difference={self.imbalance}",
            )
        return True, ""
