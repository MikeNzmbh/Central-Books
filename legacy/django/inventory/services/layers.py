from __future__ import annotations

from decimal import Decimal

from inventory.models import InventoryEvent


def _dec(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0.0000")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def compute_batch_remaining(*, workspace, item, location) -> dict[str, Decimal]:
    """
    Replay events to estimate remaining quantity per receipt batch_reference.

    - Uses explicit FIFO layer consumption (metadata.fifo_layers) when present.
    - Falls back to FIFO across known batches when not present.
    """
    events = (
        InventoryEvent.objects.filter(workspace=workspace, item=item, location=location)
        .order_by("created_at", "id")
        .only("id", "event_type", "quantity_delta", "batch_reference", "metadata")
    )

    batch_order: list[str] = []
    remaining: dict[str, Decimal] = {}

    def _ensure_batch(batch: str):
        if batch not in remaining:
            remaining[batch] = Decimal("0.0000")
            batch_order.append(batch)

    def _consume_fifo(qty_out: Decimal):
        qty_out = _dec(qty_out)
        if qty_out <= 0:
            return
        for batch in list(batch_order):
            if qty_out <= 0:
                break
            available = remaining.get(batch, Decimal("0.0000"))
            if available <= 0:
                continue
            take = available if available <= qty_out else qty_out
            remaining[batch] = available - take
            qty_out -= take

    for ev in events:
        q = _dec(ev.quantity_delta)
        if q > 0:
            batch = ev.batch_reference or f"event:{ev.id}"
            _ensure_batch(batch)
            remaining[batch] = remaining.get(batch, Decimal("0.0000")) + q
            continue

        if q == 0:
            continue

        qty_out = -q
        layers = (ev.metadata or {}).get("fifo_layers") or []
        if isinstance(layers, list) and layers:
            for layer in layers:
                if not isinstance(layer, dict):
                    continue
                batch = str(layer.get("batch_reference") or "").strip()
                if not batch:
                    continue
                _ensure_batch(batch)
                remaining[batch] = remaining.get(batch, Decimal("0.0000")) - _dec(layer.get("qty"))
            continue

        _consume_fifo(qty_out)

    # Clamp negatives that can happen when history is incomplete.
    return {b: (qty if qty > 0 else Decimal("0.0000")) for b, qty in remaining.items()}

