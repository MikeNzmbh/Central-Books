"""
Bank Reconciliation Service

Handles confirming matches and creating split/categorized journal entries
for bank transactions during reconciliation.
"""

from decimal import Decimal
from typing import Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from core.models import (
    BankTransaction,
    BankReconciliationMatch,
    JournalEntry,
    JournalLine,
    Account,
)

User = get_user_model()


class BankReconciliationService:
    """
    Service for confirming matches and creating split entries.
    """

    @staticmethod
    @transaction.atomic
    def confirm_match(
        bank_transaction: BankTransaction,
        journal_entry: JournalEntry,
        match_confidence: Decimal,
        user: Optional[User] = None,
        adjustment_entry: Optional[JournalEntry] = None,
    ) -> BankReconciliationMatch:
        """
        Confirm a suggested match between a bank transaction and journal entry.

        Args:
            bank_transaction: The bank transaction to reconcile
            journal_entry: The journal entry to match it to
            match_confidence: Confidence score (0.00 to 1.00)
            user: User performing the reconciliation
            adjustment_entry: Optional adjustment entry for fees/FX differences

        Returns:
            Created BankReconciliationMatch instance
        """
        # Create the match
        match = BankReconciliationMatch.objects.create(
            bank_transaction=bank_transaction,
            journal_entry=journal_entry,
            match_type="ONE_TO_ONE",
            match_confidence=match_confidence,
            matched_amount=abs(bank_transaction.amount),
            adjustment_journal_entry=adjustment_entry,
            reconciled_by=user,
        )

        # Update bank transaction status (link-only, no auto creation here)
        bank_transaction.status = BankTransaction.TransactionStatus.MATCHED_SINGLE
        bank_transaction.is_reconciled = True
        bank_transaction.reconciliation_status = BankTransaction.RECO_STATUS_RECONCILED
        bank_transaction.reconciled_at = timezone.now()
        bank_transaction.allocated_amount = bank_transaction.amount
        bank_transaction.posted_journal_entry = journal_entry
        bank_transaction.save(
            update_fields=[
                "status",
                "allocated_amount",
                "posted_journal_entry",
                "is_reconciled",
                "reconciliation_status",
                "reconciled_at",
            ]
        )

        return match

    @staticmethod
    @transaction.atomic
    def create_split_entry(
        bank_transaction: BankTransaction,
        splits: list[dict],
        user: Optional[User] = None,
        description: Optional[str] = None,
    ) -> tuple[JournalEntry, BankReconciliationMatch]:
        """
        Create a new journal entry for a split/categorized transaction.

        Args:
            bank_transaction: The bank transaction to split
            splits: List of dicts with:
                - account_id: int
                - amount: Decimal (absolute value)
                - description: str (optional)
            user: User creating the entry
            description: Overall description (defaults to bank tx description)

        Returns:
            Tuple of (created_journal_entry, created_match)

        Raises:
            ValueError: If splits don't balance to bank transaction amount
        """
        # Validate: splits must balance to bank transaction amount
        split_total = sum(Decimal(str(s["amount"])) for s in splits)
        tx_amount_abs = abs(bank_transaction.amount)

        if abs(split_total - tx_amount_abs) > Decimal("0.01"):
            raise ValueError(
                f"Splits must sum to {tx_amount_abs}, got {split_total}. "
                f"Difference: {abs(split_total - tx_amount_abs)}"
            )

        # Determine if this is a deposit (DR Bank) or withdrawal (CR Bank)
        is_deposit = bank_transaction.amount > 0

        # Create journal entry
        journal_entry = JournalEntry.objects.create(
            business=bank_transaction.bank_account.business,
            date=bank_transaction.date,
            description=description or f"Bank reconciliation: {bank_transaction.description}",
        )

        # Create journal lines for each split
        for split in splits:
            account = Account.objects.get(id=split["account_id"])
            split_amount = Decimal(str(split["amount"]))
            split_desc = split.get("description", bank_transaction.description)

            if is_deposit:
                # Deposit: DR Bank, CR Revenue/Other
                JournalLine.objects.create(
                    journal_entry=journal_entry,
                    account=account,
                    debit=Decimal("0"),
                    credit=split_amount,
                    description=split_desc,
                )
            else:
                # Withdrawal: DR Expense, CR Bank
                JournalLine.objects.create(
                    journal_entry=journal_entry,
                    account=account,
                    debit=split_amount,
                    credit=Decimal("0"),
                    description=split_desc,
                )

        # Add bank account line (offsetting entry)
        if bank_transaction.bank_account.account:
            if is_deposit:
                # DR Bank account
                JournalLine.objects.create(
                    journal_entry=journal_entry,
                    account=bank_transaction.bank_account.account,
                    debit=tx_amount_abs,
                    credit=Decimal("0"),
                    description=bank_transaction.description,
                )
            else:
                # CR Bank account
                JournalLine.objects.create(
                    journal_entry=journal_entry,
                    account=bank_transaction.bank_account.account,
                    debit=Decimal("0"),
                    credit=tx_amount_abs,
                    description=bank_transaction.description,
                )

        # Create reconciliation match
        match = BankReconciliationMatch.objects.create(
            bank_transaction=bank_transaction,
            journal_entry=journal_entry,
            match_type="ONE_TO_MANY" if len(splits) > 1 else "ONE_TO_ONE",
            match_confidence=Decimal("1.00"),  # User confirmed
            matched_amount=tx_amount_abs,
            reconciled_by=user,
        )

        # Update bank transaction
        bank_transaction.status = (
            BankTransaction.TransactionStatus.MATCHED_MULTI
            if len(splits) > 1
            else BankTransaction.TransactionStatus.MATCHED_SINGLE
        )
        bank_transaction.allocated_amount = bank_transaction.amount
        bank_transaction.posted_journal_entry = journal_entry
        bank_transaction.save(update_fields=["status", "allocated_amount", "posted_journal_entry"])

        return (journal_entry, match)

    @staticmethod
    @transaction.atomic
    def unmatch(match: BankReconciliationMatch, user: Optional[User] = None) -> None:
        """
        Remove a reconciliation match and reset the bank transaction to unmatched state.

        Args:
            match: The reconciliation match to remove
            user: User performing the unmatch (for audit)
        """
        bank_tx = match.bank_transaction

        # Reset bank transaction
        bank_tx.status = BankTransaction.TransactionStatus.NEW
        bank_tx.allocated_amount = Decimal("0")
        bank_tx.posted_journal_entry = None
        bank_tx.save(update_fields=["status", "allocated_amount", "posted_journal_entry"])

        # Delete the match
        match.delete()

    @staticmethod
    def get_reconciliation_progress(bank_account) -> dict:
        """
        Get reconciliation progress statistics for a bank account.

        Returns:
            Dict with:
                - total_transactions: int
                - reconciled: int
                - unreconciled: int
                - total_reconciled_amount: Decimal
                - total_unreconciled_amount: Decimal
        """
        transactions = BankTransaction.objects.filter(bank_account=bank_account)

        total = transactions.count()
        reconciled = transactions.exclude(status=BankTransaction.TransactionStatus.NEW).count()
        unreconciled = total - reconciled

        reconciled_amount = sum(
            tx.amount
            for tx in transactions.exclude(status=BankTransaction.TransactionStatus.NEW)
        )
        unreconciled_amount = sum(
            tx.amount for tx in transactions.filter(status=BankTransaction.TransactionStatus.NEW)
        )

        return {
            "total_transactions": total,
            "reconciled": reconciled,
            "unreconciled": unreconciled,
            "total_reconciled_amount": Decimal(str(reconciled_amount)),
            "total_unreconciled_amount": Decimal(str(unreconciled_amount)),
            "progress_percent": round((reconciled / total * 100) if total > 0 else 0, 1),
        }
