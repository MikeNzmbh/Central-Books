import csv
import hashlib
import io
import json
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction as db_transaction
from django.db.models import Count, Max, Q, Sum, Avg
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.forms import ModelChoiceField
from typing import cast
from django.views.decorators.http import require_POST
from django.views.generic import ListView, TemplateView, CreateView, UpdateView, View
from django.urls import reverse, reverse_lazy
from django.utils.dateparse import parse_date

from .forms import (
    BusinessForm,
    CategoryForm,
    CustomerForm,
    ExpenseForm,
    InvoiceForm,
    SignupForm,
    SupplierForm,
    ItemForm,
    BankStatementImportForm,
    BankQuickExpenseForm,
    BankAccountForm,
    BankMatchInvoiceForm,
)
from .models import (
    Account,
    Category,
    Customer,
    Expense,
    Invoice,
    Supplier,
    Item,
    JournalEntry,
    JournalLine,
    BankAccount,
    BankStatementImport,
    BankTransaction,
)
from .ledger_services import compute_ledger_pl
from .ledger_reports import account_balances_for_business
from .utils import get_current_business
from .accounting_posting_expenses import post_expense_paid
from .accounting_defaults import ensure_default_accounts
from .reconciliation import (
    Allocation,
    add_bank_match,
    allocate_bank_transaction,
    recompute_bank_transaction_status,
)


def _first_day_of_month(d: date) -> date:
    return d.replace(day=1)


def _add_months(d: date, months: int) -> date:
    month_index = (d.month - 1) + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _get_period_dates(period: str) -> tuple[date, date, str, str]:
    """
    Returns (start_date, end_date, label, normalized_period) for the requested period key.
    """
    today = timezone.localdate()

    if period == "last_month":
        first_of_this_month = today.replace(day=1)
        end_date = first_of_this_month - timedelta(days=1)
        start_date = end_date.replace(day=1)
        label = f"Last month · {start_date:%b %d, %Y} – {end_date:%b %d, %Y}"
        normalized = "last_month"
    elif period == "this_year":
        start_date = today.replace(month=1, day=1)
        end_date = today
        label = f"This year · {start_date:%b %d, %Y} – {end_date:%b %d, %Y}"
        normalized = "this_year"
    else:
        start_date = today.replace(day=1)
        if start_date.month == 12:
            next_month = start_date.replace(year=start_date.year + 1, month=1, day=1)
        else:
            next_month = start_date.replace(month=start_date.month + 1, day=1)
        end_date = min(today, next_month - timedelta(days=1))
        label = f"This month · {start_date:%b %d, %Y} – {end_date:%b %d, %Y}"
        normalized = "this_month"

    return start_date, end_date, label, normalized


def _generate_external_id(bank_account_id: int, date_str: str, description: str, amount_str: str) -> str:
    raw = f"{bank_account_id}|{date_str}|{description}|{amount_str}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _parse_import_date(value: str | None):
    candidate = (value or "").strip()
    if not candidate:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue
    return parse_date(candidate)


def _build_transaction_suggestions(transactions, business):
    """
    Return mapping of transaction id -> suggested expenses/invoices for quick matching.
    """
    cutoff_date = timezone.localdate() - timedelta(days=60)
    prefetched_expenses = list(
        Expense.objects.filter(
            business=business,
            status__in=[Expense.Status.UNPAID, Expense.Status.PARTIAL],
            date__gte=cutoff_date,
        ).order_by("-date")[:100]
    )
    expense_map = {}
    invoice_map = {}
    tolerance = Decimal("5.00")
    date_window = 15

    for tx in transactions:
        if tx.amount < 0:
            amount = abs(tx.amount)
            lower = max(Decimal("0.00"), amount - tolerance)
            upper = amount + tolerance
            start = tx.date - timedelta(days=date_window)
            end = tx.date + timedelta(days=date_window)
            matches = [
                exp
                for exp in prefetched_expenses
                if start <= exp.date <= end
                and lower <= (exp.grand_total or (exp.amount or Decimal("0.00"))) <= upper
            ][:8]
            expense_map[tx.id] = matches
        elif tx.amount > 0:
            matches = list(
                Invoice.objects.filter(
                    business=business,
                    status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL],
                    grand_total=tx.amount,
                )
                .select_related("customer")
                .order_by("-issue_date")[:5]
            )
            invoice_map[tx.id] = matches
    return expense_map, invoice_map


def _json_from_body(request):
    try:
        raw = request.body.decode("utf-8")
    except (AttributeError, UnicodeDecodeError):
        return {}
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _get_bank_tx_for_business(business, tx_id, *, for_update=False):
    qs = BankTransaction.objects.filter(
        pk=tx_id,
        bank_account__business=business,
    ).select_related("bank_account", "bank_account__account")
    if for_update:
        qs = qs.select_for_update()
    return qs.first()


def _status_counts_for_account(bank_account: BankAccount):
    return {
        row["status"]: row["count"]
        for row in BankTransaction.objects.filter(bank_account=bank_account)
        .values("status")
        .annotate(count=Count("id"))
    }


def _post_income_entry(business, bank_account, category, amount: Decimal, description: str, tx_date):
    defaults = ensure_default_accounts(business)
    cash_account = bank_account.account or defaults.get("cash")
    if cash_account is None:
        raise ValueError(
            "Link this bank account to a ledger account or configure a default cash account."
        )

    income_account = category.account or defaults.get("sales")
    if income_account is None:
        raise ValueError("The selected category is not linked to an income account.")

    entry = JournalEntry.objects.create(
        business=business,
        date=tx_date,
        description=(description or "Bank feed income")[:255],
    )
    JournalLine.objects.create(
        journal_entry=entry,
        account=cash_account,
        debit=amount,
        credit=Decimal("0.00"),
        description="Bank feed deposit",
    )
    JournalLine.objects.create(
        journal_entry=entry,
        account=income_account,
        debit=Decimal("0.00"),
        credit=amount,
        description="Income recognition",
    )
    entry.check_balance()
    return entry


def _decimal_from_form(form, field_name: str) -> Decimal:
    bound = form[field_name]
    value = bound.value()
    if value in (None, ""):
        return Decimal("0.00")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def _invoice_preview(form) -> dict:
    amount = _decimal_from_form(form, "total_amount")
    tax = _decimal_from_form(form, "tax_amount")
    return {
        "amount": amount,
        "tax": tax,
        "grand": amount + tax,
    }


def _expense_preview(form) -> dict:
    amount = _decimal_from_form(form, "amount")
    tax = _decimal_from_form(form, "tax_amount")
    return {
        "amount": amount,
        "tax": tax,
        "total": amount + tax,
    }


def signup_view(request):
    if request.method == "POST":
        f = SignupForm(request.POST)
        if f.is_valid():
            user = User.objects.create_user(
                username=f.cleaned_data["username"],
                email=f.cleaned_data["email"],
                password=f.cleaned_data["password"],
            )
            login(request, user)
            return redirect("business_setup")
    else:
        f = SignupForm()
    return render(request, "signup.html", {"form": f})


def login_view(request):
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username"),
            password=request.POST.get("password"),
        )
        if user:
            login(request, user)
            if get_current_business(user) is None:
                return redirect("business_setup")
            return redirect("dashboard")
        messages.error(request, "Invalid credentials")
    return render(request, "login.html")


@require_POST
@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def business_setup(request):
    existing = get_current_business(request.user)
    if existing is not None:
        return redirect("dashboard")
    if request.method == "POST":
        form = BusinessForm(request.POST, user=request.user)
        if form.is_valid():
            business = form.save(commit=False)
            business.owner_user = request.user
            business.save()
            return redirect("dashboard")
    else:
        form = BusinessForm(user=request.user)
    return render(request, "business_setup.html", {"form": form})


