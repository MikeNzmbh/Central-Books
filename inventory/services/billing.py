from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from core.models import JournalEntry, JournalLine
from inventory.accounts import GRNI_CODE, INVENTORY_VARIANCE_CODE, ensure_inventory_accounts, get_account_by_code
from inventory.exceptions import DomainError
from inventory.models import InventoryEvent, PurchaseDocument, PurchaseDocumentReceiptLink
from inventory.services.events import append_event_and_update_balance
from inventory.services.layers import compute_batch_remaining


MONEY_QUANT = Decimal("0.0000")


def _money(value: Decimal) -> Decimal:
    return Decimal(str(value or Decimal("0.0000"))).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


@transaction.atomic
def post_vendor_bill_against_receipts(
    *,
    workspace,
    bill_reference: str,
    receipt_event_ids: list[int],
    bill_total: Decimal,
    actor_type: str = "",
    actor_id: str = "",
    created_by=None,
):
    """
    v1.1 GRNI flow (receipt before bill):

    - Always clears GRNI for the receipt value.
    - Credits AP for the bill amount.
    - Variance rule (v1.1 simplification):
      - If ALL linked receipt quantities are still on-hand (unconsumed), adjust Inventory Asset.
      - Otherwise, book the entire delta to Inventory Variance.
    """
    bill_reference = (bill_reference or "").strip()
    if not bill_reference:
        raise DomainError("bill_reference is required.")
    bill_total = _money(Decimal(str(bill_total)))
    if bill_total <= 0:
        raise DomainError("bill_total must be > 0.")
    if not receipt_event_ids:
        raise DomainError("receipt_event_ids is required.")

    ensure_inventory_accounts(workspace)
    grni = get_account_by_code(workspace=workspace, code=GRNI_CODE)
    ap = get_account_by_code(workspace=workspace, code="2000")
    variance = get_account_by_code(workspace=workspace, code=INVENTORY_VARIANCE_CODE)

    receipts = list(
        InventoryEvent.objects.select_related("item", "location")
        .filter(workspace=workspace, id__in=receipt_event_ids, event_type=InventoryEvent.EventType.STOCK_RECEIVED)
        .order_by("created_at", "id")
    )
    if len(receipts) != len(set(receipt_event_ids)):
        raise DomainError("One or more receipt events were not found.")

    # Ensure receipts are not already linked to a different bill.
    existing_links = PurchaseDocumentReceiptLink.objects.filter(receipt_event_id__in=[r.id for r in receipts]).select_related("bill")
    if existing_links.exists():
        raise DomainError("One or more receipt events are already linked to a vendor bill.")

    receipt_value = Decimal("0.0000")
    for r in receipts:
        if r.unit_cost is None:
            raise DomainError("Receipt event is missing unit_cost.")
        receipt_value += _money(Decimal(r.quantity_delta) * Decimal(r.unit_cost))

    receipt_value = _money(receipt_value)
    if receipt_value <= 0:
        raise DomainError("Linked receipts have no value.")

    delta = _money(bill_total - receipt_value)

    bill_doc, _created = PurchaseDocument.objects.get_or_create(
        workspace=workspace,
        document_type=PurchaseDocument.DocumentType.BILL,
        external_reference=bill_reference,
        defaults={"created_by": created_by, "status": PurchaseDocument.Status.OPEN},
    )
    if bill_doc.status == PurchaseDocument.Status.VOID:
        raise DomainError("Cannot post against a void bill document.")

    # Link receipts to bill.
    for r in receipts:
        PurchaseDocumentReceiptLink.objects.create(bill=bill_doc, receipt_event=r, quantity=None)

    # Determine whether ALL receipt quantities are still on-hand.
    # We check the batch remaining for each receipt batch_reference.
    all_still_on_hand = True
    for r in receipts:
        batch = r.batch_reference or ""
        if not batch:
            all_still_on_hand = False
            break
        remaining = compute_batch_remaining(workspace=workspace, item=r.item, location=r.location).get(batch, Decimal("0.0000"))
        if remaining < Decimal(r.quantity_delta):
            all_still_on_hand = False
            break

    # Post journal (source = bill document for provenance).
    from django.contrib.contenttypes.models import ContentType

    bill_ct = ContentType.objects.get_for_model(bill_doc.__class__)
    je = JournalEntry.objects.create(
        business=workspace,
        date=timezone.now().date(),
        description=f"Vendor bill posted – {bill_reference}",
        source_content_type=bill_ct,
        source_object_id=bill_doc.id,
    )
    # Clear GRNI for receipt_value.
    JournalLine.objects.create(journal_entry=je, account=grni, debit=receipt_value, credit=Decimal("0.0000"))

    # Variance handling.
    asset_adjustments: dict[int, Decimal] = {}
    variance_amount = Decimal("0.0000")
    if delta != 0:
        if all_still_on_hand:
            # Revalue inventory by debiting/crediting the asset accounts of the receipt items.
            # v1.1: apply full delta to the involved items proportionally by receipt value.
            total = receipt_value or Decimal("0.0000")
            if total <= 0:
                raise DomainError("Cannot allocate delta without receipt value.")
            for r in receipts:
                if not r.item.asset_account_id:
                    raise DomainError("Receipt item missing asset_account mapping.")
                weight = (_money(Decimal(r.quantity_delta) * Decimal(r.unit_cost)) / total) if total else Decimal("0.0000")
                asset_adjustments[r.item.asset_account_id] = asset_adjustments.get(r.item.asset_account_id, Decimal("0.0000")) + _money(delta * weight)
        else:
            variance_amount = delta

    # Apply debits/credits for delta.
    if all_still_on_hand and asset_adjustments:
        for account_id, amount in asset_adjustments.items():
            if amount == 0:
                continue
            if amount > 0:
                JournalLine.objects.create(journal_entry=je, account_id=account_id, debit=amount, credit=Decimal("0.0000"))
            else:
                JournalLine.objects.create(journal_entry=je, account_id=account_id, debit=Decimal("0.0000"), credit=-amount)
    elif variance_amount != 0:
        if variance_amount > 0:
            JournalLine.objects.create(journal_entry=je, account=variance, debit=variance_amount, credit=Decimal("0.0000"))
        else:
            JournalLine.objects.create(journal_entry=je, account=variance, debit=Decimal("0.0000"), credit=-variance_amount)

    # Credit AP for bill_total.
    JournalLine.objects.create(journal_entry=je, account=ap, debit=Decimal("0.0000"), credit=bill_total)
    je.check_balance()

    # Emit a non-quantity posting event for provenance/correlation.
    # This does not affect on-hand/committed/on-order balances.
    # We use the first receipt's item/location for anchoring (future: multi-item bill events).
    anchor = receipts[0]
    append_event_and_update_balance(
        workspace=workspace,
        item=anchor.item,
        location=anchor.location,
        event_type=InventoryEvent.EventType.VENDOR_BILL_POSTED,
        quantity_delta=Decimal("0.0000"),
        unit_cost=None,
        source_reference=bill_reference,
        purchase_document=bill_doc,
        metadata={
            "bill_reference": bill_reference,
            "bill_total": str(bill_total),
            "receipt_value": str(receipt_value),
            "delta": str(delta),
            "all_still_on_hand": all_still_on_hand,
            "receipt_event_ids": [int(r.id) for r in receipts],
        },
        actor_type=actor_type,
        actor_id=actor_id,
        created_by=created_by,
    )

    return bill_doc, je
