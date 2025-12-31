"""
LLM Provider Architecture
=========================

STRICT RULE: OpenAI and DeepSeek have separate responsibilities.

┌─────────────────────────────────────────────────────────────────────┐
│  OpenAI (gpt-4o-mini)  →  Vision/OCR ONLY                          │
│  - Receipt image extraction                                         │
│  - Invoice image extraction                                         │
│  - Any future document image analysis                               │
│  - Requires: OPENAI_API_KEY                                         │
│  - Entry point: call_openai_vision()                                │
├─────────────────────────────────────────────────────────────────────┤
│  DeepSeek  →  ALL text reasoning                                    │
│  - Companion insights & narratives                                  │
│  - Risk ranking & prioritization                                    │
│  - Summaries, explanations, follow-ups                              │
│  - Non-image planning & reasoning                                   │
│  - Requires: COMPANION_LLM_API_KEY (DeepSeek key)                   │
│  - Entry point: call_deepseek_reasoning()                           │
└─────────────────────────────────────────────────────────────────────┘

NEVER use OpenAI for text-only reasoning.
NEVER use DeepSeek for image/vision tasks.
"""

from __future__ import annotations

from __future__ import annotations

import json
import logging
import random
import time
import hashlib
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


def call_deepseek_reasoning(prompt: str, *, temperature: float = 0.1) -> str | None:
    """
    Call DeepSeek LLM for text-based reasoning tasks.
    
    PROVIDER: DeepSeek (via COMPANION_LLM_API_KEY)
    USE FOR: Narratives, insights, rankings, summaries, reasoning
    DO NOT USE FOR: Image/vision/OCR tasks
    
    Returns the raw text content or None on failure/disabled.
    """
    if not _is_llm_enabled():
        logger.debug("[PROVIDER: DeepSeek] Disabled (COMPANION_LLM_ENABLED=False or missing keys)")
        return None

    api_base = getattr(settings, "COMPANION_LLM_API_BASE", "")
    api_key = getattr(settings, "COMPANION_LLM_API_KEY", "")
    
    # Use profile-based model selection first; fall back to env/default
    default_model = LLMProfile.LIGHT_CHAT.value
    if profile is not None:
        model = profile.value
    else:
        model = getattr(settings, "COMPANION_LLM_MODEL", None) or default_model

    logger.info("[PROVIDER: DeepSeek] Calling %s model for text reasoning", model)
    
    try:
        response = requests.post(
            api_url,
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
            logger.warning("[PROVIDER: DeepSeek] Empty choices in response")
            return None
        message = choices[0].get("message") or {}
        content = message.get("content")
        if content:
            logger.info("[PROVIDER: DeepSeek] Reasoning call succeeded")
        return content
    except Exception as exc:  # pragma: no cover - defensive network wrapper
        logger.warning("[PROVIDER: DeepSeek] Call failed: %s", exc)
        return None
    except requests.exceptions.Timeout:
        logger.warning("[PROVIDER: DeepSeek] Request timed out after %ds (model=%s)", timeout, model)
        return None
    except Exception as exc:  # pragma: no cover - defensive network wrapper
        logger.warning("[PROVIDER: DeepSeek] Call failed: %s", exc)
        return None


# Backwards compatibility alias
call_companion_llm = call_deepseek_reasoning


def call_openai_vision(
    prompt: str,
    image_base64: str,
    image_type: str = "image/jpeg",
    *,
    temperature: float = 0.1,
    max_tokens: int = 1024,
) -> str | None:
    """
    Call OpenAI Vision API for image analysis.
    
    PROVIDER: OpenAI (gpt-4o-mini)
    USE FOR: Receipt OCR, invoice OCR, document image extraction
    DO NOT USE FOR: Text-only reasoning tasks (use call_deepseek_reasoning instead)
    
    Args:
        prompt: Instructions for what to extract from the image
        image_base64: Base64-encoded image data
        image_type: MIME type of the image (default: image/jpeg)
        temperature: Sampling temperature (default: 0.1 for deterministic output)
        max_tokens: Maximum tokens in response (default: 1024)
    
    Returns:
        Extracted text content or None if OCR failed/disabled
    """
    openai_key = getattr(settings, "OPENAI_API_KEY", None)
    
    if not openai_key:
        logger.warning(
            "[PROVIDER: OpenAI] Vision OCR disabled - OPENAI_API_KEY not set. "
            "Set this environment variable to enable receipt/invoice OCR."
        )
        return None
    
    logger.info("[PROVIDER: OpenAI] Calling gpt-4o-mini for vision OCR")
    
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",  # Vision-capable model
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{image_type};base64,{image_base64}",
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=45,
        )
        
        if response.status_code == 200:
            data = response.json()
            choices = data.get("choices") or []
            if choices:
                content = choices[0].get("message", {}).get("content")
                if content:
                    logger.info("[PROVIDER: OpenAI] Vision OCR succeeded")
                    return content
            logger.warning("[PROVIDER: OpenAI] Vision API returned empty choices")
            return None
        else:
            # Extract error details for logging
            body_snippet = response.text[:400] if response.text else "(empty)"
            logger.warning(
                "[PROVIDER: OpenAI] Vision API error. status=%s error=%s",
                response.status_code,
                body_snippet,
            )
            return None
            
    except requests.exceptions.Timeout:
        logger.warning("[PROVIDER: OpenAI] Vision API timed out after 45s")
        return None
    except Exception as exc:
        logger.warning("[PROVIDER: OpenAI] Vision API call failed: %s", exc)
        return None


