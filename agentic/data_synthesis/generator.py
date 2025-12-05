"""
Synthetic Data Generator - Create Test Scenarios

Functions:
- generate_scenario_monthly_bookkeeping: Generate a month of bookkeeping data
- generate_receipt_docs_for_scenario: Generate receipt documents
- generate_invoice_docs_for_scenario: Generate invoice documents  
- generate_bank_statement_docs_for_scenario: Generate bank statement documents
"""

from typing import List, Optional
from decimal import Decimal
from datetime import date, datetime, timedelta
import random
import hashlib

from .schemas import (
    SyntheticScenario,
    SyntheticDocument,
    GroundTruthTransaction,
    ExpectedJournalEntry,
    ExpectedJournalLine,
    ExpectedComplianceResult,
    ExpectedComplianceIssue,
    ExpectedAuditResult,
    ExpectedAuditFinding,
    DocumentCategory,
    ExpenseCategory,
)


# =============================================================================
# VENDOR DATA
# =============================================================================

VENDORS = {
    "office": [
        ("Office Depot", ExpenseCategory.OFFICE_SUPPLIES, (25, 200)),
        ("Staples", ExpenseCategory.OFFICE_SUPPLIES, (15, 150)),
        ("Amazon Business", ExpenseCategory.OFFICE_SUPPLIES, (20, 500)),
    ],
    "travel": [
        ("Delta Airlines", ExpenseCategory.TRAVEL, (200, 800)),
        ("Marriott Hotels", ExpenseCategory.TRAVEL, (150, 400)),
        ("Uber", ExpenseCategory.TRAVEL, (15, 75)),
        ("Enterprise Rent-A-Car", ExpenseCategory.TRAVEL, (50, 200)),
    ],
    "software": [
        ("GitHub", ExpenseCategory.SOFTWARE, (9, 50)),
        ("AWS", ExpenseCategory.SOFTWARE, (100, 1000)),
        ("Google Cloud", ExpenseCategory.SOFTWARE, (50, 500)),
        ("Slack", ExpenseCategory.SOFTWARE, (8, 25)),
        ("Zoom", ExpenseCategory.SOFTWARE, (15, 50)),
    ],
    "utilities": [
        ("Pacific Gas & Electric", ExpenseCategory.UTILITIES, (100, 400)),
        ("AT&T Business", ExpenseCategory.UTILITIES, (80, 200)),
        ("Comcast Business", ExpenseCategory.UTILITIES, (100, 250)),
    ],
    "supplies": [
        ("ACME Corp", ExpenseCategory.RAW_MATERIALS, (500, 5000)),
        ("Industrial Supply Co", ExpenseCategory.RAW_MATERIALS, (200, 2000)),
    ],
    "shipping": [
        ("FedEx", ExpenseCategory.SHIPPING, (25, 200)),
        ("UPS", ExpenseCategory.SHIPPING, (20, 150)),
        ("USPS", ExpenseCategory.SHIPPING, (10, 50)),
    ],
}

ACCOUNT_NAMES = {
    "1000": "Cash/Bank",
    "1200": "Accounts Receivable",
    "1300": "Sales Tax Receivable",
    "2100": "Accounts Payable",
    "2200": "Sales Tax Payable",
    "5000": "Cost of Goods Sold",
    "5100": "Raw Materials",
    "5200": "Shipping & Freight",
    "6000": "Payroll Expense",
    "6100": "Office Supplies",
    "6200": "Travel & Entertainment",
    "6300": "Software & Subscriptions",
    "6400": "Rent Expense",
    "6500": "Utilities",
    "6600": "Bank Fees",
    "9000": "Suspense/Uncategorized",
}


# =============================================================================
# GENERATOR FUNCTIONS
# =============================================================================


def _seeded_random(seed: int):
    """Create a seeded random generator."""
    return random.Random(seed)


def _generate_id(prefix: str, seed: int, index: int) -> str:
    """Generate a deterministic ID."""
    data = f"{prefix}-{seed}-{index}"
    return f"{prefix}-{hashlib.md5(data.encode()).hexdigest()[:8]}"


