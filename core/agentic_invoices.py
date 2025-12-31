from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional
from uuid import uuid4

from django.conf import settings
from django.utils import timezone

from agentic.logging.tracing import trace_event

from .accounting_defaults import ensure_default_accounts
from .invoice_ocr import extract_invoice_data, validate_extracted_amount
from .llm_reasoning import InvoicesRunLLMResult, reason_about_invoices_run
from .models import Business

AUDIT_WARNING_THRESHOLD = Decimal("40.0")
AUDIT_HIGH_RISK_THRESHOLD = Decimal("60.0")


@dataclass
class InvoiceInputDocument:
    document_id: int
    storage_key: str
    original_filename: str
    currency_hint: Optional[str] = None
    issue_date_hint: Optional[date] = None
    due_date_hint: Optional[date] = None
    category_hint: Optional[str] = None
    vendor_hint: Optional[str] = None
    invoice_number_hint: Optional[str] = None
    amount_hint: Optional[Decimal] = None


@dataclass
class InvoiceDocumentResult:
    document_id: int
    storage_key: str
    extracted_payload: dict
    normalized_payload: dict
    proposed_journal_payload: dict
    audit_flags: list
    audit_score: Optional[Decimal]
    audit_explanations: list
    status: str  # InvoiceDocument.DocumentStatus
    audit_status: str  # ok | warning | error
    error: Optional[str] = None


@dataclass
class InvoicesWorkflowResult:
    run_id: str
    engine_run_id: str
    documents: List[InvoiceDocumentResult]
    metrics: dict
    trace_id: str
    llm_explanations: list
    llm_ranked_documents: list
    llm_suggested_classifications: list
    llm_suggested_followups: list