@login_required
def dashboard(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")
    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)

    invoices_qs = Invoice.objects.filter(business=business)
    expenses_all_qs = Expense.objects.filter(business=business)
    expenses_qs = expenses_all_qs.filter(status=Expense.Status.PAID)

    month_start = _first_day_of_month(today)
    next_month_start = _add_months(month_start, 1)
    month_end = next_month_start - timedelta(days=1)

    total_income_month = (
        invoices_qs.filter(
            status=Invoice.Status.PAID,
            issue_date__gte=month_start,
            issue_date__lte=month_end,
        ).aggregate(total=Sum("net_total"))["total"]
        or Decimal("0")
    )
    total_expenses_month = (
        expenses_qs.filter(date__gte=month_start, date__lte=month_end).aggregate(total=Sum("net_total"))["total"]
        or Decimal("0")
    )
    net_income_month = total_income_month - total_expenses_month

    def month_expense_for_category(category_name: str) -> Decimal:
        return (
            expenses_qs.filter(
                date__gte=month_start,
                date__lte=month_end,
                category__name__iexact=category_name,
            ).aggregate(total=Sum("net_total"))["total"]
            or Decimal("0")
        )

    subscriptions_month = month_expense_for_category("Subscriptions")
    taxes_month = month_expense_for_category("Taxes")

    category_grand_total = total_income_month + subscriptions_month + taxes_month
    if category_grand_total > 0:
        revenue_share_percent = float(total_income_month / category_grand_total * 100)
        subscriptions_share_percent = float(subscriptions_month / category_grand_total * 100)
        taxes_share_percent = float(taxes_month / category_grand_total * 100)
    else:
        revenue_share_percent = subscriptions_share_percent = taxes_share_percent = 0.0

    has_any_invoices = invoices_qs.exists()
    has_any_expenses = expenses_all_qs.exists()
    has_any_data = has_any_invoices or has_any_expenses

    overdue_qs = invoices_qs.filter(status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL], due_date__lt=today)
    overdue_total = overdue_qs.aggregate(total=Sum("grand_total"))["total"] or Decimal("0")
    overdue_count = overdue_qs.count()

    draft_qs = invoices_qs.filter(status=Invoice.Status.DRAFT)
    draft_total = draft_qs.aggregate(total=Sum("grand_total"))["total"] or Decimal("0")
    draft_count = draft_qs.count()

    revenue_30 = (
        invoices_qs.filter(status=Invoice.Status.PAID, issue_date__gte=thirty_days_ago).aggregate(
            total=Sum("net_total")
        )["total"]
        or Decimal("0")
    )
    expenses_30 = (
        expenses_qs.filter(date__gte=thirty_days_ago).aggregate(total=Sum("net_total"))["total"]
        or Decimal("0")
    )

    labels = []
    income_series = []
    expense_series = []
    current_month_start = _first_day_of_month(today)
    start_month = _add_months(current_month_start, -5)

    for i in range(6):
        month_start = _add_months(start_month, i)
        next_month_start = _add_months(month_start, 1)
        month_end = next_month_start - timedelta(days=1)

        labels.append(month_start.strftime("%b %Y"))

        month_income = (
            invoices_qs.filter(
                status=Invoice.Status.PAID,
                issue_date__gte=month_start,
                issue_date__lte=month_end,
            ).aggregate(total=Sum("net_total"))["total"]
            or Decimal("0")
        )
        month_expenses = (
            expenses_qs.filter(date__gte=month_start, date__lte=month_end).aggregate(total=Sum("net_total"))[
                "total"
            ]
            or Decimal("0")
        )

        income_series.append(float(month_income))
        expense_series.append(float(month_expenses))

    expense_by_cat_qs = (
        expenses_qs.filter(date__gte=month_start, date__lte=month_end)
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )

    mix_labels = []
    mix_values = []

    mix_labels = []
    mix_values = []
    if total_income_month > 0:
        mix_labels.append("Revenue")
        mix_values.append(float(total_income_month))
    for row in expense_by_cat_qs[:5]:
        name = row["category__name"] or "Uncategorized"
        mix_labels.append(name)
        mix_values.append(float(row["total"] or 0))

    total_mix = sum(mix_values)
    if total_mix > 0:
        mix_percentages = [round(value * 100 / total_mix, 1) for value in mix_values]
    else:
        mix_percentages = [0 for _ in mix_values]
    mix_breakdown = [
        {"label": label, "value": value, "percent": percent}
        for label, value, percent in zip(mix_labels, mix_values, mix_percentages)
    ]

    total_mix_month = total_income_month + subscriptions_month + taxes_month
    if total_mix_month > 0:
        revenue_share_percent = float(total_income_month / total_mix_month * 100)
        subscriptions_share_percent = float(subscriptions_month / total_mix_month * 100)
        taxes_share_percent = float(taxes_month / total_mix_month * 100)
    else:
        revenue_share_percent = subscriptions_share_percent = taxes_share_percent = 0.0

    expense_summary = [
        {"name": row["category__name"] or "Uncategorized", "total": row["total"]}
        for row in expense_by_cat_qs[:4]
    ]

    recent_invoices = invoices_qs.select_related("customer").order_by("-issue_date")[:5]
    recent_customers = Customer.objects.filter(business=business).order_by("-created_at")[:5]
    recent_suppliers = Supplier.objects.filter(business=business).order_by("-created_at")[:5]

    unpaid_expenses_total = (
        expenses_all_qs.filter(status__in=[Expense.Status.UNPAID, Expense.Status.PARTIAL]).aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )

    context = {
        "business": business,
        "has_any_data": has_any_data,
        "has_any_invoices": has_any_invoices,
        "has_any_expenses": has_any_expenses,
        "metrics": {
            "overdue_total": overdue_total,
            "overdue_count": overdue_count,
            "draft_total": draft_total,
            "draft_count": draft_count,
            "revenue_30": revenue_30,
            "expenses_30": expenses_30,
            "unpaid_expenses_total": unpaid_expenses_total,
            "total_income_month": total_income_month,
            "total_expenses_month": total_expenses_month,
            "net_income_month": net_income_month,
        },
        "recent_invoices": recent_invoices,
        "recent_customers": recent_customers,
        "recent_suppliers": recent_suppliers,
        "expense_summary": expense_summary,
        "categories": Category.objects.filter(business=business).order_by("name")[:8],
        "chart_cashflow_labels": json.dumps(labels),
        "chart_cashflow_income": json.dumps(income_series),
        "chart_cashflow_expenses": json.dumps(expense_series),
        "chart_mix_labels": json.dumps(mix_labels),
        "chart_mix_values": json.dumps(mix_values),
        "mix_breakdown": mix_breakdown,
        "mix_chart_has_data": bool(mix_labels),
        "revenue_share_percent": revenue_share_percent,
        "subscriptions_share_percent": subscriptions_share_percent,
        "taxes_share_percent": taxes_share_percent,
        "revenue_month": total_income_month,
        "subscriptions_month": subscriptions_month,
        "taxes_month": taxes_month,
    }
    return render(request, "dashboard.html", context)


class CustomerListView(LoginRequiredMixin, ListView):
    model = Customer
    template_name = "core/customers.html"
    context_object_name = "customers"

    def dispatch(self, request, *args, **kwargs):
        self.business = get_current_business(request.user)
        if self.business is None:
            return redirect("business_setup")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        status_filter = self.request.GET.get("status", "active")
        search_query = self.request.GET.get("q", "").strip()
        self.status_filter = status_filter
        self.search_query = search_query

        qs = Customer.objects.filter(business=self.business)

        if status_filter == "active":
            qs = qs.filter(is_active=True)
        elif status_filter == "archived":
            qs = qs.filter(is_active=False)

        if search_query:
            qs = qs.filter(
                Q(name__icontains=search_query)
                | Q(email__icontains=search_query)
                | Q(phone__icontains=search_query)
            )

        today = timezone.localdate()
        year = today.year
        month_start = today.replace(day=1)

        qs = qs.annotate(
            open_balance=Sum(
                "invoices__grand_total",
                filter=Q(invoices__status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL, Invoice.Status.DRAFT]),
            ),
            ytd_revenue=Sum(
                "invoices__net_total",
                filter=Q(
                    invoices__status=Invoice.Status.PAID,
                    invoices__issue_date__year=year,
                ),
            ),
            mtd_revenue=Sum(
                "invoices__net_total",
                filter=Q(
                    invoices__status=Invoice.Status.PAID,
                    invoices__issue_date__gte=month_start,
                ),
            ),
            last_invoice_date=Max("invoices__issue_date"),
        )

        self.today = today
        return qs.order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customers = list(context["customers"])
        context["customers"] = customers

        total_customers = len(customers)
        total_ytd = sum((customer.ytd_revenue or Decimal("0")) for customer in customers)
        total_mtd = sum((customer.mtd_revenue or Decimal("0")) for customer in customers)
        avg_per_customer = (
            (total_ytd / Decimal(total_customers)) if total_customers else Decimal("0")
        )

        selected_id = self.request.GET.get("customer")
        selected_customer = None
        if selected_id:
            for customer in customers:
                if str(customer.pk) == selected_id:
                    selected_customer = customer
                    break
        if not selected_customer and customers:
            selected_customer = customers[0]

        ytd_percent = 0
        mtd_percent = 0
        months_so_far = self.today.month or 1
        avg_monthly_selected = Decimal("0")

        if selected_customer:
            selected_ytd = selected_customer.ytd_revenue or Decimal("0")
            selected_mtd = selected_customer.mtd_revenue or Decimal("0")
            if total_ytd > 0:
                ytd_percent = int(
                    (selected_ytd / total_ytd * Decimal("100")).quantize(Decimal("1"))
                )
            if total_mtd > 0:
                mtd_percent = int(
                    (selected_mtd / total_mtd * Decimal("100")).quantize(Decimal("1"))
                )
            avg_monthly_selected = (
                selected_ytd / Decimal(months_so_far)
            ).quantize(Decimal("0.01")) if selected_ytd else Decimal("0")

        context.update(
            {
                "business": self.business,
                "status": self.status_filter,
                "search_q": self.search_query,
                "total_customers": total_customers,
                "total_ytd": total_ytd,
                "total_mtd": total_mtd,
                "avg_per_customer": avg_per_customer,
                "selected_customer": selected_customer,
                "ytd_percent": ytd_percent,
                "mtd_percent": mtd_percent,
                "avg_monthly_selected": avg_monthly_selected,
            }
        )
        return context


class InvoiceListView(LoginRequiredMixin, TemplateView):
    template_name = "core/invoices.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        business = get_current_business(self.request.user)
        if business is None:
            ctx["invoices"] = []
            return ctx

        base_qs = (
            Invoice.objects.filter(business=business)
            .select_related("customer")
        )

        start_param = self.request.GET.get("start")
        end_param = self.request.GET.get("end")
        start_date = parse_date(start_param) if start_param else None
        end_date = parse_date(end_param) if end_param else None

        if start_date:
            base_qs = base_qs.filter(issue_date__gte=start_date)
        if end_date:
            base_qs = base_qs.filter(issue_date__lte=end_date)

        status_param = self.request.GET.get("status", "all").lower()
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

        open_balance_total = (
            base_qs.filter(status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL])
            .aggregate(total=Sum("grand_total"))["total"]
            or Decimal("0")
        )

        current_year = today.year
        revenue_ytd = (
            base_qs.filter(
                status=Invoice.Status.PAID,
                issue_date__year=current_year,
            )
            .aggregate(total=Sum("net_total"))["total"]
            or Decimal("0")
        )

        total_invoices = base_qs.count()
        total_amount_all = (
            base_qs.aggregate(total=Sum("net_total"))["total"]
            or Decimal("0")
        )
        avg_invoice_value = (
            (total_amount_all / total_invoices)
            if total_invoices > 0
            else Decimal("0")
        )

        selected_invoice_id = self.request.GET.get("invoice")
        selected_invoice = None
        if selected_invoice_id:
            try:
                selected_invoice = base_qs.get(pk=selected_invoice_id)
            except Invoice.DoesNotExist:
                selected_invoice = None

        ctx.update(
            {
                "business": business,
                "invoices": invoices,
                "status_filter": status_param,
                "open_balance_total": open_balance_total,
                "revenue_ytd": revenue_ytd,
                "total_invoices": total_invoices,
                "avg_invoice_value": avg_invoice_value,
                "selected_invoice": selected_invoice,
                "today": today,
                "invoice_status_choices": Invoice.Status.choices,
            }
        )
        return ctx