def generate_receipt_docs_for_scenario(
    seed: int,
    count: int = 5,
    start_date: Optional[date] = None,
) -> List[SyntheticDocument]:
    """
    Generate synthetic receipt documents.
    
    Args:
        seed: Random seed for reproducibility
        count: Number of receipts to generate
        start_date: Starting date for receipts
    
    Returns:
        List of SyntheticDocument objects
    """
    rng = _seeded_random(seed)
    start = start_date or date.today() - timedelta(days=30)
    
    docs = []
    for i in range(count):
        # Pick random vendor category and vendor
        category = rng.choice(list(VENDORS.keys()))
        vendor_name, expense_cat, (min_amt, max_amt) = rng.choice(VENDORS[category])
        
        # Generate amount
        amount = Decimal(str(rng.uniform(min_amt, max_amt))).quantize(Decimal("0.01"))
        
        # Generate date
        days_offset = rng.randint(0, 30)
        doc_date = start + timedelta(days=days_offset)
        
        # Generate content
        content = f"{vendor_name} - ${amount} - {category.replace('_', ' ')}"
        
        docs.append(SyntheticDocument(
            id=_generate_id("rcpt", seed, i),
            filename=f"receipt_{vendor_name.lower().replace(' ', '_')}_{i+1}.pdf",
            category=DocumentCategory.RECEIPT,
            content=content,
            expected_vendor=vendor_name,
            expected_amount=amount,
            expected_currency="USD",
            expected_date=str(doc_date),
            expected_category_code=expense_cat.value,
        ))
    
    return docs


def generate_invoice_docs_for_scenario(
    seed: int,
    count: int = 3,
    start_date: Optional[date] = None,
) -> List[SyntheticDocument]:
    """
    Generate synthetic invoice documents.
    
    Args:
        seed: Random seed for reproducibility
        count: Number of invoices to generate
        start_date: Starting date for invoices
    
    Returns:
        List of SyntheticDocument objects
    """
    rng = _seeded_random(seed + 1000)  # Offset seed
    start = start_date or date.today() - timedelta(days=30)
    
    docs = []
    for i in range(count):
        # Pick vendor for invoices (typically supplies/software)
        category = rng.choice(["supplies", "software", "utilities"])
        vendor_name, expense_cat, (min_amt, max_amt) = rng.choice(VENDORS[category])
        
        # Generate amount (invoices tend to be larger)
        base_amount = Decimal(str(rng.uniform(min_amt * 2, max_amt * 2))).quantize(Decimal("0.01"))
        tax_rate = Decimal("0.08")
        tax_amount = (base_amount * tax_rate).quantize(Decimal("0.01"))
        total = base_amount + tax_amount
        
        # Generate date
        days_offset = rng.randint(0, 30)
        doc_date = start + timedelta(days=days_offset)
        
        # Generate invoice number
        inv_number = f"INV-{doc_date.strftime('%Y%m%d')}-{i+1:03d}"
        
        # Generate content
        content = f"""
INVOICE {inv_number}
From: {vendor_name}
Date: {doc_date}
Due: Net 30

Subtotal: ${base_amount}
Tax (8%): ${tax_amount}
Total: ${total}

Payment Terms: Net 30
"""
        
        docs.append(SyntheticDocument(
            id=_generate_id("inv", seed, i),
            filename=f"invoice_{vendor_name.lower().replace(' ', '_')}_{inv_number}.pdf",
            category=DocumentCategory.INVOICE,
            content=content,
            expected_vendor=vendor_name,
            expected_amount=total,
            expected_currency="USD",
            expected_date=str(doc_date),
            expected_category_code=expense_cat.value,
            metadata={
                "invoice_number": inv_number,
                "subtotal": str(base_amount),
                "tax_amount": str(tax_amount),
            },
        ))
    
    return docs


