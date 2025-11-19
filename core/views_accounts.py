from decimal import Decimal
import json

from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .ledger_reports import account_balances_for_business
from .models import Account, BankTransaction, JournalLine
from .utils import get_current_business


@login_required
def account_list_view(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    today = timezone.localdate()
    data = account_balances_for_business(business, upto_date=today)

    grouped = {}
    for account in data["accounts"]:
        grouped.setdefault(account["type"], []).append(account)

    return render(
        request,
        "accounts/account_list.html",
        {
            "business": business,
            "as_of": today,
            "grouped_accounts": grouped,
            "totals_by_type": data["totals_by_type"],
        },
    )


def _line_delta(account: Account, debit: Decimal | None, credit: Decimal | None) -> Decimal:
    debit = debit or Decimal("0.00")
    credit = credit or Decimal("0.00")
    if account.type in (Account.AccountType.ASSET, Account.AccountType.EXPENSE):
        return debit - credit
    return credit - debit


@login_required
def account_detail_view(request, account_id):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    account = get_object_or_404(Account, pk=account_id, business=business)

    today = timezone.localdate()
    start_of_month = today.replace(day=1)

    base_lines = JournalLine.objects.filter(
        journal_entry__business=business,
        journal_entry__is_void=False,
        account=account,
    )

    totals = base_lines.aggregate(total_debit=Sum("debit"), total_credit=Sum("credit"))
    balance = _line_delta(
        account,
        totals["total_debit"] or Decimal("0.00"),
        totals["total_credit"] or Decimal("0.00"),
    )

    period_lines = base_lines.filter(journal_entry__date__range=(start_of_month, today))
    period_deposits = Decimal("0.00")
    period_withdrawals = Decimal("0.00")
    for line in period_lines.values("debit", "credit"):
        delta = _line_delta(account, line["debit"], line["credit"])
        if delta >= 0:
            period_deposits += delta
        else:
            period_withdrawals += abs(delta)
    period_count = period_lines.count()

    bank_account = getattr(account, "bank_account", None)
    last_reconciled_on = (
        bank_account.last_imported_at.date() if bank_account and bank_account.last_imported_at else None
    )
    unreconciled_count = (
        BankTransaction.objects.filter(
            bank_account=bank_account,
            status=BankTransaction.TransactionStatus.NEW,
        ).count()
        if bank_account
        else 0
    )
    link_bank_feed_url = (
        reverse("bank_feed_review", args=[bank_account.id]) if bank_account else ""
    )
    api_bank_transactions_url = (
        f"{reverse('api_banking_feed_transactions')}?account_id={bank_account.id}"
        if bank_account
        else ""
    )

    context = {
        "business": business,
        "account": account,
        "account_detail_type": account.description or "Operating account",
        "is_bank_account": bool(bank_account),
        "bank_last4": bank_account.account_number_mask if bank_account else "",
        "bank_display_name": bank_account.name if bank_account else "",
        "balance": float(balance),
        "period_deposits": float(period_deposits),
        "period_withdrawals": float(period_withdrawals),
        "period_count": period_count,
        "last_reconciled_on": last_reconciled_on,
        "unreconciled_count": unreconciled_count,
        "edit_form_url": reverse("admin:core_account_change", args=[account.id]),
        "link_bank_feed_url": link_bank_feed_url,
        "api_bank_transactions_url": api_bank_transactions_url,
        "api_activity_url": reverse("api_account_activity", args=[account.id]),
        "api_ledger_url": reverse("api_account_ledger", args=[account.id]),
        "api_toggle_favorite_url": reverse("api_account_toggle_favorite", args=[account.id]),
        "api_create_manual_tx_url": reverse(
            "api_account_manual_transaction", args=[account.id]
        ),
    }

    return render(request, "coa/account_detail.html", context)


@login_required
def api_account_activity(request, account_id):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"rows": []})
    account = get_object_or_404(Account, pk=account_id, business=business)

    base_lines = JournalLine.objects.select_related("journal_entry").filter(
        journal_entry__business=business,
        journal_entry__is_void=False,
        account=account,
    )

    lines = base_lines.order_by("-journal_entry__date", "-id")[:200]

    balance_totals = base_lines.aggregate(total_debit=Sum("debit"), total_credit=Sum("credit"))
    running_balance = _line_delta(
        account,
        balance_totals["total_debit"] or Decimal("0.00"),
        balance_totals["total_credit"] or Decimal("0.00"),
    )

    rows = []
    for line in lines:
        delta = _line_delta(account, line.debit, line.credit)
        source = "Other"
        ct = getattr(line.journal_entry, "source_content_type", None)
        if ct:
            model = ct.model
            if model == "invoice":
                source = "Invoice"
            elif model == "expense":
                source = "Expense"
        elif getattr(line.journal_entry, "is_manual", False):
            source = "Manual"

        rows.append(
            {
                "id": line.id,
                "date": line.journal_entry.date.isoformat(),
                "description": line.journal_entry.description or line.description or "",
                "source": source,
                "amount": float(delta),
                "running_balance": float(running_balance),
            }
        )
        running_balance -= delta

    return JsonResponse({"rows": rows})


@login_required
def api_account_ledger(request, account_id):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"rows": []}, status=400)

    account = get_object_or_404(Account, pk=account_id, business=business)

    lines = (
        JournalLine.objects.select_related("journal_entry")
        .filter(
            journal_entry__business=business,
            journal_entry__is_void=False,
            account=account,
        )
        .order_by("journal_entry__date", "id")
    )

    running_balance = Decimal("0.00")
    rows: list[dict[str, object]] = []
    for line in lines:
        delta = _line_delta(account, line.debit, line.credit)
        running_balance += delta
        rows.append(
            {
                "id": line.id,
                "date": line.journal_entry.date.isoformat(),
                "description": line.journal_entry.description
                or line.description
                or "",
                "debit": float(line.debit or Decimal("0.00")),
                "credit": float(line.credit or Decimal("0.00")),
                "running_balance": float(running_balance),
                "entry_id": line.journal_entry_id,
            }
        )

    return JsonResponse({"rows": rows})


@login_required
@require_POST
def api_account_toggle_favorite(request, account_id):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"ok": False}, status=400)
    account = get_object_or_404(Account, pk=account_id, business=business)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        payload = {}

    favorite = bool(payload.get("favorite"))
    account.is_favorite = favorite
    account.save(update_fields=["is_favorite"])
    return JsonResponse({"ok": True, "favorite": favorite})


@login_required
@require_POST
def api_account_manual_transaction(request, account_id):
    # Placeholder for future manual posting logic
    return JsonResponse({"ok": True})
