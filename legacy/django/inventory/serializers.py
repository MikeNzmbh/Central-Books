from __future__ import annotations

from rest_framework import serializers

from core.models import Account, Business
from inventory.accounts import COGS_CODE, INVENTORY_ASSET_CODE, ensure_inventory_accounts
from inventory.models import InventoryBalance, InventoryEvent, InventoryItem, InventoryLocation, LandedCostAllocation, LandedCostBatch


class InventoryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryItem
        fields = [
            "id",
            "workspace",
            "name",
            "sku",
            "item_type",
            "costing_method",
            "default_uom",
            "asset_account",
            "cogs_account",
            "revenue_account",
            "is_active",
            "created_at",
            "updated_at",
        ]


class InventoryItemCreateSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField()
    name = serializers.CharField(max_length=255)
    sku = serializers.CharField(max_length=255)
    item_type = serializers.ChoiceField(choices=InventoryItem.ItemType.choices, default=InventoryItem.ItemType.INVENTORY)
    costing_method = serializers.ChoiceField(
        choices=InventoryItem.CostingMethod.choices,
        default=InventoryItem.CostingMethod.FIFO,
        required=False,
    )
    default_uom = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    asset_account_id = serializers.IntegerField(required=False, allow_null=True)
    cogs_account_id = serializers.IntegerField(required=False, allow_null=True)
    revenue_account_id = serializers.IntegerField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        workspace = Business.objects.filter(id=attrs["workspace_id"]).first()
        if not workspace:
            raise serializers.ValidationError({"workspace_id": "Workspace not found."})

        item_type = attrs.get("item_type") or InventoryItem.ItemType.INVENTORY
        requires_accounts = item_type in {InventoryItem.ItemType.INVENTORY, InventoryItem.ItemType.ASSEMBLY}
        asset_account_id = attrs.get("asset_account_id")
        cogs_account_id = attrs.get("cogs_account_id")

        if requires_accounts and (not asset_account_id or not cogs_account_id):
            ensure_inventory_accounts(workspace)
            if not asset_account_id:
                default_asset = Account.objects.filter(business=workspace, code=INVENTORY_ASSET_CODE).first()
                if default_asset:
                    attrs["asset_account_id"] = default_asset.id
            if not cogs_account_id:
                default_cogs = Account.objects.filter(business=workspace, code=COGS_CODE).first()
                if default_cogs:
                    attrs["cogs_account_id"] = default_cogs.id

        for key, expected_type in (
            ("asset_account_id", Account.AccountType.ASSET),
            ("cogs_account_id", Account.AccountType.EXPENSE),
            ("revenue_account_id", Account.AccountType.INCOME),
        ):
            acct_id = attrs.get(key)
            if not acct_id:
                continue
            acct = Account.objects.filter(id=acct_id).select_related("business").first()
            if not acct:
                raise serializers.ValidationError({key: "Account not found."})
            if acct.business_id != workspace.id:
                raise serializers.ValidationError({key: "Account must belong to the same workspace."})
            if expected_type and acct.type != expected_type:
                raise serializers.ValidationError({key: f"Account must be {expected_type}."})

        if requires_accounts and (not attrs.get("asset_account_id") or not attrs.get("cogs_account_id")):
            raise serializers.ValidationError("asset_account_id and cogs_account_id are required for inventory/assembly items.")
        return attrs


class InventoryBalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryBalance
        fields = [
            "id",
            "workspace",
            "item",
            "location",
            "qty_on_hand",
            "qty_committed",
            "qty_on_order",
            "qty_available",
            "last_event",
            "last_updated_at",
        ]


class InventoryEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryEvent
        fields = [
            "id",
            "workspace",
            "item",
            "location",
            "event_type",
            "quantity_delta",
            "unit_cost",
            "source_reference",
            "purchase_document",
            "batch_reference",
            "metadata",
            "actor_type",
            "actor_id",
            "created_by",
            "created_at",
        ]


class InventoryReceiveSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField()
    item_id = serializers.IntegerField()
    location_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=19, decimal_places=4)
    unit_cost = serializers.DecimalField(max_digits=19, decimal_places=4)
    po_reference = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)


class InventoryShipSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField()
    item_id = serializers.IntegerField()
    location_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=19, decimal_places=4)
    so_reference = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)


class InventoryAdjustSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField()
    item_id = serializers.IntegerField()
    location_id = serializers.IntegerField()
    physical_qty = serializers.DecimalField(max_digits=19, decimal_places=4)
    reason_code = serializers.CharField(max_length=64)


class InventoryReserveSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField()
    item_id = serializers.IntegerField()
    location_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=19, decimal_places=4)
    reference = serializers.CharField(max_length=255)


class InventoryReleaseSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField()
    item_id = serializers.IntegerField()
    location_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=19, decimal_places=4)
    reference = serializers.CharField(max_length=255)


class InventoryLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryLocation
        fields = [
            "id",
            "workspace",
            "name",
            "code",
            "location_type",
            "parent",
            "created_at",
            "updated_at",
        ]


class LandedCostAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = LandedCostAllocation
        fields = [
            "id",
            "receipt_event",
            "allocated_amount",
            "metadata",
            "created_at",
        ]


class LandedCostBatchSerializer(serializers.ModelSerializer):
    allocations = LandedCostAllocationSerializer(many=True, read_only=True)

    class Meta:
        model = LandedCostBatch
        fields = [
            "id",
            "workspace",
            "status",
            "description",
            "allocation_method",
            "total_extra_cost",
            "credit_account",
            "created_by",
            "created_at",
            "updated_at",
            "allocations",
        ]


class LandedCostBatchCreateSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField()
    description = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    allocation_method = serializers.ChoiceField(choices=LandedCostBatch.AllocationMethod.choices, default=LandedCostBatch.AllocationMethod.MANUAL)
    total_extra_cost = serializers.DecimalField(max_digits=19, decimal_places=4)
    credit_account_id = serializers.IntegerField(required=False, allow_null=True)
    allocations = serializers.ListField(child=serializers.DictField(), allow_empty=False)
