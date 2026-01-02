from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0036_receipts_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="ai_companion_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Allow the AI companion to assist with extraction, classification, and anomaly detection (never auto-posts).",
            ),
        ),
    ]
