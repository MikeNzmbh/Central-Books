"""
Bank Statement Processing Pipeline - End-to-End Workflow

Pipeline: bank statement → parse → normalize_txns → classify → detect_duplicates
         → reconcile → flag_suspense → journal_entries → compliance → audit

This workflow handles bank statement documents with:
- CSV/PDF parsing (demo uses structured input)
- Transaction classification
- Duplicate detection
- Reconciliation proposals
- Suspense account detection
- Journal entry generation
"""

from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date, datetime, timedelta
from uuid import uuid4
import hashlib

from agentic.workflows.graph import WorkflowGraph
from agentic.engine.compliance import run_basic_compliance_checks
from agentic.engine.audit import run_basic_audit_checks


# =============================================================================
# BANK STATEMENT DATA MODELS
# =============================================================================


@dataclass
class BankTransaction:
    """A single transaction from a bank statement."""
    
    id: str
    date: str
    description: str
    amount: Decimal
    balance: Decimal = Decimal("0")
    transaction_type: str = "debit"  # "debit" or "credit"
    reference: str = ""
    category_code: str = ""
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    
    def model_dump(self) -> dict:
        return {
            "id": self.id,
            "date": self.date,
            "description": self.description,
            "amount": str(self.amount),
            "balance": str(self.balance),
            "transaction_type": self.transaction_type,
            "reference": self.reference,
            "category_code": self.category_code,
            "is_duplicate": self.is_duplicate,
            "duplicate_of": self.duplicate_of,
        }
    
    def fingerprint(self) -> str:
        """Generate a fingerprint for duplicate detection."""
        data = f"{self.date}|{self.amount}|{self.description[:50]}"
        return hashlib.md5(data.encode()).hexdigest()[:12]


@dataclass
class BankStatement:
    """Parsed bank statement with metadata."""
    
    id: str
    raw_document_id: str
    account_number: str = ""
    account_name: str = ""
    bank_name: str = ""
    statement_date: str = ""
    period_start: str = ""
    period_end: str = ""
    opening_balance: Decimal = Decimal("0")
    closing_balance: Decimal = Decimal("0")
    currency: str = "USD"
    transactions: List[BankTransaction] = field(default_factory=list)
    
    def model_dump(self) -> dict:
        return {
            "id": self.id,
            "raw_document_id": self.raw_document_id,
            "account_number": self.account_number,
            "account_name": self.account_name,
            "bank_name": self.bank_name,
            "statement_date": self.statement_date,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "opening_balance": str(self.opening_balance),
            "closing_balance": str(self.closing_balance),
            "currency": self.currency,
            "transactions": [t.model_dump() for t in self.transactions],
        }


@dataclass
class ReconciliationItem:
    """A reconciliation match or proposal."""
    
    bank_txn_id: str
    ledger_entry_id: Optional[str]
    match_type: str  # "auto_matched", "suggested", "unmatched"
    confidence: float
    difference: Decimal = Decimal("0")
    notes: str = ""
    
    def model_dump(self) -> dict:
        return {
            "bank_txn_id": self.bank_txn_id,
            "ledger_entry_id": self.ledger_entry_id,
            "match_type": self.match_type,
            "confidence": self.confidence,
            "difference": str(self.difference),
            "notes": self.notes,
        }


@dataclass
class ReconciliationReport:
    """Summary of reconciliation results."""
    
    statement_id: str
    total_transactions: int
    matched_count: int
    suggested_count: int
    unmatched_count: int
    total_matched_amount: Decimal
    total_unmatched_amount: Decimal
    items: List[ReconciliationItem] = field(default_factory=list)
    is_balanced: bool = False
    balance_difference: Decimal = Decimal("0")
    
    def model_dump(self) -> dict:
        return {
            "statement_id": self.statement_id,
            "total_transactions": self.total_transactions,
            "matched_count": self.matched_count,
            "suggested_count": self.suggested_count,
            "unmatched_count": self.unmatched_count,
            "total_matched_amount": str(self.total_matched_amount),
            "total_unmatched_amount": str(self.total_unmatched_amount),
            "items": [i.model_dump() for i in self.items],
            "is_balanced": self.is_balanced,
            "balance_difference": str(self.balance_difference),
        }


