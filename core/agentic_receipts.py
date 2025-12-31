from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional
from uuid import uuid4

from django.conf import settings
from django.utils import timezone

from agentic.logging.tracing import trace_event

from .accounting_defaults import ensure_default_accounts
from .llm_reasoning import ReceiptsRunLLMResult, reason_about_receipts_run
from .models import Business
from .receipt_ocr import extract_receipt_data, validate_extracted_amount

AUDIT_WARNING_THRESHOLD = Decimal("40.0")
AUDIT_HIGH_RISK_THRESHOLD = Decimal("60.0")


@dataclass
class ReceiptInputDocument:
    document_id: int
    storage_key: str
    original_filename: str
    currency_hint: Optional[str] = None
    date_hint: Optional[str | date] = None
    category_hint: Optional[str] = None
    vendor_hint: Optional[str] = None
    amount_hint: Optional[Decimal] = None


@dataclass
class ReceiptDocumentResult:
    document_id: int
    storage_key: str
    extracted_payload: dict
    normalized_payload: dict
    proposed_journal_payload: dict
    audit_flags: list
    audit_score: Optional[Decimal]
    audit_explanations: list
    status: str  # ReceiptDocument.DocumentStatus
    audit_status: str  # ok | warning | error
    error: Optional[str] = None


@dataclass
class ReceiptsWorkflowResult:
    run_id: str
    engine_run_id: str
    documents: List[ReceiptDocumentResult]
    metrics: dict
    trace_id: str
    llm_explanations: list
    llm_ranked_documents: list
    llm_suggested_classifications: list
    llm_suggested_followups: list


