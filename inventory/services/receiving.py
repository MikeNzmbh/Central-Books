from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from core.models import JournalEntry, JournalLine
from inventory.accounts import GRNI_CODE, ensure_inventory_accounts, get_account_by_code
from inventory.exceptions import DomainError
from inventory.models import InventoryEvent, PurchaseDocument
from inventory.services.events import append_event_and_update_balance, get_balance_for_update


MONEY_QUANT = Decimal("0.0000")


def receive_stock(
    *,
    workspace,
    item,
    location,
    quantity: Decimal,
    unit_cost: Decimal,
    po_reference: str | None = None,
    actor_type: str = "",
    actor_id: str = "",
    created_by=None,
):
    quantity = Decimal(str(quantity))
    unit_cost = Decimal(str(unit_cost))
    if quantity <= 0:
        raise DomainError("quantity must be > 0.")
    if unit_cost <= 0:
        raise DomainError("unit_cost must be > 0.")
    if item.workspace_id != workspace.id:
        raise DomainError("Item does not belong to workspace.")
    if location.workspace_id != workspace.id:
        raise DomainError("Location does not belong to workspace.")
    if item.item_type not in {item.ItemType.INVENTORY, item.ItemType.ASSEMBLY}:
        raise DomainError("Only inventory/assembly items can be received into stock.")
    if not item.asset_account_id:
        raise DomainError("Inventory item is missing asset_account mapping.")

    ensure_inventory_accounts(workspace)
    grni_account = get_account_by_code(workspace=workspace, code=GRNI_CODE)

    batch_reference = uuid.uuid4().hex
    metadata = {"po_reference": po_reference or ""}

    with transaction.atomic():
        purchase_document = None
        qty_on_order_delta = Decimal("0.0000")
        if po_reference:
            po_reference = po_reference.strip()
            purchase_document, _ = PurchaseDocument.objects.get_or_create(
                workspace=workspace,
                document_type=PurchaseDocument.DocumentType.PO,
                external_reference=po_reference,
                defaults={"created_by": created_by, "status": PurchaseDocument.Status.OPEN},
            )
            balance = get_balance_for_update(workspace=workspace, item=item, location=location)
            reducible = balance.qty_on_order
            qty_on_order_delta = -(reducible if reducible <= quantity else quantity)
        else:
            balance = None

        event, _balance = append_event_and_update_balance(
            workspace=workspace,
            item=item,
            location=location,
            event_type=InventoryEvent.EventType.STOCK_RECEIVED,
            quantity_delta=quantity,
            unit_cost=unit_cost,
            source_reference=po_reference or "",
            purchase_document=purchase_document,
            batch_reference=batch_reference,
            metadata=metadata,
            qty_on_order_delta=qty_on_order_delta,
            actor_type=actor_type,
            actor_id=actor_id,
            created_by=created_by,
            balance=balance,
        )

        amount = (quantity * unit_cost).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        if amount <= 0:
            raise DomainError("Receipt value must be > 0.")

        ct = ContentType.objects.get_for_model(event.__class__)
        je = JournalEntry.objects.create(
            business=workspace,
            date=timezone.now().date(),
            description=f"Inventory received – {item.sku or item.name}",
            source_content_type=ct,
            source_object_id=event.id,
        )
        JournalLine.objects.create(journal_entry=je, account=item.asset_account, debit=amount, credit=Decimal("0.0000"))
        JournalLine.objects.create(journal_entry=je, account=grni_account, debit=Decimal("0.0000"), credit=amount)
        je.check_balance()

    return event, je
