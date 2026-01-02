from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("internal_admin", "0011_staff_profile"),
    ]

    operations = [
        migrations.AddField(
            model_name="admininvite",
            name="email_last_error",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="admininvite",
            name="full_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="admininvite",
            name="last_emailed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="admininvite",
            name="staff_profile",
            field=models.ForeignKey(
                blank=True,
                help_text="Optional: link invite to a StaffProfile (employees invite flow).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="invites",
                to="internal_admin.staffprofile",
            ),
        ),
        migrations.AddField(
            model_name="admininvite",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
