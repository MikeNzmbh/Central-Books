from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from inventory.exceptions import DomainError
from inventory.models import InventoryEvent, PurchaseDocument
from inventory.services.events import append_event_and_update_balance, get_balance_for_update


def _dec(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0.0000")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@transaction.atomic
def record_po_created(
    *,
    workspace,
    item,
    location,
    quantity: Decimal,
    po_reference: str,
    actor_type: str = "",
    actor_id: str = "",
    created_by=None,
):
    po_reference = (po_reference or "").strip()
    if not po_reference:
        raise DomainError("po_reference is required.")
    quantity = _dec(quantity)
    if quantity <= 0:
        raise DomainError("quantity must be > 0.")
    if item.workspace_id != workspace.id or location.workspace_id != workspace.id:
        raise DomainError("Item/location does not belong to workspace.")

    po_doc, _ = PurchaseDocument.objects.get_or_create(
        workspace=workspace,
        document_type=PurchaseDocument.DocumentType.PO,
        external_reference=po_reference,
        defaults={"created_by": created_by, "status": PurchaseDocument.Status.OPEN},
    )
    if po_doc.status == PurchaseDocument.Status.VOID:
        raise DomainError("PO is void.")

    balance = get_balance_for_update(workspace=workspace, item=item, location=location)
    event, updated = append_event_and_update_balance(
        workspace=workspace,
        item=item,
        location=location,
        event_type=InventoryEvent.EventType.PO_CREATED,
        quantity_delta=Decimal("0.0000"),
        source_reference=po_reference,
        purchase_document=po_doc,
        metadata={"po_reference": po_reference, "kind": "created"},
        qty_on_order_delta=quantity,
        actor_type=actor_type,
        actor_id=actor_id,
        created_by=created_by,
        balance=balance,
    )
    return po_doc, event, updated


@transaction.atomic
def record_po_updated(
    *,
    workspace,
    item,
    location,
    quantity_delta: Decimal,
    po_reference: str,
    actor_type: str = "",
    actor_id: str = "",
    created_by=None,
):
    po_reference = (po_reference or "").strip()
    if not po_reference:
        raise DomainError("po_reference is required.")
    quantity_delta = _dec(quantity_delta)
    if quantity_delta == 0:
        raise DomainError("quantity_delta must be non-zero.")
    if item.workspace_id != workspace.id or location.workspace_id != workspace.id:
        raise DomainError("Item/location does not belong to workspace.")

    po_doc, _ = PurchaseDocument.objects.get_or_create(
        workspace=workspace,
        document_type=PurchaseDocument.DocumentType.PO,
        external_reference=po_reference,
        defaults={"created_by": created_by, "status": PurchaseDocument.Status.OPEN},
    )
    if po_doc.status == PurchaseDocument.Status.VOID:
        raise DomainError("PO is void.")

    balance = get_balance_for_update(workspace=workspace, item=item, location=location)
    # Clamp reductions to avoid negative on-order.
    effective_delta = quantity_delta
    if effective_delta < 0:
        max_reducible = balance.qty_on_order
        effective_delta = -max_reducible if -effective_delta > max_reducible else effective_delta
    event, updated = append_event_and_update_balance(
        workspace=workspace,
        item=item,
        location=location,
        event_type=InventoryEvent.EventType.PO_UPDATED,
        quantity_delta=Decimal("0.0000"),
        source_reference=po_reference,
        purchase_document=po_doc,
        metadata={"po_reference": po_reference, "kind": "updated", "requested_delta": str(quantity_delta)},
        qty_on_order_delta=effective_delta,
        actor_type=actor_type,
        actor_id=actor_id,
        created_by=created_by,
        balance=balance,
    )
    return po_doc, event, updated


@transaction.atomic
def record_po_cancelled(
    *,
    workspace,
    item,
    location,
    po_reference: str,
    cancel_quantity: Decimal | None = None,
    actor_type: str = "",
    actor_id: str = "",
    created_by=None,
):
    """
    Cancel reduces on-order. If cancel_quantity is None, reduce to zero (clamped).
    """
    po_reference = (po_reference or "").strip()
    if not po_reference:
        raise DomainError("po_reference is required.")
    if item.workspace_id != workspace.id or location.workspace_id != workspace.id:
        raise DomainError("Item/location does not belong to workspace.")

    po_doc = PurchaseDocument.objects.filter(
        workspace=workspace, document_type=PurchaseDocument.DocumentType.PO, external_reference=po_reference
    ).first()
    if not po_doc:
        raise DomainError("PO not found.")

    balance = get_balance_for_update(workspace=workspace, item=item, location=location)
    reducible = balance.qty_on_order
    if cancel_quantity is not None:
        cancel_quantity = _dec(cancel_quantity)
        if cancel_quantity <= 0:
            raise DomainError("cancel_quantity must be > 0.")
        reducible = reducible if reducible <= cancel_quantity else cancel_quantity

    event, updated = append_event_and_update_balance(
        workspace=workspace,
        item=item,
        location=location,
        event_type=InventoryEvent.EventType.PO_CANCELLED,
        quantity_delta=Decimal("0.0000"),
        source_reference=po_reference,
        purchase_document=po_doc,
        metadata={"po_reference": po_reference, "kind": "cancelled", "cancel_quantity": str(reducible)},
        qty_on_order_delta=-reducible,
        actor_type=actor_type,
        actor_id=actor_id,
        created_by=created_by,
        balance=balance,
    )
    PurchaseDocument.objects.filter(id=po_doc.id).update(status=PurchaseDocument.Status.CLOSED)
    return po_doc, event, updated

