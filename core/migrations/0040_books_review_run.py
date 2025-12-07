from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0039_invoice_companion_models"),
    ]

    operations = [
        migrations.CreateModel(
            name="BooksReviewRun",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("RUNNING", "Running"), ("COMPLETED", "Completed"), ("FAILED", "Failed")], db_index=True, default="PENDING", max_length=20)),
                ("metrics", models.JSONField(blank=True, default=dict)),
                ("findings", models.JSONField(blank=True, default=list)),
                ("overall_risk_score", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("trace_id", models.CharField(blank=True, max_length=255)),
                ("business", models.ForeignKey(on_delete=models.CASCADE, related_name="books_review_runs", to="core.business")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