@dataclass
class SuspenseFlag:
    """Flag for transactions requiring suspense account."""
    
    txn_id: str
    reason: str
    suggested_account: str = "9000"  # Suspense
    severity: str = "medium"
    
    def model_dump(self) -> dict:
        return {
            "txn_id": self.txn_id,
            "reason": self.reason,
            "suggested_account": self.suggested_account,
            "severity": self.severity,
        }


@dataclass
class BankJournalLine:
    """A line in a bank transaction journal entry."""
    
    account_code: str
    account_name: str
    side: str
    amount: Decimal
    
    def model_dump(self) -> dict:
        return {
            "account_code": self.account_code,
            "account_name": self.account_name,
            "side": self.side,
            "amount": str(self.amount),
        }


@dataclass
class BankJournalEntry:
    """Journal entry for a bank transaction."""
    
    entry_id: str
    date: str
    description: str
    bank_txn_id: str
    lines: List[BankJournalLine] = field(default_factory=list)
    is_balanced: bool = True
    total_debits: Decimal = Decimal("0")
    total_credits: Decimal = Decimal("0")
    
    def model_dump(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "date": self.date,
            "description": self.description,
            "bank_txn_id": self.bank_txn_id,
            "lines": [line.model_dump() for line in self.lines],
            "is_balanced": self.is_balanced,
            "total_debits": str(self.total_debits),
            "total_credits": str(self.total_credits),
        }


# =============================================================================
# DEMO DATA FOR DETERMINISTIC EXTRACTION
# =============================================================================

TRANSACTION_CATEGORIES = {
    "payroll": ("6000", "Payroll Expense"),
    "rent": ("6400", "Rent Expense"),
    "utilities": ("6500", "Utilities"),
    "transfer": ("1000", "Bank Transfer"),
    "payment": ("2100", "Accounts Payable"),
    "deposit": ("1200", "Accounts Receivable"),
    "fee": ("6600", "Bank Fees"),
    "interest": ("4100", "Interest Income"),
}


def _classify_transaction(description: str) -> tuple:
    """Classify a transaction based on description keywords."""
    desc_lower = description.lower()
    
    for keyword, (code, name) in TRANSACTION_CATEGORIES.items():
        if keyword in desc_lower:
            return code, name
    
    # Default to uncategorized
    return "9000", "Suspense/Uncategorized"


def _generate_demo_transactions(doc_id: str) -> List[BankTransaction]:
    """Generate demo bank transactions."""
    today = date.today()
    base_balance = Decimal("10000.00")
    
    # Sample transactions
    txns = []
    descriptions = [
        ("PAYROLL DIRECT DEPOSIT", Decimal("-3500.00"), "debit"),
        ("RENT PAYMENT - OFFICE", Decimal("-2000.00"), "debit"),
        ("CUSTOMER DEPOSIT #1234", Decimal("5000.00"), "credit"),
        ("UTILITIES ELECTRIC CO", Decimal("-150.00"), "debit"),
        ("BANK FEE MONTHLY", Decimal("-25.00"), "debit"),
        ("TRANSFER FROM SAVINGS", Decimal("1000.00"), "credit"),
    ]
    
    running_balance = base_balance
    for idx, (desc, amount, txn_type) in enumerate(descriptions):
        running_balance += amount
        txns.append(BankTransaction(
            id=f"bank-txn-{doc_id[-1]}-{idx + 1}",
            date=str(today - timedelta(days=len(descriptions) - idx)),
            description=desc,
            amount=abs(amount),
            balance=running_balance,
            transaction_type=txn_type,
            reference=f"REF{idx + 1:04d}",
        ))
    
    return txns


