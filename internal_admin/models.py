from datetime import timedelta
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone


User = get_user_model()


class AdminRole(models.TextChoices):
    SUPPORT = "SUPPORT", "Support"
    OPS = "OPS", "Ops"
    ENGINEERING = "ENGINEERING", "Engineering"
    SUPERADMIN = "SUPERADMIN", "Superadmin"


class InternalAdminProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="internal_admin_profile",
    )
    role = models.CharField(
        max_length=20,
        choices=AdminRole.choices,
        default=AdminRole.SUPPORT,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Internal admin profile"
        verbose_name_plural = "Internal admin profiles"

    def __str__(self) -> str:
        return f"{self.user} ({self.role})"


class AdminAuditLog(models.Model):
    class Level(models.TextChoices):
        INFO = "INFO", "Info"
        WARNING = "WARNING", "Warning"
        ERROR = "ERROR", "Error"

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_audit_logs",
    )
    action = models.CharField(max_length=100, db_index=True)
    object_type = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=64, blank=True)
    extra = models.JSONField(default=dict, blank=True)
    remote_ip = models.GenericIPAddressField(null=True, blank=True)
    level = models.CharField(
        max_length=16,
        choices=Level.choices,
        default=Level.INFO,
        db_index=True,
    )
    category = models.CharField(max_length=64, blank=True, default="", db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["object_type", "object_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.timestamp:%Y-%m-%d %H:%M:%S} {self.action} {self.object_type}:{self.object_id}"


def _default_impersonation_expiry():
    return timezone.now() + timedelta(minutes=15)


class ImpersonationToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="impersonation_tokens_created",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="impersonation_tokens",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_default_impersonation_expiry)
    used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    remote_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["admin", "target_user"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        return f"Impersonation {self.admin_id} -> {self.target_user_id} ({self.id})"


class OverviewMetricsSnapshot(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField()

    class Meta:
        ordering = ["-created_at"]


class SupportTicket(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        NORMAL = "NORMAL", "Normal"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
    )
    workspace = models.ForeignKey(
        "core.Business",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
    )
    subject = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
        db_index=True,
    )
    source = models.CharField(max_length=50, default="IN_APP", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "priority"]),
        ]

    def __str__(self) -> str:
        return f"{self.subject} ({self.status})"


class SupportTicketNote(models.Model):
    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_ticket_notes",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class FeatureFlag(models.Model):
    key = models.SlugField(unique=True)
    label = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    is_enabled = models.BooleanField(default=False)
    rollout_percent = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key
