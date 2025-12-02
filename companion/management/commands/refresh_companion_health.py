from django.core.management.base import BaseCommand

from core.models import Business
from companion.models import WorkspaceCompanionProfile
from companion.services import create_health_snapshot, generate_bank_match_suggestions_for_workspace


class Command(BaseCommand):
    help = "Refresh Companion health index for all active workspaces."

    def handle(self, *args, **options):
        processed = 0
        snapshots = 0
        created_profiles = 0
        errors = 0

        workspaces = Business.objects.filter(status="active", is_deleted=False)
        for workspace in workspaces:
            processed += 1
            profile, created = WorkspaceCompanionProfile.objects.get_or_create(workspace=workspace)
            if created:
                created_profiles += 1

            if not profile.is_enabled or not profile.enable_health_index:
                continue

            try:
                snapshot = create_health_snapshot(workspace)
                snapshots += 1
                generate_bank_match_suggestions_for_workspace(workspace, snapshot=snapshot)
            except Exception as exc:  # pragma: no cover - logged for operational visibility
                errors += 1
                self.stderr.write(f"[companion] Failed snapshot for workspace {workspace.id}: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {processed} workspaces | snapshots={snapshots} | new_profiles={created_profiles} | errors={errors}"
            )
        )
