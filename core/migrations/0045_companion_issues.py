from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0044_receipts_invoices_llm_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanionIssue",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "surface",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("receipts", "Receipts"),
                            ("invoices", "Invoices"),
                            ("books", "Books"),
                            ("bank", "Bank"),
                        ],
                    ),
                ),
                (
                    "run_type",
                    models.CharField(
                        max_length=30,
                        blank=True,
                        choices=[
                            ("receipts", "Receipts"),
                            ("invoices", "Invoices"),
                            ("books_review", "Books Review"),
                            ("bank_review", "Bank Review"),
                        ],
                    ),
                ),
                ("run_id", models.IntegerField(null=True, blank=True, help_text="ID of the originating run (no FK enforced)")),
                (
                    "severity",
                    models.CharField(
                        max_length=10,
                        choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")],
                        default="low",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        max_length=10,
                        choices=[("open", "Open"), ("snoozed", "Snoozed"), ("resolved", "Resolved")],
                        default="open",
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("recommended_action", models.CharField(max_length=255, blank=True)),
                ("estimated_impact", models.CharField(max_length=255, blank=True)),
                ("data", models.JSONField(default=dict, blank=True)),
                ("trace_id", models.CharField(max_length=255, blank=True)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="companion_issues",
                        to="core.business",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
