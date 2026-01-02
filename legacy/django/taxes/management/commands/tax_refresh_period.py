from django.core.management.base import BaseCommand, CommandError

from core.models import Business
from taxes.services import compute_tax_period_snapshot


class Command(BaseCommand):
    help = "Compute or refresh TaxPeriodSnapshot for a business/period (deterministic, no LLM)."

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

        snapshot = compute_tax_period_snapshot(business, period_key)
        self.stdout.write(
            self.style.SUCCESS(
                f"Computed snapshot {snapshot.id} for business={business.id} period={period_key} "
                f"jurisdictions={list((snapshot.summary_by_jurisdiction or {}).keys())}"
            )
        )