# =============================================================================
# WORKFLOW STEPS
# =============================================================================


def ingest_statement_step(context: Dict[str, Any]) -> None:
    """
    Convert uploaded bank statement files to raw document objects.
    
    Input: context["uploaded_files"]
    Output: context["statement_documents"]
    """
    uploaded = context.get("uploaded_files", [])
    docs = []
    
    for idx, f in enumerate(uploaded):
        if isinstance(f, dict):
            filename = f.get("filename", f"statement-{idx + 1}.csv")
            content = f.get("content", "")
        else:
            filename = getattr(f, "name", f"statement-{idx + 1}.csv")
            content = ""
        
        docs.append({
            "id": f"stmt-doc-{idx + 1}",
            "filename": filename,
            "content": content,
            "source": "upload",
            "document_type": "bank_statement",
        })
    
    context["statement_documents"] = docs


def parse_statement_step(context: Dict[str, Any]) -> None:
    """
    Parse bank statement documents into structured format.
    
    Supports CSV and PDF (demo uses structured input).
    
    Input: context["statement_documents"]
    Output: context["parsed_statements"]
    """
    docs = context.get("statement_documents", [])
    statements = []
    today = str(date.today())
    
    for doc in docs:
        transactions = _generate_demo_transactions(doc["id"])
        
        opening = Decimal("10000.00")
        closing = transactions[-1].balance if transactions else opening
        
        statements.append(BankStatement(
            id=doc["id"].replace("stmt-doc", "stmt"),
            raw_document_id=doc["id"],
            account_number="****1234",
            account_name="Business Checking",
            bank_name="Demo Bank",
            statement_date=today,
            period_start=str(date.today() - timedelta(days=30)),
            period_end=today,
            opening_balance=opening,
            closing_balance=closing,
            currency="USD",
            transactions=transactions,
        ))
    
    context["parsed_statements"] = statements


def normalize_transactions_step(context: Dict[str, Any]) -> None:
    """
    Normalize bank transactions for further processing.
    
    Input: context["parsed_statements"]
    Output: context["normalized_statements"]
    """
    statements = context.get("parsed_statements", [])
    
    for stmt in statements:
        for txn in stmt.transactions:
            # Normalize description (trim, uppercase)
            txn.description = txn.description.strip().upper()
            
            # Ensure consistent decimal precision
            txn.amount = txn.amount.quantize(Decimal("0.01"))
    
    context["normalized_statements"] = statements


def classify_transactions_step(context: Dict[str, Any]) -> None:
    """
    Classify bank transactions into expense/income categories.
    
    Input: context["normalized_statements"]
    Output: context["classified_statements"]
    """
    statements = context.get("normalized_statements", [])
    
    for stmt in statements:
        for txn in stmt.transactions:
            code, name = _classify_transaction(txn.description)
            txn.category_code = code
    
    context["classified_statements"] = statements


def detect_duplicates_step(context: Dict[str, Any]) -> None:
    """
    Detect duplicate transactions within and across statements.
    
    Input: context["classified_statements"]
    Output: context["deduplicated_statements"]
    """
    statements = context.get("classified_statements", [])
    
    # Collect all fingerprints
    seen_fingerprints: Dict[str, str] = {}
    
    for stmt in statements:
        for txn in stmt.transactions:
            fp = txn.fingerprint()
            
            if fp in seen_fingerprints:
                txn.is_duplicate = True
                txn.duplicate_of = seen_fingerprints[fp]
            else:
                seen_fingerprints[fp] = txn.id
    
    context["deduplicated_statements"] = statements


