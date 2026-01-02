"""
Invoice Processing Pipeline - End-to-End Workflow

Pipeline: invoice document → parse → extract_lines → classify → tax_extract 
         → vendor_match → journal_entries → compliance → audit

This workflow handles invoice documents with:
- Line-item extraction and classification
- Tax amount detection
- Vendor recognition and matching
- Invoice-to-payment matching proposals
- Journal entry generation with AP/AR handling
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date, datetime
from uuid import uuid4

from agentic.workflows.graph import WorkflowGraph
from agentic.engine.compliance import run_basic_compliance_checks
from agentic.engine.audit import run_basic_audit_checks


# =============================================================================
# INVOICE DATA MODELS
# =============================================================================


@dataclass
class InvoiceLineItem:
    """A single line item from an invoice."""
    
    line_number: int
    description: str
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")
    category_code: str = "5000"  # COGS default
    tax_rate: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    
    def model_dump(self) -> dict:
        return {
            "line_number": self.line_number,
            "description": self.description,
            "quantity": str(self.quantity),
            "unit_price": str(self.unit_price),
            "amount": str(self.amount),
            "category_code": self.category_code,
            "tax_rate": str(self.tax_rate),
            "tax_amount": str(self.tax_amount),
        }


@dataclass
class ExtractedInvoice:
    """Structured data extracted from an invoice document."""
    
    id: str
    raw_document_id: str
    invoice_number: str = ""
    vendor_name: str = "Unknown Vendor"
    vendor_id: Optional[str] = None
    invoice_date: str = ""
    due_date: str = ""
    subtotal: Decimal = Decimal("0")
    tax_total: Decimal = Decimal("0")
    total_amount: Decimal = Decimal("0")
    currency: str = "USD"
    line_items: List[InvoiceLineItem] = field(default_factory=list)
    payment_terms: str = "Net 30"
    is_payable: bool = True  # AP (we owe) vs AR (owed to us)
    
    def model_dump(self) -> dict:
        return {
            "id": self.id,
            "raw_document_id": self.raw_document_id,
            "invoice_number": self.invoice_number,
            "vendor_name": self.vendor_name,
            "vendor_id": self.vendor_id,
            "invoice_date": self.invoice_date,
            "due_date": self.due_date,
            "subtotal": str(self.subtotal),
            "tax_total": str(self.tax_total),
            "total_amount": str(self.total_amount),
            "currency": self.currency,
            "line_items": [li.model_dump() for li in self.line_items],
            "payment_terms": self.payment_terms,
            "is_payable": self.is_payable,
        }


@dataclass
class InvoiceTransaction:
    """Normalized invoice transaction for journal entry generation."""
    
    id: str
    invoice_id: str
    description: str
    amount: Decimal
    tax_amount: Decimal = Decimal("0")
    currency: str = "USD"
    date: str = ""
    category_code: str = "5000"
    vendor_id: Optional[str] = None
    is_payable: bool = True
    
    def model_dump(self) -> dict:
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "description": self.description,
            "amount": str(self.amount),
            "tax_amount": str(self.tax_amount),
            "currency": self.currency,
            "date": self.date,
            "category_code": self.category_code,
            "vendor_id": self.vendor_id,
            "is_payable": self.is_payable,
        }


@dataclass 
class InvoiceJournalLine:
    """A line in an invoice journal entry."""
    
    account_code: str
    account_name: str
    side: str  # "debit" or "credit"
    amount: Decimal
    
    def model_dump(self) -> dict:
        return {
            "account_code": self.account_code,
            "account_name": self.account_name,
            "side": self.side,
            "amount": str(self.amount),
        }


@dataclass
class InvoiceJournalEntry:
    """Journal entry for an invoice."""
    
    entry_id: str
    date: str
    description: str
    invoice_id: str
    lines: List[InvoiceJournalLine] = field(default_factory=list)
    is_balanced: bool = True
    total_debits: Decimal = Decimal("0")
    total_credits: Decimal = Decimal("0")
    
    def model_dump(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "date": self.date,
            "description": self.description,
            "invoice_id": self.invoice_id,
            "lines": [line.model_dump() for line in self.lines],
            "is_balanced": self.is_balanced,
            "total_debits": str(self.total_debits),
            "total_credits": str(self.total_credits),
        }


@dataclass
class PaymentMatch:
    """Proposed match between invoice and payment."""
    
    invoice_id: str
    payment_id: Optional[str]
    match_confidence: float
    amount_matched: Decimal
    remaining_balance: Decimal
    match_type: str  # "full", "partial", "unmatched"
    
    def model_dump(self) -> dict:
        return {
            "invoice_id": self.invoice_id,
            "payment_id": self.payment_id,
            "match_confidence": self.match_confidence,
            "amount_matched": str(self.amount_matched),
            "remaining_balance": str(self.remaining_balance),
            "match_type": self.match_type,
        }


# =============================================================================
# DEMO DATA FOR DETERMINISTIC EXTRACTION
# =============================================================================

DEMO_VENDORS = {
    "acme": {
        "name": "ACME Corp",
        "id": "vendor-001",
        "default_category": "5100",  # Raw Materials
    },
    "office": {
        "name": "Office Supplies Inc",
        "id": "vendor-002",
        "default_category": "6100",  # Office Supplies
    },
    "tech": {
        "name": "TechServe Solutions",
        "id": "vendor-003",
        "default_category": "6300",  # Software
    },
    "shipping": {
        "name": "FastShip Logistics",
        "id": "vendor-004",
        "default_category": "5200",  # Shipping
    },
}

CATEGORY_MAPPING = {
    "5000": "Cost of Goods Sold",
    "5100": "Raw Materials",
    "5200": "Shipping & Freight",
    "6000": "Operating Expenses",
    "6100": "Office Supplies",
    "6200": "Travel & Entertainment",
    "6300": "Software & Subscriptions",
    "2100": "Accounts Payable",
    "1200": "Accounts Receivable",
    "2200": "Sales Tax Payable",
    "1000": "Cash/Bank",
}


def _get_demo_vendor(filename: str) -> dict:
    """Get vendor info based on filename keywords."""
    filename_lower = filename.lower()
    for keyword, vendor in DEMO_VENDORS.items():
        if keyword in filename_lower:
            return vendor
    return {"name": "Generic Vendor", "id": "vendor-999", "default_category": "5000"}


def _generate_demo_line_items(vendor_category: str, total: Decimal) -> List[InvoiceLineItem]:
    """Generate demo line items for an invoice."""
    # Split total into 2-3 line items
    if total < Decimal("100"):
        return [
            InvoiceLineItem(
                line_number=1,
                description="Service/Product",
                quantity=Decimal("1"),
                unit_price=total,
                amount=total,
                category_code=vendor_category,
            )
        ]
    
    line1_amount = (total * Decimal("0.6")).quantize(Decimal("0.01"))
    line2_amount = (total - line1_amount).quantize(Decimal("0.01"))
    
    return [
        InvoiceLineItem(
            line_number=1,
            description="Primary Service/Product",
            quantity=Decimal("1"),
            unit_price=line1_amount,
            amount=line1_amount,
            category_code=vendor_category,
        ),
        InvoiceLineItem(
            line_number=2,
            description="Additional Items",
            quantity=Decimal("1"),
            unit_price=line2_amount,
            amount=line2_amount,
            category_code=vendor_category,
        ),
    ]


# =============================================================================
# WORKFLOW STEPS
# =============================================================================


def ingest_invoice_step(context: Dict[str, Any]) -> None:
    """
    Convert uploaded invoice files to raw document objects.
    
    Input: context["uploaded_files"]
    Output: context["invoice_documents"]
    """
    uploaded = context.get("uploaded_files", [])
    docs = []
    
    for idx, f in enumerate(uploaded):
        if isinstance(f, dict):
            filename = f.get("filename", f"invoice-{idx + 1}.pdf")
            content = f.get("content", "")
        else:
            filename = getattr(f, "name", f"invoice-{idx + 1}.pdf")
            content = ""
        
        docs.append({
            "id": f"inv-doc-{idx + 1}",
            "filename": filename,
            "content": content,
            "source": "upload",
            "document_type": "invoice",
        })
    
    context["invoice_documents"] = docs


def extract_invoice_step(context: Dict[str, Any]) -> None:
    """
    Extract structured data from invoice documents.
    
    Uses deterministic demo extraction.
    Real implementation would use OCR + LLM.
    
    Input: context["invoice_documents"]
    Output: context["extracted_invoices"]
    """
    docs = context.get("invoice_documents", [])
    extracted = []
    today = str(date.today())
    
    for doc in docs:
        vendor = _get_demo_vendor(doc["filename"])
        
        # Generate demo amounts
        base_amount = Decimal("500.00") + Decimal(str(hash(doc["id"]) % 1000))
        tax_rate = Decimal("0.08")  # 8% tax
        tax_amount = (base_amount * tax_rate).quantize(Decimal("0.01"))
        total = base_amount + tax_amount
        
        line_items = _generate_demo_line_items(vendor["default_category"], base_amount)
        
        # Apply tax to line items
        for item in line_items:
            item.tax_rate = tax_rate
            item.tax_amount = (item.amount * tax_rate).quantize(Decimal("0.01"))
        
        extracted.append(ExtractedInvoice(
            id=doc["id"].replace("inv-doc", "ext-inv"),
            raw_document_id=doc["id"],
            invoice_number=f"INV-{datetime.now().strftime('%Y%m%d')}-{doc['id'][-1]}",
            vendor_name=vendor["name"],
            vendor_id=vendor["id"],
            invoice_date=today,
            due_date=today,  # Would calculate based on payment terms
            subtotal=base_amount,
            tax_total=tax_amount,
            total_amount=total,
            currency="USD",
            line_items=line_items,
            payment_terms="Net 30",
            is_payable=True,
        ))
    
    context["extracted_invoices"] = extracted


def classify_lines_step(context: Dict[str, Any]) -> None:
    """
    Classify invoice line items into expense categories.
    
    Input: context["extracted_invoices"]
    Output: context["classified_invoices"] (invoices with updated category codes)
    """
    invoices = context.get("extracted_invoices", [])
    
    # In demo mode, categories are already assigned
    # Real implementation would use LLM classification
    
    for inv in invoices:
        for line_item in inv.line_items:
            # Ensure category is valid
            if line_item.category_code not in CATEGORY_MAPPING:
                line_item.category_code = "5000"  # Default to COGS
    
    context["classified_invoices"] = invoices


def extract_tax_step(context: Dict[str, Any]) -> None:
    """
    Extract and validate tax information from invoices.
    
    Input: context["classified_invoices"]
    Output: context["tax_validated_invoices"]
    """
    invoices = context.get("classified_invoices", [])
    
    for inv in invoices:
        # Recalculate tax totals from line items
        calculated_tax = sum(
            item.tax_amount for item in inv.line_items
        )
        
        # Validate tax total matches
        if abs(calculated_tax - inv.tax_total) > Decimal("0.02"):
            # Would flag for review in production
            inv.tax_total = calculated_tax
    
    context["tax_validated_invoices"] = invoices


def match_vendor_step(context: Dict[str, Any]) -> None:
    """
    Match invoice vendors to known vendor database.
    
    Input: context["tax_validated_invoices"]
    Output: context["vendor_matched_invoices"]
    """
    invoices = context.get("tax_validated_invoices", [])
    
    # In demo mode, vendors are already matched
    # Real implementation would do fuzzy matching against vendor DB
    
    context["vendor_matched_invoices"] = invoices


def normalize_invoice_step(context: Dict[str, Any]) -> None:
    """
    Normalize invoices into transaction format for journal entry generation.
    
    Input: context["vendor_matched_invoices"]
    Output: context["invoice_transactions"]
    """
    invoices = context.get("vendor_matched_invoices", [])
    transactions = []
    
    for inv in invoices:
        transactions.append(InvoiceTransaction(
            id=f"txn-{inv.id}",
            invoice_id=inv.id,
            description=f"Invoice {inv.invoice_number} from {inv.vendor_name}",
            amount=inv.subtotal,
            tax_amount=inv.tax_total,
            currency=inv.currency,
            date=inv.invoice_date,
            category_code=inv.line_items[0].category_code if inv.line_items else "5000",
            vendor_id=inv.vendor_id,
            is_payable=inv.is_payable,
        ))
    
    context["invoice_transactions"] = transactions


def generate_invoice_entries_step(context: Dict[str, Any]) -> None:
    """
    Generate journal entries for invoices.
    
    For AP (payable) invoices:
    - DR: Expense accounts (by category)
    - DR: Sales Tax Receivable (if applicable)
    - CR: Accounts Payable
    
    Input: context["invoice_transactions"], context["vendor_matched_invoices"]
    Output: context["journal_entries"]
    """
    transactions = context.get("invoice_transactions", [])
    invoices = context.get("vendor_matched_invoices", [])
    
    # Build invoice lookup
    invoice_lookup = {inv.id: inv for inv in invoices}
    
    entries = []
    
    for txn in transactions:
        inv = invoice_lookup.get(txn.invoice_id)
        if not inv:
            continue
        
        lines = []
        total_debits = Decimal("0")
        total_credits = Decimal("0")
        
        if txn.is_payable:
            # Accounts Payable entry
            # Debit expense accounts for each line item
            for item in inv.line_items:
                category_name = CATEGORY_MAPPING.get(item.category_code, "Expense")
                lines.append(InvoiceJournalLine(
                    account_code=item.category_code,
                    account_name=category_name,
                    side="debit",
                    amount=item.amount,
                ))
                total_debits += item.amount
            
            # Debit sales tax if applicable
            if txn.tax_amount > 0:
                lines.append(InvoiceJournalLine(
                    account_code="1300",
                    account_name="Sales Tax Receivable",
                    side="debit",
                    amount=txn.tax_amount,
                ))
                total_debits += txn.tax_amount
            
            # Credit Accounts Payable
            total_payable = txn.amount + txn.tax_amount
            lines.append(InvoiceJournalLine(
                account_code="2100",
                account_name="Accounts Payable",
                side="credit",
                amount=total_payable,
            ))
            total_credits += total_payable
        
        is_balanced = total_debits == total_credits
        
        entries.append(InvoiceJournalEntry(
            entry_id=f"je-{txn.id}",
            date=txn.date,
            description=txn.description,
            invoice_id=txn.invoice_id,
            lines=lines,
            is_balanced=is_balanced,
            total_debits=total_debits,
            total_credits=total_credits,
        ))
    
    context["journal_entries"] = entries


def match_payments_step(context: Dict[str, Any]) -> None:
    """
    Match invoices to existing payments (proposal only).
    
    Input: context["vendor_matched_invoices"]
    Output: context["payment_matches"]
    """
    invoices = context.get("vendor_matched_invoices", [])
    
    # In demo mode, create unmatched proposals
    # Real implementation would query payment records
    matches = []
    
    for inv in invoices:
        matches.append(PaymentMatch(
            invoice_id=inv.id,
            payment_id=None,
            match_confidence=0.0,
            amount_matched=Decimal("0"),
            remaining_balance=inv.total_amount,
            match_type="unmatched",
        ))
    
    context["payment_matches"] = matches


def invoice_compliance_step(context: Dict[str, Any]) -> None:
    """
    Run compliance checks on invoice transactions and entries.
    
    Input: context["invoice_transactions"], context["journal_entries"]
    Output: context["compliance_result"]
    """
    transactions = context.get("invoice_transactions", [])
    entries = context.get("journal_entries", [])
    
    # Convert to format expected by compliance engine
    txn_dicts = [t.model_dump() for t in transactions]
    entry_dicts = [e.model_dump() for e in entries]
    
    result = run_basic_compliance_checks(txn_dicts, entry_dicts)
    context["compliance_result"] = result


def invoice_audit_step(context: Dict[str, Any]) -> None:
    """
    Run audit checks on invoice transactions and entries.
    
    Input: context["invoice_transactions"], context["journal_entries"]
    Output: context["audit_report"]
    """
    transactions = context.get("invoice_transactions", [])
    entries = context.get("journal_entries", [])
    
    txn_dicts = [t.model_dump() for t in transactions]
    entry_dicts = [e.model_dump() for e in entries]
    
    report = run_basic_audit_checks(txn_dicts, entry_dicts)
    context["audit_report"] = report


# =============================================================================
# WORKFLOW BUILDER
# =============================================================================


def build_invoice_workflow() -> WorkflowGraph:
    """
    Build the invoice processing workflow.
    
    Pipeline:
    1. ingest: uploaded_files → invoice_documents
    2. extract: invoice_documents → extracted_invoices
    3. classify_lines: extracted_invoices → classified_invoices
    4. extract_tax: classified_invoices → tax_validated_invoices
    5. match_vendor: tax_validated_invoices → vendor_matched_invoices
    6. normalize: vendor_matched_invoices → invoice_transactions
    7. generate_entries: invoice_transactions → journal_entries
    8. match_payments: vendor_matched_invoices → payment_matches
    9. compliance: Run compliance checks
    10. audit: Run audit checks
    
    Returns:
        Configured WorkflowGraph ready to run.
    """
    wf = WorkflowGraph("invoice_processing")
    
    # Register steps
    wf.add_step("ingest", ingest_invoice_step)
    wf.add_step("extract", extract_invoice_step)
    wf.add_step("classify_lines", classify_lines_step)
    wf.add_step("extract_tax", extract_tax_step)
    wf.add_step("match_vendor", match_vendor_step)
    wf.add_step("normalize", normalize_invoice_step)
    wf.add_step("generate_entries", generate_invoice_entries_step)
    wf.add_step("match_payments", match_payments_step)
    wf.add_step("compliance", invoice_compliance_step)
    wf.add_step("audit", invoice_audit_step)
    
    # Define dependencies
    wf.add_edge("ingest", "extract")
    wf.add_edge("extract", "classify_lines")
    wf.add_edge("classify_lines", "extract_tax")
    wf.add_edge("extract_tax", "match_vendor")
    wf.add_edge("match_vendor", "normalize")
    wf.add_edge("normalize", "generate_entries")
    wf.add_edge("match_vendor", "match_payments")
    wf.add_edge("generate_entries", "compliance")
    wf.add_edge("compliance", "audit")
    
    return wf
