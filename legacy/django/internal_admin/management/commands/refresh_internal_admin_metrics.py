from django.core.management.base import BaseCommand

from internal_admin.models import OverviewMetricsSnapshot
from internal_admin.services import compute_overview_metrics


class Command(BaseCommand):
    help = "Recompute and store the internal admin overview metrics snapshot."

    def handle(self, *args, **options):
        payload = compute_overview_metrics()
        OverviewMetricsSnapshot.objects.create(payload=payload)
        self.stdout.write(self.style.SUCCESS("Internal admin metrics snapshot refreshed."))