class ExpenseListView(LoginRequiredMixin, TemplateView):
    template_name = "core/expenses.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        business = get_current_business(self.request.user)
        if business is None:
            ctx["expenses"] = []
            return ctx

        base_qs = (
            Expense.objects.filter(business=business)
            .select_related("supplier", "category")
        )

        status_filter = self.request.GET.get("status", "all").lower()
        if status_filter == "paid":
            base_qs = base_qs.filter(status=Expense.Status.PAID)
        elif status_filter == "unpaid":
            base_qs = base_qs.filter(status__in=[Expense.Status.UNPAID, Expense.Status.PARTIAL])
        else:
            status_filter = "all"

        start_param = self.request.GET.get("start")
        end_param = self.request.GET.get("end")
        start_date = parse_date(start_param) if start_param else None
        end_date = parse_date(end_param) if end_param else None
        custom_range = bool(start_date or end_date)
        if start_date:
            base_qs = base_qs.filter(date__gte=start_date)
        if end_date:
            base_qs = base_qs.filter(date__lte=end_date)
        paid_base_qs = base_qs.filter(status=Expense.Status.PAID)

        category_param = self.request.GET.get("category")
        category_filter = None
        if category_param:
            try:
                category_filter = int(category_param)
                base_qs = base_qs.filter(category_id=category_filter)
            except (TypeError, ValueError):
                category_filter = None

        period = self.request.GET.get("period", "this_month").lower()
        today = timezone.localdate()

        def this_month_qs(qs):
            return qs.filter(date__year=today.year, date__month=today.month)

        def last_month_qs(qs):
            if today.month == 1:
                prev_year = today.year - 1
                prev_month = 12
            else:
                prev_year = today.year
                prev_month = today.month - 1
            return qs.filter(date__year=prev_year, date__month=prev_month)

        def this_year_qs(qs):
            return qs.filter(date__year=today.year)

        def last_year_qs(qs):
            return qs.filter(date__year=today.year - 1)

        if custom_range:
            expenses = base_qs
            period = "custom"
        elif period == "last_month":
            expenses = last_month_qs(base_qs)
        elif period == "this_year":
            expenses = this_year_qs(base_qs)
        elif period == "last_year":
            expenses = last_year_qs(base_qs)
        elif period == "all":
            expenses = base_qs
        else:
            period = "this_month"
            expenses = this_month_qs(base_qs)

        expenses = expenses.order_by("-date", "-id")

        expenses_ytd = (
            this_year_qs(paid_base_qs).aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )
        expenses_month = (
            this_month_qs(paid_base_qs).aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )
        total_transactions = paid_base_qs.count()
        total_all = (
            paid_base_qs.aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )
        avg_expense = (
            (total_all / total_transactions) if total_transactions else Decimal("0")
        )
        total_filtered = (
            expenses.aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )

        filtered_for_selection = expenses
        selected_expense = None
        selected_expense_id = self.request.GET.get("expense")
        if selected_expense_id:
            try:
                selected_expense = filtered_for_selection.select_related("supplier", "category").get(
                    pk=selected_expense_id
                )
            except Expense.DoesNotExist:
                selected_expense = None

        categories = Category.objects.filter(
            business=business,
            type=Category.CategoryType.EXPENSE,
        ).order_by("name")

        ctx.update(
            {
                "business": business,
                "expenses": expenses,
                "period": period,
                "categories": categories,
                "category_filter": category_filter,
                "expense_total_ytd": expenses_ytd,
                "expense_total_month": expenses_month,
                "expense_total_all": total_all,
                "avg_expense": avg_expense,
                "total_filtered": total_filtered,
                "selected_expense": selected_expense,
                "today": today,
                "status_filter": status_filter,
                "expense_status_choices": Expense.Status.choices,
            }
        )
        return ctx


class ProductServiceListView(LoginRequiredMixin, TemplateView):
    template_name = "core/products.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        business = get_current_business(self.request.user)
        if business is None:
            ctx.update(
                {
                    "business": None,
                    "items": [],
                    "active_count": 0,
                    "product_count": 0,
                    "service_count": 0,
                    "filter_kind": "all",
                    "filter_status": "active",
                    "search_query": "",
                    "currency": "",
                }
            )
            return ctx

        base_qs = Item.objects.filter(business=business)
        currency = business.currency

        kind = self.request.GET.get("kind", "all").lower()
        status = self.request.GET.get("status", "active").lower()
        search_query = self.request.GET.get("q", "").strip()

        qs = base_qs
        if kind == "product":
            qs = qs.filter(type=Item.ItemType.PRODUCT)
        elif kind == "service":
            qs = qs.filter(type=Item.ItemType.SERVICE)
        else:
            kind = "all"

        if status == "active":
            qs = qs.filter(is_archived=False)
        elif status == "archived":
            qs = qs.filter(is_archived=True)
        else:
            status = "all"

        if search_query:
            qs = qs.filter(
                Q(name__icontains=search_query)
                | Q(sku__icontains=search_query)
            )

        items = qs.order_by("name").select_related("income_category")

        ctx.update(
            business=business,
            active_count=base_qs.filter(is_archived=False).count(),
            product_count=base_qs.filter(
                type=Item.ItemType.PRODUCT, is_archived=False
            ).count(),
            service_count=base_qs.filter(
                type=Item.ItemType.SERVICE, is_archived=False
            ).count(),
            items=items,
            filter_kind=kind,
            filter_status=status,
            search_query=search_query,
            currency=currency,
        )
        return ctx


class ItemCreateView(LoginRequiredMixin, CreateView):
    model = Item
    form_class = ItemForm
    template_name = "core/item_form.html"
    success_url = reverse_lazy("product_list")

    def dispatch(self, request, *args, **kwargs):
        self.business = get_current_business(request.user)
        if self.business is None:
            return redirect("business_setup")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["business"] = self.business
        return kwargs

    def form_valid(self, form):
        form.instance.business = self.business
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["business"] = self.business
        return ctx


class ItemUpdateView(LoginRequiredMixin, UpdateView):
    model = Item
    form_class = ItemForm
    template_name = "core/item_form.html"
    success_url = reverse_lazy("product_list")

    def dispatch(self, request, *args, **kwargs):
        self.business = get_current_business(request.user)
        if self.business is None:
            return redirect("business_setup")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Item.objects.filter(business=self.business)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["business"] = self.business
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["business"] = self.business
        return ctx


class SuppliersView(LoginRequiredMixin, TemplateView):
    template_name = "core/suppliers.html"

    def dispatch(self, request, *args, **kwargs):
        self.business = get_current_business(request.user)
        if self.business is None:
            return redirect("business_setup")
        return super().dispatch(request, *args, **kwargs)

    @staticmethod
    def _initials(name: str) -> str:
        if not name:
            return "??"
        parts = [part for part in name.replace("-", " ").split(" ") if part]
        if not parts:
            return (name[:2] or "MB").upper()
        return "".join([part[0].upper() for part in parts[:2]])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        business = self.business
        today = timezone.localdate()
        start_of_year = today.replace(month=1, day=1)
        start_of_month = today.replace(day=1)

        suppliers_qs = (
            Supplier.objects.filter(business=business)
            .order_by("name")
            .prefetch_related("expenses__category")
        )
        suppliers = list(suppliers_qs)

        total_ytd = Decimal("0")
        total_mtd = Decimal("0")
        total_open_balance = Decimal("0")
        months_so_far = today.month or 1

        for supplier in suppliers:
            expenses_all_qs = supplier.expenses.all()
            paid_expenses_qs = expenses_all_qs.filter(status=Expense.Status.PAID)
            ytd = (
                paid_expenses_qs.filter(date__gte=start_of_year, date__lte=today)
                .aggregate(total=Sum("amount"))
                .get("total")
                or Decimal("0")
            )
            mtd = (
                paid_expenses_qs.filter(date__gte=start_of_month, date__lte=today)
                .aggregate(total=Sum("amount"))
                .get("total")
                or Decimal("0")
            )
            default_category = (
                expenses_all_qs.filter(category__isnull=False)
                .order_by("-date")
                .values_list("category__name", flat=True)
                .first()
            )
            open_balance = (
                expenses_all_qs.filter(status__in=[Expense.Status.UNPAID, Expense.Status.PARTIAL])
                .aggregate(total=Sum("amount"))
                .get("total")
                or Decimal("0")
            )

            supplier._ytd_spend_cache = ytd
            supplier.mtd_spend = mtd
            supplier.default_category_name = default_category
            supplier.initials = self._initials(supplier.name)
            supplier.open_balance = open_balance

            total_ytd += ytd
            total_mtd += mtd
            total_open_balance += open_balance

        supplier_lookup = {supplier.pk: supplier for supplier in suppliers}
        supplier_id = self.request.GET.get("supplier")
        selected_supplier = None
        if supplier_id:
            try:
                selected_supplier = supplier_lookup.get(int(supplier_id))
            except (TypeError, ValueError):
                selected_supplier = None

        if not selected_supplier and suppliers:
            selected_supplier = suppliers[0]

        ytd_percent = 0
        mtd_percent = 0
        if selected_supplier and total_ytd > 0:
            ytd_percent = int(
                (selected_supplier.ytd_spend / total_ytd * Decimal("100")).quantize(Decimal("1"))
            )
        if selected_supplier and total_mtd > 0:
            mtd_percent = int(
                (selected_supplier.mtd_spend / total_mtd * Decimal("100")).quantize(Decimal("1"))
            )

        avg_monthly_selected = Decimal("0")
        if selected_supplier and months_so_far > 0:
            avg_monthly_selected = (
                selected_supplier.ytd_spend / Decimal(months_so_far)
            ).quantize(Decimal("0.01"))

        context.update(
            {
                "suppliers": suppliers,
                "selected_supplier": selected_supplier,
                "total_suppliers": len(suppliers),
                "total_ytd": total_ytd,
                "total_mtd": total_mtd,
                "total_open_balance": total_open_balance,
                "avg_per_supplier": (total_ytd / Decimal(len(suppliers))) if suppliers else Decimal("0"),
                "ytd_percent": ytd_percent,
                "mtd_percent": mtd_percent,
                "avg_monthly_selected": avg_monthly_selected,
            }
        )
        return context


