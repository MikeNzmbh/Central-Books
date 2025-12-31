from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any, Callable

from django.conf import settings
from pydantic import BaseModel, Field, ValidationError, field_validator

from companion.llm import call_companion_llm

logger = logging.getLogger(__name__)

LLMCallable = Callable[[str], str | None]


class BooksRankedIssue(BaseModel):
    severity: str
    title: str
    message: str
    related_journal_ids: list[int] = Field(default_factory=list)
    related_accounts: list[str] = Field(default_factory=list)

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize_severity(cls, value: str):
        if not isinstance(value, str):
            raise ValueError("severity must be a string")
        sev = value.lower()
        if sev not in {"low", "medium", "high"}:
            raise ValueError("severity must be one of low|medium|high")
        return sev


class BooksReviewLLMResult(BaseModel):
    explanations: list[str] = Field(default_factory=list)
    ranked_issues: list[BooksRankedIssue] = Field(default_factory=list)
    suggested_checks: list[str] = Field(default_factory=list)


class BankRankedTransaction(BaseModel):
    transaction_id: str
    priority: str
    reason: str

    @field_validator("priority", mode="before")
    @classmethod
    def _normalize_priority(cls, value: str):
        if not isinstance(value, str):
            raise ValueError("priority must be a string")
        prio = value.lower()
        if prio not in {"low", "medium", "high"}:
            raise ValueError("priority must be one of low|medium|high")
        return prio


class BankReviewLLMResult(BaseModel):
    explanations: list[str] = Field(default_factory=list)
    ranked_transactions: list[BankRankedTransaction] = Field(default_factory=list)
    suggested_followups: list[str] = Field(default_factory=list)


class RankedDocument(BaseModel):
    document_id: str
    priority: str
    reason: str

    @field_validator("priority", mode="before")
    @classmethod
    def _normalize_priority(cls, value: str):
        if not isinstance(value, str):
            raise ValueError("priority must be a string")
        prio = value.lower()
        if prio not in {"low", "medium", "high"}:
            raise ValueError("priority must be one of low|medium|high")
        return prio


class SuggestedClassification(BaseModel):
    document_id: str
    suggested_account_code: str | None = None
    confidence: float | None = None
    reason: str

    @field_validator("confidence", mode="before")
    @classmethod
    def _validate_confidence(cls, value: Any):
        if value is None:
            return value
        try:
            num = float(value)
        except Exception as exc:
            raise ValueError("confidence must be numeric") from exc
        if num < 0 or num > 1:
            raise ValueError("confidence must be between 0 and 1")
        return num


class ReceiptsRunLLMResult(BaseModel):
    explanations: list[str] = Field(default_factory=list)
    ranked_documents: list[RankedDocument] = Field(default_factory=list)
    suggested_classifications: list[SuggestedClassification] = Field(default_factory=list)
    suggested_followups: list[str] = Field(default_factory=list)


class InvoicesRunLLMResult(BaseModel):
    explanations: list[str] = Field(default_factory=list)
    ranked_documents: list[RankedDocument] = Field(default_factory=list)
    suggested_classifications: list[SuggestedClassification] = Field(default_factory=list)
    suggested_followups: list[str] = Field(default_factory=list)


def _call_with_timeout(func: Callable[[], str | None], timeout_seconds: int) -> str | None:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func)
        try:
            return future.result(timeout=timeout_seconds)
        except TimeoutError:
            logger.warning("LLM reasoning call timed out after %s seconds", timeout_seconds)
            return None


def _invoke_llm(prompt: str, *, llm_client: LLMCallable | None, timeout_seconds: int | None) -> str | None:
    client = llm_client or call_companion_llm
    timeout = timeout_seconds if timeout_seconds is not None else getattr(settings, "COMPANION_LLM_TIMEOUT_SECONDS", 15)
    try:
        if timeout and timeout > 0:
            return _call_with_timeout(lambda: client(prompt), timeout)
        return client(prompt)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("LLM reasoning call failed: %s", exc)
        return None


def _strip_markdown_json(raw: str | None) -> str | None:
    """
    Strip markdown code block wrappers from LLM output.
    
    LLMs often return JSON wrapped in ```json...``` or ```...``` blocks.
    This extracts the pure JSON content.
    """
    if not raw:
        return raw
    text = raw.strip()
    # Handle ```json ... ``` or ``` ... ```
    if text.startswith("```"):
        # Find end of first line (the language hint line)
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        # Strip trailing ```
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()
    return text


