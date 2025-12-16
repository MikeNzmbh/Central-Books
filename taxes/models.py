import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class TaxComponent(models.Model):
    """
    Atomic tax rate, e.g., GST 5% or QST 9.975%.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="tax_components",
    )
    name = models.CharField(max_length=128)
    rate_percentage = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        help_text="Stored as decimal (0.05 for 5%).",
    )
    authority = models.CharField(
        max_length=32,
        help_text="Issuing authority code, e.g., 'CRA', 'RQ', 'US-NY'.",
    )
    is_recoverable = models.BooleanField(
        default=False,
        help_text="True when the tax can be claimed back (ITC), False when it is non-recoverable.",
    )
    effective_start_date = models.DateField(
        default=timezone.now,
        help_text="Start date for this rate record.",
    )
    default_coa_account = models.ForeignKey(
        "core.Account",
        on_delete=models.PROTECT,
        related_name="tax_components",
        help_text="Default ledger account (e.g., 2300 liability or 1400 recoverable asset).",
    )
    jurisdiction = models.ForeignKey(
        "TaxJurisdiction",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tax_components",
        help_text="Optional canonical jurisdiction for this component.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["business", "name"]
        unique_together = ("business", "name")

    def __str__(self):
        return f"{self.name} ({self.rate_percentage})"


class TaxRate(models.Model):
    """
    Time-versioned rates for a TaxComponent, enabling historical correctness.
    """

    class ProductCategory(models.TextChoices):
        STANDARD = "STANDARD", "Standard"
        SAAS = "SAAS", "SaaS"
        DIGITAL_GOOD = "DIGITAL_GOOD", "Digital good"
        ZERO_RATED = "ZERO_RATED", "Zero-rated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    component = models.ForeignKey(
        TaxComponent,
        on_delete=models.CASCADE,
        related_name="rates",
    )
    rate_decimal = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        help_text="Decimal form (0.05 for 5%).",
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    product_category = models.CharField(
        max_length=32,
        choices=ProductCategory.choices,
        default=ProductCategory.STANDARD,
    )
    is_compound = models.BooleanField(
        default=False,
        help_text="Reserved for future compound-stack handling; calculation is currently controlled by TaxGroup.calculation_method.",
    )
    meta_data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["component", "effective_from"]
        indexes = [
            models.Index(
                fields=["component", "product_category", "effective_from", "effective_to"],
                name="tr_comp_cat_date_idx",
            )
        ]

    def __str__(self):
        return f"{self.component.name} @ {self.rate_decimal} from {self.effective_from}"


class TaxGroup(models.Model):
    """
    What users select on invoice/expense lines; bundle of one or more components.
    """

    class ReportingCategory(models.TextChoices):
        TAXABLE = "TAXABLE", "Taxable / Standard"
        ZERO_RATED = "ZERO_RATED", "Zero-rated (0%)"
        EXEMPT = "EXEMPT", "Exempt supply"
        OUT_OF_SCOPE = "OUT_OF_SCOPE", "Out of scope (non-GST/HST)"

    class TaxTreatment(models.TextChoices):
        ON_TOP = "ON_TOP", "Tax on top (exclusive)"
        INCLUDED = "INCLUDED", "Tax included (inclusive)"

    class CalculationMethod(models.TextChoices):
        SIMPLE = "SIMPLE", "Simple (all components on base)"
        COMPOUND = "COMPOUND", "Compound/stacked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="tax_groups",
    )
    display_name = models.CharField(max_length=128)
    is_system_locked = models.BooleanField(
        default=False,
        help_text="True for built-in groups that should not be edited.",
    )
    calculation_method = models.CharField(
        max_length=10,
        choices=CalculationMethod.choices,
        default=CalculationMethod.SIMPLE,
    )
    tax_treatment = models.CharField(
        max_length=10,
        choices=TaxTreatment.choices,
        default=TaxTreatment.ON_TOP,
        help_text="Whether the entered amount is net (ON_TOP) or gross (INCLUDED).",
    )
    reporting_category = models.CharField(
        max_length=20,
        choices=ReportingCategory.choices,
        default=ReportingCategory.TAXABLE,
        help_text="Canonical reporting category (taxable/zero-rated/exempt/out-of-scope).",
    )
    components = models.ManyToManyField(
        TaxComponent,
        through="TaxGroupComponent",
        related_name="tax_groups",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["business", "display_name"]
        unique_together = ("business", "display_name")

    def __str__(self):
        return self.display_name


class TaxGroupComponent(models.Model):
    """
    Through model for TaxGroup.components, preserving calculation order.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        TaxGroup,
        on_delete=models.CASCADE,
        related_name="group_components",
    )
    component = models.ForeignKey(
        TaxComponent,
        on_delete=models.PROTECT,
        related_name="group_components",
    )
    calculation_order = models.PositiveSmallIntegerField(
        default=1,
        help_text="Order 1..n for stacked calculations.",
    )

    class Meta:
        ordering = ["group", "calculation_order"]
        unique_together = ("group", "component")

    def __str__(self):
        return f"{self.group.display_name} -> {self.component.name} (order {self.calculation_order})"


