"""
Option B compliant API endpoints for Invoices and Expenses lists.
These provide JSON data for React frontends, replacing the template-heavy ListViews.
"""
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.db.models import Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET

from .models import Invoice, Expense, Category
from .utils import get_current_business


# ─────────────────────────────────────────────────────────────────────────────
#    Page Views (thin shells for React)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def invoices_list_page(request):
    """Thin shell page that mounts InvoicesListPage React component."""
    business = get_current_business(request.user)
    return render(request, "invoices-list.html", {
        "default_currency": business.currency if business else "USD",
    })


@login_required
def expenses_list_page(request):
    """Thin shell page that mounts ExpensesListPage React component."""
    business = get_current_business(request.user)
    return render(request, "expenses-list.html", {
        "default_currency": business.currency if business else "USD",
    })


# ─────────────────────────────────────────────────────────────────────────────
#    API Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _serialize_invoice(inv: Invoice) -> dict:
    """Serialize an Invoice for JSON response."""
    return {
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "customer_id": inv.customer_id,
        "customer_name": inv.customer.name if inv.customer else None,
        "status": inv.status,
        "issue_date": inv.issue_date.isoformat() if inv.issue_date else None,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "net_total": str(inv.net_total) if inv.net_total else "0.00",
        "tax_total": str(inv.tax_total) if inv.tax_total else "0.00",
        "grand_total": str(inv.grand_total) if inv.grand_total else "0.00",
        "amount_paid": str(inv.amount_paid) if inv.amount_paid else "0.00",
        "currency": inv.currency,
    }


def _serialize_expense(exp: Expense) -> dict:
    """Serialize an Expense for JSON response."""
    return {
        "id": exp.id,
        "description": exp.description,
        "supplier_id": exp.supplier_id,
        "supplier_name": exp.supplier.name if exp.supplier else None,
        "category_id": exp.category_id,
        "category_name": exp.category.name if exp.category else None,
        "status": exp.status,
        "date": exp.date.isoformat() if exp.date else None,
        "amount": str(exp.amount) if exp.amount else "0.00",
        "currency": exp.currency,
    }


@login_required
@require_GET
def api_invoice_list(request):
    """
    JSON API for invoice list with filtering and stats.
    Query params: status, start, end, invoice (for selected)
    """
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    base_qs = Invoice.objects.filter(business=business).select_related("customer")

    # Date filtering
    start_param = request.GET.get("start")
    end_param = request.GET.get("end")
    start_date = parse_date(start_param) if start_param else None
    end_date = parse_date(end_param) if end_param else None

    if start_date:
        base_qs = base_qs.filter(issue_date__gte=start_date)
    if end_date:
        base_qs = base_qs.filter(issue_date__lte=end_date)

    # Status filtering
    status_param = request.GET.get("status", "all").lower()
    today = timezone.now().date()

    if status_param == "overdue":
        invoices = base_qs.filter(
            status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL],
            due_date__lt=today,
        )
    elif status_param in {"draft", "sent", "partial", "paid", "void"}:
        invoices = base_qs.filter(status=status_param.upper())
    else:
        status_param = "all"
        invoices = base_qs

    invoices = invoices.order_by("-issue_date", "-id")

    # Stats
    open_balance_total = (
        base_qs.filter(status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL])
        .aggregate(total=Sum("grand_total"))["total"]
        or Decimal("0")
    )

    current_year = today.year
    revenue_ytd = (
        base_qs.filter(status=Invoice.Status.PAID, issue_date__year=current_year)
        .aggregate(total=Sum("net_total"))["total"]
        or Decimal("0")
    )

    total_invoices = base_qs.count()
    total_amount_all = base_qs.aggregate(total=Sum("net_total"))["total"] or Decimal("0")
    avg_invoice_value = (
        (total_amount_all / total_invoices) if total_invoices > 0 else Decimal("0")
    )

    # Selected invoice
    selected_invoice_id = request.GET.get("invoice")
    selected_invoice = None
    if selected_invoice_id:
        try:
            inv = base_qs.get(pk=selected_invoice_id)
            selected_invoice = _serialize_invoice(inv)
        except Invoice.DoesNotExist:
            pass

    return JsonResponse({
        "invoices": [_serialize_invoice(inv) for inv in invoices[:100]],
        "stats": {
            "open_balance_total": str(open_balance_total),
            "revenue_ytd": str(revenue_ytd),
            "total_invoices": total_invoices,
            "avg_invoice_value": str(avg_invoice_value.quantize(Decimal("0.01"))),
        },
        "status_filter": status_param,
        "selected_invoice": selected_invoice,
        "currency": business.currency,
        "status_choices": [{"value": c[0], "label": c[1]} for c in Invoice.Status.choices],
    })


