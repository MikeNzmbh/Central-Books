from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import models
from django.utils import timezone

from companion.models import AIIntegrityReport, AICircuitBreakerEvent, ProvisionalLedgerEvent
from companion.v2.auditor import audit_workspace
from core.models import Business


class Command(BaseCommand):
    help = "Run Companion v2 adversarial auditor (rules-only) and write a weekly integrity report per workspace."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, default=None, help="Run only for a single workspace ID.")
        parser.add_argument("--days", type=int, default=7, help="Lookback window size (default: 7).")
        parser.add_argument("--dry-run", action="store_true", help="Compute but do not write AIIntegrityReport rows.")

    def handle(self, *args, **options):
        workspace_id = options.get("workspace_id")
        days = max(1, int(options.get("days") or 7))
        dry_run = bool(options.get("dry_run"))

        period_end = timezone.localdate()
        period_start = period_end - timedelta(days=days)

        qs = Business.objects.filter(status="active", is_deleted=False)
        if workspace_id:
            qs = qs.filter(id=int(workspace_id))

        processed = 0
        total_flagged = 0
        for workspace in qs.iterator():
            processed += 1
            summary, findings = audit_workspace(workspace=workspace, period_start=period_start, period_end=period_end)

            shadow_qs = ProvisionalLedgerEvent.objects.filter(
                workspace=workspace,
                created_at__date__gte=period_start,
                created_at__date__lte=period_end,
            )
            summary["shadow"] = {
                "proposals": shadow_qs.count(),
                "applied": shadow_qs.filter(status=ProvisionalLedgerEvent.Status.APPLIED).count(),
                "rejected": shadow_qs.filter(status=ProvisionalLedgerEvent.Status.REJECTED).count(),
            }
            breaker_qs = AICircuitBreakerEvent.objects.filter(
                workspace=workspace,
                created_at__date__gte=period_start,
                created_at__date__lte=period_end,
            )
            summary["breakers"] = {
                "trips": breaker_qs.count(),
                "by_type": list(breaker_qs.values("breaker").order_by("breaker").annotate(count=models.Count("id"))),
            }

            flagged_items = [
                {
                    "content_type_id": f.content_type_id,
                    "object_id": f.object_id,
                    "reasons": f.reasons,
                    "details": f.details,
                }
                for f in findings
            ]

            total_flagged += len(flagged_items)

            if not dry_run:
                AIIntegrityReport.objects.update_or_create(
                    workspace=workspace,
                    period_start=period_start,
                    period_end=period_end,
                    defaults={"summary": summary, "flagged_items": flagged_items},
                )

            self.stdout.write(
                f"[auditor] workspace={workspace.id} period={period_start}..{period_end} "
                f"shadow={summary['shadow']['proposals']} flagged={len(flagged_items)} dry_run={dry_run}"
            )

        self.stdout.write(self.style.SUCCESS(f"Auditor complete. workspaces={processed} flagged={total_flagged}"))
