"""
Option B compliant API endpoints for entity lists.
These provide JSON data for React frontends, replacing the template-heavy ListViews.
"""
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.db.models import Sum, Max, Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET

from .models import Invoice, Expense, Category, Customer, Supplier, Item, JournalEntry, JournalLine
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


@login_required
def customers_list_page(request):
    """Thin shell page that mounts CustomersPage React component."""
    business = get_current_business(request.user)
    return render(request, "customers-list.html", {
        "default_currency": business.currency if business else "USD",
    })


@login_required
def suppliers_list_page(request):
    """Thin shell page that mounts SuppliersPage React component."""
    business = get_current_business(request.user)
    return render(request, "suppliers-list.html", {
        "default_currency": business.currency if business else "USD",
    })


@login_required
def categories_list_page(request):
    """Thin shell page that mounts CategoriesPage React component."""
    business = get_current_business(request.user)
    return render(request, "categories-list.html", {
        "default_currency": business.currency if business else "USD",
    })


@login_required
def products_list_page(request):
    """Thin shell page that mounts ProductsPage React component."""
    business = get_current_business(request.user)
    return render(request, "products-list.html", {
        "default_currency": business.currency if business else "USD",
    })


@login_required
def journal_entries_list_page(request):
    """Thin shell page that mounts JournalEntriesPage React component."""
    business = get_current_business(request.user)
    return render(request, "journal-entries-list.html", {
        "default_currency": business.currency if business else "USD",
    })


# ─────────────────────────────────────────────────────────────────────────────
#    API Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _serialize_invoice(inv: Invoice, currency: str) -> dict:
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
        "currency": currency,
    }


