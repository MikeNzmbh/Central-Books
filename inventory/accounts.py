from __future__ import annotations

from core.accounting_defaults import ensure_default_accounts
from core.models import Account


INVENTORY_ASSET_CODE = "1500"
STOCK_IN_TRANSIT_CODE = "1510"
GRNI_CODE = "2050"
COGS_CODE = "5020"
INVENTORY_SHRINKAGE_CODE = "5030"
INVENTORY_VARIANCE_CODE = "5040"
LANDED_COST_CLEARING_CODE = "2060"


INVENTORY_DEFAULT_ACCOUNTS: list[tuple[str, str, str]] = [
    (INVENTORY_ASSET_CODE, "Inventory Asset", Account.AccountType.ASSET),
    (STOCK_IN_TRANSIT_CODE, "Stock In Transit", Account.AccountType.ASSET),
    (GRNI_CODE, "GRNI / Accrued Purchases", Account.AccountType.LIABILITY),
    (COGS_CODE, "Cost of Goods Sold", Account.AccountType.EXPENSE),
    (INVENTORY_SHRINKAGE_CODE, "Inventory Shrinkage / Adjustment", Account.AccountType.EXPENSE),
    (INVENTORY_VARIANCE_CODE, "Inventory Variance", Account.AccountType.EXPENSE),
    (LANDED_COST_CLEARING_CODE, "Freight & Duties Clearing", Account.AccountType.LIABILITY),
]


def ensure_inventory_accounts(workspace):
    """
    Ensure required inventory system accounts exist for the workspace.
    """
    ensure_default_accounts(workspace)
    accounts: dict[str, Account] = {}
    for code, name, type_ in INVENTORY_DEFAULT_ACCOUNTS:
        acc, _ = Account.objects.get_or_create(
            business=workspace,
            code=code,
            defaults={"name": name, "type": type_},
        )
        accounts[code] = acc
    return accounts


def get_account_by_code(*, workspace, code: str) -> Account:
    ensure_default_accounts(workspace)
    acct = Account.objects.filter(business=workspace, code=code).first()
    if acct:
        return acct
    created = ensure_inventory_accounts(workspace)
    if code in created:
        return created[code]
    return Account.objects.get(business=workspace, code=code)
