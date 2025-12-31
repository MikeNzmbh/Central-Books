from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from core.models import JournalEntry, JournalLine
from inventory.accounts import INVENTORY_SHRINKAGE_CODE, ensure_inventory_accounts, get_account_by_code
from inventory.costing import get_avco_cost_for_shipment, get_fifo_cost_for_shipment
from inventory.exceptions import DomainError
from inventory.models import InventoryEvent
from inventory.services.events import append_event_and_update_balance, get_balance_for_update


MONEY_QUANT = Decimal("0.0000")


def adjust_stock_to_physical_count(
    *,
    workspace,
    item,
    location,
    physical_qty: Decimal,
    reason_code: str,
    actor_type: str = "",
    actor_id: str = "",
    created_by=None,
):
    physical_qty = Decimal(str(physical_qty))
    if physical_qty < 0:
        raise DomainError("physical_qty must be >= 0.")
    if item.workspace_id != workspace.id:
        raise DomainError("Item does not belong to workspace.")
    if location.workspace_id != workspace.id:
        raise DomainError("Location does not belong to workspace.")
    if item.item_type not in {item.ItemType.INVENTORY, item.ItemType.ASSEMBLY}:
        raise DomainError("Only inventory/assembly items can be adjusted.")
    if not item.asset_account_id:
        raise DomainError("Inventory item is missing asset_account mapping.")

    ensure_inventory_accounts(workspace)
    shrinkage_account = get_account_by_code(workspace=workspace, code=INVENTORY_SHRINKAGE_CODE)

    with transaction.atomic():
        balance = get_balance_for_update(workspace=workspace, item=item, location=location)
        current = balance.qty_on_hand
        delta = (physical_qty - current).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        if delta == 0:
            return None, None

        if delta < 0:
            qty_out = -delta
            if item.costing_method == item.CostingMethod.AVCO:
                total_cost, avg_unit_cost = get_avco_cost_for_shipment(
                    workspace=workspace, item=item, location=location, quantity=qty_out
                )
                layers = []
                unit_cost = avg_unit_cost
            else:
                total_cost, layers = get_fifo_cost_for_shipment(
                    workspace=workspace, item=item, location=location, quantity=qty_out
                )
                unit_cost = (total_cost / qty_out).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP) if qty_out > 0 else Decimal("0.0000")

            total_cost = total_cost.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
            if total_cost <= 0:
                raise DomainError("Unable to value negative adjustment (missing cost basis).")

            metadata = {
                "reason_code": reason_code,
                "physical_qty": str(physical_qty),
                "costing_method": item.costing_method,
                "fifo_layers": layers,
                "total_cost": str(total_cost),
            }

            event, _balance = append_event_and_update_balance(
                workspace=workspace,
                item=item,
                location=location,
                event_type=InventoryEvent.EventType.STOCK_ADJUSTED,
                quantity_delta=delta,
                unit_cost=unit_cost,
                metadata=metadata,
                actor_type=actor_type,
                actor_id=actor_id,
                created_by=created_by,
                balance=balance,
            )

            ct = ContentType.objects.get_for_model(event.__class__)
            je = JournalEntry.objects.create(
                business=workspace,
                date=timezone.now().date(),
                description=f"Inventory adjusted (shrinkage) – {item.sku or item.name}",
                source_content_type=ct,
                source_object_id=event.id,
            )
            JournalLine.objects.create(journal_entry=je, account=shrinkage_account, debit=total_cost, credit=Decimal("0.0000"))
            JournalLine.objects.create(journal_entry=je, account=item.asset_account, debit=Decimal("0.0000"), credit=total_cost)
            je.check_balance()
            return event, je

        qty_in = delta
        if item.costing_method == item.CostingMethod.AVCO:
            _ignored, avg_unit_cost = get_avco_cost_for_shipment(
                workspace=workspace, item=item, location=location, quantity=Decimal("0.0000")
            )
            unit_cost = avg_unit_cost
            layers = []
        else:
            _ignored_total, layers = get_fifo_cost_for_shipment(
                workspace=workspace, item=item, location=location, quantity=Decimal("0.0000")
            )
            _total_cost_on_hand, avg_unit_cost = get_avco_cost_for_shipment(
                workspace=workspace, item=item, location=location, quantity=Decimal("0.0000")
            )
            unit_cost = avg_unit_cost

        if unit_cost <= 0:
            raise DomainError("Unable to value positive adjustment without an existing cost basis.")

        total_cost = (qty_in * unit_cost).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        if total_cost <= 0:
            raise DomainError("Adjustment value must be > 0.")

        metadata = {
            "reason_code": reason_code,
            "physical_qty": str(physical_qty),
            "costing_method": item.costing_method,
            "fifo_layers": layers,
            "total_cost": str(total_cost),
        }

        event, _balance = append_event_and_update_balance(
            workspace=workspace,
            item=item,
            location=location,
            event_type=InventoryEvent.EventType.STOCK_ADJUSTED,
            quantity_delta=qty_in,
            unit_cost=unit_cost,
            metadata=metadata,
            actor_type=actor_type,
            actor_id=actor_id,
            created_by=created_by,
            balance=balance,
        )

        ct = ContentType.objects.get_for_model(event.__class__)
        je = JournalEntry.objects.create(
            business=workspace,
            date=timezone.now().date(),
            description=f"Inventory adjusted (gain) – {item.sku or item.name}",
            source_content_type=ct,
            source_object_id=event.id,
        )
        JournalLine.objects.create(journal_entry=je, account=item.asset_account, debit=total_cost, credit=Decimal("0.0000"))
        JournalLine.objects.create(journal_entry=je, account=shrinkage_account, debit=Decimal("0.0000"), credit=total_cost)
        je.check_balance()
        return event, je

