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
    PRIMARY_ADMIN = "PRIMARY_ADMIN", "Primary Admin"


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


class StaffProfile(models.Model):
    """
    Internal employee profile and admin access control for /internal-admin.

    This model is the source of truth for whether a user is allowed to access
    the internal admin panel and what primary admin role they hold.
    """

    class PrimaryAdminRole(models.TextChoices):
        NONE = "none", "None"
        SUPPORT = "support", "Support"
        FINANCE = "finance", "Finance"
        ENGINEERING = "engineering", "Engineering"
        SUPERADMIN = "superadmin", "Superadmin"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="staff_profile",
    )

    display_name = models.CharField(max_length=255)
    title = models.CharField(max_length=255, blank=True)
    department = models.CharField(
        max_length=100,
        blank=True,
        help_text="e.g. Support, Finance, Engineering, Ops",
    )

    admin_panel_access = models.BooleanField(default=False, db_index=True)
    primary_admin_role = models.CharField(
        max_length=50,
        choices=PrimaryAdminRole.choices,
        default=PrimaryAdminRole.NONE,
        db_index=True,
    )
    is_active_employee = models.BooleanField(default=True, db_index=True)
    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Soft-delete flag. Deleted staff retain history but lose all access.",
    )
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="direct_reports",
        on_delete=models.SET_NULL,
    )

    workspace_scope = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            '{"mode": "all" | "region" | "specific", '
            '"ids": [workspace_ids], "region": "CA" }'
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Staff profile"
        verbose_name_plural = "Staff profiles"
        indexes = [
            models.Index(fields=["admin_panel_access", "is_active_employee"]),
            models.Index(fields=["primary_admin_role", "admin_panel_access"]),
        ]

    def __str__(self) -> str:
        return f"{self.display_name} ({self.primary_admin_role})"


class AdminAuditLog(models.Model):
    """
    Immutable audit log for all admin actions.
    Aligned with Gemini spec's "Log-First Architecture" principle.
    """
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
    # Capture role at time of action (for historical accuracy)
    actor_role = models.CharField(
        max_length=20,
        choices=AdminRole.choices,
        blank=True,
        default="",
        db_index=True,
        help_text="Admin role at time of action",
    )
    action = models.CharField(max_length=100, db_index=True)
    object_type = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=64, blank=True)
    extra = models.JSONField(default=dict, blank=True)
    remote_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="", help_text="Browser/client info")
    request_id = models.CharField(
        max_length=128,
        blank=True,
        default="",
        db_index=True,
        help_text="Correlation ID for tracing a request across logs",
    )
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
            models.Index(fields=["actor_role", "timestamp"]),
        ]

    def __str__(self) -> str:
        return f"{self.timestamp:%Y-%m-%d %H:%M:%S} {self.action} {self.object_type}:{self.object_id}"


class AdminBreakGlassGrant(models.Model):
    """
    Time-bound access grants for sensitive internal admin data.

    Intended for "break-glass" workflows where an operator must provide a reason
    and access is automatically revoked after a short TTL.
    """

    class Scope(models.TextChoices):
        APPROVAL_SENSITIVE = "APPROVAL_SENSITIVE", "Approval Sensitive Data"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="break_glass_grants",
    )
    scope = models.CharField(max_length=40, choices=Scope.choices, db_index=True)
    approval_request = models.ForeignKey(
        "internal_admin.AdminApprovalRequest",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="break_glass_grants",
    )
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    remote_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    request_id = models.CharField(max_length=128, blank=True, default="", db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["admin_user", "scope", "expires_at"]),
            models.Index(fields=["approval_request", "expires_at"]),
        ]

    @property
    def is_active(self) -> bool:
        return self.expires_at > timezone.now()


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
    reason = models.TextField(blank=True, default="", help_text="Reason for impersonation")

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


def _default_invite_expiry():
    return timezone.now() + timedelta(days=7)