def _parse_amount(value: Decimal | str | None) -> Decimal:
    try:
        return (Decimal(str(value)) if value is not None else Decimal("0")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    except Exception:
        return Decimal("0.00")


def _infer_amount_from_filename(filename: str) -> Optional[Decimal]:
    if not filename:
        return None
    matches = re.findall(r"(\d+[.,]\d{2})", filename)
    if not matches:
        currency_matches = re.findall(r"(?:cad|usd|eur|gbp)[-_]?(\d+[.,]?\d*)", filename, flags=re.IGNORECASE)
        matches = currency_matches
    if not matches:
        return None
    inferred = _parse_amount(matches[0].replace(",", "."))
    if inferred <= Decimal("0"):
        return None
    return inferred


def _is_generic_camera_name(name: str) -> bool:
    lowered = name.lower()
    prefixes = ("img_", "img-", "dsc", "pxl_", "pxl-", "screenshot", "whatsapp", "signal")
    return any(lowered.startswith(p) for p in prefixes)


def _parse_hint_date(raw: str | date | None) -> Optional[date]:
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return date.fromisoformat(raw.split("T")[0])
        except Exception:
            return None
    return None


def _normalize_currency_hint(raw: str | None) -> Optional[str]:
    if not raw:
        return None
    cleaned = raw.strip().upper()
    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned
    return cleaned or None


def _audit_document(
    extracted: dict,
    normalized: dict,
    *,
    companion_enabled: bool,
    business_currency: str,
    today: date,
    mismatch_flags: list[dict],
    trace_events: list[dict],
    trace_id: str,
) -> tuple[list, Decimal, list, str, int]:
    flags: list[dict] = list(mismatch_flags)
    explanations: list[str] = []
    score = Decimal("5.0")
    retries = 0

    extracted_currency = (extracted.get("currency") or "").upper()
    if extracted_currency and business_currency and extracted_currency != business_currency:
        flags.append(
            {
                "code": "CURRENCY_MISMATCH",
                "severity": "medium",
                "message": f"Document currency {extracted_currency} differs from business default {business_currency}.",
            }
        )
        explanations.append("Currency differs from defaults; flagged for review.")
        score += Decimal("18.0")

    amount = _parse_amount(extracted.get("total"))
    if amount <= 0:
        flags.append({"code": "MISSING_AMOUNT", "severity": "high", "message": "Unable to determine a valid total amount."})
        explanations.append("Amount missing or zero.")
        score += Decimal("45.0")
    elif amount >= Decimal("1000"):
        flags.append({"code": "UNUSUAL_AMOUNT", "severity": "high", "message": "Amount above the normal threshold for receipts."})
        score += Decimal("60.0")
    elif amount >= Decimal("250"):
        flags.append({"code": "LARGE_AMOUNT", "severity": "medium", "message": "Amount is higher than typical spend."})
        score += Decimal("18.0")

    vendor = (extracted.get("vendor") or "").strip()
    if not vendor:
        flags.append({"code": "MISSING_VENDOR", "severity": "high", "message": "Vendor is missing from extraction."})
        score += Decimal("30.0")

    try:
        parsed_date = datetime.fromisoformat(extracted.get("date")).date()
        if parsed_date > today:
            flags.append({"code": "FUTURE_DATE", "severity": "medium", "message": "Receipt date is in the future."})
            score += Decimal("10.0")
    except Exception:
        flags.append({"code": "INVALID_DATE", "severity": "medium", "message": "Date could not be parsed."})
        explanations.append("Date parsing failed during validation.")
        score += Decimal("12.0")

    if companion_enabled:
        reflection_needed = False
        if vendor and any(term in vendor.lower() for term in ["wire", "transfer", "refund", "manual"]):
            flags.append(
                {"code": "VENDOR_PATTERN", "severity": "medium", "message": "Vendor name pattern requires human confirmation."}
            )
            score += Decimal("12.0")
        category = (normalized.get("category") or "") if isinstance(normalized, dict) else ""
        if category and vendor and category.lower() in {"uncategorized", "misc"}:
            flags.append(
                {"code": "CATEGORY_WEAK", "severity": "low", "message": "Category is too generic; companion recommends review."}
            )
            score += Decimal("6.0")
        if flags:
            reflection_needed = True
            if score >= AUDIT_WARNING_THRESHOLD:
                explanations.append("Companion performed a second-pass reflection on anomalous signals.")
            else:
                explanations.append("Companion reviewed hints and extracted fields for potential mismatches.")
        if reflection_needed:
            retries += 1
            trace_events.append(
                trace_event(
                    agent="receipts.companion",
                    event="reflection",
                    metadata={
                        "trace_id": trace_id,
                        "document": extracted.get("vendor") or extracted.get("storage_key") or "",
                        "flags": [f.get("code") for f in flags],
                    },
                    level="warning",
                )
            )

    audit_status = "ok"
    if score >= AUDIT_WARNING_THRESHOLD or any(f.get("severity") == "high" for f in flags):
        audit_status = "warning"
    if any(f.get("severity") == "high" and f.get("code") in {"MISSING_AMOUNT", "MISSING_VENDOR"} for f in flags):
        audit_status = "error"

    score = min(score, Decimal("100.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return flags, score, explanations, audit_status, retries


def run_receipts_workflow(
    *,
    business_id: int,
    documents: List[ReceiptInputDocument],
    default_currency: str | None = None,
    default_date: date | None = None,
    default_category: str | None = None,
    default_vendor: str | None = None,
    triggered_by_user_id: int,
    ai_companion_enabled: bool | None = None,
) -> ReceiptsWorkflowResult:
    """
    Synchronous entry point that wraps the Receipts agentic workflow.
    Design B baseline: files are ingested, hints are optional, extraction is primary, and a result is always returned.
    """
    business = Business.objects.get(pk=business_id)
    defaults = ensure_default_accounts(business)
    cash_account = defaults.get("cash")
    expense_account = defaults.get("opex")
    if not cash_account or not expense_account:
        raise ValueError("Default cash and expense accounts are required for receipts.")

    business_currency = (default_currency or business.currency or "").upper()
    today = default_date or timezone.localdate()

    results: list[ReceiptDocumentResult] = []
    engine_run_id = f"receipt-run-{uuid4().hex}"
    trace_id = f"receipt-trace-{uuid4().hex}"
    trace_events: list[dict] = []
    llm_explanations: list[str] = []
    llm_ranked_documents: list[dict] = []
    llm_suggested_classifications: list[dict] = []
    llm_suggested_followups: list[str] = []
    agent_retry_total = 0
    # Enable OCR when we have OpenAI key (for gpt-4o-mini vision) or any Companion LLM configured
    use_ocr = bool(getattr(settings, "OPENAI_API_KEY", None)) or bool(getattr(settings, "COMPANION_LLM_API_KEY", None)) or bool(ai_companion_enabled)

    for doc in documents:
        filename_lower = (doc.original_filename or "").lower()
        if any(term in filename_lower for term in ["error", "fail", "corrupt"]):
            error_flags = [
                {"code": "INTAKE_FAILURE", "severity": "high", "message": "Document could not be auto-processed."}
            ]
            results.append(
                ReceiptDocumentResult(
                    document_id=doc.document_id,
                    storage_key=doc.storage_key,
                    extracted_payload={
                        "vendor": doc.vendor_hint or "Unknown",
                        "date": (doc.date_hint or today).isoformat() if isinstance(doc.date_hint, date) else today.isoformat(),
                        "currency": _normalize_currency_hint(doc.currency_hint) or business_currency,
                        "total": "0",
                        "user_hints": {
                            "date_hint": doc.date_hint if isinstance(doc.date_hint, str) else None,
                            "currency_hint": doc.currency_hint,
                            "vendor_hint": doc.vendor_hint,
                            "category_hint": doc.category_hint,
                        },
                    },
                    normalized_payload={},
                    proposed_journal_payload={},
                    audit_flags=error_flags,
                    audit_score=Decimal("100.00"),
                    audit_explanations=["Document marked as unsalvageable during intake."],
                    status="ERROR",
                    audit_status="error",
                    error="Document could not be auto-processed",
                )
            )
            continue

        user_date_hint = doc.date_hint if isinstance(doc.date_hint, str) else (
            doc.date_hint.isoformat() if isinstance(doc.date_hint, date) else None
        )
        parsed_date_hint = _parse_hint_date(doc.date_hint)
        user_currency_hint = doc.currency_hint
        normalized_currency_hint = _normalize_currency_hint(doc.currency_hint)
        user_vendor_hint = doc.vendor_hint
        user_category_hint = doc.category_hint
        user_hints = {
            "date_hint": user_date_hint,
            "currency_hint": user_currency_hint,
            "vendor_hint": user_vendor_hint,
            "category_hint": user_category_hint,
        }

        mismatch_flags: list[dict] = []
        ocr_data = None
        if use_ocr:
            try:
                ocr_data = extract_receipt_data(
                    storage_key=doc.storage_key,
                    original_filename=doc.original_filename,
                )
            except Exception as ocr_exc:
                trace_events.append(
                    trace_event(
                        agent="receipts.ocr",
                        event="ocr_failed",
                        metadata={
                            "trace_id": trace_id,
                            "storage_key": doc.storage_key,
                            "error": str(ocr_exc),
                        },
                        level="warning",
                    )
                )

        # Use OCR data if available, otherwise fall back to hints/filename heuristics
        if ocr_data:
            vendor = ocr_data.get("vendor") or user_vendor_hint or default_vendor or "Receipt"
            amount = validate_extracted_amount(ocr_data.get("total")) or Decimal("0.00")
            extracted_date = _parse_hint_date(ocr_data.get("date")) or parsed_date_hint or today
            extracted_currency = _normalize_currency_hint(ocr_data.get("currency")) or normalized_currency_hint or business_currency
        else:
            vendor = user_vendor_hint or default_vendor or os.path.splitext(doc.original_filename)[0] or "Receipt"
            if vendor and _is_generic_camera_name(vendor):
                vendor = default_vendor or "Receipt"
            if doc.amount_hint is not None:
                amount = doc.amount_hint
            else:
                inferred_amount = _infer_amount_from_filename(doc.original_filename)
                amount = inferred_amount if inferred_amount is not None else Decimal("10.00")
            extracted_date = parsed_date_hint or today
            extracted_currency = normalized_currency_hint or business_currency
            if use_ocr:
                mismatch_flags.append(
                    {
                        "code": "OCR_UNAVAILABLE",
                        "severity": "low",
                        "message": "Vision OCR was requested but returned no data; using filename/hints.",
                    }
                )

        # Mismatch flags between hints and extraction
        if user_currency_hint:
            if extracted_currency and _normalize_currency_hint(user_currency_hint) != extracted_currency:
                mismatch_flags.append(
                    {
                        "code": "CURRENCY_MISMATCH_HINT",
                        "severity": "low",
                        "message": f"User currency hint {user_currency_hint} differs from extracted {extracted_currency}.",
                    }
                )
        if user_date_hint:
            try:
                hint_dt = _parse_hint_date(user_date_hint)
                if hint_dt and extracted_date and hint_dt != extracted_date:
                    mismatch_flags.append(
                        {
                            "code": "DATE_MISMATCH_HINT",
                            "severity": "low",
                            "message": f"User date hint {user_date_hint} differs from extracted {extracted_date.isoformat()}.",
                        }
                    )
            except Exception:
                pass

        ocr_status = "used" if ocr_data else ("disabled_missing_api_key" if not use_ocr else "unavailable")
        extracted = {
            "vendor": vendor,
            "date": extracted_date.isoformat(),
            "total": str(_parse_amount(amount)),
            "currency": extracted_currency,
            "category_hint": user_category_hint or default_category,
            "storage_key": doc.storage_key,
            "ocr_used": ocr_data is not None,
            "ocr_status": ocr_status,
            "user_hints": user_hints,
        }
        normalized = {
            "vendor": vendor,
            "description": f"Receipt from {vendor}",
            "amount": extracted["total"],
            "currency": extracted["currency"],
            "date": extracted["date"],
            "category": extracted["category_hint"] or default_category or "expense",
        }
        proposed = {
            "date": extracted["date"],
            "description": f"Receipt - {vendor}",
            "lines": [
                {
                    "account_id": expense_account.id,
                    "debit": extracted["total"],
                    "credit": "0",
                    "description": "Expense",
                },
                {
                    "account_id": cash_account.id,
                    "debit": "0",
                    "credit": extracted["total"],
                    "description": "Cash",
                },
            ],
        }

        audit_flags, audit_score, explanations, audit_status, retries = _audit_document(
            extracted,
            normalized,
            companion_enabled=bool(ai_companion_enabled),
            business_currency=business_currency,
            today=today,
            mismatch_flags=mismatch_flags,
            trace_events=trace_events,
            trace_id=trace_id,
        )
        agent_retry_total += retries
        trace_events.append(
            trace_event(
                agent="receipts.workflow",
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
            ReceiptDocumentResult(
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
            extracted_payload = doc.extracted_payload or {}
            normalized_payload = doc.normalized_payload or {}
            proposed_lines = (doc.proposed_journal_payload or {}).get("lines") or []
            documents_payload.append(
                {
                    "document_id": doc.document_id,
                    "status": doc.status,
                    "audit_flags": doc.audit_flags,
                    "audit_score": str(doc.audit_score) if doc.audit_score is not None else None,
                    "vendor_name": extracted_payload.get("vendor"),
                    "amount": extracted_payload.get("total"),
                    "currency": extracted_payload.get("currency"),
                    "date": extracted_payload.get("date"),
                    "proposed_account_ids": [line.get("account_id") for line in proposed_lines if line.get("account_id")],
                    "proposed_category": normalized_payload.get("category"),
                }
            )
        llm_metrics = {k: v for k, v in metrics.items() if k != "trace_events"}
        llm_result = reason_about_receipts_run(metrics=llm_metrics, documents=documents_payload)
        if llm_result:
            llm_explanations = llm_result.explanations
            llm_ranked_documents = [item.model_dump() for item in llm_result.ranked_documents]
            llm_suggested_classifications = [item.model_dump() for item in llm_result.suggested_classifications]
            llm_suggested_followups = llm_result.suggested_followups

    return ReceiptsWorkflowResult(
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
