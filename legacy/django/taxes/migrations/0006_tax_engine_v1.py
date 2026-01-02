import django.db.models.deletion
import uuid
from django.db import migrations, models
import django.contrib.contenttypes.models


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("core", "0048_highriskaudit"),
        ("taxes", "0005_transactionlinetaxdetail_transaction_date"),
    ]

    operations = [
        migrations.CreateModel(
            name="TaxJurisdiction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(help_text="e.g., CA-ON, US-CA, US-CA-LA", max_length=20, unique=True)),
                ("name", models.CharField(max_length=128)),
                ("jurisdiction_type", models.CharField(choices=[("FEDERAL", "Federal"), ("PROVINCIAL", "Provincial/Territory"), ("STATE", "State"), ("COUNTY", "County"), ("CITY", "City"), ("DISTRICT", "District")], max_length=20)),
                ("country_code", models.CharField(max_length=2)),
                ("region_code", models.CharField(blank=True, max_length=10)),
                ("sourcing_rule", models.CharField(choices=[("ORIGIN", "Origin-based"), ("DESTINATION", "Destination-based"), ("HYBRID", "Hybrid")], default="DESTINATION", max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="children", to="taxes.taxjurisdiction")),
            ],
            options={
                "ordering": ["country_code", "code"],
            },
        ),
        migrations.CreateModel(
            name="TaxPeriodSnapshot",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("period_key", models.CharField(max_length=16)),
                ("country", models.CharField(max_length=2)),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("COMPUTED", "Computed"), ("REVIEWED", "Reviewed"), ("FILED", "Filed")], default="DRAFT", max_length=16)),
                ("computed_at", models.DateTimeField(auto_now=True)),
                ("summary_by_jurisdiction", models.JSONField(blank=True, default=dict)),
                ("line_mappings", models.JSONField(blank=True, default=dict)),
                ("llm_summary", models.TextField(blank=True)),
                ("llm_notes", models.TextField(blank=True)),
                ("business", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tax_snapshots", to="core.business")),
            ],
            options={
                "indexes": [models.Index(fields=["business", "period_key", "status"], name="taxsnap_business_period_idx")],
            },
        ),
        migrations.CreateModel(
            name="TaxProductRule",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("product_code", models.CharField(max_length=32)),
                ("rule_type", models.CharField(choices=[("TAXABLE", "Taxable"), ("EXEMPT", "Exempt"), ("ZERO_RATED", "Zero-rated"), ("REDUCED", "Reduced rate")], max_length=20)),
                ("special_rate", models.DecimalField(blank=True, decimal_places=6, help_text="Override rate for REDUCED type.", max_digits=9, null=True)),
                ("valid_from", models.DateField()),
                ("valid_to", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("jurisdiction", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="product_rules", to="taxes.taxjurisdiction")),
            ],
            options={
                "ordering": ["jurisdiction", "product_code", "valid_from"],
                "unique_together": {("jurisdiction", "product_code", "valid_from")},
                "indexes": [models.Index(fields=["product_code", "valid_from", "valid_to"], name="taxprod_rule_idx")],
            },
        ),
        migrations.CreateModel(
            name="TaxAnomaly",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("period_key", models.CharField(max_length=16)),
                ("code", models.CharField(max_length=64)),
                ("severity", models.CharField(choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")], max_length=10)),
                ("status", models.CharField(choices=[("OPEN", "Open"), ("ACKNOWLEDGED", "Acknowledged"), ("RESOLVED", "Resolved"), ("IGNORED", "Ignored")], default="OPEN", max_length=16)),
                ("description", models.TextField()),
                ("linked_transaction_id", models.PositiveIntegerField(blank=True, null=True)),
                ("task_code", models.CharField(blank=True, max_length=8)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("business", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tax_anomalies", to="core.business")),
                ("linked_transaction_ct", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="contenttypes.contenttype")),
            ],
            options={
                "indexes": [models.Index(fields=["business", "period_key", "code"], name="taxanomaly_period_code_idx")],
            },
        ),
        migrations.AddIndex(
            model_name="taxjurisdiction",
            index=models.Index(fields=["country_code", "region_code"], name="taxjur_country_region_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="taxperiodsnapshot",
            unique_together={("business", "period_key")},
        ),
    ]
