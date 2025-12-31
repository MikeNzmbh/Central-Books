"""
Bank Reconciliation Service

Handles confirming matches and creating split/categorized journal entries
for bank transactions during reconciliation.
"""

from decimal import Decimal
from typing import Optional

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import (
    BankTransaction,
    BankReconciliationMatch,
    JournalEntry,
    JournalLine,
    Account,
    ReconciliationSession,
)
from core.accounting_defaults import ensure_default_accounts
from core.reconciliation import _resolve_pl_account

User = get_user_model()


RECONCILED_STATUSES = {
    BankTransaction.TransactionStatus.MATCHED_SINGLE,
    BankTransaction.TransactionStatus.MATCHED_MULTI,
    BankTransaction.TransactionStatus.MATCHED,
    BankTransaction.TransactionStatus.PARTIAL,
    BankTransaction.TransactionStatus.EXCLUDED,
    BankTransaction.TransactionStatus.RECONCILED,
}


def set_reconciled_state(
    bank_transaction: BankTransaction,
    *,
    reconciled: bool,
    session: ReconciliationSession | None,
    status: str | None = None,
    reconciled_at=None,
) -> BankTransaction:
    """
    Canonical helper to keep reconciliation flags in sync.

    Rules:
    - A transaction is reconciled only when it belongs to a session AND its status
      is one of the reconciled statuses.
    - Switching a transaction between sessions without clearing first is forbidden.
    """
    if session and bank_transaction.reconciliation_session and bank_transaction.reconciliation_session_id != session.id:
        raise ValidationError("Cannot move a reconciled transaction to a different session without unmatching it first.")

    if reconciled:
        if session is None:
            raise ValidationError("Reconciled transactions must belong to a reconciliation session.")
        final_status = status or bank_transaction.status or BankTransaction.TransactionStatus.MATCHED_SINGLE
        if final_status not in RECONCILED_STATUSES:
            raise ValidationError("Reconciled transactions must use a reconciled status.")
        bank_transaction.reconciliation_session = session
        bank_transaction.status = final_status
        bank_transaction.is_reconciled = True
        bank_transaction.reconciliation_status = BankTransaction.RECO_STATUS_RECONCILED
        bank_transaction.reconciled_at = reconciled_at or timezone.now()
    else:
        # Allow attaching an unreconciled transaction to a session, but block moving it across sessions.
        if session is None:
            bank_transaction.reconciliation_session = None
        else:
            bank_transaction.reconciliation_session = session
        bank_transaction.status = status or BankTransaction.TransactionStatus.NEW
        bank_transaction.is_reconciled = False
        bank_transaction.reconciliation_status = BankTransaction.RECO_STATUS_UNRECONCILED
        bank_transaction.reconciled_at = None

    bank_transaction.save(
        update_fields=[
            "status",
            "is_reconciled",
            "reconciliation_status",
            "reconciled_at",
            "reconciliation_session",
        ]
    )
    return bank_transaction


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
        session: ReconciliationSession | None = None,
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

        bank_transaction.allocated_amount = bank_transaction.amount
        bank_transaction.posted_journal_entry = journal_entry
        bank_transaction.save(update_fields=["allocated_amount", "posted_journal_entry"])
        effective_session = session or bank_transaction.reconciliation_session
        if effective_session is None:
            raise ValidationError("A reconciliation session is required to confirm a match.")
        set_reconciled_state(
            bank_transaction,
            reconciled=True,
            session=effective_session,
            status=BankTransaction.TransactionStatus.MATCHED_SINGLE,
        )

        return match

    @staticmethod
    @transaction.atomic
    def create_adjustment_entry(
        business,
        adjustment_amount: Decimal,
        adjustment_account: Account,
        bank_account: "BankAccount",
        description: str = "Adjustment for bank reconciliation",
        date=None,
    ) -> JournalEntry:
        """
        Create a journal entry to resolve a difference between bank amount and matched GL amount.
        
        Use for:
        - Bank fees ($985 deposit matched to $1000 invoice, $15 fee)
        - FX gains/losses
        - Rounding differences
        
        Args:
            business: The business context
            adjustment_amount: Signed amount (negative = expense, positive = income)
            adjustment_account: Account to book the adjustment (e.g., Bank Charges)
            bank_account: The bank account for the offsetting entry
            description: Journal entry description
            date: Transaction date (defaults to today)
        
        Returns:
            Created JournalEntry for the adjustment
        """
        from django.utils import timezone
        
        adj_date = date or timezone.now().date()
        
        je = JournalEntry.objects.create(
            business=business,
            date=adj_date,
            description=description,
        )
        
        abs_amount = abs(adjustment_amount)
        
        if adjustment_amount < 0:
            # Expense (e.g., bank fee): DR Expense, CR Bank
            JournalLine.objects.create(
                journal_entry=je,
                account=adjustment_account,
                debit=abs_amount,
                credit=Decimal("0"),
                description=description,
            )
            if bank_account.account:
                JournalLine.objects.create(
                    journal_entry=je,
                    account=bank_account.account,
                    debit=Decimal("0"),
                    credit=abs_amount,
                    description=description,
                )
        else:
            # Income (e.g., FX gain): DR Bank, CR Income
            if bank_account.account:
                JournalLine.objects.create(
                    journal_entry=je,
                    account=bank_account.account,
                    debit=abs_amount,
                    credit=Decimal("0"),
                    description=description,
                )
            JournalLine.objects.create(
                journal_entry=je,
                account=adjustment_account,
                debit=Decimal("0"),
                credit=abs_amount,
                description=description,
            )
        
        return je

    @staticmethod
    @transaction.atomic
    def confirm_match_with_adjustment(
        bank_transaction: BankTransaction,
        journal_entry: JournalEntry,
        match_confidence: Decimal,
        adjustment_amount: Decimal,
        adjustment_account_id: int,
        user: Optional[User] = None,
        session: ReconciliationSession | None = None,
        adjustment_description: str = "Bank fee / adjustment",
    ) -> tuple[BankReconciliationMatch, JournalEntry | None]:
        """
        Confirm a match with an inline difference resolution.
        
        QBO "Resolve Difference" pattern: When bank amount differs from GL amount,
        automatically create an adjustment entry for the difference.
        
        Args:
            bank_transaction: The bank transaction to reconcile
            journal_entry: The journal entry to match it to
            match_confidence: Confidence score
            adjustment_amount: The difference to book (negative = expense)
            adjustment_account_id: Account ID for the adjustment (e.g., Bank Charges)
            user: User performing the action
            session: Reconciliation session
            adjustment_description: Description for adjustment JE
        
        Returns:
            Tuple of (match, adjustment_entry or None)
        """
        adjustment_entry = None
        
        if adjustment_amount != Decimal("0"):
            adjustment_account = Account.objects.get(id=adjustment_account_id)
            if adjustment_account.business_id != bank_transaction.bank_account.business_id:
                raise ValidationError("Adjustment account must belong to the same business.")
            
            adjustment_entry = BankReconciliationService.create_adjustment_entry(
                business=bank_transaction.bank_account.business,
                adjustment_amount=adjustment_amount,
                adjustment_account=adjustment_account,
                bank_account=bank_transaction.bank_account,
                description=adjustment_description,
                date=bank_transaction.date,
            )
        
        match = BankReconciliationService.confirm_match(
            bank_transaction=bank_transaction,
            journal_entry=journal_entry,
            match_confidence=match_confidence,
            user=user,
            adjustment_entry=adjustment_entry,
            session=session,
        )
        
        return (match, adjustment_entry)

    @staticmethod
    @transaction.atomic
    def create_split_entry(
        bank_transaction: BankTransaction,
        splits: list[dict],
        user: Optional[User] = None,
        description: Optional[str] = None,
        session: ReconciliationSession | None = None,
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
        defaults = ensure_default_accounts(bank_transaction.bank_account.business)

        # Create journal entry
        journal_entry = JournalEntry.objects.create(
            business=bank_transaction.bank_account.business,
            date=bank_transaction.date,
            description=description or f"Bank reconciliation: {bank_transaction.description}",
        )

        # Create journal lines for each split
        for split in splits:
            account = Account.objects.get(id=split["account_id"])
            if account.business_id != bank_transaction.bank_account.business_id:
                raise ValidationError("Account does not belong to this business.")
            split_amount = Decimal(str(split["amount"]))
            split_desc = split.get("description", bank_transaction.description)

            if is_deposit:
                account = _resolve_pl_account(
                    business=bank_transaction.bank_account.business,
                    provided=account,
                    desired_type=Account.AccountType.INCOME,
                    defaults=defaults,
                    default_key="sales",
                    error_message="Select an income account to record this deposit as revenue.",
                )
            else:
                account = _resolve_pl_account(
                    business=bank_transaction.bank_account.business,
                    provided=account,
                    desired_type=Account.AccountType.EXPENSE,
                    defaults=defaults,
                    default_key="opex",
                    error_message="Select an expense account to record this withdrawal as an expense.",
                )

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
        bank_transaction.allocated_amount = bank_transaction.amount
        bank_transaction.posted_journal_entry = journal_entry
        bank_transaction.save(update_fields=["allocated_amount", "posted_journal_entry"])

        reconciled_status = (
            BankTransaction.TransactionStatus.MATCHED_MULTI
            if len(splits) > 1
            else BankTransaction.TransactionStatus.MATCHED_SINGLE
        )
        set_reconciled_state(
            bank_transaction,
            reconciled=bool(session),
            session=session,
            status=reconciled_status,
        )

        return (journal_entry, match)

    @staticmethod
    @transaction.atomic
    def unmatch(match: BankReconciliationMatch, user: Optional[User] = None, session: ReconciliationSession | None = None) -> None:
        """
        Remove a reconciliation match and reset the bank transaction to unmatched state.

        Args:
            match: The reconciliation match to remove
            user: User performing the unmatch (for audit)
        """
        bank_tx = match.bank_transaction

        # Reset bank transaction
        bank_tx.allocated_amount = Decimal("0")
        bank_tx.posted_journal_entry = None
        bank_tx.save(update_fields=["allocated_amount", "posted_journal_entry"])
        set_reconciled_state(
            bank_tx,
            reconciled=False,
            session=session if session else None,
            status=BankTransaction.TransactionStatus.NEW,
        )

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
