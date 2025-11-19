from decimal import Decimal

from django.db.models import Sum

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
    base = (
        JournalLine.objects.select_related("account", "journal_entry")
        .filter(
            journal_entry__business=business,
            journal_entry__is_void=False,
        )
    )

    if upto_date:
        base = base.filter(journal_entry__date__lte=upto_date)

    rows = (
        base.values("account_id", "account__code", "account__name", "account__type")
        .annotate(total_debit=Sum("debit"), total_credit=Sum("credit"))
        .order_by("account__type", "account__code")
    )

    accounts = []
    totals_by_type = {}

    for row in rows:
        acc_type = row["account__type"]
        debit = row["total_debit"] or Decimal("0.00")
        credit = row["total_credit"] or Decimal("0.00")

        if acc_type in (Account.AccountType.ASSET, Account.AccountType.EXPENSE):
            balance = debit - credit
        else:
            balance = credit - debit

        accounts.append(
            {
                "id": row["account_id"],
                "code": row["account__code"],
                "name": row["account__name"],
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