class AdminInvite(models.Model):
    """
    Invite tokens for onboarding new internal admin users.
    Share the link /internal-admin/invite/<token> to allow signup.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    staff_profile = models.ForeignKey(
        StaffProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invites",
        help_text="Optional: link invite to a StaffProfile (employees invite flow).",
    )
    email = models.EmailField(
        blank=True,
        help_text="Optional: restrict invite to specific email address"
    )
    full_name = models.CharField(max_length=255, blank=True, default="")
    role = models.CharField(
        max_length=20,
        choices=AdminRole.choices,
        default=AdminRole.SUPPORT,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="admin_invites_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(default=_default_invite_expiry)
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_invites_used",
    )
    is_active = models.BooleanField(default=True)
    last_emailed_at = models.DateTimeField(null=True, blank=True)
    email_last_error = models.TextField(blank=True, default="")
    max_uses = models.PositiveIntegerField(default=1, help_text="0 = unlimited")
    use_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["expires_at", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"Invite {self.id} ({self.role})"

    @property
    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        if self.expires_at < timezone.now():
            return False
        if self.max_uses > 0 and self.use_count >= self.max_uses:
            return False
        return True

    def get_invite_url(self, request=None) -> str:
        path = f"/internal-admin/invite/{self.id}"
        if request:
            return request.build_absolute_uri(path)
        return path


class AdminApprovalRequest(models.Model):
    """
    Maker-Checker workflow for high-risk admin actions.
    Aligned with Gemini spec's "Maker-Checker Pattern" safety primitive.
    
    Usage:
    1. Maker initiates a request (e.g., "Reset tax period for Acme Corp")
    2. Request enters PENDING status
    3. Checker (higher role) approves or rejects
    4. On approval, the action is executed
    """
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        EXPIRED = "EXPIRED", "Expired"
        FAILED = "FAILED", "Failed"

    class ActionType(models.TextChoices):
        TAX_PERIOD_RESET = "TAX_PERIOD_RESET", "Reset Tax Period"
        LEDGER_ADJUST = "LEDGER_ADJUST", "Ledger Adjustment"
        WORKSPACE_DELETE = "WORKSPACE_DELETE", "Delete Workspace"
        BULK_REFUND = "BULK_REFUND", "Bulk Refund"
        USER_BAN = "USER_BAN", "Ban User"
        USER_REACTIVATE = "USER_REACTIVATE", "Reactivate User"
        USER_PRIVILEGE_CHANGE = "USER_PRIVILEGE_CHANGE", "Change User Privileges"
        PASSWORD_RESET_LINK = "PASSWORD_RESET_LINK", "Create Password Reset Link"
        FEATURE_FLAG_CRITICAL = "FEATURE_FLAG_CRITICAL", "Toggle Critical Feature"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    initiator_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="approval_requests_initiated",
        help_text="The admin who requested this action (Maker)",
    )
    approver_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_requests_approved",
        help_text="The admin who approved/rejected (Checker)",
    )
    action_type = models.CharField(
        max_length=50,
        choices=ActionType.choices,
        db_index=True,
    )
    workspace = models.ForeignKey(
        "core.Business",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_approval_requests",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_requests_targeting",
        help_text="User affected by this action (if applicable)",
    )
    payload = models.JSONField(
        default=dict,
        help_text="Action-specific data (e.g., amounts, IDs, settings)",
    )
    reason = models.TextField(
        help_text="Justification for the action",
    )
    rejection_reason = models.TextField(
        blank=True,
        default="",
        help_text="Reason for rejection (if rejected)",
    )
    execution_error = models.TextField(
        blank=True,
        default="",
        help_text="Execution error (if failed)",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Auto-expire if not resolved by this time",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "action_type"]),
            models.Index(fields=["initiator_admin", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.action_type} by {self.initiator_admin_id} ({self.status})"

    @property
    def is_pending(self) -> bool:
        return self.status == self.Status.PENDING

    def approve(self, approver) -> None:
        """Mark as approved by the checker."""
        self.approver_admin = approver
        self.status = self.Status.APPROVED
        self.resolved_at = timezone.now()
        self.execution_error = ""
        self.save(update_fields=["approver_admin", "status", "resolved_at", "execution_error", "payload"])

    def reject(self, approver, reason: str = "") -> None:
        """Mark as rejected by the checker."""
        self.approver_admin = approver
        self.status = self.Status.REJECTED
        self.rejection_reason = reason
        self.resolved_at = timezone.now()
        self.execution_error = ""
        self.save(
            update_fields=[
                "approver_admin",
                "status",
                "rejection_reason",
                "resolved_at",
                "execution_error",
                "payload",
            ]
        )

    def fail(self, approver, error: str) -> None:
        """Mark as failed during execution (checker attempted to execute)."""
        self.approver_admin = approver
        self.status = self.Status.FAILED
        self.resolved_at = timezone.now()
        self.execution_error = (error or "")[:5000]
        self.save(update_fields=["approver_admin", "status", "resolved_at", "execution_error", "payload"])
