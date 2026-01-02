import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models

import internal_admin.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("internal_admin", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImpersonationToken",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(default=internal_admin.models._default_impersonation_expiry)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("remote_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, default="")),
                (
                    "admin",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="impersonation_tokens_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "target_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="impersonation_tokens",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="OverviewMetricsSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("payload", models.JSONField()),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="impersonationtoken",
            index=models.Index(fields=["admin", "target_user"], name="internal_ad_admin_i_9aa49b_idx"),
        ),
        migrations.AddIndex(
            model_name="impersonationtoken",
            index=models.Index(fields=["expires_at"], name="internal_ad_expires_d7bd16_idx"),
        ),
    ]