def reconcile_step(context: Dict[str, Any]) -> None:
    """
    Generate reconciliation proposals for bank transactions.
    
    In demo mode, creates suggested matches.
    Real implementation would query ledger for actual matching.
    
    Input: context["deduplicated_statements"]
    Output: context["reconciliation_reports"]
    """
    statements = context.get("deduplicated_statements", [])
    reports = []
    
    for stmt in statements:
        items = []
        matched_count = 0
        suggested_count = 0
        unmatched_count = 0
        matched_amount = Decimal("0")
        unmatched_amount = Decimal("0")
        
        for txn in stmt.transactions:
            if txn.is_duplicate:
                # Skip duplicates
                continue
            
            # Demo: categorized transactions are "suggested"
            if txn.category_code != "9000":
                match_type = "suggested"
                confidence = 0.75
                suggested_count += 1
                matched_amount += txn.amount
            else:
                match_type = "unmatched"
                confidence = 0.0
                unmatched_count += 1
                unmatched_amount += txn.amount
            
            items.append(ReconciliationItem(
                bank_txn_id=txn.id,
                ledger_entry_id=None,  # Would be populated from ledger lookup
                match_type=match_type,
                confidence=confidence,
            ))
        
        total_txns = matched_count + suggested_count + unmatched_count
        
        # Calculate balance
        calculated_closing = stmt.opening_balance
        for txn in stmt.transactions:
            if not txn.is_duplicate:
                if txn.transaction_type == "credit":
                    calculated_closing += txn.amount
                else:
                    calculated_closing -= txn.amount
        
        balance_diff = stmt.closing_balance - calculated_closing
        
        reports.append(ReconciliationReport(
            statement_id=stmt.id,
            total_transactions=total_txns,
            matched_count=matched_count,
            suggested_count=suggested_count,
            unmatched_count=unmatched_count,
            total_matched_amount=matched_amount,
            total_unmatched_amount=unmatched_amount,
            items=items,
            is_balanced=abs(balance_diff) < Decimal("0.01"),
            balance_difference=balance_diff,
        ))
    
    context["reconciliation_reports"] = reports


def flag_suspense_step(context: Dict[str, Any]) -> None:
    """
    Flag transactions that should go to suspense accounts.
    
    Input: context["deduplicated_statements"]
    Output: context["suspense_flags"]
    """
    statements = context.get("deduplicated_statements", [])
    flags = []
    
    for stmt in statements:
        for txn in stmt.transactions:
            if txn.category_code == "9000":
                flags.append(SuspenseFlag(
                    txn_id=txn.id,
                    reason=f"Transaction '{txn.description[:30]}...' could not be classified",
                    suggested_account="9000",
                    severity="medium",
                ))
    
    context["suspense_flags"] = flags


def generate_bank_entries_step(context: Dict[str, Any]) -> None:
    """
    Generate journal entries for bank transactions.
    
    For each transaction:
    - Credit transactions: DR Bank, CR Income/AR
    - Debit transactions: DR Expense/AP, CR Bank
    
    Input: context["deduplicated_statements"]
    Output: context["journal_entries"]
    """
    statements = context.get("deduplicated_statements", [])
    entries = []
    
    for stmt in statements:
        for txn in stmt.transactions:
            if txn.is_duplicate:
                continue
            
            lines = []
            total_debits = Decimal("0")
            total_credits = Decimal("0")
            
            category_name = TRANSACTION_CATEGORIES.get(
                txn.category_code, ("9000", "Suspense")
            )
            if isinstance(category_name, tuple):
                category_name = category_name[1]
            
            if txn.transaction_type == "credit":
                # Money coming in
                lines.append(BankJournalLine(
                    account_code="1000",
                    account_name="Bank Account",
                    side="debit",
                    amount=txn.amount,
                ))
                total_debits += txn.amount
                
                lines.append(BankJournalLine(
                    account_code=txn.category_code,
                    account_name=category_name,
                    side="credit",
                    amount=txn.amount,
                ))
                total_credits += txn.amount
            else:
                # Money going out
                lines.append(BankJournalLine(
                    account_code=txn.category_code,
                    account_name=category_name,
                    side="debit",
                    amount=txn.amount,
                ))
                total_debits += txn.amount
                
                lines.append(BankJournalLine(
                    account_code="1000",
                    account_name="Bank Account",
                    side="credit",
                    amount=txn.amount,
                ))
                total_credits += txn.amount
            
            entries.append(BankJournalEntry(
                entry_id=f"je-{txn.id}",
                date=txn.date,
                description=f"Bank: {txn.description[:50]}",
                bank_txn_id=txn.id,
                lines=lines,
                is_balanced=total_debits == total_credits,
                total_debits=total_debits,
                total_credits=total_credits,
            ))
    
    context["journal_entries"] = entries