# Backwards compatibility alias
call_vision_llm = call_openai_vision


# Backwards compatibility alias
call_companion_llm = call_deepseek_reasoning


def call_openai_vision(
    prompt: str,
    image_base64: str,
    image_type: str = "image/jpeg",
    *,
    temperature: float = 0.1,
    max_tokens: int = 1024,
) -> str | None:
    """
    Call OpenAI Vision API for image analysis.
    
    PROVIDER: OpenAI (gpt-4o-mini)
    USE FOR: Receipt OCR, invoice OCR, document image extraction
    DO NOT USE FOR: Text-only reasoning tasks (use call_deepseek_reasoning instead)
    
    Args:
        prompt: Instructions for what to extract from the image
        image_base64: Base64-encoded image data
        image_type: MIME type of the image (default: image/jpeg)
        temperature: Sampling temperature (default: 0.1 for deterministic output)
        max_tokens: Maximum tokens in response (default: 1024)
    
    Returns:
        Extracted text content or None if OCR failed/disabled
    """
    openai_key = getattr(settings, "OPENAI_API_KEY", None)
    
    if not openai_key:
        logger.warning(
            "[PROVIDER: OpenAI] Vision OCR disabled - OPENAI_API_KEY not set. "
            "Set this environment variable to enable receipt/invoice OCR."
        )
        return None
    
    logger.info("[PROVIDER: OpenAI] Calling gpt-4o-mini for vision OCR")
    
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",  # Vision-capable model
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{image_type};base64,{image_base64}",
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=45,
        )
        
        if response.status_code == 200:
            data = response.json()
            choices = data.get("choices") or []
            if choices:
                content = choices[0].get("message", {}).get("content")
                if content:
                    logger.info("[PROVIDER: OpenAI] Vision OCR succeeded")
                    return content
            logger.warning("[PROVIDER: OpenAI] Vision API returned empty choices")
            return None
        else:
            # Extract error details for logging
            body_snippet = response.text[:400] if response.text else "(empty)"
            logger.warning(
                "[PROVIDER: OpenAI] Vision API error. status=%s error=%s",
                response.status_code,
                body_snippet,
            )
            return None
            
    except requests.exceptions.Timeout:
        logger.warning("[PROVIDER: OpenAI] Vision API timed out after 45s")
        return None
    except Exception as exc:
        logger.warning("[PROVIDER: OpenAI] Vision API call failed: %s", exc)
        return None


# Backwards compatibility alias
call_vision_llm = call_openai_vision


# --- Narrative reasoning ---

_LLM_CACHE: dict[tuple[int, int, str], tuple[float, dict]] = {}
_LLM_CACHE_TTL_SECONDS = 10 * 60
_LLM_CACHE_MAX_ENTRIES = 500


def _cache_get(key: tuple[int, int, str]) -> dict | None:
    entry = _LLM_CACHE.get(key)
    if not entry:
        return None
    expires_at, payload = entry
    if time.time() > expires_at:
        _LLM_CACHE.pop(key, None)
        return None
    return payload


