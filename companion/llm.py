from __future__ import annotations

from __future__ import annotations

import json
import logging
import random
import time
from typing import Iterable, Sequence

import requests
from django.conf import settings
from django.utils import timezone

from .models import CompanionInsight, CompanionSuggestedAction, HealthIndexSnapshot

logger = logging.getLogger(__name__)


# --- LLM client helpers ---

def _is_llm_enabled() -> bool:
    return bool(
        getattr(settings, "COMPANION_LLM_ENABLED", False)
        and getattr(settings, "COMPANION_LLM_API_BASE", "")
        and getattr(settings, "COMPANION_LLM_API_KEY", "")
    )


def call_companion_llm(prompt: str, *, temperature: float = 0.1) -> str | None:
    """
    Generic HTTP chat-completions call. Returns the raw text content or None on failure/disabled.
    """
    if not _is_llm_enabled():
        return None

    api_base = getattr(settings, "COMPANION_LLM_API_BASE", "")
    api_key = getattr(settings, "COMPANION_LLM_API_KEY", "")
    model = getattr(settings, "COMPANION_LLM_MODEL", "deepseek-v3.2")
    timeout = getattr(settings, "COMPANION_LLM_TIMEOUT_SECONDS", 15)
    max_tokens = getattr(settings, "COMPANION_LLM_MAX_TOKENS", 512)

    try:
        response = requests.post(
            api_base,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return None
        message = choices[0].get("message") or {}
        content = message.get("content")
        return content
    except Exception as exc:  # pragma: no cover - defensive network wrapper
        logger.warning("Companion LLM call failed: %s", exc)
        return None


# --- Narrative reasoning ---

_LLM_CACHE: dict[tuple[int, int], tuple[float, dict]] = {}
_LLM_CACHE_TTL_SECONDS = 10 * 60
_LLM_CACHE_MAX_ENTRIES = 500


def _cache_get(key: tuple[int, int]) -> dict | None:
    entry = _LLM_CACHE.get(key)
    if not entry:
        return None
    expires_at, payload = entry
    if time.time() > expires_at:
        _LLM_CACHE.pop(key, None)
        return None
    return payload


def _cache_set(key: tuple[int, int], value: dict) -> None:
    # Prune expired
    now = time.time()
    expired = [k for k, (exp, _) in _LLM_CACHE.items() if exp < now]
    for k in expired:
        _LLM_CACHE.pop(k, None)
    if len(_LLM_CACHE) >= _LLM_CACHE_MAX_ENTRIES:
        # Remove oldest entries to avoid unbounded growth.
        for stale_key in list(_LLM_CACHE.keys())[:50]:
            _LLM_CACHE.pop(stale_key, None)
    _LLM_CACHE[key] = (now + _LLM_CACHE_TTL_SECONDS, value)


def generate_companion_narrative(
    snapshot: HealthIndexSnapshot | None,
    insights: Sequence[CompanionInsight],
    raw_metrics: dict,
    actions: Sequence | None = None,
    context: str | None = None,
) -> dict:
    """
    Returns {"summary": str|None, "insight_explanations": {id: str}}
    """
    default = {"summary": None, "insight_explanations": {}, "action_explanations": {}, "context_summary": None}
    if snapshot is None:
        return default

    cache_key = (snapshot.workspace_id, snapshot.id)
    cached = _cache_get(cache_key)
    if cached:
        return cached

    if not _is_llm_enabled():
        return default

    health = {
        "score": snapshot.score,
        "breakdown": snapshot.breakdown or {},
        "raw_metrics": raw_metrics or snapshot.raw_metrics or {},
    }
    insight_payload = [
        {
            "id": insight.id,
            "domain": insight.domain,
            "context": getattr(insight, "context", CompanionInsight.CONTEXT_DASHBOARD),
            "severity": insight.severity,
            "title": insight.title,
            "body": insight.body,
        }
        for insight in insights
    ]

    system_prompt = (
        "You are an accounting companion. Explain only what is provided. "
        "Do not invent or guess new numbers, dates, or facts. "
        "If you mention numbers, they must match exactly the input. "
        "If nothing looks problematic, say everything looks fine. "
        "Insights and actions include a context tag (banking, invoices, reconciliation, expenses, reports, tax_fx); use it only to orient the user. "
        "Keep responses short and in JSON."
    )

    action_payload = []
    for action in actions or []:
        payload = action.payload or {}
        action_payload.append(
            {
                "id": action.id,
                "action_type": action.action_type,
                "context": getattr(action, "context", CompanionSuggestedAction.CONTEXT_DASHBOARD),
                "confidence": float(action.confidence or 0),
                "payload": {
                    "bank_transaction_id": payload.get("bank_transaction_id"),
                    "journal_entry_id": payload.get("journal_entry_id"),
                    "amount": payload.get("amount"),
                    "date": payload.get("date"),
                    "currency": payload.get("currency"),
                    "invoice_id": payload.get("invoice_id"),
                    "invoice_number": payload.get("invoice_number"),
                    "customer_name": payload.get("customer_name"),
                    "days_overdue": payload.get("days_overdue"),
                    "expense_ids": payload.get("expense_ids"),
                    "expenses": payload.get("expenses"),
                },
            }
        )

    prompt = json.dumps(
        {
            "health": health,
            "insights": insight_payload,
            "actions": action_payload,
            "context": context,
            "expected_output": {
                "summary": "short paragraph",
                "insight_explanations": {"<insight_id>": "explanation"},
                "action_explanations": {"<action_id>": "explanation"},
                "context_summary": "1-2 line optional summary for the provided context",
            },
        }
    )

    raw_reply = call_companion_llm(f"{system_prompt}\n\nDATA:\n{prompt}")
    if not raw_reply:
        return default

    try:
        parsed = json.loads(raw_reply)
    except Exception:
        logger.warning("Companion LLM returned non-JSON response.")
        return default

    summary = parsed.get("summary")
    explanations = parsed.get("insight_explanations") or {}
    action_explanations = parsed.get("action_explanations") or {}
    context_summary = parsed.get("context_summary")
    if not isinstance(explanations, dict):
        explanations = {}
    if not isinstance(action_explanations, dict):
        action_explanations = {}
    valid_ids = {str(insight.id) for insight in insights}
    filtered_explanations = {k: v for k, v in explanations.items() if k in valid_ids and isinstance(v, str)}
    valid_action_ids = {str(a.id) for a in actions or []}
    filtered_action_explanations = {
        k: v for k, v in action_explanations.items() if k in valid_action_ids and isinstance(v, str)
    }

    result = {
        "summary": summary if isinstance(summary, str) else None,
        "insight_explanations": filtered_explanations,
        "action_explanations": filtered_action_explanations,
        "context_summary": context_summary if isinstance(context_summary, str) else None,
    }
    _cache_set(cache_key, result)
    return result


# --- Existing sample insight generator (unchanged) ---

def _existing_titles(insights: Iterable[CompanionInsight]) -> set[str]:
    return {insight.title for insight in insights}


def generate_insights_for_snapshot(snapshot: HealthIndexSnapshot) -> list[CompanionInsight]:
    """
    Stubbed DeepSeek/LLM generator for deterministic placeholder insights.
    """
    workspace = snapshot.workspace
    metrics = snapshot.raw_metrics or {}
    existing = CompanionInsight.objects.filter(workspace=workspace, is_dismissed=False)
    taken_titles = _existing_titles(existing)

    candidates = [
        {
            "domain": "reconciliation",
            "context": CompanionInsight.CONTEXT_RECONCILIATION,
            "title": "Tighten reconciliation cadence",
            "body": f"{metrics.get('unreconciled_count', 0)} items remain unreconciled; clear the queue weekly.",
            "severity": "warning",
            "suggested_actions": [{"label": "Open banking", "action": "/banking/"}],
        },
        {
            "domain": "invoices",
            "context": CompanionInsight.CONTEXT_INVOICES,
            "title": "Follow up on overdue invoices",
            "body": f"{metrics.get('overdue_invoices', 0)} invoices are past due — nudge customers.",
            "severity": "info",
            "suggested_actions": [{"label": "View invoices", "action": "/invoices/"}],
        },
        {
            "domain": "expenses",
            "context": CompanionInsight.CONTEXT_EXPENSES,
            "title": "Categorize uncategorized expenses",
            "body": f"{metrics.get('uncategorized_expenses', 0)} expenses need categories for accurate P&L.",
            "severity": "info",
            "suggested_actions": [{"label": "Review expenses", "action": "/expenses/"}],
        },
        {
            "domain": "tax_fx",
            "context": CompanionInsight.CONTEXT_TAX_FX,
            "title": "Resolve tax mismatches",
            "body": f"{metrics.get('tax_mismatches', 0)} entries have tax set but no tax group/rate.",
            "severity": "warning",
            "suggested_actions": [{"label": "Check tax settings", "action": "/reports/tax/gst-hst/"}],
        },
        {
            "domain": "ledger_integrity",
            "context": CompanionInsight.CONTEXT_REPORTS,
            "title": "Investigate unbalanced journal entries",
            "body": f"{metrics.get('unbalanced_journal_entries', 0)} journal entries look unbalanced.",
            "severity": "critical" if metrics.get("unbalanced_journal_entries", 0) else "info",
            "suggested_actions": [{"label": "Open ledger", "action": "/chart-of-accounts/"}],
        },
    ]

    random.shuffle(candidates)
    created: list[CompanionInsight] = []
    for candidate in candidates[:5]:
        if candidate["title"] in taken_titles:
            continue
        created.append(
            CompanionInsight.objects.create(
                workspace=workspace,
                created_at=snapshot.created_at or timezone.now(),
                **candidate,
            )
        )
        taken_titles.add(candidate["title"])
    return created
