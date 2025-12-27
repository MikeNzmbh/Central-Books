from core.models import Account

DEFAULT_ACCOUNTS = [
    ("1010", "Cash at Bank", Account.AccountType.ASSET),
    ("1200", "Accounts Receivable", Account.AccountType.ASSET),
    ("1300", "Tax Recoverable", Account.AccountType.ASSET),
    ("1400", "Recoverable Tax Asset (ITCs)", Account.AccountType.ASSET),
    ("1500", "Inventory Asset", Account.AccountType.ASSET),
    ("1510", "Stock In Transit", Account.AccountType.ASSET),
    ("2000", "Accounts Payable", Account.AccountType.LIABILITY),
    ("2060", "Freight & Duties Clearing", Account.AccountType.LIABILITY),
    ("2100", "Customer Deposits", Account.AccountType.LIABILITY),
    ("2200", "Sales Tax Payable", Account.AccountType.LIABILITY),
    ("2300", "Sales Tax Payable", Account.AccountType.LIABILITY),
    ("2050", "GRNI / Accrued Purchases", Account.AccountType.LIABILITY),
    ("4010", "Sales", Account.AccountType.INCOME),
    ("4020", "Sales Returns & Allowances", Account.AccountType.INCOME),
    ("5010", "Operating Expenses", Account.AccountType.EXPENSE),
    ("5020", "Cost of Goods Sold", Account.AccountType.EXPENSE),
    ("5030", "Inventory Shrinkage / Adjustment", Account.AccountType.EXPENSE),
    ("5040", "Inventory Variance", Account.AccountType.EXPENSE),
]


def ensure_default_accounts(business):
    """Ensure baseline accounts exist for the given business and return a mapping."""
    accounts = {}
    for code, name, type_ in DEFAULT_ACCOUNTS:
        acc, _ = Account.objects.get_or_create(
            business=business,
            code=code,
            defaults={
                "name": name,
                "type": type_,
            },
        )
        accounts[(code, type_)] = acc
    return {
        "cash": accounts.get(("1010", Account.AccountType.ASSET)),
        "ar": accounts.get(("1200", Account.AccountType.ASSET)),
        "tax_recoverable": accounts.get(("1400", Account.AccountType.ASSET))
        or accounts.get(("1300", Account.AccountType.ASSET)),
        "inventory_asset": accounts.get(("1500", Account.AccountType.ASSET)),
        "stock_in_transit": accounts.get(("1510", Account.AccountType.ASSET)),
        "ap": accounts.get(("2000", Account.AccountType.LIABILITY)),
        "landed_cost_clearing": accounts.get(("2060", Account.AccountType.LIABILITY)),
        "grni": accounts.get(("2050", Account.AccountType.LIABILITY)),
        "customer_deposits": accounts.get(("2100", Account.AccountType.LIABILITY)),
        "tax": accounts.get(("2300", Account.AccountType.LIABILITY))
        or accounts.get(("2200", Account.AccountType.LIABILITY)),
        "sales": accounts.get(("4010", Account.AccountType.INCOME)),
        "sales_returns": accounts.get(("4020", Account.AccountType.INCOME))
        or accounts.get(("4010", Account.AccountType.INCOME)),
        "opex": accounts.get(("5010", Account.AccountType.EXPENSE)),
        "cogs": accounts.get(("5020", Account.AccountType.EXPENSE)),
        "inventory_shrinkage": accounts.get(("5030", Account.AccountType.EXPENSE)),
        "inventory_variance": accounts.get(("5040", Account.AccountType.EXPENSE)),
    }
