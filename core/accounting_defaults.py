from core.models import Account

DEFAULT_ACCOUNTS = [
    ("1010", "Cash at Bank", Account.AccountType.ASSET),
    ("1200", "Accounts Receivable", Account.AccountType.ASSET),
    ("1300", "Tax Recoverable", Account.AccountType.ASSET),
    ("2000", "Accounts Payable", Account.AccountType.LIABILITY),
    ("2200", "Sales Tax Payable", Account.AccountType.LIABILITY),
    ("4010", "Sales", Account.AccountType.INCOME),
    ("5010", "Operating Expenses", Account.AccountType.EXPENSE),
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
        "tax_recoverable": accounts.get(("1300", Account.AccountType.ASSET)),
        "ap": accounts.get(("2000", Account.AccountType.LIABILITY)),
        "tax": accounts.get(("2200", Account.AccountType.LIABILITY)),
        "sales": accounts.get(("4010", Account.AccountType.INCOME)),
        "opex": accounts.get(("5010", Account.AccountType.EXPENSE)),
    }
