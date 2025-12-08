"""
API endpoint for dashboard data.

Option B architecture: JSON-only API for React frontend.
"""
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Q, Sum
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .utils import get_current_business, is_empty_workspace
from .services.periods import resolve_period, resolve_comparison
from .ledger_services import compute_ledger_pl
from .services.ledger_metrics import (
    build_pl_diagnostics,
    calculate_ledger_income,
    calculate_ledger_expenses,
    calculate_ledger_expense_by_account_name,
    get_pl_period_dates,
    PLPeriod,
)
from .ledger_reports import account_balances_for_business
from .views import net_tax_position
from .models import (
    Invoice,
    Expense,
    JournalLine,
    Account,
    Customer,
    Supplier,
    BankTransaction,
    BankAccount,
    Category,
)


def _decimal_to_float(value):
    """Safely convert Decimal or other numeric to float."""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _first_day_of_month(d):
    return d.replace(day=1)


def _add_months(d, n):
    month = d.month - 1 + n
    year = d.year + month // 12
    month = month % 12 + 1
    return d.replace(year=year, month=month, day=1)


def _change_pct(current, previous):
    if previous in (None, Decimal("0.00")):
        return None
    try:
        result = ((current - previous) / abs(previous)) * Decimal("100.0")
        return float(result)
    except (InvalidOperation, ZeroDivisionError):
        return None


def _get_available_pl_months(business):
    """Generate list of available P&L month options."""
    if not business:
        return []
    
    today = timezone.localdate()
    options = []
    
    # Include current month and previous 11 months
    for i in range(12):
        month_start = _first_day_of_month(_add_months(today.replace(day=1), -i))
        label = month_start.strftime("%B %Y")
        value = f"month_{month_start.year}_{month_start.month:02d}"
        options.append({"value": value, "label": label})
    
    return options