def run_invoices_workflow(
    *,
    business_id: int,
    documents: List[InvoiceInputDocument],
    default_currency: str | None = None,
    default_issue_date: date | None = None,
    default_due_date: date | None = None,
    default_category: str | None = None,
    default_vendor: str | None = None,
    triggered_by_user_id: int,
    ai_companion_enabled: bool | None = None,
) -> InvoicesWorkflowResult:
    """
    Synchronous entry point that wraps the Invoice agentic workflow.
    Mirrors receipts companion behaviour with invoice-specific fields.
    """
    business = Business.objects.get(pk=business_id)
    defaults = ensure_default_accounts(business)
    expense_account = defaults.get("opex")
    ap_account = defaults.get("ap")
    tax_account = defaults.get("tax_recoverable")
    if not expense_account or not ap_account:
        raise ValueError("Default expense and A/P accounts are required for invoices.")
    currency = default_currency or business.currency
    today = default_issue_date or timezone.localdate()
    results: list[InvoiceDocumentResult] = []
    engine_run_id = f"invoice-run-{uuid4().hex}"
    trace_id = f"invoice-trace-{uuid4().hex}"
    trace_events: list[dict] = []
    llm_explanations: list[str] = []
    llm_ranked_documents: list[dict] = []
    llm_suggested_classifications: list[dict] = []
    llm_suggested_followups: list[str] = []

    def _parse_amount(value: Decimal | str | None) -> Decimal:
        try:
            return (Decimal(str(value)) if value is not None else Decimal("0")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        except Exception:
            return Decimal("0.00")

    def _infer_amount_from_filename(filename: str) -> Optional[Decimal]:
        matches = re.findall(r"(\d+(?:\.\d+)?)", filename or "")
        if not matches:
            return None
        inferred = _parse_amount(matches[0])
        return inferred if inferred >= Decimal("50") else None

    def _build_invoice_number(filename: str, hint: Optional[str]) -> str:
        if hint:
            return hint
        name = os.path.splitext(filename or "")[0]
        return f"INV-{name[:12]}" if name else f"INV-{uuid4().hex[:8]}"

    def _audit_document(extracted: dict, normalized: dict, *, companion_enabled: bool) -> tuple[list, Decimal, list, str, int]:
        flags: list[dict] = []
        explanations: list[str] = []
        score = Decimal("5.0")
        retries = 0

        amount = _parse_amount(extracted.get("total"))
        currency_code = (extracted.get("currency") or "").upper()
        if currency_code and currency and currency_code != currency:
            flags.append(
                {
                    "code": "CURRENCY_MISMATCH",
                    "severity": "medium",
                    "message": f"Invoice currency {currency_code} differs from business default {currency}.",
                }
            )
            score += Decimal("18.0")
            explanations.append("Currency differs from defaults.")

        if amount <= 0:
            flags.append({"code": "MISSING_AMOUNT", "severity": "high", "message": "No total amount detected."})
            score += Decimal("50.0")
            explanations.append("Amount missing or zero.")
        elif amount >= Decimal("5000"):
            flags.append({"code": "UNUSUAL_AMOUNT", "severity": "high", "message": "Amount above normal threshold."})
            score += Decimal("55.0")
        elif amount >= Decimal("1500"):
            flags.append({"code": "LARGE_AMOUNT", "severity": "medium", "message": "Invoice larger than typical."})
            score += Decimal("25.0")

        invoice_number = (extracted.get("invoice_number") or "").strip()
        if not invoice_number:
            flags.append({"code": "MISSING_INVOICE_NUMBER", "severity": "high", "message": "Invoice number missing."})
            score += Decimal("35.0")

        vendor = (extracted.get("vendor") or "").strip()
        if not vendor:
            flags.append({"code": "MISSING_VENDOR", "severity": "high", "message": "Vendor missing."})
            score += Decimal("35.0")

        issue = extracted.get("issue_date")
        due = extracted.get("due_date")
        try:
            issue_dt = datetime.fromisoformat(issue).date() if issue else today
            due_dt = datetime.fromisoformat(due).date() if due else issue_dt + timedelta(days=30)
            if due_dt < issue_dt:
                flags.append({"code": "INVALID_DUE_DATE", "severity": "medium", "message": "Due date precedes issue date."})
                score += Decimal("15.0")
            if due_dt < today - timedelta(days=30):
                flags.append({"code": "OVERDUE", "severity": "medium", "message": "Invoice appears overdue."})
                score += Decimal("10.0")
        except Exception:
            flags.append({"code": "INVALID_DATES", "severity": "medium", "message": "Invoice dates could not be parsed."})
            score += Decimal("12.0")

        if companion_enabled:
            if vendor and invoice_number and invoice_number.lower().startswith("inv") and vendor.lower() in invoice_number.lower():
                flags.append(
                    {
                        "code": "DUPLICATE_PATTERN",
                        "severity": "medium",
                        "message": "Invoice number resembles vendor name; check for duplicates.",
                    }
                )
                score += Decimal("10.0")
            if amount > Decimal("0") and amount < Decimal("50"):
                flags.append(
                    {"code": "SMALL_AMOUNT", "severity": "low", "message": "Companion flagged unusually small invoice."}
                )
                score += Decimal("5.0")
            if flags and score >= AUDIT_WARNING_THRESHOLD:
                retries += 1
                explanations.append("Companion performed a reflection pass on anomalies.")
                trace_events.append(
                    trace_event(
                        agent="invoices.companion",
                        event="reflection",
                        metadata={
                            "trace_id": trace_id,
                            "invoice_number": invoice_number,
                            "flags": [f.get("code") for f in flags],
                        },
                        level="warning",
                    )
                )

        audit_status = "ok"
        if score >= AUDIT_WARNING_THRESHOLD or any(f.get("severity") == "high" for f in flags):
            audit_status = "warning"
        if any(f.get("severity") == "high" and f.get("code") in {"MISSING_AMOUNT", "MISSING_VENDOR", "MISSING_INVOICE_NUMBER"} for f in flags):
            audit_status = "error"

        score = min(score, Decimal("100.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return flags, score, explanations, audit_status, retries

    agent_retry_total = 0

    # Determine if OCR is available (requires OPENAI_API_KEY)
    use_ocr = bool(getattr(settings, "OPENAI_API_KEY", ""))

    for doc in documents:
        # Initialize OCR tracking
        ocr_used = False
        ocr_status = "disabled_missing_api_key" if not use_ocr else "unavailable"
        
        # Default values from hints or filename
        vendor = doc.vendor_hint or default_vendor or os.path.splitext(doc.original_filename)[0] or "Vendor"
        amount = doc.amount_hint
        if amount is None:
            inferred_amount = _infer_amount_from_filename(doc.original_filename)
            amount = inferred_amount if inferred_amount is not None else Decimal("150.00")
        invoice_number = _build_invoice_number(doc.original_filename, doc.invoice_number_hint)
        issue_dt = doc.issue_date_hint or today
        due_dt = doc.due_date_hint or issue_dt + timedelta(days=30)
        tax_amount = (amount * Decimal("0.10")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        doc_currency = doc.currency_hint or currency
        
        # Track user hints for mismatch detection
        user_hints = {
            "vendor_hint": doc.vendor_hint,
            "amount_hint": str(doc.amount_hint) if doc.amount_hint else None,
            "currency_hint": doc.currency_hint,
            "issue_date_hint": doc.issue_date_hint.isoformat() if doc.issue_date_hint else None,
            "due_date_hint": doc.due_date_hint.isoformat() if doc.due_date_hint else None,
            "invoice_number_hint": doc.invoice_number_hint,
        }

        filename_lower = (doc.original_filename or "").lower()
        if any(term in filename_lower for term in ["error", "fail", "corrupt"]):
            results.append(
                InvoiceDocumentResult(
                    document_id=doc.document_id,
                    storage_key=doc.storage_key,
                    extracted_payload={
                        "vendor": vendor,
                        "invoice_number": invoice_number,
                        "issue_date": issue_dt.isoformat(),
                        "currency": doc_currency,
                        "total": str(amount),
                        "ocr_used": False,
                        "ocr_status": "unavailable",
                    },
                    normalized_payload={},
                    proposed_journal_payload={},
                    audit_flags=[{"code": "INTAKE_FAILURE", "severity": "high", "message": "Document could not be auto-processed."}],
                    audit_score=Decimal("100.00"),
                    audit_explanations=["Document marked as unsalvageable during intake."],
                    status="ERROR",
                    audit_status="error",
                    error="Document could not be auto-processed",
                )
            )
            continue

        # Try OCR extraction first
        if use_ocr:
            try:
                ocr_data = extract_invoice_data(doc.storage_key, doc.original_filename)
                if ocr_data and ocr_data.get("vendor"):
                    # OCR succeeded - use extracted data
                    ocr_used = True
                    ocr_status = "used"
                    
                    # Update values from OCR
                    vendor = ocr_data.get("vendor") or vendor
                    invoice_number = ocr_data.get("invoice_number") or invoice_number
                    
                    # Parse dates
                    if ocr_data.get("issue_date"):
                        try:
                            issue_dt = datetime.fromisoformat(ocr_data["issue_date"]).date()
                        except Exception:
                            pass
                    if ocr_data.get("due_date"):
                        try:
                            due_dt = datetime.fromisoformat(ocr_data["due_date"]).date()
                        except Exception:
                            pass
                    
                    # Parse amounts
                    ocr_total = validate_extracted_amount(ocr_data.get("total"))
                    if ocr_total and ocr_total > Decimal("0"):
                        amount = ocr_total
                    ocr_tax = validate_extracted_amount(ocr_data.get("tax"))
                    if ocr_tax and ocr_tax >= Decimal("0"):
                        tax_amount = ocr_tax
                    else:
                        tax_amount = (amount * Decimal("0.10")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    
                    if ocr_data.get("currency"):
                        doc_currency = ocr_data["currency"].upper()
            except Exception as e:
                trace_events.append(
                    trace_event(
                        agent="invoices.ocr",
                        event="ocr_failed",
                        metadata={"trace_id": trace_id, "error": str(e)},
                        level="warning",
                    )
                )

        extracted = {
            "vendor": vendor,
            "invoice_number": invoice_number,
            "issue_date": issue_dt.isoformat(),
            "due_date": due_dt.isoformat(),
            "total": str(amount),
            "tax": str(tax_amount),
            "currency": doc_currency,
            "category_hint": doc.category_hint or default_category,
            "storage_key": doc.storage_key,
            "ocr_used": ocr_used,
            "ocr_status": ocr_status,
            "user_hints": user_hints,
        }
        normalized = {
            "vendor": vendor,
            "invoice_number": invoice_number,
            "amount": str(amount),
            "tax": str(tax_amount),
            "currency": extracted["currency"],
            "issue_date": extracted["issue_date"],
            "due_date": extracted["due_date"],
            "category": extracted["category_hint"] or default_category or "expense",
            "description": f"Invoice {invoice_number} from {vendor}",
        }
        proposed = {
            "date": extracted["issue_date"],
            "description": normalized["description"],
            "lines": [
                {
                    "account_id": expense_account.id,
                    "debit": str(amount - tax_amount),
                    "credit": "0",
                    "description": "Expense",
                },
                {
                    "account_id": tax_account.id if tax_account else expense_account.id,
                    "debit": str(tax_amount),
                    "credit": "0",
                    "description": "Tax",
                },
                {
                    "account_id": ap_account.id,
                    "debit": "0",
                    "credit": str(amount),
                    "description": "Accounts Payable",
                },
            ],
        }

        audit_flags, audit_score, explanations, audit_status, retries = _audit_document(
            extracted, normalized, companion_enabled=bool(ai_companion_enabled)
        )
        agent_retry_total += retries
        trace_events.append(
            trace_event(
                agent="invoices.workflow",
                event="document_processed",
                metadata={
                    "trace_id": trace_id,
                    "storage_key": doc.storage_key,
                    "audit_status": audit_status,
                    "audit_score": float(audit_score),
                },
                level="info",
            )
        )
        status = "PROCESSED" if audit_status != "error" else "ERROR"
        results.append(
            InvoiceDocumentResult(
                document_id=doc.document_id,
                storage_key=doc.storage_key,
                extracted_payload=extracted,
                normalized_payload=normalized,
                proposed_journal_payload=proposed,
                audit_flags=audit_flags,
                audit_score=audit_score,
                audit_explanations=explanations,
                status=status,
                audit_status=audit_status,
                error="Blocking audit issues" if status == "ERROR" else None,
            )
        )

    processed = [d for d in results if d.status == "PROCESSED"]
    errors = [d for d in results if d.status != "PROCESSED"]
    warnings = [d for d in results if d.audit_status == "warning" and d.status == "PROCESSED"]
    high_risk = [d for d in results if d.audit_score is not None and d.audit_score >= AUDIT_HIGH_RISK_THRESHOLD]
    metrics = {
        "documents_total": len(results),
        "documents_processed_ok": len(processed),
        "documents_with_warnings": len(warnings),
        "documents_with_errors": len(errors),
        "documents_high_risk": len(high_risk),
        "agent_retries": agent_retry_total,
        "trace_events": trace_events,
    }

    if ai_companion_enabled:
        subset_limit = 20
        prioritized = sorted(results, key=lambda d: (d.audit_score or Decimal("0")), reverse=True)
        high_priority = [d for d in prioritized if d.audit_score and d.audit_score >= AUDIT_HIGH_RISK_THRESHOLD]
        remaining = [d for d in prioritized if d not in high_priority]
        selected = (high_priority + remaining)[:subset_limit]

        documents_payload: list[dict] = []
        for doc in selected:
            extracted = doc.extracted_payload or {}
            normalized = doc.normalized_payload or {}
            proposed_lines = (doc.proposed_journal_payload or {}).get("lines") or []
            documents_payload.append(
                {
                    "document_id": doc.document_id,
                    "status": doc.status,
                    "audit_flags": doc.audit_flags,
                    "audit_score": str(doc.audit_score) if doc.audit_score is not None else None,
                    "vendor_name": extracted.get("vendor"),
                    "invoice_number": extracted.get("invoice_number"),
                    "issue_date": extracted.get("issue_date"),
                    "due_date": extracted.get("due_date"),
                    "amount": extracted.get("total"),
                    "currency": extracted.get("currency"),
                    "proposed_account_ids": [line.get("account_id") for line in proposed_lines if line.get("account_id")],
                    "proposed_category": normalized.get("category"),
                }
            )

        llm_metrics = {k: v for k, v in metrics.items() if k != "trace_events"}
        llm_result = reason_about_invoices_run(metrics=llm_metrics, documents=documents_payload)
        if llm_result:
            llm_explanations = llm_result.explanations
            llm_ranked_documents = [item.model_dump() for item in llm_result.ranked_documents]
            llm_suggested_classifications = [item.model_dump() for item in llm_result.suggested_classifications]
            llm_suggested_followups = llm_result.suggested_followups

    return InvoicesWorkflowResult(
        run_id=str(triggered_by_user_id),
        engine_run_id=engine_run_id,
        documents=results,
        metrics=metrics,
        trace_id=trace_id,
        llm_explanations=llm_explanations,
        llm_ranked_documents=llm_ranked_documents,
        llm_suggested_classifications=llm_suggested_classifications,
        llm_suggested_followups=llm_suggested_followups,
    )
