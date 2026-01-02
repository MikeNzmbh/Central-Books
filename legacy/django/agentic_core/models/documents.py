"""
Document models for the ingestion and extraction pipeline.

These models represent documents at various stages of processing:
- RawDocument: The original uploaded file
- ExtractedDocument: Parsed/OCR'd document with structured data
- ExtractedLineItem: Individual line items from invoices/receipts
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Known document types for classification."""

    RECEIPT = "receipt"
    INVOICE = "invoice"
    BANK_STATEMENT = "bank_statement"
    CREDIT_CARD_STATEMENT = "credit_card_statement"
    CONTRACT = "contract"
    TAX_FORM = "tax_form"
    PAYROLL = "payroll"
    OTHER = "other"
    UNKNOWN = "unknown"


class ExtractionConfidence(str, Enum):
    """Confidence level for extracted data."""

    HIGH = "high"  # > 90% confidence
    MEDIUM = "medium"  # 70-90% confidence
    LOW = "low"  # < 70% confidence
    MANUAL_REVIEW = "manual_review"  # Needs human review


class RawDocument(BaseModel):
    """
    Represents a raw uploaded document before processing.

    This is the entry point for documents into the agentic pipeline.
    The document will be processed by OCR/extraction agents to produce
    an ExtractedDocument.

    Attributes:
        document_id: Unique identifier for this document.
        filename: Original filename.
        mime_type: MIME type (e.g., "application/pdf", "image/jpeg").
        file_size_bytes: Size of the file in bytes.
        storage_path: Path or URL where the file is stored.
        uploaded_at: When the document was uploaded.
        uploaded_by: User ID who uploaded the document.
        business_id: Associated business ID.
        tags: User-defined tags for organization.
        metadata: Additional metadata from upload context.
    """

    document_id: str = Field(default_factory=lambda: str(uuid4()))
    filename: str
    mime_type: str
    file_size_bytes: int = 0
    storage_path: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    uploaded_by: Optional[str] = None
    business_id: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ExtractedLineItem(BaseModel):
    """
    A single line item extracted from an invoice or receipt.

    Represents one product/service entry with quantity, price, and totals.

    Attributes:
        line_id: Unique identifier for this line item.
        description: Text description of the item/service.
        quantity: Number of units (defaults to 1).
        unit_price: Price per unit.
        total_amount: Total for this line (quantity × unit_price).
        tax_amount: Tax amount if separately stated.
        tax_rate: Tax rate percentage if detected.
        category_hint: Suggested expense category from extraction.
        account_code_hint: Suggested account code from extraction.
        confidence: Extraction confidence level.
        raw_text: Original text this was extracted from.
    """

    line_id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = Decimal("0")
    total_amount: Decimal = Decimal("0")
    tax_amount: Optional[Decimal] = None
    tax_rate: Optional[Decimal] = None
    category_hint: Optional[str] = None
    account_code_hint: Optional[str] = None
    confidence: ExtractionConfidence = ExtractionConfidence.MEDIUM
    raw_text: Optional[str] = None

    class Config:
        json_encoders = {Decimal: lambda v: str(v)}


class ExtractedDocument(BaseModel):
    """
    A document after OCR/extraction processing.

    Contains all structured data extracted from the raw document,
    ready for normalization and accounting processing.

    Attributes:
        extraction_id: Unique identifier for this extraction.
        source_document_id: Reference to the original RawDocument.
        document_type: Detected document type.
        vendor_name: Extracted vendor/payee name.
        vendor_address: Extracted vendor address.
        vendor_tax_id: Vendor tax ID if present.
        document_date: Date on the document.
        due_date: Due date for invoices.
        document_number: Invoice/receipt number.
        currency: Currency code (e.g., "USD", "CAD").
        subtotal: Subtotal before tax.
        tax_total: Total tax amount.
        total_amount: Grand total.
        payment_method: Detected payment method.
        line_items: Individual line items.
        raw_text: Full OCR text.
        confidence: Overall extraction confidence.
        extraction_warnings: Any issues during extraction.
        extracted_at: When extraction was performed.
        extraction_model: Model/method used for extraction.
    """

    extraction_id: str = Field(default_factory=lambda: str(uuid4()))
    source_document_id: str
    document_type: DocumentType = DocumentType.UNKNOWN
    vendor_name: Optional[str] = None
    vendor_address: Optional[str] = None
    vendor_tax_id: Optional[str] = None
    document_date: Optional[date] = None
    due_date: Optional[date] = None
    document_number: Optional[str] = None
    currency: str = "USD"
    subtotal: Optional[Decimal] = None
    tax_total: Optional[Decimal] = None
    total_amount: Decimal = Decimal("0")
    payment_method: Optional[str] = None
    line_items: list[ExtractedLineItem] = Field(default_factory=list)
    raw_text: Optional[str] = None
    confidence: ExtractionConfidence = ExtractionConfidence.MEDIUM
    extraction_warnings: list[str] = Field(default_factory=list)
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    extraction_model: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            Decimal: lambda v: str(v),
        }

    @property
    def has_line_items(self) -> bool:
        """Check if this document has line items."""
        return len(self.line_items) > 0

    @property
    def calculated_total(self) -> Decimal:
        """Sum of all line item totals."""
        return sum((item.total_amount for item in self.line_items), Decimal("0"))