@login_required
def customer_create(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    if request.method == "POST":
        form = CustomerForm(request.POST, business=business)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.business = business
            customer.save()
            return redirect("customer_list")
    else:
        form = CustomerForm(business=business)

    return render(
        request,
        "core/customers/customer_form.html",
        {"business": business, "form": form, "customer": None},
    )


@login_required
def customer_update(request, pk):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    customer = get_object_or_404(Customer, pk=pk, business=business)
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer, business=business)
        if form.is_valid():
            form.save()
            return redirect("customer_list")
    else:
        form = CustomerForm(instance=customer, business=business)
    return render(
        request,
        "core/customers/customer_form.html",
        {"business": business, "form": form, "customer": customer},
    )


@login_required
def customer_delete(request, pk):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    customer = get_object_or_404(Customer, pk=pk, business=business)
    if request.method == "POST":
        customer.delete()
        return redirect("customer_list")
    return render(
        request,
        "confirm_delete.html",
        {
            "business": business,
            "object": customer,
            "object_type": "customer",
            "cancel_url": "customer_list",
        },
    )


@login_required
def supplier_create(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    if request.method == "POST":
        form = SupplierForm(request.POST, business=business)
        if form.is_valid():
            supplier = form.save(commit=False)
            supplier.business = business
            supplier.save()
            return redirect("suppliers")
    else:
        form = SupplierForm(business=business)
    return render(
        request,
        "core/suppliers/supplier_form.html",
        {"business": business, "form": form, "supplier": None},
    )


@login_required
def supplier_update(request, pk):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    supplier = get_object_or_404(Supplier, pk=pk, business=business)
    if request.method == "POST":
        form = SupplierForm(request.POST, instance=supplier, business=business)
        if form.is_valid():
            form.save()
            return redirect("suppliers")
    else:
        form = SupplierForm(instance=supplier, business=business)
    return render(
        request,
        "core/suppliers/supplier_form.html",
        {"business": business, "form": form, "supplier": supplier},
    )


@login_required
def supplier_delete(request, pk):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    supplier = get_object_or_404(Supplier, pk=pk, business=business)
    if request.method == "POST":
        supplier.delete()
        return redirect("suppliers")
    return render(
        request,
        "confirm_delete.html",
        {
            "business": business,
            "object": supplier,
            "object_type": "supplier",
            "cancel_url": "suppliers",
        },
    )


@login_required
def category_list(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    category_type = request.GET.get("type", "EXPENSE")
    status = request.GET.get("status", "active")
    search_query = request.GET.get("q", "").strip()

    qs = Category.objects.filter(business=business, type=category_type)
    if status == "archived":
        qs = qs.filter(is_archived=True)
    else:
        qs = qs.filter(is_archived=False)

    if search_query:
        qs = qs.filter(Q(name__icontains=search_query) | Q(pk__icontains=search_query))

    qs = qs.annotate(usage_count=Count("expenses")).order_by("name")

    active_expense_count = Category.objects.filter(
        business=business, type="EXPENSE", is_archived=False
    ).count()
    active_income_count = Category.objects.filter(
        business=business, type="INCOME", is_archived=False
    ).count()

    context = {
        "business": business,
        "category_type": category_type,
        "status": status,
        "search_query": search_query,
        "categories": qs,
        "active_expense_count": active_expense_count,
        "active_income_count": active_income_count,
    }
    return render(request, "core/categories.html", context)


@login_required
def category_create(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    if request.method == "POST":
        form = CategoryForm(request.POST, business=business)
        if form.is_valid():
            category = form.save(commit=False)
            category.business = business
            category.save()
            return redirect("category_list")
    else:
        form = CategoryForm(business=business)
    return render(
        request,
        "category_form.html",
        {"business": business, "form": form, "category": None},
    )


@login_required
def category_update(request, pk):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    category = get_object_or_404(Category, pk=pk, business=business)
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category, business=business)
        if form.is_valid():
            form.save()
            return redirect("category_list")
    else:
        form = CategoryForm(instance=category, business=business)
    return render(
        request,
        "category_form.html",
        {"business": business, "form": form, "category": category},
    )


@login_required
def category_delete(request, pk):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    category = get_object_or_404(Category, pk=pk, business=business)
    if request.method == "POST":
        usage_count = Expense.objects.filter(business=business, category=category).count()
        if usage_count > 0:
            messages.error(
                request,
                f"Category “{category.name}” is used by {usage_count} expense(s). Archive it instead.",
            )
        else:
            category.delete()
            messages.success(request, f'Category "{category.name}" deleted.')
        return redirect("category_list")
    return render(
        request,
        "confirm_delete.html",
        {
            "business": business,
            "object": category,
            "object_type": "category",
            "cancel_url": "category_list",
        },
    )


@login_required
def category_archive(request, pk):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")
    category = get_object_or_404(Category, pk=pk, business=business)
    if request.method == "POST":
        category.is_archived = True
        category.save()
        messages.success(request, f'Category "{category.name}" archived.')
    return redirect("category_list")


@login_required
def category_restore(request, pk):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")
    category = get_object_or_404(Category, pk=pk, business=business)
    if request.method == "POST":
        category.is_archived = False
        category.save()
        messages.success(request, f'Category "{category.name}" restored.')
    return redirect("category_list")


@login_required
def invoice_create(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    if request.method == "POST":
        form = InvoiceForm(request.POST, business=business)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.business = business
            invoice.save()
            return redirect("invoice_list")
    else:
        form = InvoiceForm(business=business)
    return render(
        request,
        "invoice_form.html",
        {
            "business": business,
            "form": form,
            "invoice": None,
            "invoice_preview": _invoice_preview(form),
        },
    )


@login_required
def invoice_update(request, pk):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    invoice = get_object_or_404(Invoice, pk=pk, business=business)
    if request.method == "POST":
        form = InvoiceForm(request.POST, instance=invoice, business=business)
        if form.is_valid():
            form.save()
            return redirect("invoice_list")
    else:
        form = InvoiceForm(instance=invoice, business=business)
    return render(
        request,
        "invoice_form.html",
        {
            "business": business,
            "form": form,
            "invoice": invoice,
            "invoice_preview": _invoice_preview(form),
        },
    )


@login_required
def invoice_delete(request, pk):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    invoice = get_object_or_404(Invoice, pk=pk, business=business)
    if request.method == "POST":
        invoice.delete()
        return redirect("invoice_list")
    return render(
        request,
        "confirm_delete.html",
        {
            "business": business,
            "object": invoice,
            "object_type": "invoice",
            "cancel_url": "invoice_list",
        },
    )


@login_required
@require_POST
def invoice_status_update(request, pk):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    invoice = get_object_or_404(Invoice, pk=pk, business=business)
    new_status = request.POST.get("status")
    valid_statuses = {choice[0] for choice in Invoice.Status.choices}

    if new_status not in valid_statuses:
        messages.error(request, "Invalid status value.")
    else:
        invoice.status = new_status
        invoice.save()
        messages.success(
            request,
            f'Invoice #{invoice.invoice_number} marked as {invoice.get_status_display()}.',  # type: ignore[attr-defined]
        )

    redirect_url = request.POST.get("redirect_url")
    if redirect_url:
        return redirect(redirect_url)
    return redirect(f"{reverse('invoice_list')}?invoice={invoice.pk}")


@login_required
@require_POST
def expense_status_update(request, pk):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    expense = get_object_or_404(Expense, pk=pk, business=business)
    new_status = request.POST.get("status")
    valid_statuses = {choice[0] for choice in Expense.Status.choices}

    if new_status not in valid_statuses:
        messages.error(request, "Invalid expense status.")
    else:
        if new_status == Expense.Status.PAID:
            expense.mark_paid()
        else:
            expense.mark_unpaid()
        expense.save()
        messages.success(
            request,
            f'Expense for {expense.amount} marked as {expense.get_status_display().lower()}.',  # type: ignore[attr-defined]
        )

    redirect_url = request.POST.get("redirect_url")
    if redirect_url:
        return redirect(redirect_url)
    return redirect(f"{reverse('expense_list')}?expense={expense.pk}")


@login_required
def expense_create(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    if request.method == "POST":
        form = ExpenseForm(request.POST, business=business)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.business = business
            expense.save()
            return redirect("expense_list")
    else:
        form = ExpenseForm(business=business)
    return render(
        request,
        "expense_form.html",
        {
            "business": business,
            "form": form,
            "expense": None,
            "expense_preview": _expense_preview(form),
        },
    )


@login_required
def expense_update(request, pk):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    expense = get_object_or_404(Expense, pk=pk, business=business)
    if request.method == "POST":
        form = ExpenseForm(request.POST, instance=expense, business=business)
        if form.is_valid():
            form.save()
            return redirect("expense_list")
    else:
        form = ExpenseForm(instance=expense, business=business)
    return render(
        request,
        "expense_form.html",
        {
            "business": business,
            "form": form,
            "expense": expense,
            "expense_preview": _expense_preview(form),
        },
    )


@login_required
def expense_delete(request, pk):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    expense = get_object_or_404(Expense, pk=pk, business=business)
    if request.method == "POST":
        expense.delete()
        return redirect("expense_list")
    return render(
        request,
        "confirm_delete.html",
        {
            "business": business,
            "object": expense,
            "object_type": "expense",
            "cancel_url": "expense_list",
        },
    )


@login_required
def journal_entries(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    entries = (
        JournalEntry.objects.filter(business=business)
        .select_related("source_content_type")
        .prefetch_related("lines", "lines__account")
        .order_by("-date", "-id")
    )

    return render(
        request,
        "core/journal_entries.html",
        {"business": business, "entries": entries},
    )


@login_required
def report_pnl(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    period_param = request.GET.get("period", "this_month")
    start_date, end_date, period_label, current_period = _get_period_dates(period_param)

    ledger_pl = compute_ledger_pl(business, start_date, end_date)
    period_length = (end_date - start_date).days + 1
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_length - 1)
    previous_pl = compute_ledger_pl(business, prev_start, prev_end)

    def _change_pct(current, previous):
        if previous in (None, Decimal("0.00")):
            return None
        return ((current - previous) / abs(previous)) * Decimal("100.0")

    prev_income_map = {
        row["account__id"]: row.get("total") or Decimal("0.00")
        for row in previous_pl["income_accounts"]
    }
    prev_expense_map = {
        row["account__id"]: row.get("total") or Decimal("0.00")
        for row in previous_pl["expense_accounts"]
    }

    def _rows_with_drilldown(rows, prev_map, drilldown_kind):
        base_url = reverse("invoice_list") if drilldown_kind == "income" else reverse("expense_list")
        result = []
        for row in rows:
            amount = row.get("total") or Decimal("0.00")
            account_id = row.get("account__id")
            name = row.get("account__name") or row.get("account__code") or "Account"
            prev_amount = prev_map.get(account_id)
            query_params = {
                "account_id": account_id,
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
            }
            drilldown_url = (
                f"{base_url}?{urlencode(query_params)}" if account_id else None
            )
            result.append(
                {
                    "name": name,
                    "amount": amount,
                    "change_pct": _change_pct(amount, prev_amount),
                    "drilldown_url": drilldown_url,
                }
            )
        return result

    income_rows = _rows_with_drilldown(ledger_pl["income_accounts"], prev_income_map, "income")
    expense_rows = _rows_with_drilldown(ledger_pl["expense_accounts"], prev_expense_map, "expense")

    total_income = ledger_pl["total_income"]
    total_expenses = ledger_pl["total_expense"]
    net_profit = ledger_pl["net"]
    total_tax = ledger_pl.get("total_tax", Decimal("0.00"))
    prev_total_income = previous_pl["total_income"]
    prev_total_expenses = previous_pl["total_expense"]
    prev_net_profit = previous_pl["net"]

    period_short_map = {
        "this_month": "month",
        "last_month": "month",
        "this_year": "year",
        "this_quarter": "quarter",
        "ytd": "year",
        "last_year": "year",
        "custom": "period",
    }
    period_short_label = period_short_map.get(current_period, "period")
    net_label = "profit" if net_profit >= 0 else "loss"

    context = {
        "business": business,
        "date_start": start_date,
        "date_end": end_date,
        "start_date": start_date,
        "end_date": end_date,
        "period_label": period_label,
        "current_period": current_period,
        "period_short_label": period_short_label,
        "income_rows": income_rows,
        "expense_rows": expense_rows,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "total_tax": total_tax,
        "net_label": net_label,
        "show_comparison": True,
        "comparison_label": "last period",
        "comparison_short_label": "last period",
        "income_change_pct": _change_pct(total_income, prev_total_income),
        "expenses_change_pct": _change_pct(total_expenses, prev_total_expenses),
        "net_change_pct": _change_pct(net_profit, prev_net_profit),
    }
    return render(request, "reports/pl_ledger.html", context)


@login_required
def pl_shadow_view(request):
    """Alias to keep /reports/pl-shadow/ working during the transition."""

    return report_pnl(request)


@login_required
def bank_account_list(request):
    return banking_accounts_feed_spa(request)


@login_required
def bank_account_create(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    if request.method == "POST":
        form = BankAccountForm(request.POST, business=business)
        if form.is_valid():
            form.save()
            messages.success(request, "Bank account created.")
            return redirect("bank_account_list")
    else:
        form = BankAccountForm(business=business)

    return render(
        request,
        "banking/bank_account_form.html",
        {
            "business": business,
            "form": form,
            "is_edit": False,
            "account": None,
        },
    )


@login_required
def bank_account_edit(request, pk):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    account = get_object_or_404(BankAccount, pk=pk, business=business)

    if request.method == "POST":
        form = BankAccountForm(request.POST, instance=account, business=business)
        if form.is_valid():
            form.save()
            messages.success(request, "Bank account updated.")
            return redirect("bank_account_list")
    else:
        form = BankAccountForm(instance=account, business=business)

    return render(
        request,
        "banking/bank_account_form.html",
        {
            "business": business,
            "form": form,
            "is_edit": True,
            "account": account,
        },
    )


class BankStatementImportView(LoginRequiredMixin, View):
    template_name = "bank/import_form.html"

    def get(self, request, *args, **kwargs):
        business = get_current_business(request.user)
        if business is None:
            return redirect("business_setup")

        initial = {}
        preselect = request.GET.get("bank_account")
        if preselect:
            initial["bank_account"] = preselect
        form = BankStatementImportForm(business=business, initial=initial)
        return render(
            request,
            self.template_name,
            {
                "business": business,
                "form": form,
            },
        )

    def post(self, request, *args, **kwargs):
        business = get_current_business(request.user)
        if business is None:
            return redirect("business_setup")

        form = BankStatementImportForm(request.POST, request.FILES, business=business)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "business": business,
                    "form": form,
                },
            )

        bank_import = form.save(commit=False)
        bank_import.business = business
        bank_import.uploaded_by = request.user if request.user.is_authenticated else None
        bank_import.status = BankStatementImport.ImportStatus.PROCESSING
        bank_import.save()

        try:
            created, duplicates = self._process_import(bank_import)
        except Exception as exc:  # pragma: no cover - safety net for unexpected CSV formats
            bank_import.status = BankStatementImport.ImportStatus.FAILED
            bank_import.error_message = str(exc)
            bank_import.save(update_fields=["status", "error_message"])
            messages.error(
                request,
                "Import failed. Check the CSV structure and try again.",
            )
        else:
            bank_import.status = BankStatementImport.ImportStatus.COMPLETED
            bank_import.error_message = (
                f"Imported {created} new transaction{'s' if created != 1 else ''}. "
                f"Skipped {duplicates} duplicates."
            ).strip()
            bank_import.save(update_fields=["status", "error_message"])
            messages.success(request, "Bank transactions imported successfully.")

        return redirect("bank_feeds_overview")

    def _process_import(self, bank_import: BankStatementImport) -> tuple[int, int]:
        bank_account = bank_import.bank_account
        with bank_import.file.open("rb") as fh:
            data = fh.read().decode("utf-8", errors="ignore")
        reader = csv.DictReader(io.StringIO(data))

        created_count = 0
        duplicate_count = 0
        with db_transaction.atomic():
            for row in reader:
                if (
                    bank_import.file_format
                    == BankStatementImport.FileFormat.GENERIC_DATE_DESC_AMOUNT
                ):
                    date_raw = row.get("Date") or row.get("date")
                    description = (row.get("Description") or row.get("description") or "").strip()
                    amount_raw = row.get("Amount") or row.get("amount")
                    if not date_raw or not amount_raw:
                        continue
                    normalized_amount = amount_raw.replace(",", "").strip()
                    try:
                        amount = Decimal(normalized_amount)
                    except (InvalidOperation, TypeError):
                        continue
                else:
                    date_raw = row.get("Date") or row.get("date")
                    description = (row.get("Description") or row.get("description") or "").strip()
                    debit_raw = (row.get("Debit") or row.get("debit") or "").strip()
                    credit_raw = (row.get("Credit") or row.get("credit") or "").strip()
                    if not date_raw or (not debit_raw and not credit_raw):
                        continue
                    debit_value = debit_raw.replace(",", "")
                    credit_value = credit_raw.replace(",", "")
                    try:
                        if debit_value:
                            amount = -Decimal(debit_value)
                        else:
                            amount = Decimal(credit_value or "0")
                    except (InvalidOperation, TypeError):
                        continue

                date_obj = _parse_import_date(date_raw)
                if not date_obj:
                    continue

                normalized_amount_str = format(amount, "f")
                external_id = _generate_external_id(
                    bank_account.id,
                    date_obj.isoformat(),
                    description,
                    normalized_amount_str,
                )

                _, created_flag = BankTransaction.objects.get_or_create(
                    bank_account=bank_account,
                    external_id=external_id,
                    defaults={
                        "date": date_obj,
                        "description": description[:512],
                        "amount": amount,
                        "status": BankTransaction.TransactionStatus.NEW,
                    },
                )
                if created_flag:
                    created_count += 1
                else:
                    duplicate_count += 1

        return created_count, duplicate_count

@login_required
def bank_feeds_overview(request):
    return banking_accounts_feed_spa(request)


@login_required
def bank_feed_review(request, bank_account_id=None):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    bank_accounts = BankAccount.objects.filter(business=business).order_by("name")
    visible_status_choices = [
        choice for choice in BankTransaction.TransactionStatus.choices if not choice[0].startswith("LEGACY_")
    ]
    status_choices = [("all", "All statuses")] + visible_status_choices

    account_param = (
        request.POST.get("account")
        or request.GET.get("account")
        or bank_account_id
    )
    selected_account = (
        bank_accounts.filter(pk=account_param).first() if account_param else bank_accounts.first()
    )

    status_filter = (
        request.POST.get("status")
        or request.GET.get("status")
        or BankTransaction.TransactionStatus.NEW
    )
    valid_status_values = [choice[0] for choice in status_choices]
    if status_filter not in valid_status_values:
        status_filter = BankTransaction.TransactionStatus.NEW

    status_counts = {}
    total_transactions = 0
    if not selected_account:
        return render(
            request,
            "bank_feed_review.html",
            {
                "business": business,
                "bank_accounts": bank_accounts,
                "selected_account": None,
                "transactions": [],
                "status_filter": status_filter,
                "status_choices": status_choices,
                "selected_tx": None,
                "quick_expense_form": None,
                "status_counts": status_counts,
                "total_transactions": total_transactions,
            },
        )

    def _fetch_transactions():
        qs = (
            BankTransaction.objects.filter(bank_account=selected_account)
            .order_by("-date", "-id")
        )
        if status_filter != "all":
            qs = qs.filter(status=status_filter)
        return list(qs[:200])

    status_counts = {
        row["status"]: row["count"]
        for row in BankTransaction.objects.filter(bank_account=selected_account)
        .values("status")
        .annotate(count=Count("id"))
    }
    total_transactions = sum(status_counts.values())

    if request.method == "POST":
        tx_id = request.POST.get("tx_id")
        action = request.POST.get("action")

        with db_transaction.atomic():
            tx = (
                BankTransaction.objects.select_for_update()
                .filter(pk=tx_id, bank_account__business=business)
                .first()
            )

            if not tx:
                messages.error(request, "Transaction not found.")
            else:
                selected_account = tx.bank_account
                if action == "create_expense":
                    if tx.amount >= 0:
                        messages.error(request, "Only withdrawals can be turned into expenses.")
                    else:
                        form = BankQuickExpenseForm(request.POST, business=business)
                        if form.is_valid():
                            expense = Expense(
                                business=business,
                                date=tx.date,
                                amount=abs(tx.amount),
                                description=tx.description,
                                category=form.cleaned_data["category"],
                                supplier=form.cleaned_data["supplier"],
                                status=Expense.Status.PAID,
                            )
                            expense.paid_date = tx.date
                            expense.save()

                            journal_entry = (
                                expense.journalentry_set.order_by("-date", "-id").first()
                            )
                            if journal_entry:
                                tx.posted_journal_entry = journal_entry
                                add_bank_match(tx, journal_entry)
                            else:
                                recompute_bank_transaction_status(tx)
                            tx.matched_expense = expense
                            tx.save(update_fields=["matched_expense", "posted_journal_entry"])

                            messages.success(
                                request,
                                "Expense created and posted to the ledger.",
                            )
                        else:
                            transactions = _fetch_transactions()
                            current_balance = selected_account.current_balance
                            expense_candidates_map, invoice_candidates_map = _build_transaction_suggestions(
                                transactions, business
                            )
                            for item in transactions:
                                item.expense_candidates = expense_candidates_map.get(item.id, [])
                                item.invoice_candidates = invoice_candidates_map.get(item.id, [])
                            selected_tx = tx
                            return render(
                                request,
                                "bank_feed_review.html",
                                {
                                    "business": business,
                                    "bank_accounts": bank_accounts,
                                    "selected_account": selected_account,
                                    "transactions": transactions,
                                    "status_filter": status_filter,
                                    "status_choices": status_choices,
                                    "selected_tx": selected_tx,
                                    "quick_expense_form": form,
                                    "status_counts": status_counts,
                                    "total_transactions": total_transactions,
                                    "expense_candidates": expense_candidates_map,
                                    "current_balance": current_balance,
                                },
                            )

                elif action == "exclude":
                    tx.status = BankTransaction.TransactionStatus.EXCLUDED
                    tx.save(update_fields=["status"])
                    messages.success(request, "Transaction excluded.")
                elif action == "reset":
                    tx.status = BankTransaction.TransactionStatus.NEW
                    tx.matched_expense = None
                    tx.save(update_fields=["status", "matched_expense"])
                    messages.success(request, "Transaction reset to New.")
                elif action == "mark_created":
                    tx.status = BankTransaction.TransactionStatus.CREATED
                    tx.save(update_fields=["status"])
                    messages.success(request, "Transaction marked as created.")

        redirect_url = reverse("bank_feed_review", args=[selected_account.id])
        if status_filter:
            redirect_url = f"{redirect_url}?status={status_filter}"
        return redirect(redirect_url)

    transactions = _fetch_transactions()

    expense_candidates_map, invoice_candidates_map = _build_transaction_suggestions(
        transactions, business
    )

    for tx in transactions:
        tx.expense_candidates = expense_candidates_map.get(tx.id, [])
        tx.invoice_candidates = invoice_candidates_map.get(tx.id, [])

    selected_tx = None
    selected_tx_id = request.GET.get("tx")
    if selected_tx_id:
        for tx in transactions:
            if str(tx.id) == str(selected_tx_id):
                selected_tx = tx
                break
    if selected_tx is None and transactions:
        selected_tx = transactions[0]

    quick_expense_form = None
    if selected_tx and selected_tx.amount < 0:
        quick_expense_form = BankQuickExpenseForm(business=business)

    current_balance = selected_account.current_balance if selected_account else Decimal("0.00")

    return render(
        request,
        "bank_feed_review.html",
        {
            "business": business,
            "bank_accounts": bank_accounts,
            "selected_account": selected_account,
            "transactions": transactions,
            "status_filter": status_filter,
            "status_choices": status_choices,
            "selected_tx": selected_tx,
            "quick_expense_form": quick_expense_form,
            "status_counts": status_counts,
            "total_transactions": total_transactions,
            "expense_candidates": expense_candidates_map,
            "current_balance": current_balance,
        },
    )


@login_required
def bank_feed_match_invoice(request, bank_account_id, tx_id):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    bank_account = get_object_or_404(
        BankAccount,
        pk=bank_account_id,
        business=business,
    )
    bank_tx = get_object_or_404(
        BankTransaction,
        pk=tx_id,
        bank_account=bank_account,
    )

    if bank_tx.amount <= 0:
        messages.error(request, "Only deposits can be matched to invoices.")
        return redirect("bank_feed_review", bank_account_id=bank_account.id)

    if request.method == "POST":
        form = BankMatchInvoiceForm(
            request.POST,
            business=business,
            bank_tx=bank_tx,
        )
        if form.is_valid():
            invoice = form.cleaned_data["invoice"]
            with db_transaction.atomic():
                if invoice.status in (Invoice.Status.SENT, Invoice.Status.PARTIAL):
                    invoice.status = Invoice.Status.PAID
                    invoice.save()
                payment_entry = (
                    invoice.journalentry_set.filter(description__icontains="Invoice paid")
                    .order_by("-date", "-id")
                    .first()
                )
                bank_tx.matched_invoice = invoice
                bank_tx.customer = invoice.customer
                if payment_entry:
                    bank_tx.posted_journal_entry = payment_entry
                bank_tx.save(update_fields=["matched_invoice", "customer", "posted_journal_entry"])
                if payment_entry:
                    add_bank_match(bank_tx, payment_entry)
                else:
                    recompute_bank_transaction_status(bank_tx)

            messages.success(
                request,
                f"Transaction on {bank_tx.date:%b %d, %Y} matched to invoice {invoice.invoice_number}.",
            )
            return redirect("bank_feed_review", bank_account_id=bank_account.id)
    else:
        form = BankMatchInvoiceForm(
            business=business,
            bank_tx=bank_tx,
        )

    invoice_field = cast(ModelChoiceField, form.fields["invoice"])
    has_candidates = invoice_field.queryset.exists()

    return render(
        request,
        "bank_feed_match_invoice.html",
        {
            "business": business,
            "bank_account": bank_account,
            "bank_tx": bank_tx,
            "form": form,
            "has_candidates": has_candidates,
        },
    )


@login_required
def bank_feed_exclude_tx(request, bank_account_id, tx_id):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    bank_account = get_object_or_404(
        BankAccount,
        pk=bank_account_id,
        business=business,
    )
    bank_tx = get_object_or_404(
        BankTransaction,
        pk=tx_id,
        bank_account=bank_account,
    )

    if bank_tx.status != BankTransaction.TransactionStatus.NEW:
        messages.error(
            request,
            "Only new transactions can be excluded.",
        )
        return redirect("bank_feed_review", bank_account_id=bank_account.id)

    if bank_tx.posted_journal_entry_id:
        messages.error(
            request,
            "This transaction has already posted to the ledger and cannot be excluded.",
        )
        return redirect("bank_feed_review", bank_account_id=bank_account.id)

    bank_tx.status = BankTransaction.TransactionStatus.EXCLUDED
    bank_tx.allocated_amount = Decimal("0.00")
    bank_tx.save(update_fields=["status", "allocated_amount"])
    messages.success(request, "Transaction excluded from review.")
    return redirect("bank_feed_review", bank_account_id=bank_account.id)


@login_required
def api_banking_overview(request):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"detail": "No business"}, status=400)

    accounts = (
        BankAccount.objects.filter(business=business)
        .select_related("account")
        .prefetch_related("bank_transactions")
        .order_by("name")
    )

    account_payload = []
    total_new = total_created = total_matched = total_partial = 0

    for account in accounts:
        txs = account.bank_transactions.all()
        new_count = txs.filter(status=BankTransaction.TransactionStatus.NEW).count()
        partial_count = txs.filter(status=BankTransaction.TransactionStatus.PARTIAL).count()
        created_count = txs.filter(status=BankTransaction.TransactionStatus.MATCHED_SINGLE).count()
        matched_count = txs.filter(status=BankTransaction.TransactionStatus.MATCHED_MULTI).count()

        total_new += new_count
        total_partial += partial_count
        total_created += created_count
        total_matched += matched_count

        if new_count > 0 or partial_count > 0:
            feed_status = "ACTION_NEEDED"
        elif not txs.exists():
            feed_status = "DISCONNECTED"
        else:
            feed_status = "OK"

        account_payload.append(
            {
                "id": account.id,
                "name": account.name,
                "last4": account.account_number_mask or "",
                "bank": account.bank_name or "",
                "currency": business.currency,
                "ledger_linked": bool(account.account_id),
                "ledger_balance": str(account.current_balance),
                "feed_status": feed_status,
                "last_import_at": (
                    timezone.localtime(account.last_imported_at).isoformat()
                    if account.last_imported_at
                    else None
                ),
                "new_count": new_count + partial_count,
                "created_count": created_count,
                "matched_count": matched_count,
                "review_url": reverse("bank_feed_review", args=[account.id]),
                "import_url": f"{reverse('bank_feed_import')}?bank_account={account.id}",
            }
        )

    total_items = total_new + total_partial + total_created + total_matched
    reconciled_percent = (
        int((total_matched / total_items) * 100) if total_items > 0 else 100
    )

    summary = {
        "new_to_review": total_new + total_partial,
        "created_from_feed": total_created,
        "matched_to_invoices": total_matched,
        "reconciled_percent": reconciled_percent,
    }

    return JsonResponse({"accounts": account_payload, "summary": summary})


@login_required
def api_banking_feed_transactions(request):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"detail": "No business"}, status=400)

    account_id = request.GET.get("account_id")
    if not account_id:
        return JsonResponse({"detail": "account_id is required"}, status=400)
    try:
        account_id_int = int(account_id)
    except (TypeError, ValueError):
        return JsonResponse({"detail": "Invalid account_id"}, status=400)

    bank_account = (
        BankAccount.objects.filter(business=business)
        .select_related("account")
        .filter(pk=account_id_int)
        .first()
    )
    if not bank_account:
        return JsonResponse({"detail": "Bank account not found"}, status=404)

    status_filter = request.GET.get("status") or "ALL"

    transactions = list(
        BankTransaction.objects.filter(bank_account=bank_account)
        .select_related(
            "posted_journal_entry",
            "category",
            "customer",
            "supplier",
            "matched_invoice",
            "matched_invoice__customer",
            "matched_expense",
            "matched_expense__supplier",
        )
        .prefetch_related("posted_journal_entry__lines__account")
        .order_by("-date", "-id")
    )

    if status_filter != "ALL":
        transactions = [
            tx for tx in transactions if tx.status == status_filter
        ]

    expense_map, invoice_map = _build_transaction_suggestions(transactions, business)

    status_counts = {
        row["status"]: row["count"]
        for row in BankTransaction.objects.filter(bank_account=bank_account)
        .values("status")
        .annotate(count=Count("id"))
    }

    tx_payload = []
    for tx in transactions:
        posted_entry = tx.posted_journal_entry
        entry_payload = None
        if posted_entry:
            entry_payload = {
                "id": posted_entry.id,
                "date": posted_entry.date.isoformat(),
                "description": posted_entry.description,
                "lines": [
                    {
                        "account_name": line.account.name,
                        "account_code": line.account.code,
                        "debit": float(line.debit),
                        "credit": float(line.credit),
                    }
                    for line in posted_entry.lines.all()
                ],
            }
        counterparty = (
            getattr(tx.customer, "name", "")
            or getattr(tx.supplier, "name", "")
        )
        matched_invoice_customer = getattr(tx.matched_invoice, "customer", None)
        if not counterparty and matched_invoice_customer:
            counterparty = getattr(matched_invoice_customer, "name", "")
        matched_expense_supplier = getattr(tx.matched_expense, "supplier", None)
        if not counterparty and matched_expense_supplier:
            counterparty = getattr(matched_expense_supplier, "name", "")

        tx_payload.append(
            {
                "id": tx.id,
                "date": tx.date.isoformat(),
                "description": tx.description,
                "memo": tx.description,
                "amount": float(tx.amount),
                "status": tx.status,
                "status_label": tx.get_status_display(),
                "allocated_amount": float(tx.allocated_amount or Decimal("0.00")),
                "side": "IN" if tx.amount >= 0 else "OUT",
                "category": tx.category.name if tx.category else "",
                "category_id": tx.category_id,
                "counterparty": counterparty,
                "customer": getattr(tx.customer, "name", ""),
                "supplier": getattr(tx.supplier, "name", ""),
                "matched_invoice_id": tx.matched_invoice_id,
                "matched_expense_id": tx.matched_expense_id,
                "posted_journal_entry": entry_payload,
                "expense_candidates": [
                    {
                        "id": exp.id,
                        "description": exp.description,
                        "date": exp.date.isoformat(),
                        "amount": float(exp.amount or Decimal("0.00")),
                    }
                    for exp in expense_map.get(tx.id, [])
                ],
                "invoice_candidates": [
                    {
                        "id": inv.id,
                        "invoice_number": getattr(inv, "invoice_number", ""),
                        "customer": getattr(inv.customer, "name", "") if inv.customer else "",
                        "date": inv.issue_date.isoformat() if inv.issue_date else "",
                        "amount": float(inv.grand_total or ((inv.net_total or Decimal("0.00")) + (inv.tax_total or Decimal("0.00")))),
                    }
                    for inv in invoice_map.get(tx.id, [])
                ],
            }
        )

    account_payload = {
        "id": bank_account.id,
        "name": bank_account.name,
        "last4": bank_account.account_number_mask or "",
        "ledger_balance": str(bank_account.current_balance),
    }

    return JsonResponse(
        {
            "account": account_payload,
            "balance": float(bank_account.current_balance),
            "status_counts": status_counts,
            "transactions": tx_payload,
        }
    )


