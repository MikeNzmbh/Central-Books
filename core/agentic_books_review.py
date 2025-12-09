from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import List
from uuid import uuid4

from django.db.models import Sum

from agentic.logging.tracing import trace_event

from .llm_reasoning import BooksReviewLLMResult, reason_about_books_review
from .models import Business, JournalEntry, JournalLine, Account

RISK_WARNING_THRESHOLD = Decimal("40.0")
RISK_HIGH_THRESHOLD = Decimal("70.0")


@dataclass
class BooksReviewResult:
    trace_id: str
    metrics: dict
    overall_risk_score: Decimal
    findings: list
    engine_run_id: str
    llm_explanations: list
    llm_ranked_issues: list
    llm_suggested_checks: list


def run_books_review_workflow(
    *,
    business_id: int,
    period_start: date,
    period_end: date,
    triggered_by_user_id: int,
    ai_companion_enabled: bool | None = None,
    user_name: str | None = None,
) -> BooksReviewResult:
    """
    Read-only, ledger-wide review for a period.
    Deterministic engine runs first (metrics, findings, risk); AI companion is an optional reasoning layer that never mutates data.
    """
    business = Business.objects.get(pk=business_id)
    trace_id = f"books-review-trace-{uuid4().hex}"
    engine_run_id = f"books-review-run-{uuid4().hex}"
    findings: list[dict] = []
    trace_events: list[dict] = []
    llm_explanations: list[str] = []
    llm_ranked_issues: list[dict] = []
    llm_suggested_checks: list[str] = []

    entries_qs = (
        JournalEntry.objects.filter(
            business=business,
            is_void=False,
            date__gte=period_start,
            date__lte=period_end,
        )
        .annotate(total_debit=Sum("lines__debit"), total_credit=Sum("lines__credit"))
        .order_by("-date", "-id")
    )
    entries = list(entries_qs)

    journals_total = len(entries)
    accounts_touched = (
        JournalLine.objects.filter(journal_entry__in=entries)
        .values_list("account_id", flat=True)
        .distinct()
        .count()
    )

    avg_amount = Decimal("0.00")
    amounts: list[Decimal] = []
    for entry in entries:
        amount = max(entry.total_debit or 0, entry.total_credit or 0)
        amounts.append(Decimal(amount or 0))
    if amounts:
        avg_amount = sum(amounts) / len(amounts)

    def add_finding(code: str, severity: str, message: str, refs: dict | None = None):
        findings.append(
            {
                "code": code,
                "severity": severity,
                "message": message,
                "references": refs or {},
            }
        )

    # Basic rule-based checks
    for entry in entries:
        amount = Decimal(entry.total_debit or 0)
        if amount >= Decimal("5000"):
            add_finding(
                "LARGE_ENTRY",
                "high",
                f"Large journal entry {entry.id} ({amount}) on {entry.date}",
                {"journal_entry_id": entry.id},
            )
        if entry.description and entry.description.lower().startswith("adjustment"):
            add_finding(
                "ADJUSTMENT_ENTRY",
                "medium",
                f"Adjustment entry {entry.id} on {entry.date}",
                {"journal_entry_id": entry.id},
            )

    # Duplicate detection (description + date + amount)
    duplicate_cache: dict[tuple[str, date, Decimal], list[int]] = {}
    for entry in entries:
        key = (entry.description or "", entry.date, Decimal(entry.total_debit or 0))
        duplicate_cache.setdefault(key, []).append(entry.id)
    for key, ids in duplicate_cache.items():
        if len(ids) > 1:
            add_finding(
                "POSSIBLE_DUPLICATE",
                "medium",
                f"{len(ids)} entries share desc/date/amount ({key[0]} / {key[1]} / {key[2]})",
                {"journal_entry_ids": ids},
            )

    agent_retries = 0

    if ai_companion_enabled:
        # Companion-enabled: reflect on outliers vs average and suspicious account combos.
        high_threshold = avg_amount * Decimal("3") if avg_amount > 0 else Decimal("3000")
        for entry in entries:
            amount = Decimal(entry.total_debit or 0)
            if avg_amount > 0 and amount > high_threshold:
                add_finding(
                    "OUTLIER_AMOUNT",
                    "high",
                    f"Entry {entry.id} amount {amount} is an outlier vs avg {avg_amount:.2f}",
                    {"journal_entry_id": entry.id},
                )
        # Reflective pass logged as agent retry when findings exist
        if findings:
            agent_retries += 1
            trace_events.append(
                trace_event(
                    agent="books_review.companion",
                    event="reflection",
                    metadata={
                        "trace_id": trace_id,
                        "finding_codes": [f["code"] for f in findings],
                    },
                    level="warning",
                )
            )

    high_risk = [f for f in findings if f.get("severity") == "high"]
    warnings = [f for f in findings if f.get("severity") == "medium"]

    # Overall risk score
    score = Decimal("5.0") + Decimal("20.0") * len(high_risk) + Decimal("10.0") * len(warnings)
    score = min(score, Decimal("100.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    metrics = {
        "journals_total": journals_total,
        "journals_high_risk": len(high_risk),
        "journals_with_warnings": len(warnings),
        "findings_count": len(findings),
        "accounts_touched": accounts_touched,
        "agent_retries": agent_retries,
        "trace_events": trace_events,
    }

    if ai_companion_enabled:
        # Bound and serialize a small, safe subset of journals for LLM context.
        sample_limit = 12
        sample_ids: set[int] = set()
        for finding in findings:
            refs = finding.get("references") or {}
            if refs.get("journal_entry_id"):
                sample_ids.add(int(refs["journal_entry_id"]))
            for jid in refs.get("journal_entry_ids") or []:
                sample_ids.add(int(jid))
        prioritized_entries = [e for e in entries if e.id in sample_ids]
        if len(prioritized_entries) < sample_limit:
            remaining = [e for e in entries if e.id not in sample_ids]
            remaining_sorted = sorted(
                remaining,
                key=lambda e: Decimal(max(e.total_debit or 0, e.total_credit or 0)),
                reverse=True,
            )
            prioritized_entries.extend(remaining_sorted[: sample_limit - len(prioritized_entries)])

        lines = (
            JournalLine.objects.filter(journal_entry__in=[e.id for e in prioritized_entries])
            .select_related("account")
        )
        lines_by_entry: dict[int, list[JournalLine]] = {}
        for line in lines:
            lines_by_entry.setdefault(line.journal_entry_id, []).append(line)

        sample_journals: list[dict] = []
        for entry in prioritized_entries[:sample_limit]:
            amount = Decimal(max(entry.total_debit or 0, entry.total_credit or 0))
            accounts_payload = []
            for line in lines_by_entry.get(entry.id, []):
                if line.account:
                    accounts_payload.append(
                        {
                            "id": line.account.id,
                            "code": line.account.code,
                            "name": line.account.name,
                        }
                    )
            sample_journals.append(
                {
                    "id": entry.id,
                    "date": entry.date.isoformat(),
                    "description": entry.description or "",
                    "amount": str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                    "accounts": accounts_payload,
                }
            )

        llm_metrics = {k: v for k, v in metrics.items() if k != "trace_events"}
        try:
            # Determine risk level for tone
            risk_level = "low" if len(high_risk) == 0 else "high" if len(high_risk) >= 3 else "medium"
            llm_result = reason_about_books_review(
                metrics=llm_metrics,
                findings=findings,
                sample_journals=sample_journals,
                user_name=user_name,
                risk_level=risk_level,
                timeout_seconds=60,  # DeepSeek Reasoner needs generous timeout for chain-of-thought
            )
            if llm_result:
                llm_explanations = llm_result.explanations
                llm_ranked_issues = [issue.model_dump() for issue in llm_result.ranked_issues]
                llm_suggested_checks = llm_result.suggested_checks
        except Exception as exc:
            # LLM is a best-effort reasoning layer; failures must not block deterministic results.
            import logging
            logger = logging.getLogger(__name__)
            logger.error("Books Review LLM failed: %s", exc, exc_info=True)
            llm_explanations = []
            llm_ranked_issues = []
            llm_suggested_checks = []

    trace_events.append(
        trace_event(
            agent="books_review.workflow",
            event="completed",
            metadata={
                "trace_id": trace_id,
                "journals_total": journals_total,
                "score": float(score),
            },
            level="info",
        )
    )

    return BooksReviewResult(
        trace_id=trace_id,
        metrics=metrics,
        overall_risk_score=score,
        findings=findings,
        engine_run_id=engine_run_id,
        llm_explanations=llm_explanations,
        llm_ranked_issues=llm_ranked_issues,
        llm_suggested_checks=llm_suggested_checks,
    )
