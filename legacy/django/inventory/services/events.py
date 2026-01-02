from __future__ import annotations

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from inventory.exceptions import DomainError
from inventory.models import InventoryBalance, InventoryEvent


def _dec(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0.0000")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def get_balance_for_update(*, workspace, item, location) -> InventoryBalance:
    balance = (
        InventoryBalance.objects.select_for_update()
        .filter(workspace=workspace, item=item, location=location)
        .first()
    )
    if balance:
        return balance
    try:
        return InventoryBalance.objects.create(
            workspace=workspace,
            item=item,
            location=location,
            qty_on_hand=Decimal("0.0000"),
            qty_committed=Decimal("0.0000"),
            qty_on_order=Decimal("0.0000"),
            qty_available=Decimal("0.0000"),
            last_updated_at=timezone.now(),
        )
    except IntegrityError:
        return (
            InventoryBalance.objects.select_for_update()
            .filter(workspace=workspace, item=item, location=location)
            .get()
        )


@transaction.atomic
def append_event_and_update_balance(
    *,
    workspace,
    item,
    location,
    event_type: str,
    quantity_delta: Decimal,
    unit_cost: Decimal | None = None,
    source_reference: str | None = None,
    batch_reference: str | None = None,
    purchase_document=None,
    metadata: dict | None = None,
    qty_committed_delta: Decimal = Decimal("0.0000"),
    qty_on_order_delta: Decimal = Decimal("0.0000"),
    actor_type: str = "",
    actor_id: str = "",
    created_by=None,
    balance: InventoryBalance | None = None,
):
    metadata = dict(metadata or {})
    if qty_committed_delta:
        metadata["qty_committed_delta"] = str(_dec(qty_committed_delta))
    if qty_on_order_delta:
        metadata["qty_on_order_delta"] = str(_dec(qty_on_order_delta))

    event = InventoryEvent.objects.create(
        workspace=workspace,
        item=item,
        location=location,
        event_type=event_type,
        quantity_delta=_dec(quantity_delta),
        unit_cost=unit_cost,
        source_reference=source_reference or "",
        purchase_document=purchase_document,
        batch_reference=batch_reference or "",
        metadata=metadata,
        actor_type=actor_type or "",
        actor_id=actor_id or "",
        created_by=created_by,
    )

    balance = balance or get_balance_for_update(workspace=workspace, item=item, location=location)
    balance.qty_on_hand = _dec(balance.qty_on_hand) + _dec(quantity_delta)
    balance.qty_committed = _dec(balance.qty_committed) + _dec(qty_committed_delta)
    balance.qty_on_order = _dec(balance.qty_on_order) + _dec(qty_on_order_delta)

    if balance.qty_on_hand < 0:
        raise DomainError("Negative inventory is not allowed.")
    if balance.qty_committed < 0:
        raise DomainError("Committed quantity cannot be negative.")
    if balance.qty_on_order < 0:
        raise DomainError("On-order quantity cannot be negative.")

    balance.recompute_available()
    balance.last_event = event
    balance.last_updated_at = timezone.now()
    balance.save(
        update_fields=[
            "qty_on_hand",
            "qty_committed",
            "qty_on_order",
            "qty_available",
            "last_event",
            "last_updated_at",
        ]
    )
    return event, balance
