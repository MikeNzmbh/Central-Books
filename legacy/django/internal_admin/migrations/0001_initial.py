from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InternalAdminProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("SUPPORT", "Support"), ("OPS", "Ops"), ("ENGINEERING", "Engineering"), ("SUPERADMIN", "Superadmin")], db_index=True, default="SUPPORT", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="internal_admin_profile", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Internal admin profile",
                "verbose_name_plural": "Internal admin profiles",
            },
        ),
        migrations.CreateModel(
            name="AdminAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("timestamp", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("action", models.CharField(db_index=True, max_length=100)),
                ("object_type", models.CharField(db_index=True, max_length=100)),
                ("object_id", models.CharField(blank=True, max_length=64)),
                ("extra", models.JSONField(blank=True, default=dict)),
                ("remote_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("admin_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="admin_audit_logs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-timestamp"],
            },
        ),
        migrations.AddIndex(
            model_name="adminauditlog",
            index=models.Index(fields=["object_type", "object_id"], name="internal_ad_object_0ca4ef_idx"),
        ),
    ]
