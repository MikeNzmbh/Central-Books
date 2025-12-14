from django.db import migrations


def seed_more_us_jurisdictions(apps, schema_editor):
    TaxJurisdiction = apps.get_model("taxes", "TaxJurisdiction")

    def upsert(code, name, region_code, sourcing_rule):
        parent = TaxJurisdiction.objects.filter(code="US").first()
        TaxJurisdiction.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "jurisdiction_type": "STATE",
                "country_code": "US",
                "region_code": region_code,
                "sourcing_rule": sourcing_rule,
                "parent": parent,
                "is_active": True,
            },
        )

    # Blueprint-aligned origin states (missing from initial seed).
    upsert("US-AZ", "Arizona", "AZ", "ORIGIN")
    upsert("US-MO", "Missouri", "MO", "ORIGIN")
    upsert("US-UT", "Utah", "UT", "ORIGIN")
    upsert("US-VA", "Virginia", "VA", "ORIGIN")

    # Blueprint correction: Illinois is origin-based.
    upsert("US-IL", "Illinois", "IL", "ORIGIN")


class Migration(migrations.Migration):
    dependencies = [
        ("taxes", "0010_taxgroup_tax_treatment"),
    ]

    operations = [
        migrations.RunPython(seed_more_us_jurisdictions, migrations.RunPython.noop),
    ]