class TransactionLineTaxDetail(models.Model):
    """
    Component-level tax amounts per transaction line (invoice/bill).
    """

    class DocumentSide(models.TextChoices):
        SALE = "SALE", "Sale"
        PURCHASE = "PURCHASE", "Purchase"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="tax_details",
    )
    tax_group = models.ForeignKey(
        TaxGroup,
        on_delete=models.PROTECT,
        related_name="tax_details",
    )
    tax_component = models.ForeignKey(
        TaxComponent,
        on_delete=models.PROTECT,
        related_name="tax_details",
    )

    transaction_line_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    transaction_line_object_id = models.PositiveIntegerField(null=True, blank=True)
    transaction_line = GenericForeignKey(
        "transaction_line_content_type",
        "transaction_line_object_id",
    )

    taxable_amount_txn_currency = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    taxable_amount_home_currency_cad = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    tax_amount_txn_currency = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    tax_amount_home_currency_cad = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    jurisdiction_code = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text="Resolved jurisdiction code at calculation time (e.g., CA-ON, US-CA).",
    )
    transaction_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Economic event date used for accrual reporting.",
    )
    document_side = models.CharField(
        max_length=8,
        choices=DocumentSide.choices,
        blank=True,
        default="",
        db_index=True,
        help_text="Classification for reporting: SALE or PURCHASE. Prefer this over inferring from content type.",
    )

    is_recoverable = models.BooleanField(
        help_text="Snapshot of TaxComponent.is_recoverable at calculation time.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=[
                    "transaction_line_content_type",
                    "transaction_line_object_id",
                ],
                name="tax_detail_line_idx",
            )
        ]

    def __str__(self):
        return f"{self.tax_component.name} – {self.tax_amount_home_currency_cad} CAD"


class TaxJurisdiction(models.Model):
    """
    Canonical jurisdiction for tax purposes (federal, state/provincial, local).
    """

    class JurisdictionType(models.TextChoices):
        FEDERAL = "FEDERAL", "Federal"
        PROVINCIAL = "PROVINCIAL", "Provincial/Territory"
        STATE = "STATE", "State"
        COUNTY = "COUNTY", "County"
        CITY = "CITY", "City"
        DISTRICT = "DISTRICT", "District"

    class SourcingRule(models.TextChoices):
        ORIGIN = "ORIGIN", "Origin-based"
        DESTINATION = "DESTINATION", "Destination-based"
        HYBRID = "HYBRID", "Hybrid"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True, help_text="e.g., CA-ON, US-CA, US-CA-LA")
    name = models.CharField(max_length=128)
    jurisdiction_type = models.CharField(max_length=20, choices=JurisdictionType.choices)
    country_code = models.CharField(max_length=2)
    region_code = models.CharField(max_length=10, blank=True)
    sourcing_rule = models.CharField(
        max_length=20,
        choices=SourcingRule.choices,
        default=SourcingRule.DESTINATION,
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["country_code", "code"]
        indexes = [
            models.Index(fields=["country_code", "region_code"], name="taxjur_country_region_idx"),
        ]

    def __str__(self):
        return f"{self.code} – {self.name}"


class TaxProductRule(models.Model):
    """
    Taxability rule for a product category within a jurisdiction.
    """

    class RuleType(models.TextChoices):
        TAXABLE = "TAXABLE", "Taxable"
        EXEMPT = "EXEMPT", "Exempt"
        ZERO_RATED = "ZERO_RATED", "Zero-rated"
        REDUCED = "REDUCED", "Reduced rate"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jurisdiction = models.ForeignKey(TaxJurisdiction, on_delete=models.CASCADE, related_name="product_rules")
    product_code = models.CharField(max_length=32)
    rule_type = models.CharField(max_length=20, choices=RuleType.choices)
    special_rate = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Override rate for REDUCED type.",
    )
    ssuta_code = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Optional SSUTA product category code (for future standardized mapping).",
    )
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["jurisdiction", "product_code", "valid_from"]
        indexes = [
            models.Index(fields=["product_code", "valid_from", "valid_to"], name="taxprod_rule_idx"),
        ]
        unique_together = ("jurisdiction", "product_code", "valid_from")

    def __str__(self):
        return f"{self.product_code} @ {self.jurisdiction.code} ({self.rule_type})"


