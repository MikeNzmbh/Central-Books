"""
Receipts Workflow

End-to-end workflow for processing uploaded receipts/documents into
journal entries. This is the primary demo workflow for the agentic
accounting system.

Pipeline Steps:
1. Accept uploaded documents (RawDocument[])
2. Run extraction pipeline → ExtractedDocument[]
3. Normalize documents → NormalizedTransaction[]
4. Run AccountingAgent → JournalEntryProposal[]
5. (Future) Run ComplianceAgent → ComplianceCheckResult
6. (Future) Run AuditAgent → AuditReport
7. Return complete workflow result

Example usage:
    workflow = ReceiptsWorkflow(llm_client=openai_client)
    result = await workflow.run(documents=[raw_doc1, raw_doc2])
    
    print(f"Processed {len(result.transactions)} transactions")
    print(f"Generated {len(result.proposals)} journal entries")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4

from agentic_core.agents.accounting_agent import AccountingAgent
from agentic_core.models.audit import AuditReport
from agentic_core.models.base import AgentTrace
from agentic_core.models.compliance import ComplianceCheckResult
from agentic_core.models.documents import (
    DocumentType,
    ExtractedDocument,
    ExtractedLineItem,
    ExtractionConfidence,
    RawDocument,
)
from agentic_core.models.ledger import (
    JournalEntryProposal,
    NormalizedTransaction,
    TransactionType,
)


@dataclass
class WorkflowResult:
    """
    Result of the receipts workflow execution.

    Contains all outputs from each stage of the pipeline along with
    execution metadata.

    Attributes:
        workflow_id: Unique identifier for this workflow run.
        status: Final status ("success", "partial", "error").
        summary: Human-readable summary of what was processed.
        documents_received: Count of input documents.
        documents_extracted: Count of successfully extracted documents.
        transactions: Normalized transactions.
        proposals: Generated journal entry proposals.
        trace: Accounting agent execution trace.
        compliance_result: Compliance check result (Phase 2).
        audit_report: Audit findings (Phase 2).
        errors: Any errors encountered.
        started_at: When the workflow started.
        completed_at: When the workflow completed.
        duration_ms: Total execution time.
    """

    workflow_id: str = field(default_factory=lambda: str(uuid4()))
    status: str = "pending"
    summary: str = ""
    documents_received: int = 0
    documents_extracted: int = 0
    transactions: list[NormalizedTransaction] = field(default_factory=list)
    proposals: list[JournalEntryProposal] = field(default_factory=list)
    trace: Optional[AgentTrace] = None
    compliance_result: Optional[ComplianceCheckResult] = None
    audit_report: Optional[AuditReport] = None
    errors: list[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0

    def complete(self, status: str = "success") -> None:
        """Mark the workflow as complete."""
        self.completed_at = datetime.utcnow()
        if self.started_at:
            self.duration_ms = (
                (self.completed_at - self.started_at).total_seconds() * 1000
            )
        self.status = status

    def generate_summary(self) -> str:
        """Generate a summary of the workflow execution."""
        parts = [
            f"Processed {self.documents_received} document(s).",
            f"Extracted {self.documents_extracted} document(s) successfully.",
            f"Created {len(self.transactions)} normalized transaction(s).",
            f"Generated {len(self.proposals)} journal entry proposal(s).",
        ]
        if self.errors:
            parts.append(f"Encountered {len(self.errors)} error(s).")
        return " ".join(parts)


# =============================================================================
# PLACEHOLDER FUNCTIONS - To be replaced with real implementations
# =============================================================================


async def extract_documents(
    documents: list[RawDocument],
) -> list[ExtractedDocument]:
    """
    Placeholder: Extract structured data from raw documents.

    TODO (Phase 2): Integrate with:
    - OpenAI Vision API for receipt/invoice OCR
    - AWS Textract or Google Document AI
    - Custom fine-tuned extraction models

    For now, returns mock extracted data for demonstration.
    """
    extracted = []

    for doc in documents:
        # Create mock extraction based on document type
        mock_type = DocumentType.RECEIPT
        if "invoice" in doc.filename.lower():
            mock_type = DocumentType.INVOICE

        extraction = ExtractedDocument(
            source_document_id=doc.document_id,
            document_type=mock_type,
            vendor_name=f"Vendor from {doc.filename}",
            document_date=date.today(),
            currency="USD",
            total_amount=Decimal("100.00"),  # Placeholder amount
            line_items=[
                ExtractedLineItem(
                    description=f"Item from {doc.filename}",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    total_amount=Decimal("100.00"),
                    confidence=ExtractionConfidence.MEDIUM,
                )
            ],
            confidence=ExtractionConfidence.MEDIUM,
            extraction_model="placeholder_v0",
            extraction_warnings=["This is placeholder extraction - implement OCR"],
        )
        extracted.append(extraction)

    return extracted


async def normalize_documents_to_transactions(
    documents: list[ExtractedDocument],
) -> list[NormalizedTransaction]:
    """
    Normalize extracted documents into standardized transactions.

    TODO (Phase 2): Implement:
    - Vendor matching/deduplication
    - Category inference from historical data
    - Account code suggestions from ML model
    - Tax code detection

    For now, creates basic transactions from extracted data.
    """
    transactions = []

    for doc in documents:
        # Determine transaction type from document type
        txn_type = TransactionType.EXPENSE
        if doc.document_type == DocumentType.INVOICE:
            # Could be income if it's a customer invoice
            txn_type = TransactionType.EXPENSE  # Assume expense for receipts

        # Create normalized transaction
        txn = NormalizedTransaction(
            source_type="document",
            source_id=doc.extraction_id,
            transaction_type=txn_type,
            transaction_date=doc.document_date or date.today(),
            amount=doc.total_amount,
            currency=doc.currency,
            description=f"{doc.document_type.value.title()} from {doc.vendor_name or 'Unknown'}",
            payee_name=doc.vendor_name,
            category_hint="Office Supplies" if not doc.vendor_name else None,
            tax_amount=doc.tax_total,
            reference_number=doc.document_number,
            metadata={
                "line_items": len(doc.line_items),
                "extraction_confidence": doc.confidence.value,
            },
        )
        transactions.append(txn)

    return transactions


# =============================================================================
# MAIN WORKFLOW CLASS
# =============================================================================


class ReceiptsWorkflow:
    """
    End-to-end workflow for receipt/document processing.

    This workflow orchestrates the complete pipeline from document
    upload to journal entry generation.

    Stages:
    1. Document ingestion (RawDocument[])
    2. Document extraction (→ ExtractedDocument[])
    3. Transaction normalization (→ NormalizedTransaction[])
    4. Journal entry generation (→ JournalEntryProposal[])
    5. [Future] Compliance checking
    6. [Future] Audit analysis

    Attributes:
        accounting_agent: The accounting agent for entry generation.
        chart_of_accounts: Optional chart of accounts data.
        business_context: Optional business context string.
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        chart_of_accounts: Optional[list[dict[str, Any]]] = None,
        business_context: Optional[str] = None,
    ):
        """
        Initialize the receipts workflow.

        Args:
            llm_client: OpenAI-compatible LLM client.
            chart_of_accounts: Available accounts for mapping.
            business_context: Context about the business.
        """
        self.accounting_agent = AccountingAgent(llm_client=llm_client)
        self.chart_of_accounts = chart_of_accounts
        self.business_context = business_context

    async def run(
        self,
        documents: list[RawDocument],
    ) -> WorkflowResult:
        """
        Execute the complete receipts workflow.

        Args:
            documents: List of raw uploaded documents.

        Returns:
            WorkflowResult with all outputs and metadata.
        """
        result = WorkflowResult(
            started_at=datetime.utcnow(),
            documents_received=len(documents),
        )

        try:
            # Stage 1: Extract documents
            extracted_docs = await extract_documents(documents)
            result.documents_extracted = len(extracted_docs)

            # Stage 2: Normalize to transactions
            transactions = await normalize_documents_to_transactions(extracted_docs)
            result.transactions = transactions

            # Stage 3: Generate journal entries
            proposals, trace = await self.accounting_agent.execute(
                transactions=transactions,
                chart_of_accounts=self.chart_of_accounts,
                business_context=self.business_context,
                input_summary=f"Processing {len(transactions)} transactions",
            )
            result.proposals = proposals
            result.trace = trace

            # Stage 4: [Future] Run compliance checks
            # result.compliance_result = await self.compliance_agent.execute(...)

            # Stage 5: [Future] Run audit analysis
            # result.audit_report = await self.audit_agent.execute(...)

            # Generate summary
            result.summary = result.generate_summary()
            result.complete(status="success")

        except Exception as e:
            result.errors.append(str(e))
            result.complete(status="error")

        return result

    async def run_demo(
        self,
        demo_files: Optional[list[str]] = None,
    ) -> WorkflowResult:
        """
        Run a demo version with synthetic documents.

        Useful for testing and demonstration purposes.

        Args:
            demo_files: Optional list of demo filenames.

        Returns:
            WorkflowResult with demo data.
        """
        demo_files = demo_files or [
            "office_supplies_receipt.pdf",
            "software_subscription_invoice.pdf",
            "travel_expense_receipt.jpg",
        ]

        # Create mock documents
        documents = [
            RawDocument(
                filename=filename,
                mime_type="application/pdf" if filename.endswith(".pdf") else "image/jpeg",
                file_size_bytes=1024,
                storage_path=f"/demo/uploads/{filename}",
                tags=["demo"],
            )
            for filename in demo_files
        ]

        return await self.run(documents)


