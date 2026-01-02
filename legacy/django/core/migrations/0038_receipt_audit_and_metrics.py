from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0037_business_ai_companion"),
    ]

    operations = [
        migrations.AddField(
            model_name="receiptrun",
            name="metrics",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="receiptrun",
            name="trace_id",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name="receiptdocument",
            name="audit_flags",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="receiptdocument",
            name="audit_explanations",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
