from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class PurchaseDocument(models.Model):
    """
    Minimal purchasing document shell for v1.1 correlation.

    - PO: increases qty_on_order (non-posting for now)
    - BILL: clears GRNI and creates AP postings (via billing service)
    """

    class DocumentType(models.TextChoices):
        PO = "PO", "Purchase Order"
        BILL = "BILL", "Vendor Bill"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        VOID = "void", "Void"

    workspace = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="purchase_documents",
    )
    document_type = models.CharField(max_length=8, choices=DocumentType.choices, db_index=True)
    external_reference = models.CharField(max_length=255, blank=True, default="", db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_purchase_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "document_type", "external_reference"],
                name="uniq_purchase_document_type_reference_per_workspace",
            )
        ]
        indexes = [
            models.Index(fields=["workspace", "document_type", "status"]),
        ]
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        ref = self.external_reference or str(self.id)
        return f"{self.document_type} {ref}"


class InventoryItem(models.Model):
    class ItemType(models.TextChoices):
        INVENTORY = "inventory", "Inventory"
        NON_INVENTORY = "non_inventory", "Non-inventory"
        SERVICE = "service", "Service"
        BUNDLE = "bundle", "Bundle"
        ASSEMBLY = "assembly", "Assembly"

    class CostingMethod(models.TextChoices):
        FIFO = "fifo", "FIFO"
        AVCO = "avco", "Weighted Average (AVCO)"

    workspace = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="inventory_items",
    )
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=255)
    item_type = models.CharField(max_length=32, choices=ItemType.choices, default=ItemType.INVENTORY, db_index=True)
    costing_method = models.CharField(
        max_length=8,
        choices=CostingMethod.choices,
        default=CostingMethod.FIFO,
        db_index=True,
    )
    default_uom = models.CharField(max_length=32, blank=True, default="")

    asset_account = models.ForeignKey(
        "core.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_items_asset",
        help_text="Inventory asset account (required for inventory/assembly items).",
    )
    cogs_account = models.ForeignKey(
        "core.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_items_cogs",
        help_text="COGS account (required for inventory/assembly items).",
    )
    revenue_account = models.ForeignKey(
        "core.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_items_revenue",
        help_text="Optional revenue account override.",
    )

    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["workspace", "sku"], name="uniq_inventory_item_sku_per_workspace"),
        ]
        indexes = [
            models.Index(fields=["workspace", "item_type", "is_active"]),
        ]
        ordering = ["name", "sku", "id"]

    def __str__(self) -> str:
        return f"{self.sku} – {self.name}" if self.sku else self.name

    def clean(self):
        super().clean()
        if not self.workspace_id:
            return

        requires_accounts = self.item_type in {self.ItemType.INVENTORY, self.ItemType.ASSEMBLY}
        if requires_accounts:
            if not self.asset_account_id:
                raise ValidationError({"asset_account": "asset_account is required for inventory/assembly items."})
            if not self.cogs_account_id:
                raise ValidationError({"cogs_account": "cogs_account is required for inventory/assembly items."})

        from core.models import Account

        if self.asset_account_id:
            if self.asset_account.business_id != self.workspace_id:
                raise ValidationError({"asset_account": "Account must belong to the same workspace."})
            if self.asset_account.type != Account.AccountType.ASSET:
                raise ValidationError({"asset_account": "asset_account must be an ASSET account."})

        if self.cogs_account_id:
            if self.cogs_account.business_id != self.workspace_id:
                raise ValidationError({"cogs_account": "Account must belong to the same workspace."})
            if self.cogs_account.type != Account.AccountType.EXPENSE:
                raise ValidationError({"cogs_account": "cogs_account must be an EXPENSE account."})

        if self.revenue_account_id:
            if self.revenue_account.business_id != self.workspace_id:
                raise ValidationError({"revenue_account": "Account must belong to the same workspace."})
            if self.revenue_account.type != Account.AccountType.INCOME:
                raise ValidationError({"revenue_account": "revenue_account must be an INCOME account."})


