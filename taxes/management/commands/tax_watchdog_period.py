from django.core.management.base import BaseCommand, CommandError

from core.models import Business
from taxes.services import compute_tax_anomalies, compute_tax_period_snapshot


class Command(BaseCommand):
    help = "Run deterministic tax anomaly checks for a business/period."

    def add_arguments(self, parser):
        parser.add_argument("--business-id", required=True, help="Business UUID/ID")
        parser.add_argument("--period", required=True, help="Period key, e.g., 2025Q2 or 2025-04")

    def handle(self, *args, **options):
        business_id = options["business_id"]
        period_key = options["period"]
        try:
            business = Business.objects.get(pk=business_id)
        except Business.DoesNotExist:
            raise CommandError(f"Business {business_id} not found")

        # Ensure snapshot exists
        compute_tax_period_snapshot(business, period_key)
        anomalies = compute_tax_anomalies(business, period_key)
        codes = [a.code for a in anomalies]
        self.stdout.write(
            self.style.SUCCESS(
                f"Watchdog complete for business={business.id} period={period_key}. Anomalies: {codes or 'none'}"
            )
        )