def generate_bank_statement_docs_for_scenario(
    seed: int,
    transaction_count: int = 10,
    start_date: Optional[date] = None,
) -> List[SyntheticDocument]:
    """
    Generate synthetic bank statement documents.
    
    Args:
        seed: Random seed for reproducibility
        transaction_count: Number of transactions in statement
        start_date: Statement start date
    
    Returns:
        List of SyntheticDocument objects (one per statement)
    """
    rng = _seeded_random(seed + 2000)  # Offset seed
    start = start_date or date.today() - timedelta(days=30)
    end = start + timedelta(days=30)
    
    # Generate transactions
    txn_lines = []
    running_balance = Decimal("10000.00")
    
    for i in range(transaction_count):
        # Pick transaction type
        is_credit = rng.random() < 0.3  # 30% are credits (deposits)
        
        if is_credit:
            # Deposit
            amount = Decimal(str(rng.uniform(500, 5000))).quantize(Decimal("0.01"))
            description = rng.choice([
                "CUSTOMER DEPOSIT",
                "WIRE TRANSFER IN",
                "ACH CREDIT",
                "REFUND",
            ])
            running_balance += amount
            category = "1200"  # AR
        else:
            # Expense
            category = rng.choice(list(VENDORS.keys()))
            vendor_name, expense_cat, (min_amt, max_amt) = rng.choice(VENDORS[category])
            amount = Decimal(str(rng.uniform(min_amt, max_amt))).quantize(Decimal("0.01"))
            description = f"{vendor_name.upper()} PAYMENT"
            running_balance -= amount
            category = expense_cat.value
        
        txn_date = start + timedelta(days=rng.randint(0, 30))
        
        txn_lines.append({
            "date": str(txn_date),
            "description": description,
            "amount": str(amount),
            "type": "credit" if is_credit else "debit",
            "balance": str(running_balance),
            "category": category,
        })
    
    # Sort by date
    txn_lines.sort(key=lambda x: x["date"])
    
    # Build statement content
    content_lines = [
        f"BANK STATEMENT",
        f"Account: Business Checking ****1234",
        f"Period: {start} to {end}",
        f"Opening Balance: $10,000.00",
        f"",
        f"DATE        DESCRIPTION                    AMOUNT      BALANCE",
        f"-" * 70,
    ]
    
    for txn in txn_lines:
        sign = "+" if txn["type"] == "credit" else "-"
        content_lines.append(
            f"{txn['date']}  {txn['description'][:30]:<30}  {sign}${txn['amount']:>10}  ${txn['balance']:>10}"
        )
    
    content_lines.append(f"-" * 70)
    content_lines.append(f"Closing Balance: ${running_balance}")
    
    content = "\n".join(content_lines)
    
    docs = [SyntheticDocument(
        id=_generate_id("stmt", seed, 0),
        filename=f"bank_statement_{start.strftime('%Y%m')}.csv",
        category=DocumentCategory.BANK_STATEMENT,
        content=content,
        expected_vendor="Demo Bank",
        expected_amount=abs(running_balance - Decimal("10000")),
        expected_currency="USD",
        expected_date=str(end),
        metadata={
            "opening_balance": "10000.00",
            "closing_balance": str(running_balance),
            "transaction_count": transaction_count,
            "transactions": txn_lines,
        },
    )]
    
    return docs


def _generate_transactions_from_docs(
    docs: List[SyntheticDocument],
) -> List[GroundTruthTransaction]:
    """Generate ground truth transactions from documents."""
    transactions = []
    
    for doc in docs:
        txn_type = "debit"
        if doc.category == DocumentCategory.BANK_STATEMENT:
            # Bank statements have multiple transactions
            for i, txn in enumerate(doc.metadata.get("transactions", [])):
                transactions.append(GroundTruthTransaction(
                    id=f"txn-{doc.id}-{i}",
                    source_document_id=doc.id,
                    description=txn.get("description", f"Transaction from {doc.filename}"),
                    amount=Decimal(txn.get("amount", "0")),
                    currency="USD",
                    date=txn.get("date", doc.expected_date or ""),
                    category_code=txn.get("category", "9000"),
                    vendor_name=doc.expected_vendor,
                    transaction_type=txn.get("type", "debit"),
                ))
        else:
            transactions.append(GroundTruthTransaction(
                id=f"txn-{doc.id}",
                source_document_id=doc.id,
                description=f"Transaction from {doc.expected_vendor}",
                amount=doc.expected_amount,
                currency=doc.expected_currency,
                date=doc.expected_date or "",
                category_code=doc.expected_category_code,
                vendor_name=doc.expected_vendor,
                transaction_type=txn_type,
            ))
    
    return transactions


