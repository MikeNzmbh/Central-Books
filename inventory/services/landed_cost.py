from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from core.models import JournalEntry, JournalLine
from inventory.accounts import LANDED_COST_CLEARING_CODE, ensure_inventory_accounts, get_account_by_code
from inventory.exceptions import DomainError
from inventory.models import InventoryEvent, LandedCostAllocation, LandedCostBatch
from inventory.services.events import append_event_and_update_balance


MONEY_QUANT = Decimal("0.0000")


def _money(value) -> Decimal:
    return Decimal(str(value or Decimal("0.0000"))).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


@transaction.atomic
def create_landed_cost_batch(
    *,
    workspace,
    description: str,
    allocation_method: str,
    total_extra_cost: Decimal,
    allocations: list[dict],
    credit_account_id: int | None = None,
    created_by=None,
):
    ensure_inventory_accounts(workspace)
    total_extra_cost = _money(total_extra_cost)
    if total_extra_cost <= 0:
        raise DomainError("total_extra_cost must be > 0.")
    if not allocations:
        raise DomainError("allocations are required.")

    batch = LandedCostBatch.objects.create(
        workspace=workspace,
        status=LandedCostBatch.Status.DRAFT,
        description=description or "",
        allocation_method=allocation_method or LandedCostBatch.AllocationMethod.MANUAL,
        total_extra_cost=total_extra_cost,
        credit_account_id=credit_account_id,
        created_by=created_by,
    )

    for line in allocations:
        receipt_event_id = int(line.get("receipt_event_id"))
        allocated_amount = _money(line.get("allocated_amount"))
        if allocated_amount <= 0:
            raise DomainError("allocated_amount must be > 0.")
        receipt = InventoryEvent.objects.select_related("item", "location").filter(
            workspace=workspace, id=receipt_event_id, event_type=InventoryEvent.EventType.STOCK_RECEIVED
        ).first()
        if not receipt:
            raise DomainError("Receipt event not found.")
        LandedCostAllocation.objects.create(
            batch=batch,
            receipt_event=receipt,
            allocated_amount=allocated_amount,
            metadata=dict(line.get("metadata") or {}),
        )

    return batch


@transaction.atomic
def apply_landed_cost(
    *,
    workspace,
    batch_id: int,
    actor_type: str = "",
    actor_id: str = "",
    created_by=None,
):
    batch = (
        LandedCostBatch.objects.select_for_update()
        .select_related("credit_account")
        .filter(id=batch_id, workspace=workspace)
        .first()
    )
    if not batch:
        raise DomainError("Batch not found.")
    if batch.status != LandedCostBatch.Status.DRAFT:
        raise DomainError("Only draft batches can be applied.")

    allocations = list(
        LandedCostAllocation.objects.select_related("receipt_event", "receipt_event__item", "receipt_event__location")
        .filter(batch=batch)
        .order_by("id")
    )
    if not allocations:
        raise DomainError("Batch has no allocations.")

    total_alloc = _money(sum((_money(a.allocated_amount) for a in allocations), Decimal("0.0000")))
    if total_alloc != _money(batch.total_extra_cost):
        raise DomainError("Sum of allocations must equal total_extra_cost.")

    ensure_inventory_accounts(workspace)
    credit_account = batch.credit_account or get_account_by_code(workspace=workspace, code=LANDED_COST_CLEARING_CODE)

    # Post GL entry: debit inventory asset(s) per allocation, credit clearing for total.
    ct = ContentType.objects.get_for_model(batch.__class__)
    je = JournalEntry.objects.create(
        business=workspace,
        date=timezone.now().date(),
        description=f"Landed cost applied – batch {batch.id}",
        source_content_type=ct,
        source_object_id=batch.id,
    )

    debit_by_account: dict[int, Decimal] = {}
    for alloc in allocations:
        receipt = alloc.receipt_event
        item = receipt.item
        if not item.asset_account_id:
            raise DomainError("Receipt item missing asset_account mapping.")
        debit_by_account[item.asset_account_id] = debit_by_account.get(item.asset_account_id, Decimal("0.0000")) + _money(alloc.allocated_amount)

    for account_id, amount in debit_by_account.items():
        if amount <= 0:
            continue
        JournalLine.objects.create(journal_entry=je, account_id=account_id, debit=amount, credit=Decimal("0.0000"))
    JournalLine.objects.create(journal_entry=je, account=credit_account, debit=Decimal("0.0000"), credit=total_alloc)
    je.check_balance()

    # Emit valuation-only inventory events (no quantity delta).
    for alloc in allocations:
        receipt = alloc.receipt_event
        append_event_and_update_balance(
            workspace=workspace,
            item=receipt.item,
            location=receipt.location,
            event_type=InventoryEvent.EventType.STOCK_LANDED_COST_ALLOCATED,
            quantity_delta=Decimal("0.0000"),
            unit_cost=None,
            source_reference=f"landed_cost_batch:{batch.id}",
            metadata={
                "landed_cost_batch_id": int(batch.id),
                "allocation_id": int(alloc.id),
                "receipt_event_id": int(receipt.id),
                "allocated_amount": str(_money(alloc.allocated_amount)),
            },
            actor_type=actor_type,
            actor_id=actor_id,
            created_by=created_by,
        )

    LandedCostBatch.objects.filter(id=batch.id).update(status=LandedCostBatch.Status.APPLIED, updated_at=timezone.now())
    return batch, je

