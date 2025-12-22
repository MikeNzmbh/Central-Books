from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from inventory.models import InventoryEvent


QTY_QUANT = Decimal("0.0000")
MONEY_QUANT = Decimal("0.0000")


def _q(value: Decimal) -> Decimal:
    return (value or Decimal("0.0000")).quantize(QTY_QUANT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class LayerConsumption:
    batch_reference: str
    qty: Decimal
    unit_cost: Decimal


def _events_for_item_location(*, workspace, item, location):
    return (
        InventoryEvent.objects.filter(workspace=workspace, item=item, location=location)
        .order_by("created_at", "id")
        .only("id", "event_type", "quantity_delta", "unit_cost", "batch_reference")
    )


def get_fifo_cost_for_shipment(*, workspace, item, location, quantity: Decimal):
    """
    Replay inventory events to compute FIFO layer consumption and total cost.
    """
    quantity = _q(Decimal(quantity))
    if quantity <= 0:
        return Decimal("0.0000"), []

    layers: list[dict[str, Decimal | str]] = []

    def add_layer(qty_in: Decimal, unit_cost: Decimal, batch_reference: str, event_id: int):
        qty_in = _q(qty_in)
        if qty_in <= 0:
            return
        batch = batch_reference or f"event:{event_id}"
        layers.append(
            {
                "batch_reference": batch,
                "qty_remaining": qty_in,
                "unit_cost": _q(unit_cost),
            }
        )

    def consume(qty_out: Decimal):
        qty_out = _q(qty_out)
        if qty_out <= 0:
            return
        while qty_out > 0:
            if not layers:
                add_layer(qty_out, Decimal("0.0000"), "UNKNOWN", 0)
            layer = layers[0]
            available = _q(layer["qty_remaining"])  # type: ignore[arg-type]
            take = available if available <= qty_out else qty_out
            layer["qty_remaining"] = _q(available - take)  # type: ignore[index]
            qty_out = _q(qty_out - take)
            if _q(layer["qty_remaining"]) <= 0:  # type: ignore[arg-type]
                layers.pop(0)

    for ev in _events_for_item_location(workspace=workspace, item=item, location=location):
        if ev.quantity_delta > 0:
            add_layer(ev.quantity_delta, ev.unit_cost or Decimal("0.0000"), ev.batch_reference, ev.id)
        elif ev.quantity_delta < 0:
            consume(-ev.quantity_delta)

    qty_to_consume = quantity
    consumptions: list[LayerConsumption] = []
    total_cost = Decimal("0.0000")
    while qty_to_consume > 0:
        if not layers:
            add_layer(qty_to_consume, Decimal("0.0000"), "UNKNOWN", 0)
        layer = layers[0]
        available = _q(layer["qty_remaining"])  # type: ignore[arg-type]
        take = available if available <= qty_to_consume else qty_to_consume
        unit_cost = _q(layer["unit_cost"])  # type: ignore[arg-type]
        consumptions.append(
            LayerConsumption(
                batch_reference=str(layer["batch_reference"]),
                qty=_q(take),
                unit_cost=unit_cost,
            )
        )
        total_cost += _q(take * unit_cost)
        layer["qty_remaining"] = _q(available - take)  # type: ignore[index]
        qty_to_consume = _q(qty_to_consume - take)
        if _q(layer["qty_remaining"]) <= 0:  # type: ignore[arg-type]
            layers.pop(0)

    total_cost = total_cost.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    return (
        total_cost,
        [
            {
                "batch_reference": c.batch_reference,
                "qty": str(c.qty),
                "unit_cost": str(c.unit_cost),
            }
            for c in consumptions
        ],
    )


def get_avco_cost_for_shipment(*, workspace, item, location, quantity: Decimal):
    """
    Rolling weighted average (AVCO) based on on-hand value/qty from events.
    """
    quantity = _q(Decimal(quantity))

    qty_on_hand = Decimal("0.0000")
    value_on_hand = Decimal("0.0000")

    for ev in _events_for_item_location(workspace=workspace, item=item, location=location):
        if ev.quantity_delta > 0:
            qty_on_hand += _q(ev.quantity_delta)
            value_on_hand += _q(ev.quantity_delta * (ev.unit_cost or Decimal("0.0000")))
        elif ev.quantity_delta < 0:
            qty_out = _q(-ev.quantity_delta)
            avg = (value_on_hand / qty_on_hand).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP) if qty_on_hand > 0 else Decimal("0.0000")
            unit_cost_out = _q(ev.unit_cost) if ev.unit_cost is not None else avg
            qty_on_hand = _q(qty_on_hand - qty_out)
            value_on_hand = _q(value_on_hand - (qty_out * unit_cost_out))

    avg_unit_cost = (value_on_hand / qty_on_hand).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP) if qty_on_hand > 0 else Decimal("0.0000")
    if quantity <= 0:
        return Decimal("0.0000"), avg_unit_cost

    total_cost = (avg_unit_cost * quantity).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    return total_cost, avg_unit_cost


def get_current_avco_unit_cost(*, workspace, item, location) -> Decimal:
    """
    Compute current on-hand AVCO unit cost (value/qty) based on stored event unit_cost.
    """
    _total_cost, avg_unit_cost = get_avco_cost_for_shipment(
        workspace=workspace,
        item=item,
        location=location,
        quantity=Decimal("0.0000"),
    )
    return avg_unit_cost
