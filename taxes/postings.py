from collections import defaultdict
from decimal import Decimal
from typing import Iterable, Tuple

from core.models import JournalEntry, JournalLine, Account
from .models import TransactionLineTaxDetail


def add_sales_tax_lines(
    entry: JournalEntry,
    tax_details: Iterable[TransactionLineTaxDetail],
) -> Tuple[Decimal, Decimal]:
    """
    Create JournalLines on a sales/invoice JournalEntry:
    - Credit liability accounts (typically 2300) per component.default_coa_account.
    Returns (total_tax_home_currency, total_tax_txn_currency).
    """
    totals_by_account: dict[int, Decimal] = defaultdict(Decimal)
    total_txn_currency = Decimal("0.00")
    for detail in tax_details:
        account = detail.tax_component.default_coa_account
        if detail.tax_component.is_recoverable:
            # On sales/output, credit liability even if component is recoverable on purchases.
            account = (
                Account.objects.filter(business=detail.business, code="2300").first()
                or account
            )
        if account is None:
            continue
        totals_by_account[account.id] += detail.tax_amount_home_currency_cad
        total_txn_currency += detail.tax_amount_txn_currency

    for account_id, amount_home in totals_by_account.items():
        JournalLine.objects.create(
            journal_entry=entry,
            account_id=account_id,
            debit=Decimal("0.00"),
            credit=amount_home,
            description="Sales tax payable",
        )

    return sum(totals_by_account.values(), Decimal("0.00")), total_txn_currency


def add_expense_tax_lines(
    entry: JournalEntry,
    tax_details: Iterable[TransactionLineTaxDetail],
) -> Decimal:
    """
    Create JournalLines for recoverable tax on expenses:
    - Debit recoverable tax (typically 1400) for recoverable components.
    Returns the non-recoverable tax total (home currency) to roll into expense lines.
    """
    recoverable_totals: dict[int, Decimal] = defaultdict(Decimal)
    non_recoverable_total_home = Decimal("0.00")

    for detail in tax_details:
        account = detail.tax_component.default_coa_account
        if detail.is_recoverable and account:
            recoverable_totals[account.id] += detail.tax_amount_home_currency_cad
        else:
            non_recoverable_total_home += detail.tax_amount_home_currency_cad

    for account_id, amount_home in recoverable_totals.items():
        JournalLine.objects.create(
            journal_entry=entry,
            account_id=account_id,
            debit=amount_home,
            credit=Decimal("0.00"),
            description="Recoverable tax",
        )

    return non_recoverable_total_home
