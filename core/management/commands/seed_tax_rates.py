"""
Management command to seed demo tax rates for Canadian and US businesses.

Usage:
    python manage.py seed_tax_rates --business-id=1
    python manage.py seed_tax_rates --all-businesses
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from core.models import Business, TaxRate


class Command(BaseCommand):
    help = "Seed demo tax rates for development/testing (Canada and US)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--business-id",
            type=int,
            help="Seed rates for a specific business ID"
        )
        parser.add_argument(
            "--all-businesses",
            action="store_true",
            help="Seed rates for all businesses"
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip businesses that already have tax rates"
        )

    def handle(self, *args, **options):
        business_id = options.get("business_id")
        all_businesses = options.get("all_businesses")
        skip_existing = options.get("skip_existing")

        if not business_id and not all_businesses:
            self.stdout.write(
                self.style.ERROR(
                    "Please specify --business-id=<id> or --all-businesses"
                )
            )
            return

        if business_id:
            businesses = Business.objects.filter(id=business_id)
            if not businesses.exists():
                self.stdout.write(
                    self.style.ERROR(f"Business with ID {business_id} not found")
                )
                return
        else:
            businesses = Business.objects.all()

        total_created = 0
        for business in businesses:
            if skip_existing and TaxRate.objects.filter(business=business).exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping {business.name} - already has tax rates"
                    )
                )
                continue

            created_count = self.seed_business(business)
            total_created += created_count
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created {created_count} tax rates for {business.name}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Successfully seeded {total_created} tax rates total"
            )
        )

    def seed_business(self, business):
        """Seed tax rates for a single business based on their country."""
        country = (business.tax_country or "CA").upper()
        created_count = 0

        if country == "CA":
            created_count = self.seed_canadian_rates(business)
        elif country == "US":
            created_count = self.seed_us_rates(business)
        else:
            # Default to Canadian rates for unknown countries
            self.stdout.write(
                self.style.WARNING(
                    f"{business.name} has unsupported country '{country}', using Canadian rates as default"
                )
            )
            created_count = self.seed_canadian_rates(business)

        return created_count

    def seed_canadian_rates(self, business):
        """Seed Canadian tax rates (GST + HST variants)."""
        rates_to_create = [
            {
                "name": "GST",
                "code": "GST",
                "percentage": Decimal("0.05"),
                "country": "CA",
                "region": "",
                "applies_to_sales": True,
                "applies_to_purchases": True,
                "is_active": True,
                "is_default_sales_rate": True,
                "is_default_purchase_rate": True,
            },
            {
                "name": "HST Ontario",
                "code": "HST_ON",
                "percentage": Decimal("0.13"),
                "country": "CA",
                "region": "ON",
                "applies_to_sales": True,
                "applies_to_purchases": True,
                "is_active": True,
            },
            {
                "name": "HST Nova Scotia",
                "code": "HST_NS",
                "percentage": Decimal("0.15"),
                "country": "CA",
                "region": "NS",
                "applies_to_sales": True,
                "applies_to_purchases": True,
                "is_active": True,
            },
            {
                "name": "HST New Brunswick",
                "code": "HST_NB",
                "percentage": Decimal("0.15"),
                "country": "CA",
                "region": "NB",
                "applies_to_sales": True,
                "applies_to_purchases": True,
                "is_active": True,
            },
            {
                "name": "HST Prince Edward Island",
                "code": "HST_PE",
                "percentage": Decimal("0.15"),
                "country": "CA",
                "region": "PE",
                "applies_to_sales": True,
                "applies_to_purchases": True,
                "is_active": True,
            },
            {
                "name": "HST Newfoundland",
                "code": "HST_NL",
                "percentage": Decimal("0.15"),
                "country": "CA",
                "region": "NL",
                "applies_to_sales": True,
                "applies_to_purchases": True,
                "is_active": True,
            },
        ]

        created_count = 0
        for rate_data in rates_to_create:
            rate, created = TaxRate.objects.get_or_create(
                business=business,
                code=rate_data["code"],
                defaults=rate_data
            )
            if created:
                created_count += 1

        return created_count

    def seed_us_rates(self, business):
        """Seed US tax rates (sample state sales tax)."""
        rates_to_create = [
            {
                "name": "Sales Tax (CA)",
                "code": "SALES_TAX_CA",
                "percentage": Decimal("0.085"),
                "country": "US",
                "region": "CA",
                "applies_to_sales": True,
                "applies_to_purchases": False,  # Sales tax typically only on sales
                "is_active": True,
                "is_default_sales_rate": True,
            },
            {
                "name": "Sales Tax (NY)",
                "code": "SALES_TAX_NY",
                "percentage": Decimal("0.08"),
                "country": "US",
                "region": "NY",
                "applies_to_sales": True,
                "applies_to_purchases": False,
                "is_active": True,
            },
            {
                "name": "Sales Tax (TX)",
                "code": "SALES_TAX_TX",
                "percentage": Decimal("0.0625"),
                "country": "US",
                "region": "TX",
                "applies_to_sales": True,
                "applies_to_purchases": False,
                "is_active": True,
            },
        ]

        created_count = 0
        for rate_data in rates_to_create:
            rate, created = TaxRate.objects.get_or_create(
                business=business,
                code=rate_data["code"],
                defaults=rate_data
            )
            if created:
                created_count += 1

        return created_count
