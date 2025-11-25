import uuid
from decimal import Decimal

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
    transaction_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Economic event date used for accrual reporting.",
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