def reason_about_books_review(
    *,
    metrics: dict,
    findings: list[dict],
    sample_journals: list[dict],
    llm_client: LLMCallable | None = None,
    timeout_seconds: int | None = None,
) -> BooksReviewLLMResult | None:
    """
    Guardrailed LLM reasoning for books review runs. Returns None on failure/disabled.
    """
    allowed_journal_ids = {int(j["id"]) for j in sample_journals if isinstance(j, dict) and j.get("id") is not None}
    allowed_accounts = set()
    for journal in sample_journals:
        for acct in journal.get("accounts", []):
            code = acct.get("code")
            if code:
                allowed_accounts.add(str(code))

    system_prompt = (
        "You are an accounting QA companion. Only reason about the JSON provided. "
        "Do not invent transactions, dates, or amounts. Do not change numbers. "
        "Only reference journal_entry_ids or account codes that appear in the input. "
        "Respond with JSON only and no extra text."
    )

    expected_schema = {
        "explanations": ["short narrative sentences about the ledger health"],
        "ranked_issues": [
            {
                "severity": "low|medium|high",
                "title": "short title",
                "message": "explain the pattern using only provided numbers",
                "related_journal_ids": ["must come from input sample_journals"],
                "related_accounts": ["account codes present in input"],
            }
        ],
        "suggested_checks": ["short suggestions on where to look next"],
    }

    payload = {
        "metrics": metrics,
        "findings": findings,
        "sample_journals": sample_journals,
        "output_schema": expected_schema,
        "rules": [
            "Do not fabricate transactions, IDs, dates, or amounts.",
            "Only cite journal ids and account codes from sample_journals.",
            "Use concise, factual language.",
            "Return ONLY the JSON object described by output_schema.",
        ],
    }

    prompt = f"{system_prompt}\n\nDATA:\n{json.dumps(payload, default=str)}"
    raw = _invoke_llm(prompt, llm_client=llm_client, timeout_seconds=timeout_seconds)
    if not raw:
        return None

    try:
        parsed_json = json.loads(_strip_markdown_json(raw))
    except Exception:
        logger.warning("Books review LLM returned non-JSON response.")
        return None

    try:
        result = BooksReviewLLMResult.model_validate(parsed_json)
    except ValidationError as exc:
        logger.warning("Books review LLM validation failed: %s", exc)
        return None

    cleaned_issues: list[BooksRankedIssue] = []
    for issue in result.ranked_issues:
        valid_journal_ids = [jid for jid in issue.related_journal_ids if jid in allowed_journal_ids]
        valid_accounts = [code for code in issue.related_accounts if code in allowed_accounts]
        cleaned_issues.append(
            issue.model_copy(update={"related_journal_ids": valid_journal_ids, "related_accounts": valid_accounts})
        )

    return result.model_copy(update={"ranked_issues": cleaned_issues})


def reason_about_bank_review(
    *,
    metrics: dict,
    transactions: list[dict],
    llm_client: LLMCallable | None = None,
    timeout_seconds: int | None = None,
) -> BankReviewLLMResult | None:
    """
    Guardrailed LLM reasoning for bank review runs. Returns None on failure/disabled.
    """
    allowed_ids = {str(tx["transaction_id"]) for tx in transactions if isinstance(tx, dict) and tx.get("transaction_id") is not None}

    system_prompt = (
        "You are an audit-focused bank reconciliation assistant. Only reason about the JSON provided. "
        "Do not invent transactions, IDs, dates, or amounts. "
        "Return ONLY JSON with explanations, ranked_transactions, and suggested_followups."
    )

    expected_schema = {
        "explanations": ["1-2 sentence narrative about reconciliation status"],
        "ranked_transactions": [
            {"transaction_id": "<existing id from input>", "priority": "high|medium|low", "reason": "why this line matters"}
        ],
        "suggested_followups": ["concise next steps for a human reviewer"],
    }

    payload = {
        "metrics": metrics,
        "transactions": transactions,
        "output_schema": expected_schema,
        "rules": [
            "Only reference transaction_id values that were provided.",
            "Do not invent new amounts or balances; treat numerics descriptively.",
            "Keep reasons short and actionable.",
            "Respond with ONLY the JSON object described by output_schema.",
        ],
    }

    prompt = f"{system_prompt}\n\nDATA:\n{json.dumps(payload, default=str)}"
    raw = _invoke_llm(prompt, llm_client=llm_client, timeout_seconds=timeout_seconds)
    if not raw:
        return None

    try:
        parsed_json = json.loads(_strip_markdown_json(raw))
    except Exception:
        logger.warning("Bank review LLM returned non-JSON response.")
        return None

    try:
        result = BankReviewLLMResult.model_validate(parsed_json)
    except ValidationError as exc:
        logger.warning("Bank review LLM validation failed: %s", exc)
        return None

    cleaned: list[BankRankedTransaction] = []
    for tx in result.ranked_transactions:
        if str(tx.transaction_id) not in allowed_ids:
            continue
        cleaned.append(tx)

    return result.model_copy(update={"ranked_transactions": cleaned})


