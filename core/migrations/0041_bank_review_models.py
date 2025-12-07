from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0040_books_review_run"),
    ]

    operations = [
        migrations.CreateModel(
            name="BankReviewRun",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("period_start", models.DateField(blank=True, null=True)),
                ("period_end", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("RUNNING", "Running"), ("COMPLETED", "Completed"), ("FAILED", "Failed")], db_index=True, default="PENDING", max_length=20)),
                ("metrics", models.JSONField(blank=True, default=dict)),
                ("overall_risk_score", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("trace_id", models.CharField(blank=True, max_length=255)),
                ("business", models.ForeignKey(on_delete=models.CASCADE, related_name="bank_review_runs", to="core.business")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="BankTransactionReview",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("matched_journal_ids", models.JSONField(blank=True, default=list)),
                ("status", models.CharField(choices=[("MATCHED", "Matched"), ("UNMATCHED", "Unmatched"), ("PARTIAL_MATCH", "Partial match"), ("DUPLICATE", "Duplicate"), ("ERROR", "Error")], db_index=True, default="UNMATCHED", max_length=20)),
                ("audit_flags", models.JSONField(blank=True, default=list)),
                ("audit_score", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("audit_explanations", models.JSONField(blank=True, default=list)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("business", models.ForeignKey(on_delete=models.CASCADE, related_name="bank_transaction_reviews", to="core.business")),
                ("run", models.ForeignKey(on_delete=models.CASCADE, related_name="transactions", to="core.bankreviewrun")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