def _serialize_expense(exp: Expense, currency: str) -> dict:
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
        "currency": currency,
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

    customer_id = request.GET.get("customer")
    if customer_id:
        try:
            customer_id_int = int(customer_id)
        except (TypeError, ValueError):
            return JsonResponse({"error": "Invalid customer"}, status=400)
        base_qs = base_qs.filter(customer_id=customer_id_int)

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
            selected_invoice = _serialize_invoice(inv, business.currency)
        except Invoice.DoesNotExist:
            pass

    return JsonResponse({
        "invoices": [_serialize_invoice(inv, business.currency) for inv in invoices[:100]],
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
            selected_expense = _serialize_expense(exp, business.currency)
        except Expense.DoesNotExist:
            pass

    # Categories for filter dropdown
    categories = Category.objects.filter(
        business=business,
        type=Category.CategoryType.EXPENSE,
    ).order_by("name").values("id", "name")

    return JsonResponse({
        "expenses": [_serialize_expense(exp, business.currency) for exp in expenses[:100]],
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


# ─────────────────────────────────────────────────────────────────────────────
#    Customers API
# ─────────────────────────────────────────────────────────────────────────────

def _serialize_customer(cust: Customer) -> dict:
    """Serialize a Customer for JSON response."""
    return {
        "id": cust.id,
        "name": cust.name,
        "email": cust.email or "",
        "phone": cust.phone or "",
        "is_active": cust.is_active,
        "open_balance": str(getattr(cust, "open_balance", None) or "0.00"),
        "ytd_revenue": str(getattr(cust, "ytd_revenue", None) or "0.00"),
        "mtd_revenue": str(getattr(cust, "mtd_revenue", None) or "0.00"),
        "last_invoice_date": cust.last_invoice_date.isoformat() if getattr(cust, "last_invoice_date", None) else None,
    }


@login_required
@require_GET
def api_customer_list(request):
    """JSON API for customer list with stats."""
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    today = timezone.localdate()
    year = today.year
    month_start = today.replace(day=1)

    qs = Customer.objects.filter(business=business)

    # Search
    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(phone__icontains=search_query)
        )

    # Annotate with stats
    qs = qs.annotate(
        open_balance=Sum(
            "invoices__grand_total",
            filter=Q(invoices__status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL, Invoice.Status.DRAFT]),
        ),
        ytd_revenue=Sum(
            "invoices__net_total",
            filter=Q(invoices__status=Invoice.Status.PAID, invoices__issue_date__year=year),
        ),
        mtd_revenue=Sum(
            "invoices__net_total",
            filter=Q(invoices__status=Invoice.Status.PAID, invoices__issue_date__gte=month_start),
        ),
        last_invoice_date=Max("invoices__issue_date"),
    ).order_by("name")

    customers = list(qs[:100])
    total_ytd = sum((c.ytd_revenue or Decimal("0")) for c in customers)
    total_mtd = sum((c.mtd_revenue or Decimal("0")) for c in customers)
    total_open = sum((c.open_balance or Decimal("0")) for c in customers)

    return JsonResponse({
        "customers": [_serialize_customer(c) for c in customers],
        "stats": {
            "total_customers": len(customers),
            "total_ytd": str(total_ytd),
            "total_mtd": str(total_mtd),
            "total_open_balance": str(total_open),
        },
        "currency": business.currency,
    })


# ─────────────────────────────────────────────────────────────────────────────
#    Suppliers API
# ─────────────────────────────────────────────────────────────────────────────

def _serialize_supplier(sup: Supplier) -> dict:
    """Serialize a Supplier for JSON response."""
    return {
        "id": sup.id,
        "name": sup.name,
        "email": sup.email or "",
        "phone": sup.phone or "",
        "total_spend": str(getattr(sup, "total_spend", None) or "0.00"),
        "ytd_spend": str(getattr(sup, "ytd_spend", None) or "0.00"),
        "expense_count": getattr(sup, "expense_count", 0) or 0,
    }


@login_required
@require_GET
def api_supplier_list(request):
    """JSON API for supplier list with stats."""
    from django.db.models import Count
    
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    today = timezone.localdate()
    year = today.year

    qs = Supplier.objects.filter(business=business)

    # Search
    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(name__icontains=search_query)
            | Q(email__icontains=search_query)
        )

    # Annotate with stats
    qs = qs.annotate(
        total_spend=Sum("expenses__amount", filter=Q(expenses__status=Expense.Status.PAID)),
        ytd_spend=Sum(
            "expenses__amount",
            filter=Q(expenses__status=Expense.Status.PAID, expenses__date__year=year),
        ),
        expense_count=Count("expenses"),
    ).order_by("name")

    suppliers = list(qs[:100])
    total_spend = sum((s.total_spend or Decimal("0")) for s in suppliers)
    total_ytd = sum((s.ytd_spend or Decimal("0")) for s in suppliers)

    return JsonResponse({
        "suppliers": [_serialize_supplier(s) for s in suppliers],
        "stats": {
            "total_suppliers": len(suppliers),
            "total_spend": str(total_spend),
            "ytd_spend": str(total_ytd),
        },
        "currency": business.currency,
    })


# ─────────────────────────────────────────────────────────────────────────────
#    Categories API
# ─────────────────────────────────────────────────────────────────────────────

def _serialize_category(cat: Category) -> dict:
    """Serialize a Category for JSON response."""
    return {
        "id": cat.id,
        "name": cat.name,
        "type": cat.type,
        "is_archived": cat.is_archived,
        "expense_count": getattr(cat, "expense_count", 0) or 0,
        "total_amount": str(getattr(cat, "total_amount", None) or "0.00"),
    }


@login_required
@require_GET
def api_category_list(request):
    """JSON API for category list."""
    from django.db.models import Count
    
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    type_filter = request.GET.get("type", "all").lower()
    show_archived = request.GET.get("archived", "false").lower() == "true"

    qs = Category.objects.filter(business=business)
    
    if type_filter == "expense":
        qs = qs.filter(type=Category.CategoryType.EXPENSE)
    elif type_filter == "income":
        qs = qs.filter(type=Category.CategoryType.INCOME)

    if not show_archived:
        qs = qs.filter(is_archived=False)

    # Annotate
    qs = qs.annotate(
        expense_count=Count("expenses"),
        total_amount=Sum("expenses__amount"),
    ).order_by("type", "name")

    categories = list(qs)
    expense_count = sum(1 for c in categories if c.type == Category.CategoryType.EXPENSE)
    income_count = sum(1 for c in categories if c.type == Category.CategoryType.INCOME)

    return JsonResponse({
        "categories": [_serialize_category(c) for c in categories],
        "stats": {
            "total_categories": len(categories),
            "expense_categories": expense_count,
            "income_categories": income_count,
        },
        "type_choices": [{"value": c[0], "label": c[1]} for c in Category.CategoryType.choices],
    })


# ─────────────────────────────────────────────────────────────────────────────
#    Products API
# ─────────────────────────────────────────────────────────────────────────────

def _serialize_item(item: Item) -> dict:
    """Serialize an Item (Product/Service) for JSON response."""
    return {
        "id": item.id,
        "name": item.name,
        "sku": item.sku,
        "type": item.type,
        "price": str(item.price) if item.price else "0.00",
        "description": item.description,
        "is_archived": item.is_archived,
        "income_category_id": item.income_category_id,
        "income_category_name": item.income_category.name if item.income_category else None,
    }


@login_required
@require_GET
def api_product_list(request):
    """JSON API for products/services list."""
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    kind = request.GET.get("kind", "all").lower()
    status = request.GET.get("status", "active").lower()
    search_query = request.GET.get("q", "").strip()

    qs = Item.objects.filter(business=business).select_related("income_category")

    if kind == "product":
        qs = qs.filter(type=Item.ItemType.PRODUCT)
    elif kind == "service":
        qs = qs.filter(type=Item.ItemType.SERVICE)

    if status == "active":
        qs = qs.filter(is_archived=False)
    elif status == "archived":
        qs = qs.filter(is_archived=True)

    if search_query:
        qs = qs.filter(Q(name__icontains=search_query) | Q(sku__icontains=search_query))

    items = list(qs.order_by("name")[:100])
    
    # Stats
    all_items = Item.objects.filter(business=business, is_archived=False)
    active_count = all_items.count()
    product_count = all_items.filter(type=Item.ItemType.PRODUCT).count()
    service_count = all_items.filter(type=Item.ItemType.SERVICE).count()

    return JsonResponse({
        "items": [_serialize_item(i) for i in items],
        "stats": {
            "active_count": active_count,
            "product_count": product_count,
            "service_count": service_count,
        },
        "currency": business.currency,
        "type_choices": [{"value": c[0], "label": c[1]} for c in Item.ItemType.choices],
    })


# ─────────────────────────────────────────────────────────────────────────────
#    Journal Entries API
# ─────────────────────────────────────────────────────────────────────────────

def _serialize_journal_line(line: JournalLine) -> dict:
    """Serialize a JournalLine for JSON response."""
    return {
        "id": line.id,
        "account_id": line.account_id,
        "account_name": line.account.name if line.account else None,
        "account_code": line.account.code if line.account else None,
        "debit": str(line.debit),
        "credit": str(line.credit),
        "description": line.description,
    }


def _serialize_journal_entry(entry: JournalEntry) -> dict:
    """Serialize a JournalEntry for JSON response."""
    source_type = None
    source_label = None
    if entry.source_content_type:
        source_type = entry.source_content_type.model
        source_label = source_type.title()
    
    # Calculate totals from lines
    total_debit = sum(line.debit for line in entry.lines.all())
    total_credit = sum(line.credit for line in entry.lines.all())
    
    return {
        "id": entry.id,
        "date": entry.date.isoformat(),
        "description": entry.description,
        "is_void": entry.is_void,
        "source_type": source_type,
        "source_label": source_label,
        "source_object_id": entry.source_object_id,
        "total_debit": str(total_debit),
        "total_credit": str(total_credit),
        "lines": [_serialize_journal_line(line) for line in entry.lines.all()],
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


@login_required
@require_GET
def api_journal_entry_list(request):
    """JSON API for journal entries list."""
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)

    # Date filtering
    start_param = request.GET.get("start")
    end_param = request.GET.get("end")
    start_date = parse_date(start_param) if start_param else None
    end_date = parse_date(end_param) if end_param else None

    # Search
    search_query = request.GET.get("q", "").strip()
    
    # Source type filter
    source_filter = request.GET.get("source", "all").lower()
    
    # Show void entries?
    show_void = request.GET.get("show_void", "false").lower() == "true"

    qs = (
        JournalEntry.objects.filter(business=business)
        .select_related("source_content_type")
        .prefetch_related("lines", "lines__account")
    )

    if start_date:
        qs = qs.filter(date__gte=start_date)
    if end_date:
        qs = qs.filter(date__lte=end_date)

    if search_query:
        qs = qs.filter(description__icontains=search_query)

    if not show_void:
        qs = qs.filter(is_void=False)

    if source_filter != "all":
        from django.contrib.contenttypes.models import ContentType
        try:
            ct = ContentType.objects.get(model=source_filter)
            qs = qs.filter(source_content_type=ct)
        except ContentType.DoesNotExist:
            pass

    qs = qs.order_by("-date", "-id")
    entries = list(qs[:200])

    # Stats
    today = timezone.localdate()
    year = today.year
    month_start = today.replace(day=1)

    all_entries = JournalEntry.objects.filter(business=business, is_void=False)
    total_entries = all_entries.count()
    ytd_entries = all_entries.filter(date__year=year).count()
    mtd_entries = all_entries.filter(date__gte=month_start).count()

    # Get unique source types for filter dropdown
    source_types = (
        JournalEntry.objects.filter(business=business, source_content_type__isnull=False)
        .values_list("source_content_type__model", flat=True)
        .distinct()
    )
    source_choices = [{"value": s, "label": s.title()} for s in source_types if s]

    return JsonResponse({
        "entries": [_serialize_journal_entry(e) for e in entries],
        "stats": {
            "total_entries": total_entries,
            "ytd_entries": ytd_entries,
            "mtd_entries": mtd_entries,
        },
        "source_choices": source_choices,
        "currency": business.currency,
    })