@login_required
@require_POST
def api_allocate_bank_transaction(request, bank_tx_id):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"ok": False, "error": "No business."}, status=400)

    bank_tx = (
        BankTransaction.objects.select_related("bank_account", "bank_account__business")
        .filter(pk=bank_tx_id, bank_account__business=business)
        .first()
    )
    if not bank_tx:
        return JsonResponse({"ok": False, "error": "Transaction not found."}, status=404)

    payload = _json_from_body(request)
    if not isinstance(payload, dict):
        return JsonResponse({"ok": False, "error": "Invalid payload."}, status=400)

    def _build_allocation(raw: dict) -> Allocation:
        try:
            kind = str(raw["type"]).upper()
            amount = Decimal(str(raw["amount"]))
        except (KeyError, TypeError, InvalidOperation, ValueError):
            raise ValidationError("Invalid allocation payload.")
        return Allocation(
            kind=kind,
            id=raw.get("id"),
            account_id=raw.get("account_id"),
            amount=amount,
        )

    try:
        allocation_items = payload.get("allocations") or []
        allocations = [_build_allocation(item) for item in allocation_items]

        fees = None
        if payload.get("fees"):
            fees = Allocation(
                kind="DIRECT_EXPENSE",
                id=None,
                account_id=payload["fees"].get("account_id"),
                amount=Decimal(str(payload["fees"].get("amount"))),
            )

        rounding = None
        if payload.get("rounding"):
            rounding = Allocation(
                kind="DIRECT_EXPENSE",
                id=None,
                account_id=payload["rounding"].get("account_id"),
                amount=Decimal(str(payload["rounding"].get("amount"))),
            )

        overpayment = None
        if payload.get("overpayment"):
            overpayment = Allocation(
                kind="CREDIT_NOTE",
                id=None,
                account_id=payload["overpayment"].get("account_id"),
                amount=Decimal(str(payload["overpayment"].get("amount"))),
            )

        tolerance_cents = int(payload.get("tolerance_cents", 2))
        operation_id = payload.get("operation_id")

        entry = allocate_bank_transaction(
            bank_tx=bank_tx,
            allocations=allocations,
            fees=fees,
            rounding=rounding,
            overpayment=overpayment,
            user=request.user,
            tolerance_cents=tolerance_cents,
            operation_id=operation_id,
        )
    except ValidationError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except (InvalidOperation, TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Invalid payload."}, status=400)

    bank_tx.refresh_from_db()

    return JsonResponse(
        {
            "ok": True,
            "journal_entry_id": entry.id,
            "bank_transaction": {
                "id": bank_tx.id,
                "status": bank_tx.status,
                "status_label": bank_tx.get_status_display(),
                "allocated_amount": str(bank_tx.allocated_amount or Decimal("0.00")),
            },
        }
    )


@login_required
def api_banking_feed_metadata(request):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"detail": "No business"}, status=400)

    expense_categories = list(
        Category.objects.filter(
            business=business,
            type=Category.CategoryType.EXPENSE,
            is_archived=False,
        )
        .order_by("name")
        .values("id", "name")
    )
    income_categories = list(
        Category.objects.filter(
            business=business,
            type=Category.CategoryType.INCOME,
            is_archived=False,
        )
        .order_by("name")
        .values("id", "name")
    )
    suppliers = list(
        Supplier.objects.filter(business=business)
        .order_by("name")
        .values("id", "name")
    )
    customers = list(
        Customer.objects.filter(business=business)
        .order_by("name")
        .values("id", "name")
    )
    return JsonResponse(
        {
            "expense_categories": expense_categories,
            "income_categories": income_categories,
            "suppliers": suppliers,
            "customers": customers,
        }
    )


