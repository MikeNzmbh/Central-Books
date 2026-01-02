from decimal import Decimal

from django.db.models import Q, Sum, Value
from django.db.models.functions import Coalesce

from .models import Account, JournalLine


def _sum_side(qs, field):
    return qs.aggregate(total=Sum(field))["total"] or Decimal("0.00")


def ledger_pnl_for_period(business, start_date, end_date):
    base = (
        JournalLine.objects.select_related("account", "journal_entry")
        .filter(
            journal_entry__business=business,
            journal_entry__date__range=(start_date, end_date),
            journal_entry__is_void=False,
        )
    )

    income_qs = base.filter(account__type=Account.AccountType.INCOME)
    expense_qs = base.filter(account__type=Account.AccountType.EXPENSE)

    income_debits = _sum_side(income_qs, "debit")
    income_credits = _sum_side(income_qs, "credit")
    total_income = income_credits - income_debits

    expense_debits = _sum_side(expense_qs, "debit")
    expense_credits = _sum_side(expense_qs, "credit")
    total_expenses = expense_debits - expense_credits

    net_profit = total_income - total_expenses

    income_by_account = list(
        income_qs.values("account__code", "account__name")
        .annotate(total=Sum("credit") - Sum("debit"))
        .order_by("account__code")
    )
    expense_by_account = list(
        expense_qs.values("account__code", "account__name")
        .annotate(total=Sum("debit") - Sum("credit"))
        .order_by("account__code")
    )

    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "income_by_account": income_by_account,
        "expense_by_account": expense_by_account,
    }


def account_balances_for_business(business, upto_date=None):
    """
    Return every active account for the business with its running balance, even if
    the account has no journal lines yet (e.g., freshly created cash/bank accounts).
    """
    date_filter = Q()
    if upto_date:
        date_filter = Q(journal_lines__journal_entry__date__lte=upto_date)

    accounts_qs = (
        Account.objects.filter(business=business, is_active=True)
        .annotate(
            total_debit=Coalesce(
                Sum(
                    "journal_lines__debit",
                    filter=Q(journal_lines__journal_entry__is_void=False) & date_filter,
                ),
                Value(Decimal("0.00")),
            ),
            total_credit=Coalesce(
                Sum(
                    "journal_lines__credit",
                    filter=Q(journal_lines__journal_entry__is_void=False) & date_filter,
                ),
                Value(Decimal("0.00")),
            ),
        )
        .order_by("type", "code", "name")
    )

    accounts = []
    totals_by_type = {}

    for acc in accounts_qs:
        acc_type = acc.type
        debit = acc.total_debit or Decimal("0.00")
        credit = acc.total_credit or Decimal("0.00")

        if acc_type in (Account.AccountType.ASSET, Account.AccountType.EXPENSE):
            balance = debit - credit
        else:
            balance = credit - debit

        accounts.append(
            {
                "id": acc.id,
                "code": acc.code,
                "name": acc.name,
                "type": acc_type,
                "balance": balance,
            }
        )

        totals_by_type.setdefault(acc_type, Decimal("0.00"))
        totals_by_type[acc_type] += balance

    return {
        "accounts": accounts,
        "totals_by_type": totals_by_type,
    }
