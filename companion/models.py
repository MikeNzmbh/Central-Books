from django.db import models


class WorkspaceCompanionProfile(models.Model):
    workspace = models.OneToOneField(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="companion_profile",
    )
    is_enabled = models.BooleanField(default=True)
    enable_health_index = models.BooleanField(default=True)
    enable_suggestions = models.BooleanField(default=True)
    conservatism_level = models.CharField(
        max_length=16,
        choices=[
            ("conservative", "Conservative"),
            ("standard", "Standard"),
        ],
        default="conservative",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Companion profile for {self.workspace_id}"


class HealthIndexSnapshot(models.Model):
    workspace = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="health_snapshots",
    )
    score = models.PositiveSmallIntegerField()
    breakdown = models.JSONField(default=dict)
    raw_metrics = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Health {self.score} for {self.workspace_id} @ {self.created_at}"


class CompanionInsight(models.Model):
    workspace = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="companion_insights",
    )
    domain = models.CharField(max_length=32)
    title = models.CharField(max_length=200)
    body = models.TextField()
    severity = models.CharField(
        max_length=16,
        choices=[
            ("info", "Info"),
            ("warning", "Warning"),
            ("critical", "Critical"),
        ],
        default="info",
    )
    suggested_actions = models.JSONField(default=list)
    is_dismissed = models.BooleanField(default=False)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.domain} – {self.title}"


class WorkspaceMemory(models.Model):
    workspace = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="companion_memory",
    )
    key = models.CharField(max_length=128)
    value = models.JSONField(default=dict)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("workspace", "key")

    def __str__(self) -> str:
        return f"{self.workspace_id}:{self.key}"


class CompanionSuggestedAction(models.Model):
    ACTION_BANK_MATCH_REVIEW = "bank_match_review"
    ACTION_CHOICES = [
        (ACTION_BANK_MATCH_REVIEW, "Bank match review"),
    ]
    STATUS_OPEN = "open"
    STATUS_APPLIED = "applied"
    STATUS_DISMISSED = "dismissed"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_APPLIED, "Applied"),
        (STATUS_DISMISSED, "Dismissed"),
    ]

    workspace = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="companion_actions",
    )
    action_type = models.CharField(max_length=64, choices=ACTION_CHOICES, default=ACTION_BANK_MATCH_REVIEW)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN)
    payload = models.JSONField(default=dict)
    confidence = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    summary = models.CharField(max_length=255)
    source_snapshot = models.ForeignKey(
        HealthIndexSnapshot,
        on_delete=models.SET_NULL,
        related_name="suggested_actions",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action_type} ({self.status}) for workspace {self.workspace_id}"