def _cache_set(key: tuple[int, int, str], value: dict) -> None:
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


def _severity_rank(value: str | None) -> int:
    order = {
        CompanionSuggestedAction.SEVERITY_CRITICAL: 0,
        CompanionSuggestedAction.SEVERITY_HIGH: 1,
        CompanionSuggestedAction.SEVERITY_MEDIUM: 2,
        CompanionSuggestedAction.SEVERITY_LOW: 3,
        CompanionSuggestedAction.SEVERITY_INFO: 4,
    }
    return order.get(value or CompanionSuggestedAction.SEVERITY_INFO, len(order))


def generate_companion_narrative(
    snapshot: HealthIndexSnapshot | None,
    insights: Sequence[CompanionInsight],
    raw_metrics: dict,
    actions: Sequence | None = None,
    context: str | None = None,
    context_reasons: Sequence[str] | None = None,
    metrics_summary: dict | None = None,
    context_severity: str | None = None,
) -> dict:
    """
    Returns {"summary": str|None, "insight_explanations": {id: str}}
    """
    default = {"summary": None, "insight_explanations": {}, "action_explanations": {}, "context_summary": None}
    if snapshot is None:
        return default

    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "metrics": metrics_summary or raw_metrics,
                "actions": [
                    {"id": a.id, "severity": getattr(a, "severity", None), "short_title": getattr(a, "short_title", None)}
                    for a in actions or []
                ],
                "reasons": list(context_reasons or []),
                "context": context,
            },
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    cache_key = (snapshot.workspace_id, snapshot.id, fingerprint)
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
        "You are a senior bookkeeper. Only use the metrics, context reasons, and actions provided. "
        "Never invent numbers, dates, accounts, or entities. "
        "Produce a concise JSON response with: "
        "summary (2-3 sentences, lead with the highest severity issues; if all clear, say so), "
        "context_summary (1-3 short lines for the current context), "
        "focus_items (up to 3 directive bullets), "
        "insight_explanations (map insight_id -> short sentence), "
        "action_explanations (map action_id -> short sentence). "
        "Tone: calm, professional, direct; prioritize higher severities."
    )

    sorted_actions = sorted(actions or [], key=lambda a: (_severity_rank(getattr(a, "severity", None)), -(a.created_at.timestamp() if getattr(a, "created_at", None) else 0)))
    top_actions = sorted_actions[:3]
    action_payload = []
    for action in top_actions:
        payload = action.payload or {}
        severity = getattr(action, "severity", None) or payload.get("severity") or CompanionSuggestedAction.SEVERITY_INFO
        action_payload.append(
            {
                "id": action.id,
                "short_title": getattr(action, "short_title", None) or action.summary,
                "action_type": action.action_type,
                "context": getattr(action, "context", CompanionSuggestedAction.CONTEXT_DASHBOARD),
                "confidence": float(action.confidence or 0),
                "severity": severity,
                "impact": payload.get("impact"),
                "metrics": {
                    "count": payload.get("old_unreconciled") or payload.get("unreconciled_remaining") or payload.get("expense_ids") and len(payload.get("expense_ids")),
                    "amount": payload.get("total_amount") or payload.get("balance") or payload.get("amount"),
                    "days": payload.get("days_overdue"),
                },
            }
        )

    prompt = json.dumps(
        {
            "health": health,
            "insights": insight_payload,
            "actions": action_payload,
            "context": context,
            "context_reasons": list(context_reasons or []),
            "metrics_summary": metrics_summary or {},
            "context_severity": context_severity,
            "expected_output": {
                "summary": "short paragraph",
                "insight_explanations": {"<insight_id>": "explanation"},
                "action_explanations": {"<action_id>": "explanation"},
                "context_summary": "1-2 line optional summary for the provided context",
                "focus_items": ["item 1", "item 2"],
            },
        }
    )

    try:
        raw_reply = call_companion_llm(
            f"{system_prompt}\n\nDATA:\n{prompt}",
            profile=LLMProfile.HEAVY_REASONING,
            context_tag="companion_narrative",
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Companion LLM call raised: %s", exc)
        return default
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
    focus_items = parsed.get("focus_items") if isinstance(parsed.get("focus_items"), list) else []
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
        "focus_items": focus_items if isinstance(focus_items, list) else [],
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
