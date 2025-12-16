from __future__ import annotations

import json
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from companion.models import CompanionInsight
from core.models import Business
from taxes.models import TaxAnomaly, TaxPeriodSnapshot
from taxes.services import compute_tax_due_date

class Command(BaseCommand):
    """
    Tax nudge notifications (Option B cron-friendly).

    This command is intentionally deterministic-first:
    - It never computes tax amounts via AI.
    - It creates lightweight CompanionInsight records to surface filing risk and tax blockers.

    Intended to run via cron after tax_refresh_period + tax_watchdog_period.
    Spec: docs/tax_engine_v1_blueprint.md
    """

    help = "Create/update tax nudges (Companion insights) for due-soon/overdue filings and unresolved anomalies."

    def add_arguments(self, parser):
        parser.add_argument("--business-id", help="Optional Business UUID/ID to scope the run")
        parser.add_argument(
            "--lookback-days",
            type=int,
            default=120,
            help="Only consider snapshots whose period end is within this lookback window (default 120).",
        )
        parser.add_argument("--dry-run", action="store_true", help="Print nudges but do not write to DB.")

    def handle(self, *args, **options):
        business_id = options.get("business_id")
        lookback_days = int(options.get("lookback_days") or 120)
        dry_run = bool(options.get("dry_run"))

        businesses = Business.objects.all()
        if business_id:
            businesses = businesses.filter(pk=business_id)

        today = timezone.localdate()
        created = 0
        updated = 0
        emitted = 0

        for business in businesses.iterator():
            # Only look at recent-ish snapshots to avoid resurrecting very old filings.
            snapshots = list(TaxPeriodSnapshot.objects.filter(business=business).order_by("-period_key")[:36])
            if not snapshots:
                continue

            def _period_end(snap: TaxPeriodSnapshot):
                # Use the due-date helper to infer period end indirectly; safe enough for lookback gating.
                # (We don't store period_end, and period_key can be monthly or quarterly.)
                try:
                    due = compute_tax_due_date(business, snap.period_key)
                except Exception:
                    return None
                # end_date is "due month - 1"; approximate as due - 1 month.
                approx_end = due - timedelta(days=min(31, due.day))
                return approx_end

            cutoff = today - timedelta(days=lookback_days)
            snapshots = [s for s in snapshots if (_period_end(s) is None or _period_end(s) >= cutoff)]
            if not snapshots:
                continue

            def _due_meta(snap: TaxPeriodSnapshot):
                due = compute_tax_due_date(business, snap.period_key)
                is_filed = snap.status == TaxPeriodSnapshot.SnapshotStatus.FILED
                is_overdue = (today > due) and not is_filed
                is_due_soon = (not is_overdue) and (not is_filed) and 0 <= (due - today).days <= 7
                return due, is_due_soon, is_overdue

            # Choose one filing-risk nudge: overdue beats due-soon.
            filing_candidate = None
            filing_state = None  # "overdue" | "due_soon"
            for snap in snapshots:
                due, is_due_soon, is_overdue = _due_meta(snap)
                if is_overdue:
                    # Prefer the most recently missed due date (closest overdue).
                    if not filing_candidate:
                        filing_candidate = (snap, due)
                        filing_state = "overdue"
                    else:
                        _, best_due = filing_candidate
                        if due > best_due:
                            filing_candidate = (snap, due)
                            filing_state = "overdue"
                elif is_due_soon and filing_state != "overdue":
                    if not filing_candidate:
                        filing_candidate = (snap, due)
                        filing_state = "due_soon"
                    else:
                        _, best_due = filing_candidate
                        if due < best_due:
                            filing_candidate = (snap, due)
                            filing_state = "due_soon"

            # Choose one anomalies nudge: any high-sev open anomalies for the latest period with blockers.
            anomalies_candidate = None
            for snap in snapshots:
                blockers = TaxAnomaly.objects.filter(
                    business=business,
                    period_key=snap.period_key,
                    severity=TaxAnomaly.AnomalySeverity.HIGH,
                    status=TaxAnomaly.AnomalyStatus.OPEN,
                )
                if blockers.exists():
                    anomalies_candidate = snap
                    break

            def upsert_insight(*, title: str, body: str, severity: str, period_key: str | None):
                nonlocal created, updated, emitted
                emitted += 1
                suggested_actions = []
                if period_key:
                    suggested_actions.append(
                        {"label": "Open Tax Guardian", "action": f"/ai-companion/tax?period={period_key}"}
                    )
                suggested_actions.append({"label": "Tax settings", "action": "/ai-companion/tax/settings"})
                payload = {
                    "domain": "tax_filing",
                    "context": CompanionInsight.CONTEXT_TAX_FX,
                    "title": title,
                    "body": body,
                    "severity": severity,
                    "suggested_actions": suggested_actions,
                    "valid_until": (timezone.now() + timedelta(days=30)),
                }
                if dry_run:
                    self.stdout.write(json.dumps({"business": str(business.id), **payload}, default=str))
                    return

                existing = CompanionInsight.objects.filter(
                    workspace=business,
                    domain=payload["domain"],
                    title=payload["title"],
                    is_dismissed=False,
                ).first()
                if existing:
                    existing.body = payload["body"]
                    existing.severity = payload["severity"]
                    existing.suggested_actions = payload["suggested_actions"]
                    existing.context = payload["context"]
                    existing.valid_until = payload["valid_until"]
                    existing.save(update_fields=["body", "severity", "suggested_actions", "context", "valid_until"])
                    updated += 1
                else:
                    CompanionInsight.objects.create(workspace=business, **payload)
                    created += 1

            if filing_candidate and filing_state:
                snap, due = filing_candidate
                if filing_state == "overdue":
                    upsert_insight(
                        title=f"Tax filing overdue — {snap.period_key}",
                        body=f"Tax period {snap.period_key} is past due (due {due.isoformat()}). File or mark as filed once complete.",
                        severity="critical",
                        period_key=snap.period_key,
                    )
                else:
                    upsert_insight(
                        title=f"Tax filing due soon — {snap.period_key}",
                        body=f"Tax period {snap.period_key} is due soon (due {due.isoformat()}). Review anomalies before filing.",
                        severity="warning",
                        period_key=snap.period_key,
                    )

            if anomalies_candidate:
                blockers_count = TaxAnomaly.objects.filter(
                    business=business,
                    period_key=anomalies_candidate.period_key,
                    severity=TaxAnomaly.AnomalySeverity.HIGH,
                    status=TaxAnomaly.AnomalyStatus.OPEN,
                ).count()
                upsert_insight(
                    title=f"High-severity tax anomalies — {anomalies_candidate.period_key}",
                    body=f"{blockers_count} high-severity tax anomalies are still open for {anomalies_candidate.period_key}. Resolve before filing.",
                    severity="warning" if blockers_count < 3 else "critical",
                    period_key=anomalies_candidate.period_key,
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Tax nudges complete. emitted={emitted} created={created} updated={updated} dry_run={dry_run}"
            )
        )
