from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Sequence

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.db.models import Sum

from .accounting_defaults import ensure_default_accounts
from .tax_utils import compute_tax_breakdown
from .models import (
    Account,
    BankReconciliationMatch,
    BankTransaction,
    Expense,
    Invoice,
    JournalEntry,
    JournalLine,
    TaxRate,
)

AllocationKind = Literal[
    "INVOICE",
    "BILL",
    "DIRECT_INCOME",
    "DIRECT_EXPENSE",
    "CREDIT_NOTE",
]


@dataclass
class Allocation:
    kind: AllocationKind
    amount: Decimal
    id: int | None = None
    account_id: int | None = None
    tax_treatment: str | None = None
    tax_rate_id: int | None = None


def recompute_bank_transaction_status(bank_tx: BankTransaction) -> BankTransaction:
    """
    Recalculate the status + allocated_amount for a bank transaction based on its matches.

    Excluded transactions retain their status but still store the allocated amount for auditing.
    """

    totals = bank_tx.matches.aggregate(total=Sum("matched_amount"))
    allocated = totals.get("total") or Decimal("0.00")
    abs_amount = abs(bank_tx.amount or Decimal("0.00"))

    if bank_tx.status == BankTransaction.TransactionStatus.EXCLUDED:
        if bank_tx.allocated_amount != allocated:
            bank_tx.allocated_amount = allocated
            bank_tx.save(update_fields=["allocated_amount"])
        return bank_tx

    if allocated == 0:
        status = BankTransaction.TransactionStatus.NEW
    elif abs_amount == 0:
        status = BankTransaction.TransactionStatus.MATCHED_SINGLE
    elif allocated < abs_amount:
        status = BankTransaction.TransactionStatus.PARTIAL
    elif allocated == abs_amount:
        match_count = bank_tx.matches.count()
        status = (
            BankTransaction.TransactionStatus.MATCHED_SINGLE
            if match_count <= 1
            else BankTransaction.TransactionStatus.MATCHED_MULTI
        )
    else:
        raise ValueError(
            f"Allocated amount {allocated} exceeds bank amount {abs_amount} for tx {bank_tx.pk}"
        )

    needs_update = (
        bank_tx.status != status or bank_tx.allocated_amount != allocated
    )
    if needs_update:
        bank_tx.status = status
        bank_tx.allocated_amount = allocated
        bank_tx.save(update_fields=["status", "allocated_amount"])
    return bank_tx


def add_bank_match(
    bank_tx: BankTransaction,
    journal_entry: JournalEntry,
    *,
    amount: Decimal | None = None,
) -> BankReconciliationMatch:
    """
    Create a reconciliation match and recompute the transaction status.
    """

    if amount is None:
        amount = abs(bank_tx.amount or Decimal("0.00"))
    if amount <= 0:
        raise ValueError("matched amount must be positive")

    match = BankReconciliationMatch.objects.create(
        bank_transaction=bank_tx,
        journal_entry=journal_entry,
        matched_amount=amount,
    )
    recompute_bank_transaction_status(bank_tx)
    return match


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _require_account(business, account_id: int | None) -> Account:
    if not account_id:
        raise ValidationError("An account_id is required for this allocation.")
    try:
        return Account.objects.get(business=business, pk=account_id)
    except Account.DoesNotExist as exc:  # pragma: no cover - defensive
        raise ValidationError("Account does not belong to this business.") from exc