def build_dashboard_payload(request, business):
    """
    Build the complete dashboard payload data.
    
    This is the core function that computes all dashboard metrics.
    Used by both the API endpoint and the template view.
    """
    today = timezone.localdate()
    thirty_days_ago = today - timedelta(days=30)

    invoices_qs = Invoice.objects.filter(business=business)
    expenses_all_qs = Expense.objects.filter(business=business)
    expenses_qs = expenses_all_qs.filter(status=Expense.Status.PAID)

    # Handle P&L period selection
    pl_period_preset = request.GET.get("pl_period_preset") or request.GET.get("pl_month") or "this_month"
    pl_start_date = request.GET.get("pl_start_date")
    pl_end_date = request.GET.get("pl_end_date")
    pl_compare_to = request.GET.get("pl_compare_to") or "previous_period"

    period_info = resolve_period(
        pl_period_preset,
        pl_start_date,
        pl_end_date,
        business.fiscal_year_start if business else None,
        today=today,
    )
    month_start = period_info["start"]
    month_end = period_info["end"]
    pl_period_label = period_info["label"]
    pl_period_preset_normalized = period_info["preset"]

    comparison_info = resolve_comparison(month_start, month_end, pl_compare_to)
    pl_compare_to_normalized = comparison_info.get("compare_to") or "none"
    if (
        pl_compare_to_normalized == "previous_period"
        and pl_period_preset_normalized == PLPeriod.THIS_MONTH.value
        and month_start
    ):
        prev_start_month, prev_end_month, prev_label, _ = get_pl_period_dates(PLPeriod.LAST_MONTH, today=today)
        comparison_info = {
            "compare_start": prev_start_month,
            "compare_end": prev_end_month,
            "compare_label": prev_label,
            "compare_to": "previous_period",
        }
        pl_compare_to_normalized = "previous_period"
    
    prev_start = comparison_info.get("compare_start")
    prev_end = comparison_info.get("compare_end")
    pl_prev_period_label = comparison_info.get("compare_label") or ""

    ledger_pl = compute_ledger_pl(business, month_start, month_end)
    
    # Compute previous period P&L if comparison is enabled
    if prev_start and prev_end:
        prev_ledger_pl = compute_ledger_pl(business, prev_start, prev_end)
        prev_income = prev_ledger_pl["total_income"]
        prev_expenses = prev_ledger_pl["total_expense"]
        prev_net = prev_ledger_pl["net"]
    else:
        prev_income = None
        prev_expenses = None
        prev_net = None

    pl_diagnostics = build_pl_diagnostics(business, month_start, month_end)

    total_income_month = ledger_pl["total_income"]
    total_expenses_month = ledger_pl["total_expense"]
    net_income_month = ledger_pl["net"]

    income_line_count = JournalLine.objects.filter(
        journal_entry__business=business,
        journal_entry__date__gte=month_start,
        journal_entry__date__lte=month_end,
        journal_entry__is_void=False,
        account__type=Account.AccountType.INCOME,
    ).count()
    expense_line_count = JournalLine.objects.filter(
        journal_entry__business=business,
        journal_entry__date__gte=month_start,
        journal_entry__date__lte=month_end,
        journal_entry__is_void=False,
        account__type=Account.AccountType.EXPENSE,
    ).count()
    no_ledger_activity_for_period = income_line_count == 0 and expense_line_count == 0

    last_income_entry_date = (
        JournalLine.objects.filter(
            journal_entry__business=business,
            journal_entry__is_void=False,
            account__type=Account.AccountType.INCOME,
        )
        .order_by("-journal_entry__date")
        .values_list("journal_entry__date", flat=True)
        .first()
    )
    last_expense_entry_date = (
        JournalLine.objects.filter(
            journal_entry__business=business,
            journal_entry__is_void=False,
            account__type=Account.AccountType.EXPENSE,
        )
        .order_by("-journal_entry__date")
        .values_list("journal_entry__date", flat=True)
        .first()
    )

    # Overdue and draft invoices
    overdue_qs = invoices_qs.filter(status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL], due_date__lt=today)
    overdue_total = overdue_qs.aggregate(total=Sum("grand_total"))["total"] or Decimal("0")
    overdue_count = overdue_qs.count()

    draft_qs = invoices_qs.filter(status=Invoice.Status.DRAFT)
    draft_total = draft_qs.aggregate(total=Sum("grand_total"))["total"] or Decimal("0")
    draft_count = draft_qs.count()

    # 30-day P&L
    revenue_30 = calculate_ledger_income(business, thirty_days_ago, today)
    expenses_30 = calculate_ledger_expenses(business, thirty_days_ago, today)

    # Cashflow chart data
    labels = []
    income_series = []
    expense_series = []
    current_month_start = _first_day_of_month(today)
    start_month = _add_months(current_month_start, -5)

    for i in range(6):
        series_month_start = _add_months(start_month, i)
        next_month_start = _add_months(series_month_start, 1)
        series_month_end = next_month_start - timedelta(days=1)

        labels.append(series_month_start.strftime("%b %Y"))

        month_transactions = BankTransaction.objects.filter(
            bank_account__business=business,
            date__gte=series_month_start,
            date__lte=series_month_end,
        )

        inflows = (
            month_transactions.filter(amount__gte=0).aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )
        outflows_sum = (
            month_transactions.filter(amount__lt=0).aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )
        outflows = abs(outflows_sum)

        income_series.append(float(inflows))
        expense_series.append(float(outflows))

    # Expense by category
    expense_by_cat_qs = (
        expenses_qs.filter(date__gte=month_start, date__lte=month_end)
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )

    expense_summary = [
        {"name": row["category__name"] or "Uncategorized", "total": _decimal_to_float(row["total"])}
        for row in expense_by_cat_qs[:4]
    ]

    # Recent invoices
    recent_invoices = invoices_qs.select_related("customer").order_by("-issue_date")[:5]
    recent_invoices_payload = []
    for inv in recent_invoices:
        if inv.due_date:
            delta = (inv.due_date - today).days
            if delta > 0:
                due_label = f"Due in {delta}d"
            elif delta == 0:
                due_label = "Due today"
            else:
                due_label = f"{abs(delta)}d overdue"
        else:
            due_label = ""
        recent_invoices_payload.append({
            "number": inv.invoice_number,
            "customer": inv.customer.name if inv.customer else "",
            "status": inv.status,
            "issue_date": inv.issue_date.isoformat() if inv.issue_date else "",
            "amount": _decimal_to_float(inv.grand_total),
            "due_label": due_label,
            "url": reverse("invoice_update", args=[inv.pk]),
        })

    # Bank feed
    bank_feed_items = (
        BankTransaction.objects.filter(bank_account__business=business).order_by("-date", "-id")[:5]
    )
    bank_feed_payload = []
    for tx in bank_feed_items:
        note_value = getattr(tx, "status_label", None)
        if note_value is None:
            note_value = getattr(tx, "statusLabel", tx.status)
        direction = "in" if (tx.amount or Decimal("0")) >= 0 else "out"
        bank_feed_payload.append({
            "description": tx.description,
            "note": note_value,
            "amount": _decimal_to_float(tx.amount),
            "direction": direction,
            "date": tx.date.isoformat() if tx.date else "",
        })

    # Bank reconciliation status
    bank_reco = []
    for ba in BankAccount.objects.filter(business=business).select_related("account"):
        unreconciled = (
            BankTransaction.objects.filter(
                bank_account=ba,
                is_reconciled=False,
            )
            .exclude(status=BankTransaction.TransactionStatus.EXCLUDED)
            .count()
        )
        bank_reco.append({
            "id": ba.id,
            "name": ba.name,
            "unreconciled": unreconciled,
            "account_code": ba.account.code if ba.account else "",
        })

    # Top suppliers
    supplier_stats_qs = (
        Supplier.objects.filter(business=business)
        .annotate(
            payment_count=Count(
                "expenses",
                filter=Q(expenses__status=Expense.Status.PAID),
            ),
            mtd_spend=Sum(
                "expenses__amount",
                filter=Q(
                    expenses__status=Expense.Status.PAID,
                    expenses__date__gte=month_start,
                    expenses__date__lte=month_end,
                ),
            ),
            last_payment=Max(
                "expenses__date",
                filter=Q(expenses__status=Expense.Status.PAID),
            ),
        )
        .order_by("-payment_count", "-mtd_spend", "-last_payment", "-id")[:5]
    )

    supplier_ids = [s.id for s in supplier_stats_qs]
    supplier_recent_category = {}
    if supplier_ids:
        for row in (
            Expense.objects.filter(
                business=business, supplier_id__in=supplier_ids, category__isnull=False
            )
            .order_by("-date", "-id")
            .values("supplier_id", "category__name")
        ):
            supplier_recent_category.setdefault(row["supplier_id"], row["category__name"])

    top_suppliers = []
    for supplier in supplier_stats_qs:
        top_suppliers.append({
            "name": supplier.name,
            "mtdSpend": _decimal_to_float(getattr(supplier, "mtd_spend", Decimal("0")) or Decimal("0")),
            "paymentCount": getattr(supplier, "payment_count", 0) or 0,
            "category": supplier_recent_category.get(supplier.id, ""),
        })

    # Unpaid expenses
    unpaid_expenses_total = (
        expenses_all_qs.filter(status__in=[Expense.Status.UNPAID, Expense.Status.PARTIAL])
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )

    # Cash on hand
    cash_balances = account_balances_for_business(business)
    cash_on_hand = Decimal("0")
    for account in cash_balances["accounts"]:
        if account["type"] == Account.AccountType.ASSET:
            cash_on_hand += account["balance"]

    # Open invoices
    open_invoices_qs = invoices_qs.filter(status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL])
    open_invoices_total = open_invoices_qs.aggregate(total=Sum("grand_total"))["total"] or Decimal("0")
    open_invoices_count = open_invoices_qs.count()

    # Tax position
    tax_position = net_tax_position(business)
    if tax_position["net_tax"] > 0:
        tax_position_label = "Estimated tax owing"
    elif tax_position["net_tax"] < 0:
        tax_position_label = "Estimated tax refund receivable"
    else:
        tax_position_label = "Net tax is balanced"

    # Build final payload
    empty_workspace = is_empty_workspace(business)
    start_books_url = reverse("customer_create")
    bank_import_url = reverse("bank_import")

    return {
        "username": request.user.get_username() or request.user.get_full_name() or request.user.email,
        "business": business.name if business else "",
        "currency": business.currency if business else "",
        "is_empty_workspace": empty_workspace,
        "metrics": {
            "cash_on_hand": _decimal_to_float(cash_on_hand),
            "open_invoices_total": _decimal_to_float(open_invoices_total),
            "open_invoices_count": open_invoices_count,
            "net_income_month": _decimal_to_float(net_income_month),
            "revenue_30": _decimal_to_float(revenue_30),
            "expenses_30": _decimal_to_float(expenses_30),
            "overdue_total": _decimal_to_float(overdue_total),
            "overdue_count": overdue_count,
            "draft_total": _decimal_to_float(draft_total),
            "draft_count": draft_count,
            "unpaid_expenses_total": _decimal_to_float(unpaid_expenses_total),
            "revenue_month": _decimal_to_float(total_income_month),
            "expenses_month": _decimal_to_float(total_expenses_month),
            "pl_period_start": month_start.isoformat() if month_start else None,
            "pl_period_end": month_end.isoformat() if month_end else None,
            "pl_period_preset": pl_period_preset_normalized,
            "pl_period_label": pl_period_label,
            "pl_compare_to": pl_compare_to_normalized,
            "pl_compare_label": pl_prev_period_label,
            "pl_compare_start": prev_start.isoformat() if prev_start else None,
            "pl_compare_end": prev_end.isoformat() if prev_end else None,
            "pl_prev_period_label": pl_prev_period_label,
            "pl_prev_income": _decimal_to_float(prev_income) if prev_income is not None else None,
            "pl_prev_expenses": _decimal_to_float(prev_expenses) if prev_expenses is not None else None,
            "pl_prev_net": _decimal_to_float(prev_net) if prev_net is not None else None,
            "pl_change_income_pct": _change_pct(total_income_month, prev_income) if prev_income is not None else None,
            "pl_change_expenses_pct": _change_pct(total_expenses_month, prev_expenses) if prev_expenses is not None else None,
            "pl_change_net_pct": _change_pct(net_income_month, prev_net) if prev_net is not None else None,
            "pl_selected_month": pl_period_preset_normalized,
            "pl_month_options": _get_available_pl_months(business),
            "pl_diagnostics": pl_diagnostics,
            "pl_debug": {
                "period_start": month_start.isoformat() if month_start else None,
                "period_end": month_end.isoformat() if month_end else None,
                "income_line_count": income_line_count,
                "expense_line_count": expense_line_count,
                "last_income_entry_date": last_income_entry_date.isoformat() if last_income_entry_date else None,
                "last_expense_entry_date": last_expense_entry_date.isoformat() if last_expense_entry_date else None,
                "no_ledger_activity_for_period": no_ledger_activity_for_period,
            },
        },
        "tax": {
            "sales_tax_payable": _decimal_to_float(tax_position["sales_tax_payable"]),
            "recoverable_tax_asset": _decimal_to_float(tax_position["recoverable_tax_asset"]),
            "net_tax": _decimal_to_float(tax_position["net_tax"]),
            "label": tax_position_label,
        },
        "bankReconciliation": bank_reco,
        "recentInvoices": recent_invoices_payload,
        "bankFeed": bank_feed_payload,
        "expenseSummary": expense_summary,
        "cashflow": {
            "labels": labels,
            "income": income_series,
            "expenses": expense_series,
        },
        "topSuppliers": top_suppliers,
        "urls": {
            "newInvoice": reverse("invoice_create"),
            "invoices": reverse("invoice_list"),
            "banking": reverse("banking_accounts_feed"),
            "expenses": reverse("expense_list"),
            "suppliers": reverse("suppliers"),
            "profitAndLoss": reverse("report_pnl"),
            "bankReview": reverse("banking_accounts_feed"),
            "overdueInvoices": reverse("invoice_list"),
            "unpaidExpenses": reverse("expense_list"),
            "cashflowReport": reverse("cashflow_report"),
            "startBooks": start_books_url,
            "bankImport": bank_import_url,
        },
    }


@login_required
@require_GET
def api_dashboard(request):
    """
    GET /api/dashboard/
    
    Returns dashboard data as JSON for the React frontend.
    Option B architecture: API-only, no template logic.
    """
    try:
        business = get_current_business(request.user)
        if business is None:
            return JsonResponse({
                "error": "No business context",
                "details": "Please set up a business first.",
            }, status=400)

        payload = build_dashboard_payload(request, business)
        return JsonResponse(payload)

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("Dashboard API error")
        return JsonResponse({
            "error": "Failed to load dashboard",
            "details": str(e),
        }, status=500)
