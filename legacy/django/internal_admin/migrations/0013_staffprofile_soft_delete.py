from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("internal_admin", "0012_admininvite_staff_invite_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffprofile",
            name="deleted_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="staffprofile",
            name="is_deleted",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Soft-delete flag. Deleted staff retain history but lose all access.",
            ),
        ),
    ]