@login_required
@require_GET
def api_expense_list(request):
    """
    JSON API for expense list with filtering and stats.
    Query params: status, period, category, start, end, expense (for selected)
    """
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    base_qs = Expense.objects.filter(business=business).select_related("supplier", "category")

    # Status filtering
    status_filter = request.GET.get("status", "all").lower()
    if status_filter == "paid":
        base_qs = base_qs.filter(status=Expense.Status.PAID)
    elif status_filter == "unpaid":
        base_qs = base_qs.filter(status__in=[Expense.Status.UNPAID, Expense.Status.PARTIAL])
    else:
        status_filter = "all"

    # Date filtering
    start_param = request.GET.get("start")
    end_param = request.GET.get("end")
    start_date = parse_date(start_param) if start_param else None
    end_date = parse_date(end_param) if end_param else None
    custom_range = bool(start_date or end_date)
    if start_date:
        base_qs = base_qs.filter(date__gte=start_date)
    if end_date:
        base_qs = base_qs.filter(date__lte=end_date)

    # Category filtering
    category_param = request.GET.get("category")
    category_filter = None
    if category_param:
        try:
            category_filter = int(category_param)
            base_qs = base_qs.filter(category_id=category_filter)
        except (TypeError, ValueError):
            pass

    # Period filtering
    period = request.GET.get("period", "this_month").lower()
    today = timezone.localdate()

    def this_month_qs(qs):
        return qs.filter(date__year=today.year, date__month=today.month)

    def this_year_qs(qs):
        return qs.filter(date__year=today.year)

    if custom_range:
        expenses = base_qs
        period = "custom"
    elif period == "this_year":
        expenses = this_year_qs(base_qs)
    elif period == "all":
        expenses = base_qs
    else:
        period = "this_month"
        expenses = this_month_qs(base_qs)

    expenses = expenses.order_by("-date", "-id")

    # Stats
    paid_base_qs = base_qs.filter(status=Expense.Status.PAID)
    expenses_ytd = this_year_qs(paid_base_qs).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    expenses_month = this_month_qs(paid_base_qs).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    total_transactions = paid_base_qs.count()
    total_all = paid_base_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    avg_expense = (total_all / total_transactions) if total_transactions else Decimal("0")
    total_filtered = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    # Selected expense
    selected_expense_id = request.GET.get("expense")
    selected_expense = None
    if selected_expense_id:
        try:
            exp = expenses.get(pk=selected_expense_id)
            selected_expense = _serialize_expense(exp)
        except Expense.DoesNotExist:
            pass

    # Categories for filter dropdown
    categories = Category.objects.filter(
        business=business,
        type=Category.CategoryType.EXPENSE,
    ).order_by("name").values("id", "name")

    return JsonResponse({
        "expenses": [_serialize_expense(exp) for exp in expenses[:100]],
        "stats": {
            "expenses_ytd": str(expenses_ytd),
            "expenses_month": str(expenses_month),
            "total_all": str(total_all),
            "avg_expense": str(avg_expense.quantize(Decimal("0.01"))),
            "total_filtered": str(total_filtered),
        },
        "period": period,
        "status_filter": status_filter,
        "category_filter": category_filter,
        "categories": list(categories),
        "selected_expense": selected_expense,
        "currency": business.currency,
        "status_choices": [{"value": c[0], "label": c[1]} for c in Expense.Status.choices],
    })
