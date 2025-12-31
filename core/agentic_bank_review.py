from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional
from uuid import uuid4

from django.db.models import Sum

from agentic.logging.tracing import trace_event

from .llm_reasoning import BankReviewLLMResult, reason_about_bank_review
from .models import Business, JournalEntry

RISK_WARNING_THRESHOLD = Decimal("40.0")
RISK_HIGH_THRESHOLD = Decimal("70.0")


@dataclass
class BankInputLine:
    date: date
    description: str
    amount: Decimal
    external_id: Optional[str] = None


@dataclass
class BankTransactionResult:
    raw_payload: dict
    matched_journal_ids: list
    status: str
    audit_flags: list
    audit_score: Decimal | None
    audit_explanations: list
    error: Optional[str] = None
    reference_id: str | None = None


@dataclass
class BankReconciliationResult:
    engine_run_id: str
    trace_id: str
    transactions: List[BankTransactionResult]
    metrics: dict
    overall_risk_score: Decimal
    llm_explanations: list
    llm_ranked_transactions: list
    llm_suggested_followups: list


def run_bank_reconciliation_workflow(
    *,
    business_id: int,
    bank_lines: List[BankInputLine],
    period_start: date | None,
    period_end: date | None,
    triggered_by_user_id: int,
    ai_companion_enabled: bool | None = None,
) -> BankReconciliationResult:
    """
    Review-only reconciliation helper. Deterministic matching/audit runs first; AI companion is an optional, best-effort reasoning layer that never mutates data.
    """
    business = Business.objects.get(pk=business_id)
    trace_id = f"bank-review-trace-{uuid4().hex}"
    engine_run_id = f"bank-review-run-{uuid4().hex}"
    results: list[BankTransactionResult] = []
    trace_events: list[dict] = []
    agent_retries = 0
    llm_explanations: list[str] = []
    llm_ranked_transactions: list[dict] = []
    llm_suggested_followups: list[str] = []

    # Precompute journal entry amounts keyed by (date, rounded abs amount)
    entries = JournalEntry.objects.filter(business=business)
    if period_start:
        entries = entries.filter(date__gte=period_start)
    if period_end:
        entries = entries.filter(date__lte=period_end)
    entries = entries.annotate(total_debit=Sum("lines__debit"), total_credit=Sum("lines__credit"))

    journal_map: dict[tuple[date, Decimal], list[int]] = {}
    journal_desc_map: dict[str, list[int]] = {}
    for entry in entries:
        amount = max(Decimal(entry.total_debit or 0), Decimal(entry.total_credit or 0))
        key = (entry.date, amount.quantize(Decimal("0.01")))
        journal_map.setdefault(key, []).append(entry.id)
        if entry.description:
            journal_desc_map.setdefault(entry.description.lower(), []).append(entry.id)

    seen_external_ids: set[str] = set()

    def _score_flags(flags: list[dict]) -> Decimal:
        base = Decimal("5.0")
        for f in flags:
            sev = (f.get("severity") or "").lower()
            if sev == "high":
                base += Decimal("40.0")
            elif sev == "medium":
                base += Decimal("20.0")
            else:
                base += Decimal("5.0")
        return min(base, Decimal("100.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    for idx, line in enumerate(bank_lines):
        flags: list[dict] = []
        explanations: list[str] = []
        matched_ids: list[int] = []
        status = "UNMATCHED"
        reference_id = line.external_id or f"line-{idx}"

        if line.external_id and line.external_id in seen_external_ids:
            flags.append({"code": "DUPLICATE_LINE", "severity": "high", "message": "Duplicate external bank id detected."})
            status = "DUPLICATE"
        seen_external_ids.add(line.external_id or "")

        key = (line.date, abs(line.amount).quantize(Decimal("0.01")))
        if key in journal_map:
            matched_ids.extend(journal_map[key])
            status = "MATCHED"
        else:
            flags.append({"code": "UNMATCHED_TRANSACTION", "severity": "high", "message": "No ledger match found."})

        if ai_companion_enabled and status != "MATCHED":
            # Fuzzy/heuristic attempt: match by description substring
            for desc, ids in journal_desc_map.items():
                if line.description and line.description.lower().split()[0:1] and any(
                    token in desc for token in line.description.lower().split()
                ):
                    matched_ids.extend(ids)
                    status = "PARTIAL_MATCH"
                    flags.append(
                        {
                            "code": "POTENTIAL_MATCH",
                            "severity": "medium",
                            "message": "Description similarity suggests a potential match.",
                        }
                    )
                    break
            if flags:
                agent_retries += 1
                explanations.append("Companion reflection attempted fuzzy matching on unmatched lines.")
                trace_events.append(
                    trace_event(
                        agent="bank_review.companion",
                        event="reflection",
                        metadata={
                            "trace_id": trace_id,
                            "line_description": line.description,
                            "flags": [f.get("code") for f in flags],
                        },
                        level="warning",
                    )
                )

        audit_score = _score_flags(flags)
        trace_events.append(
            trace_event(
                agent="bank_review.workflow",
                event="line_reviewed",
                metadata={
                    "trace_id": trace_id,
                    "status": status,
                    "audit_score": float(audit_score),
                },
                level="info",
            )
        )
        results.append(
            BankTransactionResult(
                raw_payload={
                    "date": line.date.isoformat(),
                    "description": line.description,
                    "amount": str(line.amount),
                    "external_id": line.external_id,
                },
                matched_journal_ids=matched_ids,
                status=status,
                audit_flags=flags,
                audit_score=audit_score,
                audit_explanations=explanations,
                error="Duplicate line" if status == "DUPLICATE" else None,
                reference_id=reference_id,
            )
        )

    total = len(results)
    unmatched = [r for r in results if r.status in {"UNMATCHED", "ERROR"}]
    high_risk = [r for r in results if r.audit_score is not None and r.audit_score >= RISK_HIGH_THRESHOLD]
    reconciled = [r for r in results if r.status == "MATCHED"]

    overall_risk = (
        min(Decimal("5.0") + Decimal("15.0") * len(high_risk) + Decimal("10.0") * len(unmatched), Decimal("100.0"))
        .quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )

    metrics = {
        "transactions_total": total,
        "transactions_reconciled": len(reconciled),
        "transactions_unreconciled": len(unmatched),
        "transactions_high_risk": len(high_risk),
        "agent_retries": agent_retries,
        "trace_events": trace_events,
    }

    if ai_companion_enabled:
        def _tx_priority(tx: BankTransactionResult):
            score_val = Decimal(tx.audit_score or 0)
            is_unmatched = tx.status in {"UNMATCHED", "ERROR", "DUPLICATE"}
            return (0 if is_unmatched else 1, -float(score_val))

        candidates = sorted(results, key=_tx_priority)
        subset: list[dict] = []
        subset_limit = 15
        for tx in candidates:
            if len(subset) >= subset_limit:
                break
            subset.append(
                {
                    "transaction_id": tx.reference_id,
                    "date": tx.raw_payload.get("date"),
                    "description": tx.raw_payload.get("description"),
                    "amount": tx.raw_payload.get("amount"),
                    "status": tx.status,
                    "audit_flags": tx.audit_flags,
                    "audit_score": str(tx.audit_score) if tx.audit_score is not None else None,
                    "audit_explanations": tx.audit_explanations,
                    "matched_journal_ids": tx.matched_journal_ids,
                }
            )

        llm_metrics = {k: v for k, v in metrics.items() if k != "trace_events"}
        try:
            llm_result = reason_about_bank_review(metrics=llm_metrics, transactions=subset)
            if llm_result:
                llm_explanations = llm_result.explanations
                llm_ranked_transactions = [tx.model_dump() for tx in llm_result.ranked_transactions]
                llm_suggested_followups = llm_result.suggested_followups
        except Exception:
            llm_explanations = []
            llm_ranked_transactions = []
            llm_suggested_followups = []

    return BankReconciliationResult(
        engine_run_id=engine_run_id,
        trace_id=trace_id,
        transactions=results,
        metrics=metrics,
        overall_risk_score=overall_risk,
        llm_explanations=llm_explanations,
        llm_ranked_transactions=llm_ranked_transactions,
        llm_suggested_followups=llm_suggested_followups,
    )