@login_required
@require_POST
def api_banking_feed_create_entry(request, tx_id):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"detail": "No business"}, status=400)

    payload = _json_from_body(request)
    category_id = payload.get("category_id")
    if not category_id:
        return JsonResponse({"detail": "category_id is required"}, status=400)
    try:
        category_id = int(category_id)
    except (TypeError, ValueError):
        return JsonResponse({"detail": "Invalid category_id"}, status=400)

    category = (
        Category.objects.filter(
            business=business,
            pk=category_id,
            is_archived=False,
        )
        .select_related("account")
        .first()
    )
    if not category:
        return JsonResponse({"detail": "Category not found"}, status=404)

    memo = (payload.get("memo") or "").strip()

    with db_transaction.atomic():
        bank_tx = _get_bank_tx_for_business(business, tx_id, for_update=True)
        if not bank_tx:
            return JsonResponse({"detail": "Transaction not found"}, status=404)
        if bank_tx.status != BankTransaction.TransactionStatus.NEW:
            return JsonResponse(
                {"detail": "Only new transactions can be converted."},
                status=400,
            )
        if bank_tx.amount == 0:
            return JsonResponse({"detail": "Transaction amount is zero."}, status=400)

        if bank_tx.amount < 0:
            if category.type != Category.CategoryType.EXPENSE:
                return JsonResponse(
                    {"detail": "Select an expense category."},
                    status=400,
                )
            supplier = None
            supplier_id = payload.get("supplier_id")
            if supplier_id not in (None, "", 0, "0"):
                try:
                    supplier = Supplier.objects.get(
                        pk=int(supplier_id),
                        business=business,
                    )
                except (Supplier.DoesNotExist, ValueError, TypeError):
                    return JsonResponse({"detail": "Supplier not found."}, status=404)
            expense = Expense(
                business=business,
                supplier=supplier,
                category=category,
                date=bank_tx.date,
                description=memo or bank_tx.description,
                amount=abs(bank_tx.amount),
                status=Expense.Status.PAID,
                paid_date=bank_tx.date,
            )
            try:
                expense.save()
            except Exception as exc:  # pragma: no cover - surfaced to UI
                return JsonResponse(
                    {"detail": f"Unable to save expense: {exc}"},
                    status=400,
                )
            journal_entry = expense.journalentry_set.order_by("-date", "-id").first()
            bank_tx.matched_expense = expense
            bank_tx.matched_invoice = None
            bank_tx.category = category
            bank_tx.supplier = supplier
            bank_tx.customer = None
            bank_tx.posted_journal_entry = journal_entry
            bank_tx.save(
                update_fields=[
                    "matched_expense",
                    "matched_invoice",
                    "category",
                    "supplier",
                    "customer",
                    "posted_journal_entry",
                ]
            )
            add_bank_match(bank_tx, journal_entry)
        else:
            if category.type != Category.CategoryType.INCOME:
                return JsonResponse(
                    {"detail": "Select an income category."},
                    status=400,
                )
            customer = None
            customer_id = payload.get("customer_id")
            if customer_id not in (None, "", 0, "0"):
                try:
                    customer = Customer.objects.get(
                        pk=int(customer_id),
                        business=business,
                    )
                except (Customer.DoesNotExist, ValueError, TypeError):
                    return JsonResponse({"detail": "Customer not found."}, status=404)
            try:
                entry = _post_income_entry(
                    business,
                    bank_tx.bank_account,
                    category,
                    Decimal(bank_tx.amount),
                    memo or bank_tx.description,
                    bank_tx.date,
                )
            except ValueError as exc:
                return JsonResponse({"detail": str(exc)}, status=400)
            bank_tx.matched_invoice = None
            bank_tx.matched_expense = None
            bank_tx.category = category
            bank_tx.customer = customer
            bank_tx.supplier = None
            bank_tx.posted_journal_entry = entry
            bank_tx.save(
                update_fields=[
                    "matched_invoice",
                    "matched_expense",
                    "category",
                    "customer",
                    "supplier",
                    "posted_journal_entry",
                ]
            )
            add_bank_match(bank_tx, entry)

    return JsonResponse({"success": True})


