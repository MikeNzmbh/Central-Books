from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

CONTEXT_DASHBOARD = "dashboard"
CONTEXT_BANK = "bank"
CONTEXT_RECONCILIATION = "reconciliation"
CONTEXT_INVOICES = "invoices"
CONTEXT_EXPENSES = "expenses"
CONTEXT_REPORTS = "reports"
CONTEXT_TAX_FX = "tax_fx"

CONTEXT_CHOICES = [
    (CONTEXT_DASHBOARD, "Dashboard"),
    (CONTEXT_BANK, "Bank"),
    (CONTEXT_RECONCILIATION, "Reconciliation"),
    (CONTEXT_INVOICES, "Invoices"),
    (CONTEXT_EXPENSES, "Expenses"),
    (CONTEXT_REPORTS, "Reports"),
    (CONTEXT_TAX_FX, "Tax & FX"),
]


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
    last_seen_bank_at = models.DateTimeField(null=True, blank=True)
    last_seen_reconciliation_at = models.DateTimeField(null=True, blank=True)
    last_seen_invoices_at = models.DateTimeField(null=True, blank=True)
    last_seen_expenses_at = models.DateTimeField(null=True, blank=True)
    last_seen_reports_at = models.DateTimeField(null=True, blank=True)
    last_seen_tax_fx_at = models.DateTimeField(null=True, blank=True)
    last_seen_dashboard_at = models.DateTimeField(null=True, blank=True)
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
    CONTEXT_DASHBOARD = CONTEXT_DASHBOARD
    CONTEXT_BANK = CONTEXT_BANK
    CONTEXT_RECONCILIATION = CONTEXT_RECONCILIATION
    CONTEXT_INVOICES = CONTEXT_INVOICES
    CONTEXT_EXPENSES = CONTEXT_EXPENSES
    CONTEXT_REPORTS = CONTEXT_REPORTS
    CONTEXT_TAX_FX = CONTEXT_TAX_FX
    CONTEXT_CHOICES = CONTEXT_CHOICES

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
    context = models.CharField(max_length=32, choices=CONTEXT_CHOICES, default=CONTEXT_DASHBOARD)

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
    CONTEXT_DASHBOARD = CONTEXT_DASHBOARD
    CONTEXT_BANK = CONTEXT_BANK
    CONTEXT_RECONCILIATION = CONTEXT_RECONCILIATION
    CONTEXT_INVOICES = CONTEXT_INVOICES
    CONTEXT_EXPENSES = CONTEXT_EXPENSES
    CONTEXT_REPORTS = CONTEXT_REPORTS
    CONTEXT_TAX_FX = CONTEXT_TAX_FX
    CONTEXT_CHOICES = CONTEXT_CHOICES

    ACTION_BANK_MATCH_REVIEW = "bank_match_review"
    ACTION_INVOICE_REMINDER = "send_invoice_reminder"
    ACTION_CATEGORIZE_EXPENSES_BATCH = "categorize_expenses_batch"
    ACTION_OVERDUE_INVOICE_REMINDERS = "overdue_invoice_reminders"
    ACTION_UNCATEGORIZED_EXPENSE_REVIEW = "uncategorized_expense_review"
    ACTION_UNCATEGORIZED_TRANSACTIONS_CLEANUP = "uncategorized_transactions_cleanup"
    ACTION_RECONCILIATION_PERIOD_TO_CLOSE = "reconciliation_period_to_close"
    ACTION_INACTIVE_CUSTOMERS_FOLLOWUP = "inactive_customers_followup"
    ACTION_SPIKE_EXPENSE_CATEGORY_REVIEW = "spike_expense_category_review"
    ACTION_OLD_UNRECONCILED_INVESTIGATE = "old_unreconciled_investigate"
    ACTION_SUSPENSE_BALANCE_REVIEW = "suspense_balance_review"

    ACTION_CHOICES = [
        (ACTION_BANK_MATCH_REVIEW, "Bank match review"),
        (ACTION_INVOICE_REMINDER, "Send invoice reminder"),
        (ACTION_CATEGORIZE_EXPENSES_BATCH, "Categorize expenses batch"),
        (ACTION_OVERDUE_INVOICE_REMINDERS, "Overdue invoice reminders"),
        (ACTION_UNCATEGORIZED_EXPENSE_REVIEW, "Uncategorized expense review"),
        (ACTION_UNCATEGORIZED_TRANSACTIONS_CLEANUP, "Uncategorized transactions cleanup"),
        (ACTION_RECONCILIATION_PERIOD_TO_CLOSE, "Reconciliation period to close"),
        (ACTION_INACTIVE_CUSTOMERS_FOLLOWUP, "Inactive customers follow-up"),
        (ACTION_SPIKE_EXPENSE_CATEGORY_REVIEW, "Expense category spike review"),
        (ACTION_OLD_UNRECONCILED_INVESTIGATE, "Investigate old unreconciled"),
        (ACTION_SUSPENSE_BALANCE_REVIEW, "Suspense balance review"),
    ]
    STATUS_OPEN = "open"
    STATUS_APPLIED = "applied"
    STATUS_DISMISSED = "dismissed"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_APPLIED, "Applied"),
        (STATUS_DISMISSED, "Dismissed"),
    ]
    SEVERITY_INFO = "INFO"
    SEVERITY_LOW = "LOW"
    SEVERITY_MEDIUM = "MEDIUM"
    SEVERITY_HIGH = "HIGH"
    SEVERITY_CRITICAL = "CRITICAL"
    SEVERITY_CHOICES = [
        (SEVERITY_INFO, "Info"),
        (SEVERITY_LOW, "Low"),
        (SEVERITY_MEDIUM, "Medium"),
        (SEVERITY_HIGH, "High"),
        (SEVERITY_CRITICAL, "Critical"),
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
    short_title = models.CharField(max_length=64, blank=True, default="")
    severity = models.CharField(max_length=12, choices=SEVERITY_CHOICES, default=SEVERITY_INFO)
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
    context = models.CharField(max_length=32, choices=CONTEXT_CHOICES, default=CONTEXT_DASHBOARD)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action_type} ({self.status}) for workspace {self.workspace_id}"

    def save(self, *args, **kwargs):
        if not self.short_title:
            self.short_title = (self.summary or self.action_type)[:64]
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Companion v2: Shadow Ledger + Safe Accountant Mode
# ─────────────────────────────────────────────────────────────────────────────


