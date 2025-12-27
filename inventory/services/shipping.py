from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from core.models import JournalEntry, JournalLine
from inventory.costing import get_avco_cost_for_shipment, get_fifo_cost_for_shipment
from inventory.exceptions import DomainError
from inventory.models import InventoryEvent
from inventory.services.events import append_event_and_update_balance, get_balance_for_update


MONEY_QUANT = Decimal("0.0000")


def ship_stock(
    *,
    workspace,
    item,
    location,
    quantity: Decimal,
    so_reference: str | None = None,
    actor_type: str = "",
    actor_id: str = "",
    created_by=None,
):
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise DomainError("quantity must be > 0.")
    if item.workspace_id != workspace.id:
        raise DomainError("Item does not belong to workspace.")
    if location.workspace_id != workspace.id:
        raise DomainError("Location does not belong to workspace.")
    if item.item_type not in {item.ItemType.INVENTORY, item.ItemType.ASSEMBLY}:
        raise DomainError("Only inventory/assembly items can be shipped from stock.")
    if not item.asset_account_id or not item.cogs_account_id:
        raise DomainError("Inventory item is missing GL mappings (asset_account/cogs_account).")

    with transaction.atomic():
        balance = get_balance_for_update(workspace=workspace, item=item, location=location)
        if balance.qty_on_hand < quantity:
            raise DomainError("Insufficient stock to fulfill shipment.")

        committed_reduction = balance.qty_committed if balance.qty_committed <= quantity else quantity

        if item.costing_method == item.CostingMethod.AVCO:
            total_cost, avg_unit_cost = get_avco_cost_for_shipment(
                workspace=workspace, item=item, location=location, quantity=quantity
            )
            layers = []
            effective_unit_cost = avg_unit_cost
        else:
            total_cost, layers = get_fifo_cost_for_shipment(
                workspace=workspace, item=item, location=location, quantity=quantity
            )
            effective_unit_cost = (total_cost / quantity).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP) if quantity > 0 else Decimal("0.0000")

        total_cost = total_cost.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        if total_cost <= 0:
            raise DomainError("Unable to compute COGS for shipment (missing cost basis).")

        metadata = {
            "so_reference": so_reference or "",
            "costing_method": item.costing_method,
            "fifo_layers": layers,
            "total_cost": str(total_cost),
        }

        event, _balance = append_event_and_update_balance(
            workspace=workspace,
            item=item,
            location=location,
            event_type=InventoryEvent.EventType.STOCK_SHIPPED,
            quantity_delta=-quantity,
            unit_cost=effective_unit_cost,
            source_reference=so_reference or "",
            metadata=metadata,
            qty_committed_delta=-committed_reduction,
            actor_type=actor_type,
            actor_id=actor_id,
            created_by=created_by,
            balance=balance,
        )

        ct = ContentType.objects.get_for_model(event.__class__)
        je = JournalEntry.objects.create(
            business=workspace,
            date=timezone.now().date(),
            description=f"Inventory shipped – {item.sku or item.name}",
            source_content_type=ct,
            source_object_id=event.id,
        )
        JournalLine.objects.create(journal_entry=je, account=item.cogs_account, debit=total_cost, credit=Decimal("0.0000"))
        JournalLine.objects.create(journal_entry=je, account=item.asset_account, debit=Decimal("0.0000"), credit=total_cost)
        je.check_balance()

    return event, je