@login_required
@require_POST
def api_banking_feed_match_invoice_api(request, tx_id):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"detail": "No business"}, status=400)

    payload = _json_from_body(request)
    invoice_id = payload.get("invoice_id")
    if not invoice_id:
        return JsonResponse({"detail": "invoice_id is required"}, status=400)
    try:
        invoice_id = int(invoice_id)
    except (TypeError, ValueError):
        return JsonResponse({"detail": "Invalid invoice_id"}, status=400)

    invoice = Invoice.objects.filter(business=business, pk=invoice_id).select_related("customer").first()
    if not invoice:
        return JsonResponse({"detail": "Invoice not found."}, status=404)

    with db_transaction.atomic():
        bank_tx = _get_bank_tx_for_business(business, tx_id, for_update=True)
        if not bank_tx:
            return JsonResponse({"detail": "Transaction not found"}, status=404)
        if bank_tx.amount <= 0:
            return JsonResponse(
                {"detail": "Only deposits can be matched to invoices."},
                status=400,
            )
        if bank_tx.status != BankTransaction.TransactionStatus.NEW:
            return JsonResponse(
                {"detail": "This transaction has already been processed."},
                status=400,
            )

        if invoice.status in (Invoice.Status.SENT, Invoice.Status.PARTIAL):
            invoice.status = Invoice.Status.PAID
            invoice.save()

        payment_entry = (
            invoice.journalentry_set.filter(description__icontains="Invoice paid")
            .order_by("-date", "-id")
            .first()
        )

        bank_tx.matched_invoice = invoice
        bank_tx.matched_expense = None
        bank_tx.customer = invoice.customer
        if payment_entry:
            bank_tx.posted_journal_entry = payment_entry
        bank_tx.save(
            update_fields=[
                "matched_invoice",
                "matched_expense",
                "customer",
                "posted_journal_entry",
            ]
        )

        if payment_entry:
            add_bank_match(bank_tx, payment_entry)
        else:
            recompute_bank_transaction_status(bank_tx)

    return JsonResponse({"success": True})