class InventoryLocation(models.Model):
    class LocationType(models.TextChoices):
        SITE = "site", "Site"
        BIN = "bin", "Bin"
        IN_TRANSIT = "in_transit", "In transit"

    workspace = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="inventory_locations",
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=32)
    location_type = models.CharField(max_length=16, choices=LocationType.choices, default=LocationType.SITE, db_index=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["workspace", "code"], name="uniq_inventory_location_code_per_workspace"),
        ]
        indexes = [
            models.Index(fields=["workspace", "location_type"]),
        ]
        ordering = ["name", "code", "id"]

    def __str__(self) -> str:
        return f"{self.code} – {self.name}" if self.code else self.name

    def clean(self):
        super().clean()
        if self.parent_id and self.parent.workspace_id != self.workspace_id:
            raise ValidationError({"parent": "Parent location must belong to the same workspace."})


class InventoryEvent(models.Model):
    class EventType(models.TextChoices):
        PO_CREATED = "PO_CREATED", "PO created"
        PO_UPDATED = "PO_UPDATED", "PO updated"
        PO_CANCELLED = "PO_CANCELLED", "PO cancelled"
        STOCK_RECEIVED = "STOCK_RECEIVED", "Stock received"
        STOCK_SHIPPED = "STOCK_SHIPPED", "Stock shipped"
        STOCK_COMMITTED = "STOCK_COMMITTED", "Stock committed"
        STOCK_UNCOMMITTED = "STOCK_UNCOMMITTED", "Stock uncommitted"
        STOCK_ADJUSTED = "STOCK_ADJUSTED", "Stock adjusted"
        STOCK_TRANSFERRED = "STOCK_TRANSFERRED", "Stock transferred"
        STOCK_LANDED_COST_ALLOCATED = "STOCK_LANDED_COST_ALLOCATED", "Landed cost allocated (stub)"
        VENDOR_BILL_POSTED = "VENDOR_BILL_POSTED", "Vendor bill posted"

    workspace = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="inventory_events",
    )
    item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.PROTECT,
        related_name="events",
    )
    location = models.ForeignKey(
        "inventory.InventoryLocation",
        on_delete=models.PROTECT,
        related_name="events",
    )
    event_type = models.CharField(max_length=64, choices=EventType.choices, db_index=True)
    quantity_delta = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0.0000"))
    unit_cost = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)

    source_reference = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="External reference (PO, receipt, SO, shipment, etc.).",
    )
    purchase_document = models.ForeignKey(
        "inventory.PurchaseDocument",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_events",
        help_text="Optional purchasing document context (PO/BILL).",
    )
    batch_reference = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="FIFO batch identifier (optional).",
    )
    metadata = models.JSONField(default=dict, blank=True)

    actor_type = models.CharField(max_length=32, blank=True, default="")
    actor_id = models.CharField(max_length=128, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_inventory_events",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["workspace", "item", "location", "created_at"]),
            models.Index(fields=["workspace", "event_type", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(event_type="STOCK_RECEIVED", unit_cost__isnull=False)
                | ~models.Q(event_type="STOCK_RECEIVED"),
                name="inventoryevent_received_requires_unit_cost",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} {self.quantity_delta} {self.item_id}@{self.location_id}"

    def clean(self):
        super().clean()
        if self.item_id and self.item.workspace_id != self.workspace_id:
            raise ValidationError({"item": "Item must belong to the same workspace."})
        if self.location_id and self.location.workspace_id != self.workspace_id:
            raise ValidationError({"location": "Location must belong to the same workspace."})

        if self.event_type == self.EventType.STOCK_RECEIVED and self.unit_cost is None:
            raise ValidationError({"unit_cost": "unit_cost is required for STOCK_RECEIVED events."})

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("InventoryEvent is immutable once created.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # pragma: no cover
        raise TypeError("InventoryEvent cannot be deleted.")


class InventoryBalance(models.Model):
    workspace = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="inventory_balances",
    )
    item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.PROTECT,
        related_name="balances",
    )
    location = models.ForeignKey(
        "inventory.InventoryLocation",
        on_delete=models.PROTECT,
        related_name="balances",
    )

    qty_on_hand = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0.0000"))
    qty_committed = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0.0000"))
    qty_on_order = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0.0000"))
    qty_available = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0.0000"))

    last_event = models.ForeignKey(
        "inventory.InventoryEvent",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    last_updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "item", "location"],
                name="uniq_inventory_balance_item_location_per_workspace",
            ),
            models.CheckConstraint(check=models.Q(qty_on_hand__gte=0), name="inventorybalance_qty_on_hand_gte_0"),
            models.CheckConstraint(check=models.Q(qty_committed__gte=0), name="inventorybalance_qty_committed_gte_0"),
            models.CheckConstraint(check=models.Q(qty_on_order__gte=0), name="inventorybalance_qty_on_order_gte_0"),
        ]
        indexes = [
            models.Index(fields=["workspace", "item"]),
            models.Index(fields=["workspace", "location"]),
        ]
        ordering = ["item_id", "location_id"]

    def __str__(self) -> str:
        return f"Bal {self.workspace_id} {self.item_id}@{self.location_id}: {self.qty_on_hand}"

    def recompute_available(self) -> None:
        self.qty_available = (self.qty_on_hand or Decimal("0.0000")) - (self.qty_committed or Decimal("0.0000"))


