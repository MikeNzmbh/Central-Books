from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from core.models import JournalEntry, JournalLine
from inventory.accounts import GRNI_CODE, INVENTORY_VARIANCE_CODE, ensure_inventory_accounts, get_account_by_code
from inventory.exceptions import DomainError


MONEY_QUANT = Decimal("0.0000")


@transaction.atomic
def voucher_vendor_bill_against_grni(
    *,
    workspace,
    bill_reference: str,
    amount: Decimal,
    ap_account_code: str = "2000",
    variance_amount: Decimal | None = None,
    actor_type: str = "",
    actor_id: str = "",
    created_by=None,
):
    """
    Phase 1 stub: Voucher a vendor bill matched to receipts.

    GL:
    - Debit GRNI
    - Credit Accounts Payable
    - Optional variance posted to Inventory Variance (future: allocate properly)
    """
    amount = Decimal(str(amount)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    if amount <= 0:
        raise DomainError("amount must be > 0.")

    ensure_inventory_accounts(workspace)
    grni = get_account_by_code(workspace=workspace, code=GRNI_CODE)
    ap = get_account_by_code(workspace=workspace, code=ap_account_code)

    je = JournalEntry.objects.create(
        business=workspace,
        date=timezone.now().date(),
        description=f"Vendor bill vouchered – {bill_reference}",
    )
    JournalLine.objects.create(journal_entry=je, account=grni, debit=amount, credit=Decimal("0.0000"))
    JournalLine.objects.create(journal_entry=je, account=ap, debit=Decimal("0.0000"), credit=amount)

    if variance_amount is not None and Decimal(str(variance_amount)) != 0:
        variance = Decimal(str(variance_amount)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        variance_account = get_account_by_code(workspace=workspace, code=INVENTORY_VARIANCE_CODE)
        if variance > 0:
            JournalLine.objects.create(journal_entry=je, account=variance_account, debit=variance, credit=Decimal("0.0000"))
            JournalLine.objects.create(journal_entry=je, account=ap, debit=Decimal("0.0000"), credit=variance)
        else:
            variance = -variance
            JournalLine.objects.create(journal_entry=je, account=ap, debit=variance, credit=Decimal("0.0000"))
            JournalLine.objects.create(journal_entry=je, account=variance_account, debit=Decimal("0.0000"), credit=variance)

    je.check_balance()
    return je
