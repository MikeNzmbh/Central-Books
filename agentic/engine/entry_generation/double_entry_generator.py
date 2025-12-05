"""
Double Entry Generator - Creates balanced journal entries from transactions.

Provides:
- DoubleEntryGenerator: Class for generating individual entries
- generate_journal_entries_for_transactions: Batch helper function
"""

from typing import Any, List, Optional
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date
from uuid import uuid4


@dataclass
class JournalLine:
    """A single line in a journal entry."""

    account_code: str = ""
    account_name: str = ""
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    description: str = ""

    @property
    def is_debit(self) -> bool:
        return self.debit > 0

    @property
    def is_credit(self) -> bool:
        return self.credit > 0

    @property
    def side(self) -> str:
        return "debit" if self.is_debit else "credit"

    @property
    def amount(self) -> Decimal:
        return self.debit if self.is_debit else self.credit


@dataclass
class GeneratedEntry:
    """A generated journal entry."""

    entry_id: str = ""
    date: str = ""
    description: str = ""
    lines: List[JournalLine] = field(default_factory=list)
    is_balanced: bool = False
    confidence: float = 0.0
    reasoning: str = ""
    source_transaction_id: Optional[str] = None

    @property
    def total_debits(self) -> Decimal:
        return sum((line.debit for line in self.lines), Decimal("0"))

    @property
    def total_credits(self) -> Decimal:
        return sum((line.credit for line in self.lines), Decimal("0"))

    def model_dump(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "entry_id": self.entry_id,
            "date": self.date,
            "description": self.description,
            "lines": [
                {
                    "account_code": l.account_code,
                    "account_name": l.account_name,
                    "debit": str(l.debit),
                    "credit": str(l.credit),
                    "description": l.description,
                    "side": l.side,
                    "amount": str(l.amount),
                }
                for l in self.lines
            ],
            "is_balanced": self.is_balanced,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "source_transaction_id": self.source_transaction_id,
            "total_debits": str(self.total_debits),
            "total_credits": str(self.total_credits),
        }


class DoubleEntryGenerator:
    """
    Generates balanced double-entry journal entries.

    Uses deterministic rules for demo purposes.
    Real implementation would use LLM + Chart of Accounts.
    """

    def __init__(
        self,
        default_cash_account: str = "1000",
        default_expense_account: str = "6000",
        default_income_account: str = "4000",
    ):
        """Initialize the generator."""
        self.default_cash_account = default_cash_account
        self.default_expense_account = default_expense_account
        self.default_income_account = default_income_account

        # Simple account mapping
        self.account_names = {
            "1000": "Cash/Bank",
            "4000": "Revenue",
            "5000": "Cost of Goods Sold",
            "6000": "Operating Expenses",
            "6100": "Office Supplies",
            "6200": "Travel & Entertainment",
            "6300": "Software & Subscriptions",
        }

    def generate_for_expense(
        self,
        transaction_id: str,
        description: str,
        amount: Decimal,
        txn_date: str,
        category_code: Optional[str] = None,
    ) -> GeneratedEntry:
        """Generate a journal entry for an expense transaction."""
        expense_account = category_code or self.default_expense_account

        entry = GeneratedEntry(
            entry_id=f"je-{uuid4().hex[:8]}",
            date=txn_date,
            description=description,
            source_transaction_id=transaction_id,
            confidence=0.85,
            reasoning="Expense recorded as debit to expense, credit to cash",
        )

        # Debit expense account
        entry.lines.append(
            JournalLine(
                account_code=expense_account,
                account_name=self.account_names.get(expense_account, "Expense"),
                debit=amount,
                credit=Decimal("0"),
                description=description,
            )
        )

        # Credit cash account
        entry.lines.append(
            JournalLine(
                account_code=self.default_cash_account,
                account_name=self.account_names.get(
                    self.default_cash_account, "Cash"
                ),
                debit=Decimal("0"),
                credit=amount,
                description=description,
            )
        )

        entry.is_balanced = entry.total_debits == entry.total_credits
        return entry


def generate_journal_entries_for_transactions(
    transactions: List[Any],
) -> List[GeneratedEntry]:
    """
    Generate journal entries for a list of transactions.

    This is a batch helper function for workflow steps.

    Args:
        transactions: List of NormalizedTransaction or similar objects.

    Returns:
        List of GeneratedEntry objects.
    """
    generator = DoubleEntryGenerator()
    entries: List[GeneratedEntry] = []

    for txn in transactions:
        # Handle both dict and object-style transactions
        if hasattr(txn, "model_dump"):
            txn_data = txn.model_dump()
        elif isinstance(txn, dict):
            txn_data = txn
        else:
            txn_data = {
                "id": getattr(txn, "id", str(uuid4())),
                "description": getattr(txn, "description", "Transaction"),
                "amount": getattr(txn, "amount", Decimal("0")),
                "date": getattr(txn, "date", str(date.today())),
                "category_code": getattr(txn, "category_code", None),
            }

        # Get values
        txn_id = txn_data.get("id") or txn_data.get("transaction_id", str(uuid4()))
        description = txn_data.get("description", "Transaction")
        amount = Decimal(str(txn_data.get("amount", 0)))
        txn_date = str(txn_data.get("date", date.today()))
        category = txn_data.get("category_code")

        entry = generator.generate_for_expense(
            transaction_id=str(txn_id),
            description=description,
            amount=amount,
            txn_date=txn_date,
            category_code=category,
        )
        entries.append(entry)

    return entries