def reason_about_receipts_run(
    *,
    metrics: dict,
    documents: list[dict],
    llm_client: LLMCallable | None = None,
    timeout_seconds: int | None = None,
) -> ReceiptsRunLLMResult | None:
    allowed_ids = {str(doc["document_id"]) for doc in documents if isinstance(doc, dict) and doc.get("document_id") is not None}

    system_prompt = (
        "You are a receipts audit companion. Only reason about the JSON provided. "
        "Do not invent receipts, amounts, vendors, or account codes. "
        "Return ONLY JSON with explanations, ranked_documents, suggested_classifications, suggested_followups."
    )
    expected_schema = {
        "explanations": ["short sentences summarizing risk and focus areas"],
        "ranked_documents": [
            {"document_id": "<existing id from input>", "priority": "high|medium|low", "reason": "why to review"}
        ],
        "suggested_classifications": [
            {
                "document_id": "<existing id from input>",
                "suggested_account_code": "string code if any",
                "confidence": "0-1",
                "reason": "short rationale",
            }
        ],
        "suggested_followups": ["concise next steps for a human reviewer"],
    }
    payload = {
        "metrics": metrics,
        "documents": documents,
        "output_schema": expected_schema,
        "rules": [
            "Only reference document_id values that were provided.",
            "Do not invent new amounts or vendors; rely only on the provided JSON.",
            "Suggested classifications are proposals only.",
            "Respond with ONLY the JSON object described by output_schema.",
        ],
    }
    prompt = f"{system_prompt}\n\nDATA:\n{json.dumps(payload, default=str)}"
    raw = _invoke_llm(prompt, llm_client=llm_client, timeout_seconds=timeout_seconds)
    if not raw:
        return None

    try:
        parsed_json = json.loads(_strip_markdown_json(raw))
    except Exception:
        logger.warning("Receipts run LLM returned non-JSON response.")
        return None

    try:
        result = ReceiptsRunLLMResult.model_validate(parsed_json)
    except ValidationError as exc:
        logger.warning("Receipts run LLM validation failed: %s", exc)
        return None

    ranked = [item for item in result.ranked_documents if str(item.document_id) in allowed_ids]
    suggested = [item for item in result.suggested_classifications if str(item.document_id) in allowed_ids]
    return result.model_copy(update={"ranked_documents": ranked, "suggested_classifications": suggested})


def reason_about_invoices_run(
    *,
    metrics: dict,
    documents: list[dict],
    llm_client: LLMCallable | None = None,
    timeout_seconds: int | None = None,
) -> InvoicesRunLLMResult | None:
    allowed_ids = {str(doc["document_id"]) for doc in documents if isinstance(doc, dict) and doc.get("document_id") is not None}

    system_prompt = (
        "You are an invoices audit companion. Only reason about the JSON provided. "
        "Do not invent invoices, amounts, vendors, or account codes. "
        "Return ONLY JSON with explanations, ranked_documents, suggested_classifications, suggested_followups."
    )
    expected_schema = {
        "explanations": ["short sentences summarizing invoice health"],
        "ranked_documents": [
            {"document_id": "<existing id from input>", "priority": "high|medium|low", "reason": "why to review"}
        ],
        "suggested_classifications": [
            {
                "document_id": "<existing id from input>",
                "suggested_account_code": "string code if any",
                "confidence": "0-1",
                "reason": "short rationale",
            }
        ],
        "suggested_followups": ["concise next steps for a human reviewer"],
    }
    payload = {
        "metrics": metrics,
        "documents": documents,
        "output_schema": expected_schema,
        "rules": [
            "Only reference document_id values that were provided.",
            "Do not invent new amounts or vendors; rely only on the provided JSON.",
            "Suggested classifications are proposals only.",
            "Respond with ONLY the JSON object described by output_schema.",
        ],
    }
    prompt = f"{system_prompt}\n\nDATA:\n{json.dumps(payload, default=str)}"
    raw = _invoke_llm(prompt, llm_client=llm_client, timeout_seconds=timeout_seconds)
    if not raw:
        return None

    try:
        parsed_json = json.loads(_strip_markdown_json(raw))
    except Exception:
        logger.warning("Invoices run LLM returned non-JSON response.")
        return None

    try:
        result = InvoicesRunLLMResult.model_validate(parsed_json)
    except ValidationError as exc:
        logger.warning("Invoices run LLM validation failed: %s", exc)
        return None

    ranked = [item for item in result.ranked_documents if str(item.document_id) in allowed_ids]
    suggested = [item for item in result.suggested_classifications if str(item.document_id) in allowed_ids]
    return result.model_copy(update={"ranked_documents": ranked, "suggested_classifications": suggested})
