from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from django.utils import timezone

from companion.llm import LLMProfile
from core.llm_reasoning import _invoke_llm, _strip_markdown_json
from taxes.models import TaxAnomaly, TaxPeriodSnapshot
from taxes.services import compute_tax_due_date

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaxLLMEnrichment:
    summary: str
    notes: list[str]
    raw_response: str


def _net_tax_from_snapshot(snapshot: TaxPeriodSnapshot) -> Decimal:
    total = Decimal("0.00")
    for data in (snapshot.summary_by_jurisdiction or {}).values():
        total += Decimal(str((data or {}).get("net_tax", 0)))
    return total


def _rank_anomalies(anomalies: Iterable[TaxAnomaly]) -> list[TaxAnomaly]:
    severity_rank = {
        TaxAnomaly.AnomalySeverity.HIGH: 0,
        TaxAnomaly.AnomalySeverity.MEDIUM: 1,
        TaxAnomaly.AnomalySeverity.LOW: 2,
    }
    return sorted(
        list(anomalies),
        key=lambda a: (
            severity_rank.get(a.severity, 3),
            0 if a.status == TaxAnomaly.AnomalyStatus.OPEN else 1,
            -(a.created_at.timestamp() if a.created_at else 0),
        ),
    )


def build_tax_llm_enrichment_prompt(*, business, snapshot: TaxPeriodSnapshot, anomalies: list[TaxAnomaly]) -> str:
    """
    Build a compact, deterministic-first prompt for LLM observer enrichment.

    Guardrails:
    - Amounts are authoritative from deterministic computation.
    - The model may explain/describe, but must not "recalculate" or change numbers.
    """
    due_date = None
    try:
        due_date = compute_tax_due_date(business, snapshot.period_key).isoformat()
    except Exception:
        due_date = None

    top_anomalies = []
    for a in _rank_anomalies(anomalies)[:3]:
        top_anomalies.append(
            {
                "code": a.code,
                "severity": a.severity,
                "status": a.status,
                "description": a.description,
            }
        )

    payload = {
        "business": {
            "name": getattr(business, "name", None),
            "currency": getattr(business, "currency", None),
            "tax_country": getattr(business, "tax_country", None),
            "tax_region": getattr(business, "tax_region", None),
        },
        "period_key": snapshot.period_key,
        "country": snapshot.country,
        "status": snapshot.status,
        "due_date": due_date,
        "net_tax_total": str(_net_tax_from_snapshot(snapshot)),
        "line_mappings": snapshot.line_mappings or {},
        "top_anomalies": top_anomalies,
    }

    return (
        "You are Central Books Tax Guardian (observer). "
        "Amounts and line mappings are authoritative and already computed deterministically. "
        "Do NOT recompute, adjust, or invent numbers. "
        "Return ONLY valid JSON with this schema:\n"
        "{\n"
        '  "summary": string,  // <= 40 words\n'
        '  "notes": string[]   // up to 5 bullets, <= 16 words each\n'
        "}\n\n"
        "DATA:\n"
        f"{json.dumps(payload, separators=(',', ':'), ensure_ascii=False)}"
    )


def enrich_tax_period_snapshot_llm(
    *,
    business,
    snapshot: TaxPeriodSnapshot,
    anomalies: list[TaxAnomaly],
    profile: LLMProfile = LLMProfile.LIGHT_CHAT,
    llm_client=None,
    timeout_seconds: int | None = 20,
) -> TaxLLMEnrichment | None:
    """
    Call the LLM as an observer and store a compact narrative.
    Returns None if disabled/failed/invalid output.
    """
    prompt = build_tax_llm_enrichment_prompt(business=business, snapshot=snapshot, anomalies=anomalies)
    raw = _invoke_llm(
        prompt,
        llm_client=llm_client,
        timeout_seconds=timeout_seconds,
        profile=profile,
        context_tag="tax_enrich",
    )
    if not raw:
        return None
    try:
        parsed = json.loads(_strip_markdown_json(raw))
    except Exception:
        logger.warning("Tax LLM enrichment returned non-JSON output")
        return None

    summary = (parsed.get("summary") or "").strip()
    notes = parsed.get("notes") or []
    if not isinstance(notes, list):
        notes = []
    notes = [str(n).strip() for n in notes if str(n).strip()]
    if not summary:
        return None

    return TaxLLMEnrichment(summary=summary, notes=notes[:5], raw_response=raw)
