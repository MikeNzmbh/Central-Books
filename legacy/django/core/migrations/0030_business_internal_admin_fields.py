from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0029_banktransaction_reconciliation_status_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="is_deleted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="business",
            name="plan",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="business",
            name="status",
            field=models.CharField(db_index=True, default="active", max_length=20),
        ),
    ]
