from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from companion.llm import generate_insights_for_snapshot
from companion.models import CompanionInsight, WorkspaceCompanionProfile
from companion.services import get_latest_health_snapshot
from core.models import Business


class Command(BaseCommand):
    help = "Generate sample Companion insights (stubbed LLM) for recent health snapshots."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Look back this many hours for snapshots.",
        )

    def handle(self, *args, **options):
        hours = options["hours"]
        cutoff = timezone.now() - timedelta(hours=hours)
        created = 0
        skipped = 0

        for workspace in Business.objects.filter(status="active", is_deleted=False):
            profile, _ = WorkspaceCompanionProfile.objects.get_or_create(workspace=workspace)
            if not profile.is_enabled or not profile.enable_suggestions:
                skipped += 1
                continue

            snapshot = (
                workspace.health_snapshots.filter(created_at__gte=cutoff).order_by("-created_at").first()
                or get_latest_health_snapshot(workspace)
            )
            if snapshot is None:
                skipped += 1
                continue

            existing = CompanionInsight.objects.filter(workspace=workspace, is_dismissed=False)
            if existing.exists():
                skipped += 1
                continue

            generated = generate_insights_for_snapshot(snapshot)
            created += len(generated)

        self.stdout.write(self.style.SUCCESS(f"Generated {created} insights; skipped {skipped} workspaces."))