class PurchaseDocumentReceiptLink(models.Model):
    """
    Link a BILL to one or more STOCK_RECEIVED events (receipt matching).
    """

    bill = models.ForeignKey(
        "inventory.PurchaseDocument",
        on_delete=models.CASCADE,
        related_name="receipt_links",
        limit_choices_to={"document_type": PurchaseDocument.DocumentType.BILL},
    )
    receipt_event = models.ForeignKey(
        "inventory.InventoryEvent",
        on_delete=models.PROTECT,
        related_name="bill_links",
    )
    quantity = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Optional partial quantity invoiced; defaults to full receipt quantity when null.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["bill", "receipt_event"], name="uniq_bill_receipt_event_link"),
        ]
        indexes = [
            models.Index(fields=["bill", "created_at"]),
            models.Index(fields=["receipt_event", "created_at"]),
        ]

    def clean(self):
        super().clean()
        if self.bill_id and self.receipt_event_id:
            if self.bill.workspace_id != self.receipt_event.workspace_id:
                raise ValidationError("Bill and receipt must belong to same workspace.")
            if self.receipt_event.event_type != InventoryEvent.EventType.STOCK_RECEIVED:
                raise ValidationError("receipt_event must be a STOCK_RECEIVED event.")


class LandedCostBatch(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPLIED = "applied", "Applied"
        VOID = "void", "Void"

    class AllocationMethod(models.TextChoices):
        VALUE = "value", "Value"
        WEIGHT = "weight", "Weight"
        QUANTITY = "quantity", "Quantity"
        MANUAL = "manual", "Manual"

    workspace = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="landed_cost_batches",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    description = models.CharField(max_length=255, blank=True, default="")
    allocation_method = models.CharField(max_length=16, choices=AllocationMethod.choices, default=AllocationMethod.MANUAL)
    total_extra_cost = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0.0000"))
    credit_account = models.ForeignKey(
        "core.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="landed_cost_batches_credit",
        help_text="Credit account for landed cost (clearing/AP placeholder).",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_landed_cost_batches",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["workspace", "status", "created_at"]),
        ]
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"Landed cost {self.id} ({self.status})"


class LandedCostAllocation(models.Model):
    """
    Manual allocation line (v1.1 skeleton) tying extra cost to a receipt event.
    """

    batch = models.ForeignKey(
        "inventory.LandedCostBatch",
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    receipt_event = models.ForeignKey(
        "inventory.InventoryEvent",
        on_delete=models.PROTECT,
        related_name="landed_cost_allocations",
        help_text="Must be a STOCK_RECEIVED event.",
    )
    allocated_amount = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0.0000"))
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["batch", "created_at"]),
            models.Index(fields=["receipt_event", "created_at"]),
        ]

    def clean(self):
        super().clean()
        if self.batch_id and self.receipt_event_id:
            if self.batch.workspace_id != self.receipt_event.workspace_id:
                raise ValidationError("Batch and receipt must belong to same workspace.")
            if self.receipt_event.event_type != InventoryEvent.EventType.STOCK_RECEIVED:
                raise ValidationError("receipt_event must be a STOCK_RECEIVED event.")
