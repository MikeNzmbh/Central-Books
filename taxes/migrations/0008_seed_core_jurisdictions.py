from django.db import migrations


def seed_jurisdictions(apps, schema_editor):
    TaxJurisdiction = apps.get_model("taxes", "TaxJurisdiction")

    def upsert(code, name, jurisdiction_type, country_code, region_code="", sourcing_rule="DESTINATION", parent_code=None):
        parent = TaxJurisdiction.objects.filter(code=parent_code).first() if parent_code else None
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

    # Federal roots
    upsert("CA", "Canada", "FEDERAL", "CA", sourcing_rule="DESTINATION")
    upsert("US", "United States", "FEDERAL", "US", sourcing_rule="DESTINATION")

    # Canada provinces/territories
    provinces = [
        ("CA-ON", "Ontario", "ON"),
        ("CA-QC", "Quebec", "QC"),
        ("CA-BC", "British Columbia", "BC"),
        ("CA-AB", "Alberta", "AB"),
        ("CA-MB", "Manitoba", "MB"),
        ("CA-SK", "Saskatchewan", "SK"),
        ("CA-NS", "Nova Scotia", "NS"),
        ("CA-NB", "New Brunswick", "NB"),
        ("CA-PE", "Prince Edward Island", "PE"),
        ("CA-NL", "Newfoundland and Labrador", "NL"),
        ("CA-YT", "Yukon", "YT"),
        ("CA-NT", "Northwest Territories", "NT"),
        ("CA-NU", "Nunavut", "NU"),
    ]
    for code, name, region in provinces:
        upsert(code, name, "PROVINCIAL", "CA", region_code=region, sourcing_rule="DESTINATION", parent_code="CA")

    # US states (minimal set)
    states = [
        ("US-CA", "California", "CA", "HYBRID"),
        ("US-NY", "New York", "NY", "DESTINATION"),
        ("US-TX", "Texas", "TX", "ORIGIN"),
        ("US-WA", "Washington", "WA", "DESTINATION"),
        ("US-FL", "Florida", "FL", "DESTINATION"),
        ("US-IL", "Illinois", "IL", "DESTINATION"),
        ("US-PA", "Pennsylvania", "PA", "ORIGIN"),
        ("US-OH", "Ohio", "OH", "ORIGIN"),
    ]
    for code, name, region, sourcing in states:
        upsert(code, name, "STATE", "US", region_code=region, sourcing_rule=sourcing, parent_code="US")


def link_components_to_jurisdictions(apps, schema_editor):
    TaxJurisdiction = apps.get_model("taxes", "TaxJurisdiction")
    TaxComponent = apps.get_model("taxes", "TaxComponent")

    name_map = {
        "Ontario": "CA-ON",
        "New Brunswick": "CA-NB",
        "Newfoundland": "CA-NL",
        "Prince Edward Island": "CA-PE",
        "Nova Scotia": "CA-NS",
        "British Columbia": "CA-BC",
        "Manitoba": "CA-MB",
        "Saskatchewan": "CA-SK",
        "Quebec": "CA-QC",
        "Federal": "CA",
        "GST": "CA",
    }
    authority_map = {
        "BC-PST": "CA-BC",
        "MB-RST": "CA-MB",
        "SK-PST": "CA-SK",
        "CRA": "CA",
        "RQ": "CA-QC",
    }

    for component in TaxComponent.objects.all():
        if component.jurisdiction_id:
            continue
        code = None
        # Try authority first
        code = authority_map.get(getattr(component, "authority", "") or "")
        # Try name match
        if not code:
            for token, j_code in name_map.items():
                if token.lower() in (component.name or "").lower():
                    code = j_code
                    break
        jurisdiction = TaxJurisdiction.objects.filter(code=code).first() if code else None
        if jurisdiction:
            component.jurisdiction = jurisdiction
            component.save(update_fields=["jurisdiction"])


class Migration(migrations.Migration):

    dependencies = [
        ("taxes", "0007_taxcomponent_jurisdiction_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_jurisdictions, migrations.RunPython.noop),
        migrations.RunPython(link_components_to_jurisdictions, migrations.RunPython.noop),
    ]