# =============================================================================
# CLI EXAMPLE
# =============================================================================


async def main():
    """
    Example CLI for running the receipts workflow.

    Run with: python -m agentic_core.workflows.receipts_workflow
    """
    print("=" * 60)
    print("Agentic Accounting OS - Receipts Workflow Demo")
    print("=" * 60)
    print()

    # Create workflow (without LLM client for demo)
    workflow = ReceiptsWorkflow()

    # Run demo
    print("Running demo with synthetic documents...")
    result = await workflow.run_demo()

    # Print results
    print()
    print(f"Status: {result.status}")
    print(f"Summary: {result.summary}")
    print(f"Duration: {result.duration_ms:.2f}ms")
    print()

    print("Normalized Transactions:")
    for txn in result.transactions:
        print(f"  - {txn.description}: {txn.amount} {txn.currency}")

    print()
    print("Journal Entry Proposals:")
    for proposal in result.proposals:
        print(f"  Entry: {proposal.description}")
        for line in proposal.lines:
            dr_cr = f"DR {line.debit}" if line.is_debit else f"CR {line.credit}"
            print(f"    {line.account_code}: {dr_cr}")
        is_balanced = "✓" if proposal.is_balanced else "✗"
        print(f"    Balanced: {is_balanced}")

    if result.trace:
        print()
        print("Agent Trace:")
        print(f"  LLM Calls: {len(result.trace.llm_calls)}")
        print(f"  Steps: {len(result.trace.steps)}")
        print(f"  Total Tokens: {result.trace.total_tokens_used}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
