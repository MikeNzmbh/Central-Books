from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0043_alter_bankreviewrun_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="receiptrun",
            name="llm_explanations",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="receiptrun",
            name="llm_ranked_documents",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="receiptrun",
            name="llm_suggested_classifications",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="receiptrun",
            name="llm_suggested_followups",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="invoicerun",
            name="llm_explanations",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="invoicerun",
            name="llm_ranked_documents",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="invoicerun",
            name="llm_suggested_classifications",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="invoicerun",
            name="llm_suggested_followups",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
