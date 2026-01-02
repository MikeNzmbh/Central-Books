from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from inventory.exceptions import DomainError
from inventory.models import InventoryEvent
from inventory.services.events import append_event_and_update_balance, get_balance_for_update


def commit_stock(
    *,
    workspace,
    item,
    location,
    quantity: Decimal,
    so_reference: str,
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

    with transaction.atomic():
        balance = get_balance_for_update(workspace=workspace, item=item, location=location)
        available = balance.qty_on_hand - balance.qty_committed
        if available < quantity:
            raise DomainError("Insufficient available stock to reserve.")
        event, updated = append_event_and_update_balance(
            workspace=workspace,
            item=item,
            location=location,
            event_type=InventoryEvent.EventType.STOCK_COMMITTED,
            quantity_delta=Decimal("0.0000"),
            source_reference=so_reference,
            metadata={"so_reference": so_reference},
            qty_committed_delta=quantity,
            actor_type=actor_type,
            actor_id=actor_id,
            created_by=created_by,
            balance=balance,
        )
    return event, updated


def uncommit_stock(
    *,
    workspace,
    item,
    location,
    quantity: Decimal,
    so_reference: str,
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

    with transaction.atomic():
        balance = get_balance_for_update(workspace=workspace, item=item, location=location)
        if balance.qty_committed < quantity:
            raise DomainError("Cannot uncommit more stock than is committed.")
        event, updated = append_event_and_update_balance(
            workspace=workspace,
            item=item,
            location=location,
            event_type=InventoryEvent.EventType.STOCK_UNCOMMITTED,
            quantity_delta=Decimal("0.0000"),
            source_reference=so_reference,
            metadata={"so_reference": so_reference},
            qty_committed_delta=-quantity,
            actor_type=actor_type,
            actor_id=actor_id,
            created_by=created_by,
            balance=balance,
        )
    return event, updated