class WorkspaceAISettings(models.Model):
    """
    Kill switch + operating mode for Companion v2.

    This is the control-plane record the backend checks before allowing:
    - Any Companion write to the Shadow Ledger (proposals)
    - Any Companion command dispatch (apply/promote)
    """

    class AIMode(models.TextChoices):
        SHADOW_ONLY = "shadow_only", "Shadow only"
        SUGGEST_ONLY = "suggest_only", "Suggest only"
        DRAFTS = "drafts", "Drafts"
        AUTOPILOT_LIMITED = "autopilot_limited", "Limited autopilot"

    workspace = models.OneToOneField(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="ai_settings",
    )
    ai_enabled = models.BooleanField(default=False)
    kill_switch = models.BooleanField(
        default=False,
        help_text="Emergency stop for this workspace. When enabled, Companion cannot propose or apply.",
    )
    ai_mode = models.CharField(max_length=32, choices=AIMode.choices, default=AIMode.SHADOW_ONLY, db_index=True)

    # Circuit breaker thresholds (workspace overrides).
    velocity_limit_per_minute = models.PositiveIntegerField(
        default=120,
        help_text="If Companion proposes/applies more than this per minute, pause further actions.",
    )
    value_breaker_threshold = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=5000,
        help_text="If a single transaction exceeds this absolute amount, force Tier-2 review (no auto-apply).",
    )
    anomaly_stddev_threshold = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=3,
        help_text="If amount is > N stddev from vendor baseline, mark as high risk (proposal only).",
    )
    trust_downgrade_rejection_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.30,
        help_text="If user rejects more than this share of suggestions, downgrade from autopilot to suggest-only.",
    )

    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"AI settings for workspace {self.workspace_id}"


class BusinessPolicy(models.Model):
    """
    BusinessProfile v2: live policy constraints for Companion.

    Stored separately from core.Business to keep the accounting data model stable
    while evolving AI policy semantics.
    """

    class RiskAppetite(models.TextChoices):
        CONSERVATIVE = "conservative", "Conservative"
        STANDARD = "standard", "Standard"
        AGGRESSIVE = "aggressive", "Aggressive"

    workspace = models.OneToOneField(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="business_policy",
    )
    materiality_threshold = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=1,
        help_text="Write-off / rounding tolerance for tiny differences (in workspace currency).",
    )
    risk_appetite = models.CharField(max_length=16, choices=RiskAppetite.choices, default=RiskAppetite.STANDARD)
    commingling_risk_vendors = models.JSONField(
        default=list,
        blank=True,
        help_text="Vendors requiring extra friction / mandatory review (e.g. Amazon, Target, Costco).",
    )
    related_entities = models.JSONField(
        default=list,
        blank=True,
        help_text="List of related workspace IDs / entities for intercompany awareness.",
    )
    intercompany_enabled = models.BooleanField(default=False)
    sector_archetype = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Industry archetype (SaaS, e-commerce, construction, agency, etc.).",
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Business policy for workspace {self.workspace_id}"