def _generate_journal_entries_from_transactions(
    transactions: List[GroundTruthTransaction],
) -> List[ExpectedJournalEntry]:
    """Generate expected journal entries from transactions."""
    entries = []
    
    for txn in transactions:
        lines = []
        
        if txn.transaction_type == "credit":
            # Money coming in: DR Bank, CR Revenue/AR
            lines = [
                ExpectedJournalLine(
                    account_code="1000",
                    account_name="Cash/Bank",
                    side="debit",
                    amount=txn.amount,
                ),
                ExpectedJournalLine(
                    account_code=txn.category_code or "1200",
                    account_name=ACCOUNT_NAMES.get(txn.category_code, "Revenue"),
                    side="credit",
                    amount=txn.amount,
                ),
            ]
        else:
            # Money going out: DR Expense, CR Bank
            lines = [
                ExpectedJournalLine(
                    account_code=txn.category_code or "5000",
                    account_name=ACCOUNT_NAMES.get(txn.category_code, "Expense"),
                    side="debit",
                    amount=txn.amount,
                ),
                ExpectedJournalLine(
                    account_code="1000",
                    account_name="Cash/Bank",
                    side="credit",
                    amount=txn.amount,
                ),
            ]
        
        entries.append(ExpectedJournalEntry(
            entry_id=f"je-{txn.id}",
            source_transaction_id=txn.id,
            date=txn.date,
            description=txn.description,
            lines=lines,
            is_balanced=True,
            total_debits=txn.amount,
            total_credits=txn.amount,
        ))
    
    return entries


def _generate_compliance_result(
    transactions: List[GroundTruthTransaction],
) -> ExpectedComplianceResult:
    """Generate expected compliance result."""
    issues = []
    
    for txn in transactions:
        # Check for high-value transactions
        if txn.amount > Decimal("10000"):
            issues.append(ExpectedComplianceIssue(
                code="HIGH_VALUE_TRANSACTION",
                severity="medium",
                message=f"Transaction exceeds $10,000 threshold",
                transaction_id=txn.id,
            ))
        
        # Check for uncategorized
        if txn.category_code == "9000":
            issues.append(ExpectedComplianceIssue(
                code="UNCATEGORIZED_EXPENSE",
                severity="low",
                message=f"Transaction not categorized",
                transaction_id=txn.id,
            ))
    
    return ExpectedComplianceResult(
        is_compliant=len([i for i in issues if i.severity in ["high", "critical"]]) == 0,
        issues=issues,
    )


def _generate_audit_result(
    transactions: List[GroundTruthTransaction],
) -> ExpectedAuditResult:
    """Generate expected audit result."""
    findings = []
    
    # Calculate average for anomaly detection
    amounts = [txn.amount for txn in transactions]
    if amounts:
        avg = sum(amounts) / len(amounts)
        
        for txn in transactions:
            if txn.amount > avg * Decimal("3"):
                findings.append(ExpectedAuditFinding(
                    code="UNUSUAL_SCALE",
                    severity="medium",
                    message=f"Transaction 3x above average",
                    transaction_id=txn.id,
                ))
    
    # Determine risk level
    if len([f for f in findings if f.severity in ["high", "critical"]]) > 0:
        risk_level = "high"
    elif len(findings) > 3:
        risk_level = "medium"
    else:
        risk_level = "low"
    
    return ExpectedAuditResult(
        risk_level=risk_level,
        findings=findings,
    )


def generate_scenario_monthly_bookkeeping(
    seed: int,
    month_date: Optional[date] = None,
) -> SyntheticScenario:
    """
    Generate a complete monthly bookkeeping scenario.
    
    Args:
        seed: Random seed for reproducibility
        month_date: First day of the month
    
    Returns:
        Complete SyntheticScenario with all components
    """
    start = month_date or (date.today().replace(day=1) - timedelta(days=30))
    
    # Generate documents
    receipts = generate_receipt_docs_for_scenario(seed, count=5, start_date=start)
    invoices = generate_invoice_docs_for_scenario(seed, count=3, start_date=start)
    statements = generate_bank_statement_docs_for_scenario(seed, transaction_count=10, start_date=start)
    
    all_docs = receipts + invoices + statements
    
    # Generate ground truth
    transactions = _generate_transactions_from_docs(all_docs)
    entries = _generate_journal_entries_from_transactions(transactions)
    compliance = _generate_compliance_result(transactions)
    audit = _generate_audit_result(transactions)
    
    # Calculate totals
    total_expenses = sum(
        txn.amount for txn in transactions 
        if txn.transaction_type == "debit"
    )
    total_revenue = sum(
        txn.amount for txn in transactions 
        if txn.transaction_type == "credit"
    )
    
    return SyntheticScenario(
        id=f"scenario-{seed}",
        name=f"Monthly Bookkeeping {start.strftime('%B %Y')}",
        description=f"Synthetic bookkeeping scenario for {start.strftime('%B %Y')}",
        seed=seed,
        documents=all_docs,
        transactions=transactions,
        journal_entries=entries,
        compliance=compliance,
        audit=audit,
        total_expenses=total_expenses,
        total_revenue=total_revenue,
        net_income=total_revenue - total_expenses,
    )
