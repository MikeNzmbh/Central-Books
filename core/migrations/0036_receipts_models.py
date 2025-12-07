from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0035_set_tax_defaults"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReceiptRun",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("RUNNING", "Running"),
                            ("COMPLETED", "Completed"),
                            ("FAILED", "Failed"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("total_documents", models.IntegerField(default=0)),
                ("success_count", models.IntegerField(default=0)),
                ("warning_count", models.IntegerField(default=0)),
                ("error_count", models.IntegerField(default=0)),
                ("engine_run_id", models.CharField(blank=True, max_length=255)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="receipt_runs", to="core.business"
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ReceiptDocument",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("storage_key", models.CharField(max_length=500)),
                ("original_filename", models.CharField(blank=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("PROCESSED", "Processed"),
                            ("POSTED", "Posted"),
                            ("DISCARDED", "Discarded"),
                            ("ERROR", "Error"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("extracted_payload", models.JSONField(blank=True, default=dict)),
                ("proposed_journal_payload", models.JSONField(blank=True, default=dict)),
                ("audit_flags", models.JSONField(blank=True, default=dict)),
                ("audit_score", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("discarded_at", models.DateTimeField(blank=True, null=True)),
                ("discard_reason", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approved_receipts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="receipt_documents", to="core.business"
                    ),
                ),
                (
                    "discarded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="discarded_receipts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "posted_journal_entry",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="receipt_documents",
                        to="core.journalentry",
                    ),
                ),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="documents", to="core.receiptrun"
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