class ProvisionalLedgerEvent(models.Model):
    """
    Shadow Ledger (Stream B) event for Companion drafts/proposals.

    These events never affect financial statements directly.
    They can be wiped/replayed without touching the canonical ledger.
    """

    class Status(models.TextChoices):
        PROPOSED = "proposed", "Proposed"
        APPLIED = "applied", "Applied"
        REJECTED = "rejected", "Rejected"
        SUPERSEDED = "superseded", "Superseded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="shadow_events",
    )
    # Propose* command_id (from the command payload), used for audit/debug correlation.
    command_id = models.UUIDField(null=True, blank=True, db_index=True)
    # Optional direct pointer for the common case (banking/reconciliation).
    bank_transaction = models.ForeignKey(
        "core.BankTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="companion_shadow_events",
    )
    # Primary command record that produced this shadow event (usually the Propose* command).
    source_command = models.OneToOneField(
        "companion.AICommandRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_shadow_event",
    )
    event_type = models.CharField(max_length=128, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PROPOSED, db_index=True)

    # Optional subject pointer (bank transaction, receipt, invoice, etc.).
    subject_content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    subject_object_id = models.PositiveIntegerField(null=True, blank=True)
    subject = GenericForeignKey("subject_content_type", "subject_object_id")

    data = models.JSONField(default=dict, blank=True)

    # Explainability & governance metadata (duplicated into typed fields for queryability).
    actor = models.CharField(max_length=128, default="system_companion_v2")
    confidence_score = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    logic_trace_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    rationale = models.TextField(blank=True, default="")
    business_profile_constraint = models.CharField(max_length=128, blank=True, default="")
    human_in_the_loop = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_shadow_events",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["workspace", "status", "created_at"]),
            models.Index(fields=["workspace", "event_type", "created_at"]),
            models.Index(fields=["workspace", "subject_content_type", "subject_object_id"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.event_type} ({self.status}) {self.id}"


class AICommandRecord(models.Model):
    """
    Command-sourcing record for Companion actions (intent).

    Propose* commands validate -> append to Shadow Ledger.
    Apply* commands validate -> mutate canonical ledger -> append provenance.
    """

    class Status(models.TextChoices):
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        ERRORED = "errored", "Errored"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey("core.Business", on_delete=models.CASCADE, related_name="ai_commands")
    command_type = models.CharField(max_length=128, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    actor = models.CharField(max_length=128, default="system_companion_v2", db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACCEPTED, db_index=True)
    error_message = models.TextField(blank=True, default="")

    shadow_event = models.ForeignKey(
        ProvisionalLedgerEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="command_records",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_command_records",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.command_type} ({self.status}) {self.id}"


class CanonicalLedgerProvenance(models.Model):
    """
    Provenance/explainability link from canonical objects to a shadow event.

    This provides the "why did Companion do this?" audit trail for:
    - Journal entries created/adjusted
    - Bank matches applied
    - Categorization changes
    """

    workspace = models.ForeignKey("core.Business", on_delete=models.CASCADE, related_name="canonical_provenance")
    shadow_event = models.ForeignKey(
        ProvisionalLedgerEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="canonical_promotions",
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey("content_type", "object_id")

    actor = models.CharField(max_length=128, default="system_companion_v2")
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_canonical_provenance",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["workspace", "content_type", "object_id"]),
            models.Index(fields=["workspace", "shadow_event"]),
            models.Index(fields=["workspace", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Provenance {self.workspace_id} {self.content_type_id}:{self.object_id}"


class AICircuitBreakerEvent(models.Model):
    class Breaker(models.TextChoices):
        KILL_SWITCH = "kill_switch", "Kill switch"
        VELOCITY = "velocity", "Velocity"
        VALUE = "value", "Value"
        ANOMALY = "anomaly", "Anomaly"
        TRUST = "trust", "Trust"

    workspace = models.ForeignKey("core.Business", on_delete=models.CASCADE, related_name="ai_breaker_events")
    breaker = models.CharField(max_length=16, choices=Breaker.choices, db_index=True)
    action = models.CharField(max_length=128, blank=True, default="")
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.breaker} for {self.workspace_id} @ {self.created_at:%Y-%m-%d}"


class AIIntegrityReport(models.Model):
    """
    Weekly integrity report generated by the adversarial auditor ("Checker").
    """

    workspace = models.ForeignKey("core.Business", on_delete=models.CASCADE, related_name="ai_integrity_reports")
    period_start = models.DateField()
    period_end = models.DateField()
    summary = models.JSONField(default=dict, blank=True)
    flagged_items = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "period_start", "period_end"],
                name="uniq_ai_integrity_report_period",
            )
        ]
        indexes = [
            models.Index(fields=["workspace", "created_at"]),
            models.Index(fields=["workspace", "period_start", "period_end"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Integrity report {self.workspace_id} {self.period_start}..{self.period_end}"
