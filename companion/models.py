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
