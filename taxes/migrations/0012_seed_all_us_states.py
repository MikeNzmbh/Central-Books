from django.db import migrations


def seed_all_us_states(apps, schema_editor):
    TaxJurisdiction = apps.get_model("taxes", "TaxJurisdiction")

    us_root, _ = TaxJurisdiction.objects.update_or_create(
        code="US",
        defaults={
            "name": "United States",
            "jurisdiction_type": "FEDERAL",
            "country_code": "US",
            "region_code": "",
            "sourcing_rule": "DESTINATION",
            "parent": None,
            "is_active": True,
        },
    )

    origin_states = {"AZ", "IL", "MO", "OH", "PA", "TX", "UT", "VA"}

    states = [
        ("AL", "Alabama"),
        ("AK", "Alaska"),
        ("AZ", "Arizona"),
        ("AR", "Arkansas"),
        ("CA", "California"),
        ("CO", "Colorado"),
        ("CT", "Connecticut"),
        ("DE", "Delaware"),
        ("FL", "Florida"),
        ("GA", "Georgia"),
        ("HI", "Hawaii"),
        ("ID", "Idaho"),
        ("IL", "Illinois"),
        ("IN", "Indiana"),
        ("IA", "Iowa"),
        ("KS", "Kansas"),
        ("KY", "Kentucky"),
        ("LA", "Louisiana"),
        ("ME", "Maine"),
        ("MD", "Maryland"),
        ("MA", "Massachusetts"),
        ("MI", "Michigan"),
        ("MN", "Minnesota"),
        ("MS", "Mississippi"),
        ("MO", "Missouri"),
        ("MT", "Montana"),
        ("NE", "Nebraska"),
        ("NV", "Nevada"),
        ("NH", "New Hampshire"),
        ("NJ", "New Jersey"),
        ("NM", "New Mexico"),
        ("NY", "New York"),
        ("NC", "North Carolina"),
        ("ND", "North Dakota"),
        ("OH", "Ohio"),
        ("OK", "Oklahoma"),
        ("OR", "Oregon"),
        ("PA", "Pennsylvania"),
        ("RI", "Rhode Island"),
        ("SC", "South Carolina"),
        ("SD", "South Dakota"),
        ("TN", "Tennessee"),
        ("TX", "Texas"),
        ("UT", "Utah"),
        ("VT", "Vermont"),
        ("VA", "Virginia"),
        ("WA", "Washington"),
        ("WV", "West Virginia"),
        ("WI", "Wisconsin"),
        ("WY", "Wyoming"),
    ]

    for abbr, name in states:
        if abbr == "CA":
            sourcing_rule = "HYBRID"
        elif abbr in origin_states:
            sourcing_rule = "ORIGIN"
        else:
            sourcing_rule = "DESTINATION"
        TaxJurisdiction.objects.update_or_create(
            code=f"US-{abbr}",
            defaults={
                "name": name,
                "jurisdiction_type": "STATE",
                "country_code": "US",
                "region_code": abbr,
                "sourcing_rule": sourcing_rule,
                "parent": us_root,
                "is_active": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("taxes", "0011_seed_more_us_jurisdictions"),
    ]

    operations = [
        migrations.RunPython(seed_all_us_states, migrations.RunPython.noop),
    ]