class TaxPeriodSnapshot(models.Model):
    """
    Canonical snapshot of computed tax data for a filing period.
    """

    class SnapshotStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        COMPUTED = "COMPUTED", "Computed"
        REVIEWED = "REVIEWED", "Reviewed"
        FILED = "FILED", "Filed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey("core.Business", on_delete=models.CASCADE, related_name="tax_snapshots")
    period_key = models.CharField(max_length=16)
    country = models.CharField(max_length=2)
    status = models.CharField(max_length=16, choices=SnapshotStatus.choices, default=SnapshotStatus.DRAFT)
    computed_at = models.DateTimeField(auto_now=True)

    summary_by_jurisdiction = models.JSONField(default=dict, blank=True)
    line_mappings = models.JSONField(default=dict, blank=True)
    llm_summary = models.TextField(blank=True)
    llm_notes = models.TextField(blank=True)
    filed_at = models.DateTimeField(null=True, blank=True)
    last_filed_at = models.DateTimeField(null=True, blank=True)
    last_reset_at = models.DateTimeField(null=True, blank=True)
    last_reset_reason = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        unique_together = ("business", "period_key")
        indexes = [
            models.Index(fields=["business", "period_key", "status"], name="taxsnap_business_period_idx"),
        ]

    def __str__(self):
        return f"{self.business.name} – {self.period_key}"


class TaxPayment(models.Model):
    """
    Records real-world payments/refunds against a tax period.

    Use `kind` to distinguish:
    - PAYMENT: money paid to tax authority (reduces liability)
    - REFUND: money received from tax authority (reduces receivable)

    Amounts should always be positive; the `kind` field determines direction.
    This matches QuickBooks mental model where refunds are separate transactions.
    """

    class Kind(models.TextChoices):
        PAYMENT = "PAYMENT", "Payment to tax authority"
        REFUND = "REFUND", "Refund/credit from tax authority"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey("core.Business", on_delete=models.CASCADE, related_name="tax_payments")
    period_key = models.CharField(max_length=16, db_index=True)
    snapshot = models.ForeignKey(
        "taxes.TaxPeriodSnapshot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    bank_account = models.ForeignKey(
        "core.BankAccount",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tax_payments",
    )
    # Explicit kind field for PAYMENT vs REFUND (clearer than signed amounts)
    kind = models.CharField(
        max_length=10,
        choices=Kind.choices,
        default=Kind.PAYMENT,
        help_text="PAYMENT = money paid to authority, REFUND = money received from authority."
    )
    # Fallback label when no bank_account FK is set
    bank_account_label = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Manual bank account label for display when FK is not set."
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="CAD")
    payment_date = models.DateField()
    method = models.CharField(max_length=64, blank=True, default="")
    reference = models.CharField(max_length=128, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tax_payments_created",
    )

    class Meta:
        ordering = ["-payment_date", "-created_at"]
        indexes = [
            models.Index(fields=["business", "period_key"], name="taxpay_business_period_idx"),
            models.Index(fields=["business", "payment_date"], name="taxpay_business_date_idx"),
        ]

    def __str__(self):
        return f"{self.business.name} {self.period_key}: {self.kind} {self.amount} {self.currency} on {self.payment_date}"


class TaxAnomaly(models.Model):
    """
    Canonical tax anomaly record, surfaced through Tax Guardian.
    """

    class AnomalySeverity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    class AnomalyStatus(models.TextChoices):
        OPEN = "OPEN", "Open"
        ACKNOWLEDGED = "ACKNOWLEDGED", "Acknowledged"
        RESOLVED = "RESOLVED", "Resolved"
        IGNORED = "IGNORED", "Ignored"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey("core.Business", on_delete=models.CASCADE, related_name="tax_anomalies")
    period_key = models.CharField(max_length=16)
    code = models.CharField(max_length=64)
    severity = models.CharField(max_length=10, choices=AnomalySeverity.choices)
    status = models.CharField(max_length=16, choices=AnomalyStatus.choices, default=AnomalyStatus.OPEN)
    description = models.TextField()

    linked_transaction_ct = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    linked_transaction_id = models.PositiveIntegerField(null=True, blank=True)
    linked_transaction = GenericForeignKey("linked_transaction_ct", "linked_transaction_id")

    task_code = models.CharField(max_length=8, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "period_key", "code"], name="taxanomaly_period_code_idx"),
        ]

    def __str__(self):
        return f"{self.code} ({self.period_key})"
