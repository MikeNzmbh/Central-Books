from datetime import date
from decimal import Decimal

from django.db.models import Sum

from .models import Account, JournalEntry, JournalLine


def get_account_balance(account: Account) -> Decimal:
    """
    Compute the live balance for an account using all journal lines.
    Assets/Expenses return debit - credit; everything else uses credit - debit.
    """
    agg = JournalLine.objects.filter(account=account).aggregate(
        debit_sum=Sum("debit"),
        credit_sum=Sum("credit"),
    )
    debit = agg["debit_sum"] or Decimal("0")
    credit = agg["credit_sum"] or Decimal("0")

    if account.type in (Account.AccountType.ASSET, Account.AccountType.EXPENSE):
        return debit - credit
    return credit - debit


def _normalize_rows(rows):
    account_ids = [row["account_id"] for row in rows]
    accounts = Account.objects.in_bulk(account_ids)
    normalized = []
    for row in rows:
        account = accounts.get(row["account_id"])
        amount = row["total"] or Decimal("0")
        normalized.append(
            {
                "account": account,
                "amount": amount,
                "account__id": row["account_id"],
                "account__code": getattr(account, "code", ""),
                "account__name": getattr(account, "name", ""),
            }
        )
    return normalized


def compute_ledger_pl(business, start_date: date, end_date: date):
    """
    Compute Income, Expenses and Net Profit/Loss from the ledger (JournalLine).
    Used as the primary P&L data source.
    """

    base_qs = JournalLine.objects.filter(
        journal_entry__business=business,
        journal_entry__date__range=(start_date, end_date),
        journal_entry__is_void=False,
        account__type__in=[
            Account.AccountType.INCOME,
            Account.AccountType.EXPENSE,
        ],
    ).select_related("account")

    income_rows = (
        base_qs.filter(account__type=Account.AccountType.INCOME)
        .values("account_id")
        .annotate(total=Sum("credit") - Sum("debit"))
        .order_by("account__code", "account__name")
    )

    expense_rows = (
        base_qs.filter(account__type=Account.AccountType.EXPENSE)
        .values("account_id")
        .annotate(total=Sum("debit") - Sum("credit"))
        .order_by("account__code", "account__name")
    )

    income = _normalize_rows(income_rows)
    expense = _normalize_rows(expense_rows)

    total_income = sum((row["amount"] for row in income), Decimal("0"))
    total_expense = sum((row["amount"] for row in expense), Decimal("0"))
    net = total_income - total_expense

    tax_account = Account.objects.filter(code="2200", business=business).first()
    tax_total = Decimal("0")
    if tax_account:
        tax_total = (
            base_qs.filter(account=tax_account).aggregate(total=Sum("credit") - Sum("debit"))["total"]
            or Decimal("0")
        )

    return {
        "income": income,
        "expense": expense,
        "total_income": total_income,
        "total_expense": total_expense,
        "net": net,
        # Backwards-compatible keys for templates that still expect these.
        "income_accounts": [
            {
                "account__id": row["account__id"],
                "account__code": row["account__code"],
                "account__name": row["account__name"],
                "total": row["amount"],
            }
            for row in income
        ],
        "expense_accounts": [
            {
                "account__id": row["account__id"],
                "account__code": row["account__code"],
                "account__name": row["account__name"],
                "total": row["amount"],
            }
            for row in expense
        ],
        "net_profit": net,
        "total_expenses": total_expense,
        "total_tax": tax_total,
    }


def post_journal_entry_from_proposal(business, proposal: dict, approved_by):
    """
    Create a JournalEntry from a validated proposal payload.
    Proposal format:
    {
        "date": "YYYY-MM-DD" or date,
        "description": str,
        "lines": [
            {"account_id": int, "debit": Decimal/str/float, "credit": Decimal/str/float, "description": str}
        ]
    }
    """
    from datetime import date as date_cls

    if not proposal or "lines" not in proposal:
        raise ValueError("Invalid journal proposal.")

    entry_date_raw = proposal.get("date") or date.today()
    if isinstance(entry_date_raw, str):
        entry_date = date_cls.fromisoformat(entry_date_raw)
    else:
        entry_date = entry_date_raw

    description = proposal.get("description") or "Receipt approval"
    lines_payload = proposal["lines"]
    if not lines_payload:
        raise ValueError("Journal proposal has no lines.")

    account_ids = [line.get("account_id") for line in lines_payload if line.get("account_id")]
    accounts = Account.objects.filter(id__in=account_ids, business=business).in_bulk()

    lines: list[JournalLine] = []
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")

    for line in lines_payload:
        account_id = line.get("account_id")
        account = accounts.get(account_id)
        if not account:
            raise ValueError("Account not found for this business.")
        debit = Decimal(str(line.get("debit", "0") or "0"))
        credit = Decimal(str(line.get("credit", "0") or "0"))
        total_debit += debit
        total_credit += credit
        lines.append(
            JournalLine(
                account=account,
                debit=debit,
                credit=credit,
                description=line.get("description", "") or description,
            )
        )

    if total_debit.quantize(Decimal("0.01")) != total_credit.quantize(Decimal("0.01")):
        raise ValueError("Journal is not balanced.")

    entry_kwargs = {
        "business": business,
        "date": entry_date,
        "description": description,
    }
    if hasattr(JournalEntry, "created_by"):
        entry_kwargs["created_by"] = approved_by  # type: ignore[assignment]
    entry = JournalEntry.objects.create(**entry_kwargs)
    for line in lines:
        line.journal_entry = entry
        line.save()
    return entry
