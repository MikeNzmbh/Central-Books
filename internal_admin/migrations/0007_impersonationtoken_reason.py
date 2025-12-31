from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("internal_admin", "0006_central_admin_phase1"),
    ]

    operations = [
        migrations.AddField(
            model_name="impersonationtoken",
            name="reason",
            field=models.TextField(blank=True, default="", help_text="Reason for impersonation"),
        ),
    ]

