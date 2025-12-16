from django.db import migrations


def seed_sample_us_locals(apps, schema_editor):
    TaxJurisdiction = apps.get_model("taxes", "TaxJurisdiction")

    def upsert(*, code: str, name: str, jurisdiction_type: str, country_code: str, region_code: str, parent_code: str, sourcing_rule: str):
        parent = TaxJurisdiction.objects.filter(code=parent_code).first()
        TaxJurisdiction.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "jurisdiction_type": jurisdiction_type,
                "country_code": country_code,
                "region_code": region_code,
                "sourcing_rule": sourcing_rule,
                "parent": parent,
                "is_active": True,
            },
        )

    # California locals (for HYBRID model examples)
    upsert(
        code="US-CA-LA",
        name="Los Angeles County",
        jurisdiction_type="COUNTY",
        country_code="US",
        region_code="CA",
        parent_code="US-CA",
        sourcing_rule="DESTINATION",
    )
    upsert(
        code="US-CA-SF",
        name="San Francisco",
        jurisdiction_type="CITY",
        country_code="US",
        region_code="CA",
        parent_code="US-CA",
        sourcing_rule="DESTINATION",
    )
    upsert(
        code="US-CA-DIST-1",
        name="BART District (example)",
        jurisdiction_type="DISTRICT",
        country_code="US",
        region_code="CA",
        parent_code="US-CA",
        sourcing_rule="DESTINATION",
    )

    # Destination state local example
    upsert(
        code="US-NY-NYC",
        name="New York City",
        jurisdiction_type="CITY",
        country_code="US",
        region_code="NY",
        parent_code="US-NY",
        sourcing_rule="DESTINATION",
    )

    # Origin state local example
    upsert(
        code="US-TX-TRV",
        name="Travis County",
        jurisdiction_type="COUNTY",
        country_code="US",
        region_code="TX",
        parent_code="US-TX",
        sourcing_rule="ORIGIN",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("taxes", "0012_seed_all_us_states"),
    ]

    operations = [
        migrations.RunPython(seed_sample_us_locals, migrations.RunPython.noop),
    ]

