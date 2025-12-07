"""
Vision-based receipt OCR using OpenAI Vision API.

This module provides functions to extract structured data from receipt images
using OpenAI's gpt-4o-mini model (via call_openai_vision helper).

PROVIDER: OpenAI (gpt-4o-mini)
REQUIRES: OPENAI_API_KEY environment variable
"""
from __future__ import annotations

import base64
import json
import logging
import mimetypes
from decimal import Decimal
from typing import TypedDict

from django.core.files.storage import default_storage

from companion.llm import call_vision_llm

logger = logging.getLogger(__name__)


class ExtractedReceiptData(TypedDict, total=False):
    """Structured data extracted from a receipt image."""
    vendor: str
    date: str  # ISO format YYYY-MM-DD
    total: str  # Decimal string
    currency: str  # 3-letter ISO code
    subtotal: str | None
    tax: str | None
    line_items: list[dict]
    receipt_number: str | None
    payment_method: str | None
    raw_text: str | None


# Prompt for receipt extraction
RECEIPT_EXTRACTION_PROMPT = """Analyze this receipt image and extract the following information.
Return ONLY a valid JSON object with these fields:

{
  "vendor": "Name of the business/store",
  "date": "YYYY-MM-DD format",
  "total": "Total amount as decimal string (e.g., '31.50')",
  "currency": "3-letter ISO currency code (e.g., 'CAD', 'USD')",
  "subtotal": "Subtotal before tax if visible, or null",
  "tax": "Tax amount if visible, or null",
  "line_items": [{"description": "item name", "amount": "item price"}],
  "receipt_number": "Receipt/invoice number if visible, or null",
  "payment_method": "Payment method if visible (e.g., 'Credit Card'), or null"
}

IMPORTANT:
- For total, extract the FINAL TOTAL AMOUNT PAID (not subtotals)
- If currency is not explicitly shown, infer from symbols ($ = USD/CAD depending on context)
- Date must be in YYYY-MM-DD format
- Return ONLY the JSON object, no other text
- If a field cannot be determined, use null
"""


def _get_image_mime_type(filename: str) -> str:
    """Guess the MIME type from a filename."""
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type and mime_type.startswith("image/"):
        return mime_type
    # Fall back to common types
    ext = filename.lower().split(".")[-1] if "." in filename else ""
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "heic": "image/heic",
        "pdf": "application/pdf",
    }.get(ext, "image/jpeg")


def _read_file_as_base64(storage_key: str) -> tuple[str, str] | None:
    """
    Read a file from storage and return as (base64_data, mime_type).
    Returns None if the file cannot be read.
    """
    try:
        with default_storage.open(storage_key, "rb") as f:
            file_bytes = f.read()
        base64_data = base64.b64encode(file_bytes).decode("utf-8")
        mime_type = _get_image_mime_type(storage_key)
        return base64_data, mime_type
    except Exception as exc:
        logger.warning("Failed to read file %s: %s", storage_key, exc)
        return None


def _parse_llm_response(raw_response: str | None) -> ExtractedReceiptData | None:
    """Parse the LLM response into structured data."""
    if not raw_response:
        return None

    # Try to extract JSON from the response
    text = raw_response.strip()
    
    # Handle markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # Try direct JSON parse first
    try:
        data = json.loads(text)
        return _build_extracted_data(data)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text (model might add preamble/epilogue)
    import re
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            logger.info("[receipts_ocr] Extracted JSON from mixed response")
            return _build_extracted_data(data)
        except json.JSONDecodeError:
            pass

    logger.warning("[receipts_ocr] Failed to parse LLM response as JSON. Response preview: %s", text[:300])
    return None


def _build_extracted_data(data: dict) -> ExtractedReceiptData:
    """Build ExtractedReceiptData from parsed JSON dict."""
    return ExtractedReceiptData(
        vendor=data.get("vendor") or "",
        date=data.get("date") or "",
        total=str(data.get("total") or "0"),  # Convert to string in case it's a number
        currency=data.get("currency") or "USD",
        subtotal=str(data.get("subtotal")) if data.get("subtotal") else None,
        tax=str(data.get("tax")) if data.get("tax") else None,
        line_items=data.get("line_items") or [],
        receipt_number=data.get("receipt_number"),
        payment_method=data.get("payment_method"),
    )


def extract_receipt_data(
    storage_key: str,
    original_filename: str | None = None,
) -> ExtractedReceiptData | None:
    """
    Extract structured data from a receipt image using vision LLM.
    
    Args:
        storage_key: Storage path to the receipt file
        original_filename: Original filename (used for MIME type detection)
    
    Returns:
        Extracted receipt data, or None if extraction failed
    """
    # Read the file
    file_result = _read_file_as_base64(storage_key)
    if not file_result:
        logger.warning("Could not read receipt file: %s", storage_key)
        return None

    base64_data, mime_type = file_result
    
    # Use original filename for better MIME detection if available
    if original_filename:
        mime_type = _get_image_mime_type(original_filename)

    # Call vision LLM
    raw_response = call_vision_llm(
        prompt=RECEIPT_EXTRACTION_PROMPT,
        image_base64=base64_data,
        image_type=mime_type,
        max_tokens=1024,
    )

    if not raw_response:
        logger.warning("Vision LLM returned no response for: %s", storage_key)
        return None

    # Parse the response
    extracted = _parse_llm_response(raw_response)
    if extracted:
        logger.info(
            "Extracted receipt data: vendor=%s, total=%s, date=%s",
            extracted.get("vendor"),
            extracted.get("total"),
            extracted.get("date"),
        )
    return extracted


def validate_extracted_amount(amount_str: str | None) -> Decimal | None:
    """Validate and parse an extracted amount string."""
    if not amount_str:
        return None
    # Remove currency symbols and whitespace
    cleaned = amount_str.replace("$", "").replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except Exception:
        return None