@login_required
@require_POST
def api_banking_feed_match_expense_api(request, tx_id):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"detail": "No business"}, status=400)

    payload = _json_from_body(request)
    expense_id = payload.get("expense_id")
    if not expense_id:
        return JsonResponse({"detail": "expense_id is required"}, status=400)
    try:
        expense_id = int(expense_id)
    except (TypeError, ValueError):
        return JsonResponse({"detail": "Invalid expense_id"}, status=400)

    expense = Expense.objects.filter(business=business, pk=expense_id).select_related("category", "supplier").first()
    if not expense:
        return JsonResponse({"detail": "Expense not found."}, status=404)

    with db_transaction.atomic():
        bank_tx = _get_bank_tx_for_business(business, tx_id, for_update=True)
        if not bank_tx:
            return JsonResponse({"detail": "Transaction not found"}, status=404)
        if bank_tx.amount >= 0:
            return JsonResponse(
                {"detail": "Only withdrawals can be matched to expenses."},
                status=400,
            )
        if bank_tx.status != BankTransaction.TransactionStatus.NEW:
            return JsonResponse(
                {"detail": "This transaction has already been processed."},
                status=400,
            )
        if expense.status not in (Expense.Status.UNPAID, Expense.Status.PARTIAL):
            return JsonResponse(
                {"detail": "Only open expenses can be matched."},
                status=400,
            )

        journal_entry = post_expense_paid(expense)
        if journal_entry is None:
            journal_entry = expense.journalentry_set.order_by("-date", "-id").first()

        expense.status = Expense.Status.PAID
        expense.paid_date = bank_tx.date
        expense.save()

        bank_tx.matched_expense = expense
        bank_tx.matched_invoice = None
        bank_tx.category = expense.category
        bank_tx.supplier = expense.supplier
        bank_tx.posted_journal_entry = journal_entry
        bank_tx.save(
            update_fields=[
                "matched_expense",
                "matched_invoice",
                "category",
                "supplier",
                "posted_journal_entry",
            ]
        )
        add_bank_match(bank_tx, journal_entry)

    return JsonResponse({"success": True})


@login_required
@require_POST
def api_banking_feed_exclude(request, tx_id):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"detail": "No business"}, status=400)

    with db_transaction.atomic():
        bank_tx = _get_bank_tx_for_business(business, tx_id, for_update=True)
        if not bank_tx:
            return JsonResponse({"detail": "Transaction not found"}, status=404)
        if bank_tx.status != BankTransaction.TransactionStatus.NEW:
            return JsonResponse(
                {"detail": "Only new transactions can be excluded."},
                status=400,
            )
        if bank_tx.posted_journal_entry_id:
            return JsonResponse(
                {"detail": "Posted transactions cannot be excluded."},
                status=400,
            )
        bank_tx.status = BankTransaction.TransactionStatus.EXCLUDED
        bank_tx.allocated_amount = Decimal("0.00")
        bank_tx.save(update_fields=["status", "allocated_amount"])

    return JsonResponse({"success": True})


@login_required
def bank_feed_match_expense(request, bank_account_id, tx_id):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    bank_account = get_object_or_404(
        BankAccount,
        pk=bank_account_id,
        business=business,
    )
    bank_tx = get_object_or_404(
        BankTransaction,
        pk=tx_id,
        bank_account=bank_account,
    )

    if request.method != "POST":
        return redirect("bank_feed_review", bank_account_id=bank_account.id)

    expense_id = request.POST.get("expense_id")
    if not expense_id:
        messages.error(request, "Select an expense to match to.")
        return redirect("bank_feed_review", bank_account_id=bank_account.id)

    expense = get_object_or_404(
        Expense,
        pk=expense_id,
        business=business,
    )

    if bank_tx.amount >= 0:
        messages.error(request, "Only withdrawals can be matched to expenses.")
        return redirect("bank_feed_review", bank_account_id=bank_account.id)

    if bank_tx.status != BankTransaction.TransactionStatus.NEW:
        messages.error(request, "This transaction has already been processed.")
        return redirect("bank_feed_review", bank_account_id=bank_account.id)

    if expense.status not in (Expense.Status.UNPAID, Expense.Status.PARTIAL):
        messages.error(request, "Only open expenses can be matched.")
        return redirect("bank_feed_review", bank_account_id=bank_account.id)

    if abs(bank_tx.amount) != expense.amount:
        messages.warning(
            request,
            "Amounts do not match exactly. Make sure this is the right expense.",
        )

    with db_transaction.atomic():
        journal_entry = post_expense_paid(expense)
        if journal_entry is None:
            journal_entry = (
                expense.journalentry_set.order_by("-date", "-id").first()
            )

        expense.status = Expense.Status.PAID
        expense.paid_date = bank_tx.date
        expense.save()

        bank_tx.matched_expense = expense
        bank_tx.posted_journal_entry = journal_entry
        bank_tx.save(update_fields=["matched_expense", "posted_journal_entry"])
        add_bank_match(bank_tx, journal_entry)

    messages.success(request, "Expense matched and marked as paid.")
    return redirect("bank_feed_review", bank_account_id=bank_account.id)


@login_required
def pl_export_csv(request):
    """Placeholder endpoint for future CSV exports."""

    return HttpResponse("Export coming soon.", content_type="text/plain")


@login_required
def bank_feed_spa(request):
    return render(request, "bank_feed.html")


@login_required
def banking_accounts_feed_spa(request):
    return render(request, "banking_accounts_feed.html")


@login_required
def chart_of_accounts_spa(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    balances = account_balances_for_business(business)
    balance_map = {
        row["id"]: row["balance"]
        for row in balances.get("accounts", [])
    }

    accounts = (
        Account.objects.filter(business=business)
        .order_by("code", "name")
        .only("id", "code", "name", "type", "description", "is_active")
    )

    payload: list[dict[str, object]] = []
    for account in accounts:
        payload.append(
            {
                "id": account.id,
                "code": account.code or "",
                "name": account.name,
                "type": account.type,
                "detailType": account.description or "",
                "isActive": account.is_active,
                "balance": float(balance_map.get(account.id) or 0),
                "favorite": account.is_favorite,
                "detailUrl": reverse("coa_account_detail", args=[account.id]),
            }
        )

    totals_by_type = {
        key: float(value)
        for key, value in (balances.get("totals_by_type") or {}).items()
    }

    spa_payload = {
        "accounts": payload,
        "currencyCode": business.currency or "USD",
        "totalsByType": totals_by_type,
    }

    context = {
        "spa_payload": spa_payload,
        "spa_initial": json.dumps(spa_payload, cls=DjangoJSONEncoder),
        "new_account_url": reverse("bank_account_create"),
    }
    return render(request, "chart_of_accounts_spa.html", context)
