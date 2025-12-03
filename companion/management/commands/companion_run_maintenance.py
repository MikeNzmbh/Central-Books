from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from companion.models import CompanionSuggestedAction, WorkspaceCompanionProfile
from companion.services import create_health_snapshot, get_latest_health_snapshot, refresh_suggested_actions_for_workspace
from core.models import Business


class Command(BaseCommand):
    help = "Run periodic Companion maintenance: refresh stale health snapshots and regenerate suggested actions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-age-hours",
            type=int,
            default=24,
            help="Maximum age (in hours) before a health snapshot is refreshed. Default: 24h.",
        )

    def handle(self, *args, **options):
        max_age_hours = max(1, options.get("max_age_hours") or 24)
        max_age_minutes = max_age_hours * 60

        processed = 0
        snapshots_refreshed = 0
        actions_generated = 0
        created_profiles = 0
        errors = 0

        workspaces = Business.objects.filter(status="active", is_deleted=False)
        for workspace in workspaces:
            processed += 1
            profile, created = WorkspaceCompanionProfile.objects.get_or_create(workspace=workspace)
            if created:
                created_profiles += 1

            if not profile.is_enabled:
                continue

            snapshot = get_latest_health_snapshot(workspace)
            try:
                if profile.enable_health_index:
                    is_stale = not snapshot or (
                        snapshot.created_at < timezone.now() - timedelta(minutes=max_age_minutes)
                    )
                    if is_stale:
                        snapshot = create_health_snapshot(workspace)
                        snapshots_refreshed += 1

                if profile.enable_suggestions:
                    before_count = CompanionSuggestedAction.objects.filter(
                        workspace=workspace, status=CompanionSuggestedAction.STATUS_OPEN
                    ).count()
                    refresh_suggested_actions_for_workspace(workspace, snapshot=snapshot)
                    after_count = CompanionSuggestedAction.objects.filter(
                        workspace=workspace, status=CompanionSuggestedAction.STATUS_OPEN
                    ).count()
                    actions_generated += max(0, after_count - before_count)
            except Exception as exc:  # pragma: no cover - defensive logging
                errors += 1
                self.stderr.write(f"[companion] Maintenance failed for workspace {workspace.id}: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {processed} workspaces | refreshed={snapshots_refreshed} | "
                f"actions_delta={actions_generated} | new_profiles={created_profiles} | errors={errors}"
            )
        )