@db_transaction.atomic
def allocate_bank_transaction(
    *,
    bank_tx: BankTransaction,
    allocations: Sequence[Allocation],
    fees: Allocation | None = None,
    rounding: Allocation | None = None,
    overpayment: Allocation | None = None,
    user: User | None,
    tolerance_cents: int = 2,
    operation_id: str | None = None,
) -> JournalEntry:
    if not allocations:
        raise ValidationError("Provide at least one allocation.")

    business = bank_tx.bank_account.business
    abs_amount = abs(bank_tx.amount or Decimal("0.00"))
    if abs_amount == 0:
        raise ValidationError("Cannot allocate a zero-amount transaction.")

    tolerance = Decimal(tolerance_cents or 0) / Decimal("100")
    existing_entry = None
    if operation_id:
        existing_entry = (
            JournalEntry.objects.filter(
                business=business,
                allocation_operation_id=operation_id,
            )
            .first()
        )
        if existing_entry:
            if existing_entry.bank_matches.filter(bank_transaction=bank_tx).exists():
                return existing_entry
            raise ValidationError("Operation ID already used for another transaction.")

    bank_portion = abs_amount - (bank_tx.allocated_amount or Decimal("0.00"))
    if bank_portion <= 0:
        raise ValidationError("This bank transaction has no remaining amount to allocate.")

    if bank_tx.status == BankTransaction.TransactionStatus.EXCLUDED:
        raise ValidationError("Excluded transactions cannot be allocated.")

    if bank_tx.matches.exists():
        raise ValidationError("This bank transaction already has allocations.")

    is_deposit = bank_tx.amount >= 0
    defaults = ensure_default_accounts(business)
    bank_account = bank_tx.bank_account.account or defaults.get("cash")
    if bank_account is None:
        raise ValidationError("Set a ledger account for this bank before reconciling.")
    sales_tax_account = defaults.get("tax")
    recoverable_tax_account = defaults.get("tax_recoverable") or sales_tax_account

    ar_account = defaults.get("ar")
    ap_account = defaults.get("ap")
    if ar_account is None or ap_account is None:
        raise ValidationError("Default AR/AP accounts are required for reconciliation.")

    allocation_sum = Decimal("0.00")
    invoice_allocations: list[tuple[Invoice, Decimal]] = []
    bill_allocations: list[tuple[Expense, Decimal]] = []
    credit_lines: list[tuple[Account, Decimal]] = []
    debit_lines: list[tuple[Account, Decimal]] = []
    tax_lines: list[tuple[Account, Decimal, Decimal]] = []
    direct_income_allocations: list[tuple[Account, Decimal]] = []
    direct_expense_allocations: list[tuple[Account, Decimal]] = []
    credit_note_allocations: list[tuple[Account, Decimal]] = []
    match_targets: list[tuple[str, object | None, Decimal]] = []

    for alloc in allocations:
        amount = _to_decimal(alloc.amount)
        if amount <= 0:
            raise ValidationError("Allocation amounts must be positive.")
        if alloc.kind == "INVOICE":
            if not is_deposit:
                raise ValidationError("Invoice allocations require a deposit transaction.")
            if not alloc.id:
                raise ValidationError("Invoice allocations require an id.")
            invoice = (
                Invoice.objects.select_for_update()
                .filter(business=business, pk=alloc.id)
                .first()
            )
            if not invoice:
                raise ValidationError("Invoice not found for this business.")
            remaining = (invoice.grand_total or (invoice.net_total + invoice.tax_total)) - (invoice.amount_paid or Decimal("0"))
            if amount - remaining > tolerance:
                raise ValidationError("Allocation exceeds the invoice balance.")
            invoice_allocations.append((invoice, amount))
            allocation_sum += amount
        elif alloc.kind == "BILL":
            if is_deposit:
                raise ValidationError("Bill allocations require a withdrawal transaction.")
            if not alloc.id:
                raise ValidationError("Bill allocations require an id.")
            expense = (
                Expense.objects.select_for_update()
                .filter(business=business, pk=alloc.id)
                .first()
            )
            if not expense:
                raise ValidationError("Bill not found for this business.")
            remaining = (expense.amount or Decimal("0")) - (expense.amount_paid or Decimal("0"))
            if amount - remaining > tolerance:
                raise ValidationError("Allocation exceeds the bill balance.")
            bill_allocations.append((expense, amount))
            allocation_sum += amount
        elif alloc.kind == "DIRECT_INCOME":
            if not is_deposit:
                raise ValidationError("Direct income requires a deposit transaction.")
            account = _require_account(business, alloc.account_id)
            credit_lines.append((account, amount))
            direct_income_allocations.append((account, amount))
            match_targets.append(("direct_income", None, amount))
            allocation_sum += amount
        elif alloc.kind == "DIRECT_EXPENSE":
            if is_deposit:
                raise ValidationError("Direct expense allocations require a withdrawal.")
            account = _require_account(business, alloc.account_id)
            debit_lines.append((account, amount))
            direct_expense_allocations.append((account, amount))
            match_targets.append(("direct_expense", None, amount))
            allocation_sum += amount
        elif alloc.kind == "CREDIT_NOTE":
            if not is_deposit:
                raise ValidationError("Credit note allocations require a deposit transaction.")
            account = _require_account(business, alloc.account_id)
            credit_lines.append((account, amount))
            credit_note_allocations.append((account, amount))
            match_targets.append(("credit_note", None, amount))
            allocation_sum += amount
        else:  # pragma: no cover - safeguard
            raise ValidationError(f"Unsupported allocation kind: {alloc.kind}")

        # Apply tax after the base validation so both income/expense share logic.
        if alloc.kind in ("DIRECT_INCOME", "DIRECT_EXPENSE") and (alloc.tax_treatment or alloc.tax_rate_id):
            treatment = (alloc.tax_treatment or "NONE").upper()
            if treatment not in ("NONE", "INCLUDED", "ON_TOP"):
                raise ValidationError("Invalid tax treatment.")
            if treatment != "NONE":
                if not alloc.tax_rate_id:
                    raise ValidationError("Tax rate is required when tax is enabled.")
                tax_rate = (
                    TaxRate.objects.filter(
                        business=business, pk=alloc.tax_rate_id, is_active=True
                    )
                    .only("percentage", "applies_to_sales", "applies_to_purchases")
                    .first()
                )
                if not tax_rate:
                    raise ValidationError("Tax rate not found for this business.")
                if alloc.kind == "DIRECT_INCOME" and not tax_rate.applies_to_sales:
                    raise ValidationError("This tax rate is not configured for sales.")
                if alloc.kind == "DIRECT_EXPENSE" and not tax_rate.applies_to_purchases:
                    raise ValidationError("This tax rate is not configured for purchases.")
                net_value, tax_value, gross_value = compute_tax_breakdown(
                    amount, treatment, tax_rate.percentage
                )
            else:
                net_value, tax_value, gross_value = amount, Decimal("0.00"), amount

            if alloc.kind == "DIRECT_INCOME":
                # Replace the previously added credit line with net and attach tax.
                credit_lines.pop()
                credit_lines.append((account, net_value))
                if tax_value and tax_value != 0:
                    if not sales_tax_account:
                        raise ValidationError("Configure a sales tax account before posting tax.")
                    tax_lines.append((sales_tax_account, Decimal("0.00"), tax_value))
                allocation_sum = allocation_sum - amount + gross_value
                match_targets[-1] = ("direct_income", None, gross_value)
            elif alloc.kind == "DIRECT_EXPENSE":
                debit_lines.pop()
                debit_lines.append((account, net_value))
                if tax_value and tax_value != 0:
                    if not recoverable_tax_account:
                        raise ValidationError("Configure a tax recoverable account before posting tax.")
                    tax_lines.append((recoverable_tax_account, tax_value, Decimal("0.00")))
                allocation_sum = allocation_sum - amount + gross_value
                match_targets[-1] = ("direct_expense", None, gross_value)

    fee_amount = Decimal("0.00")
    fee_account = None
    if fees is not None:
        fee_amount = _to_decimal(fees.amount)
        if fee_amount <= 0:
            raise ValidationError("Fee amount must be positive.")
        fee_account = _require_account(business, fees.account_id)

    rounding_amount = Decimal("0.00")
    rounding_account = None
    if rounding is not None:
        rounding_amount = _to_decimal(rounding.amount)
        if rounding_amount == 0:
            rounding = None
        else:
            rounding_account = _require_account(business, rounding.account_id)

    overpayment_amount = Decimal("0.00")
    overpayment_account = None
    if overpayment is not None:
        if not is_deposit:
            raise ValidationError("Overpayments only apply to deposits.")
        overpayment_amount = _to_decimal(overpayment.amount)
        if overpayment_amount <= 0:
            raise ValidationError("Overpayment amount must be positive.")
        overpayment_account = _require_account(business, overpayment.account_id)

    if not is_deposit and overpayment is not None:
        raise ValidationError("Overpayments are not valid for withdrawals.")

    if not is_deposit and credit_lines:
        raise ValidationError("Credit allocations are not valid for withdrawals.")

    if is_deposit and bill_allocations:
        raise ValidationError("Bills cannot be allocated against deposits.")

    if not is_deposit and invoice_allocations:
        raise ValidationError("Invoices cannot be allocated against withdrawals.")

    if is_deposit:
        expected_bank = allocation_sum + overpayment_amount - fee_amount - rounding_amount
    else:
        expected_bank = allocation_sum + fee_amount + rounding_amount

    difference = bank_portion - expected_bank
    if difference.copy_abs() > tolerance:
        if rounding_account is None:
            rounding_account = defaults.get("sales") if is_deposit else defaults.get("opex")
        if rounding_account is None:
            raise ValidationError("Allocations do not reconcile with the bank amount.")
        if is_deposit:
            rounding_amount -= difference
        else:
            rounding_amount += difference
        expected_bank = bank_portion

    if (expected_bank - bank_portion).copy_abs() > tolerance:
        raise ValidationError("Allocations do not reconcile with the bank amount.")

    description_base = bank_tx.description or "Bank reconciliation"
    user_hint = f" · {user.username}" if user else ""
    entry = JournalEntry.objects.create(
        business=business,
        date=bank_tx.date,
        description=f"{description_base[:200]}{user_hint}",
        allocation_operation_id=operation_id,
    )

    lines: list[tuple[Account, Decimal, Decimal]] = []

    def add_line(account: Account, debit: Decimal, credit: Decimal):
        if debit < 0 or credit < 0:
            raise ValidationError("Debit and credit values must be non-negative.")
        if debit == 0 and credit == 0:
            return
        lines.append((account, debit, credit))

    if is_deposit:
        add_line(bank_account, bank_portion, Decimal("0.00"))
    else:
        add_line(bank_account, Decimal("0.00"), bank_portion)

    for invoice, amount in invoice_allocations:
        add_line(ar_account, Decimal("0.00"), amount)

    for expense, amount in bill_allocations:
        add_line(ap_account, amount, Decimal("0.00"))

    for account, amount in credit_lines:
        add_line(account, Decimal("0.00"), amount)

    for account, amount in debit_lines:
        add_line(account, amount, Decimal("0.00"))

    for account, debit, credit in tax_lines:
        add_line(account, debit, credit)

    if fee_account and fee_amount > 0:
        add_line(fee_account, fee_amount, Decimal("0.00"))

    if rounding_account and rounding_amount != 0:
        if rounding_amount > 0:
            add_line(rounding_account, rounding_amount, Decimal("0.00"))
        else:
            add_line(rounding_account, Decimal("0.00"), abs(rounding_amount))

    if overpayment_account and overpayment_amount > 0:
        add_line(overpayment_account, Decimal("0.00"), overpayment_amount)

    total_debits = sum(item[1] for item in lines)
    total_credits = sum(item[2] for item in lines)
    if (total_debits - total_credits).copy_abs() > Decimal("0.0001"):
        raise ValidationError("Generated journal entry is not balanced.")

    JournalLine.objects.bulk_create(
        [
            JournalLine(
                journal_entry=entry,
                account=account,
                debit=debit,
                credit=credit,
            )
            for account, debit, credit in lines
        ]
    )

    if invoice_allocations:
        for invoice, amount in invoice_allocations:
            invoice.amount_paid = (invoice.amount_paid or Decimal("0.00")) + amount
            invoice.save()
            match_targets.append(("invoice", invoice, amount))

    if bill_allocations:
        for expense, amount in bill_allocations:
            expense.amount_paid = (expense.amount_paid or Decimal("0.00")) + amount
            expense.save()
            match_targets.append(("bill", expense, amount))

    bank_tx.posted_journal_entry = entry
    if len(invoice_allocations) == 1 and not bill_allocations and not credit_lines and not debit_lines:
        bank_tx.matched_invoice = invoice_allocations[0][0]
    if len(bill_allocations) == 1 and not invoice_allocations and not credit_lines and not debit_lines:
        bank_tx.matched_expense = bill_allocations[0][0]
    else:
        bank_tx.matched_invoice = None
        bank_tx.matched_expense = None
    bank_tx.save(update_fields=["posted_journal_entry", "matched_invoice", "matched_expense"])

    match_results: list[Decimal] = []
    if match_targets:
        base_total = sum(amount for _, _, amount in match_targets)
        desired_total = bank_portion - overpayment_amount if is_deposit else bank_portion
        adjustment_delta = fee_amount + rounding_amount
        adjustment_effect = -adjustment_delta if is_deposit else adjustment_delta
        running_total = Decimal("0.00")
        for idx, (_, _, amount) in enumerate(match_targets):
            share = amount / base_total if base_total else Decimal("0.00")
            adjustment = share * adjustment_effect
            match_amount = amount + adjustment
            match_amount = match_amount.quantize(Decimal("0.0001"))
            match_results.append(match_amount)
            running_total += match_amount
        if match_results:
            diff = desired_total - running_total
            match_results[-1] += diff
    if overpayment_amount > 0:
        match_targets.append(("overpayment", None, overpayment_amount))
        match_results.append(overpayment_amount)

    if not match_results:
        match_targets = [("bank", None, bank_portion)]
        match_results = [bank_portion]

    for (kind, _obj, _amount), match_amount in zip(match_targets, match_results):
        match_amount = max(match_amount, Decimal("0.00"))
        if match_amount == 0:
            continue
        BankReconciliationMatch.objects.create(
            bank_transaction=bank_tx,
            journal_entry=entry,
            matched_amount=match_amount,
        )

    recompute_bank_transaction_status(bank_tx)
    return entry


__all__ = [
    "Allocation",
    "allocate_bank_transaction",
    "recompute_bank_transaction_status",
    "add_bank_match",
]
