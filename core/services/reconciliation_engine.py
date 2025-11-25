from datetime import timedelta
from decimal import Decimal
from typing import Iterable, List

from django.db import transaction
from django.utils import timezone

from core.models import BankAccount, BankTransaction, JournalLine, ReconciliationSession


class ReconciliationEngine:
    DATE_WINDOW_DAYS = 3
    AMOUNT_TOLERANCE = Decimal("0.01")

    def __init__(self, business, bank_account: BankAccount):
        self.business = business
        self.bank_account = bank_account
        self.ledger_account = bank_account.account

    def get_unreconciled_bank_lines(self, start_date=None, end_date=None):
        qs = (
            BankTransaction.objects.filter(
                bank_account=self.bank_account,
                bank_account__business=self.business,
            )
            .exclude(status=BankTransaction.TransactionStatus.EXCLUDED)
            .filter(is_reconciled=False)
            .order_by("date", "id")
        )
        if start_date:
            qs = qs.filter(date__gte=start_date)
        if end_date:
            qs = qs.filter(date__lte=end_date)
        return qs

    def get_candidate_matches(self, bank_line: BankTransaction) -> List[JournalLine]:
        if not self.ledger_account:
            return []

        window_start = bank_line.date - timedelta(days=self.DATE_WINDOW_DAYS)
        window_end = bank_line.date + timedelta(days=self.DATE_WINDOW_DAYS)

        lines = (
            JournalLine.objects.select_related("journal_entry", "account")
            .filter(
                account=self.ledger_account,
                journal_entry__business=self.business,
                journal_entry__is_void=False,
                journal_entry__date__range=(window_start, window_end),
                is_reconciled=False,
            )
            .order_by("journal_entry__date", "id")
        )

        amount_abs = abs(bank_line.amount or Decimal("0.00"))
        bank_sign = 1 if (bank_line.amount or Decimal("0.00")) >= 0 else -1
        matches: List[JournalLine] = []

        for line in lines:
            line_amount = (line.debit or Decimal("0.00")) - (line.credit or Decimal("0.00"))
            line_sign = 1 if line_amount >= 0 else -1
            if line_sign != bank_sign:
                continue
            if abs(abs(line_amount) - amount_abs) <= self.AMOUNT_TOLERANCE:
                matches.append(line)
        return matches

    @transaction.atomic
    def reconcile(
        self,
        bank_line: BankTransaction,
        journal_lines: Iterable[JournalLine],
        session: ReconciliationSession | None = None,
    ):
        ts = timezone.now()
        bank_line.is_reconciled = True
        bank_line.reconciled_at = ts
        bank_line.reconciliation_session = session
        bank_line.status = BankTransaction.TransactionStatus.MATCHED_SINGLE
        bank_line.allocated_amount = abs(bank_line.amount or Decimal("0.00"))
        bank_line.save(
            update_fields=[
                "is_reconciled",
                "reconciled_at",
                "reconciliation_session",
                "status",
                "allocated_amount",
            ]
        )

        for line in journal_lines:
            line.is_reconciled = True
            line.reconciled_at = ts
            line.reconciliation_session = session
            line.save(update_fields=["is_reconciled", "reconciled_at", "reconciliation_session"])