def bank_compliance_step(context: Dict[str, Any]) -> None:
    """
    Run compliance checks on bank transactions and entries.
    
    Input: context["deduplicated_statements"], context["journal_entries"]
    Output: context["compliance_result"]
    """
    statements = context.get("deduplicated_statements", [])
    entries = context.get("journal_entries", [])
    
    # Flatten transactions
    txn_dicts = []
    for stmt in statements:
        for txn in stmt.transactions:
            if not txn.is_duplicate:
                txn_dicts.append(txn.model_dump())
    
    entry_dicts = [e.model_dump() for e in entries]
    
    result = run_basic_compliance_checks(txn_dicts, entry_dicts)
    context["compliance_result"] = result


def bank_audit_step(context: Dict[str, Any]) -> None:
    """
    Run audit checks on bank transactions and entries.
    
    Input: context["deduplicated_statements"], context["journal_entries"]
    Output: context["audit_report"]
    """
    statements = context.get("deduplicated_statements", [])
    entries = context.get("journal_entries", [])
    
    txn_dicts = []
    for stmt in statements:
        for txn in stmt.transactions:
            if not txn.is_duplicate:
                txn_dicts.append(txn.model_dump())
    
    entry_dicts = [e.model_dump() for e in entries]
    
    report = run_basic_audit_checks(txn_dicts, entry_dicts)
    context["audit_report"] = report


# =============================================================================
# WORKFLOW BUILDER
# =============================================================================


def build_bank_statement_workflow() -> WorkflowGraph:
    """
    Build the bank statement processing workflow.
    
    Pipeline:
    1. ingest: uploaded_files → statement_documents
    2. parse: statement_documents → parsed_statements
    3. normalize: parsed_statements → normalized_statements
    4. classify: normalized_statements → classified_statements
    5. deduplicate: classified_statements → deduplicated_statements
    6. reconcile: deduplicated_statements → reconciliation_reports
    7. flag_suspense: deduplicated_statements → suspense_flags
    8. generate_entries: deduplicated_statements → journal_entries
    9. compliance: Run compliance checks
    10. audit: Run audit checks
    
    Returns:
        Configured WorkflowGraph ready to run.
    """
    wf = WorkflowGraph("bank_statement_processing")
    
    # Register steps
    wf.add_step("ingest", ingest_statement_step)
    wf.add_step("parse", parse_statement_step)
    wf.add_step("normalize", normalize_transactions_step)
    wf.add_step("classify", classify_transactions_step)
    wf.add_step("deduplicate", detect_duplicates_step)
    wf.add_step("reconcile", reconcile_step)
    wf.add_step("flag_suspense", flag_suspense_step)
    wf.add_step("generate_entries", generate_bank_entries_step)
    wf.add_step("compliance", bank_compliance_step)
    wf.add_step("audit", bank_audit_step)
    
    # Define dependencies
    wf.add_edge("ingest", "parse")
    wf.add_edge("parse", "normalize")
    wf.add_edge("normalize", "classify")
    wf.add_edge("classify", "deduplicate")
    wf.add_edge("deduplicate", "reconcile")
    wf.add_edge("deduplicate", "flag_suspense")
    wf.add_edge("deduplicate", "generate_entries")
    wf.add_edge("generate_entries", "compliance")
    wf.add_edge("compliance", "audit")
    
    return wf
