import csv
import logging
import hashlib
import io
import json
from collections import OrderedDict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction as db_transaction
from django.db.models import Count, Max, Q, Sum, Avg
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.forms import ModelChoiceField
from typing import cast, Any
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST, require_http_methods
from django.views.generic import ListView, TemplateView, CreateView, UpdateView, View
from django.urls import reverse, reverse_lazy, NoReverseMatch
from django.utils.dateparse import parse_date
try:
    from weasyprint import HTML
except Exception as exc:  # pragma: no cover - optional dependency in some envs
    HTML = None
    logging.getLogger(__name__).warning("weasyprint unavailable; PDF generation will be skipped. (%s)", exc)
from django.utils.text import slugify

from .forms import (
    BusinessForm,
    BusinessProfileForm,
    CategoryForm,
    CustomerForm,
    ExpenseForm,
    InvoiceForm,
    SignupForm,
    SupplierForm,
    UserProfileForm,
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
    InvoiceEmailLog,
    InvoiceEmailTemplate,
    Supplier,
    Item,
    JournalEntry,
    JournalLine,
    BankAccount,
    BankStatementImport,
    BankTransaction,
    Business,
    TaxRate,
    BankReconciliationMatch,
)
from .ledger_services import compute_ledger_pl
from .ledger_reports import account_balances_for_business
from .utils import get_current_business, is_empty_workspace

logger = logging.getLogger(__name__)

def _messages_payload(request):
    storage = messages.get_messages(request)
    return [{"level": m.level_tag, "message": str(m)} for m in storage]


def _serialize_form(form, form_name: str | None = None):
    if form is None:
        return None

    visible_fields = [bf for bf in form if not bf.is_hidden]
    field_payload = []
    for bound_field in visible_fields:
        widget = bound_field.field.widget
        widget_name = widget.__class__.__name__.lower()
        input_type = getattr(widget, "input_type", None)
        if not input_type:
            if "select" in widget_name:
                input_type = "select"
            elif "textarea" in widget_name:
                input_type = "textarea"
            else:
                input_type = "text"
        value = bound_field.value()
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        if value is None:
            value = ""
        value = str(value)
        choices = None
        widget_choices = getattr(widget, "choices", None)
        if widget_choices:
            choices = [
                {"value": str(choice_value), "label": str(choice_label)}
                for choice_value, choice_label in widget_choices
            ]
        field_payload.append(
            {
                "name": bound_field.html_name,
                "id": bound_field.auto_id or bound_field.id_for_label or bound_field.html_name,
                "label": bound_field.label,
                "value": value,
                "errors": list(bound_field.errors),
                "type": input_type,
                "choices": choices,
                "required": bound_field.field.required,
                "help_text": bound_field.help_text or "",
            }
        )
    return {
        "form_id": form_name or "",
        "action": getattr(form, "action", ""),
        "method": getattr(form, "method", "post"),
        "fields": field_payload,
        "non_field_errors": list(form.non_field_errors()),
        "hidden_fields": [str(hidden) for hidden in form.hidden_fields()],
    }
from .accounting_posting_expenses import post_expense_paid
from .accounting_defaults import ensure_default_accounts
from .reconciliation import (
    Allocation,
    AllocationKind,
    add_bank_match,
    allocate_bank_transaction,
    recompute_bank_transaction_status,
)
from .tax_utils import compute_tax_breakdown


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


def _normalize_tax_treatment(raw: str | None) -> str:
    normalized = (raw or "NONE").upper()
    mapping = {
        "NO_TAX": "NONE",
        "TAX_ON_TOP": "ON_TOP",
        "TAX_INCLUDED": "INCLUDED",
    }
    return mapping.get(normalized, normalized)


def _tax_rate_payload(rate: TaxRate) -> dict[str, object]:
    default_sales = bool(rate.is_default_sales or rate.is_default_sales_rate)
    default_purchase = bool(rate.is_default_purchases or rate.is_default_purchase_rate)
    return {
        "id": rate.id,
        "name": rate.name,
        "code": rate.code,
        "rate": float(rate.rate),
        "percentage": float(rate.percentage),
        "country": rate.country,
        "region": rate.region,
        "applies_to_sales": rate.applies_to_sales,
        "applies_to_purchases": rate.applies_to_purchases,
        "is_default_sales_rate": default_sales,
        "is_default_purchase_rate": default_purchase,
        "is_active": rate.is_active,
    }


def _load_tax_rate(
    business: Business,
    rate_id,
    *,
    require_sales: bool = False,
    require_purchases: bool = False,
):
    try:
        rate_pk = int(rate_id)
    except (TypeError, ValueError):
        raise ValidationError("Invalid tax rate id.")

    rate = TaxRate.objects.filter(pk=rate_pk, business=business, is_active=True).first()
    if not rate:
        raise ValidationError("Tax rate not found.")
    if require_sales and not rate.applies_to_sales:
        raise ValidationError("This tax rate is not configured for sales.")
    if require_purchases and not rate.applies_to_purchases:
        raise ValidationError("This tax rate is not configured for purchases.")
    return rate


def _percentage_from_rate_value(raw_value) -> Decimal:
    try:
        rate_decimal = Decimal(str(raw_value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError("Enter a valid tax rate.")
    if rate_decimal < 0:
        raise ValidationError("Tax rate cannot be negative.")
    # Accept decimals (0.13) or percentages (13)
    percentage = rate_decimal * Decimal("100") if rate_decimal <= 1 else rate_decimal
    if percentage > Decimal("1000"):
        raise ValidationError("Tax rate looks too large.")
    return percentage.quantize(Decimal("0.01"))


def _clear_default_tax_flags(business: Business, *, sales: bool = False, purchases: bool = False, exclude_id=None):
    qs = TaxRate.objects.filter(business=business)
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    updates = {}
    if sales:
        updates["is_default_sales"] = False
        updates["is_default_sales_rate"] = False
    if purchases:
        updates["is_default_purchases"] = False
        updates["is_default_purchase_rate"] = False
    if updates:
        qs.update(**updates)


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

def net_tax_position(business):
    """
    Compute a simple net tax position for the given business.

    This returns a dict containing:
      - sales_tax_payable: total sales tax (invoices)
      - recoverable_tax_asset: total recoverable tax (expenses)
      - net_tax: sales_tax_payable - recoverable_tax_asset

    If any lookup fails, the function falls back to zero values so callers
    (like the dashboard) do not raise NameError or unexpected exceptions.
    """
    sales_tax_payable = Decimal("0.00")
    recoverable_tax_asset = Decimal("0.00")

    try:
        sales_tax_payable = (
            Invoice.objects.filter(business=business).aggregate(total=Sum("tax_total"))["total"]
            or Decimal("0.00")
        )
    except Exception:
        sales_tax_payable = Decimal("0.00")

    try:
        recoverable_tax_asset = (
            Expense.objects.filter(business=business).aggregate(total=Sum("tax_amount"))["total"]
            or Decimal("0.00")
        )
    except Exception:
        recoverable_tax_asset = Decimal("0.00")

    net_tax = sales_tax_payable - recoverable_tax_asset

    return {
        "sales_tax_payable": sales_tax_payable,
        "recoverable_tax_asset": recoverable_tax_asset,
        "net_tax": net_tax,
    }

def _post_income_entry(
    business,
    bank_account,
    category,
    amount: Decimal,
    description: str,
    tx_date,
    *,
    tax_treatment: str = "NONE",
    tax_rate: TaxRate | None = None,
    base_amount: Decimal | None = None,
):
    defaults = ensure_default_accounts(business)
    cash_account = bank_account.account or defaults.get("cash")
    if cash_account is None:
        raise ValueError(
            "Link this bank account to a ledger account or configure a default cash account."
        )

    income_account = category.account or defaults.get("sales")
    if income_account is None:
        raise ValueError("The selected category is not linked to an income account.")

    base_value = Decimal(base_amount) if base_amount is not None else Decimal(amount)
    rate_pct = tax_rate.percentage if tax_rate else Decimal("0.00")
    net_amount, tax_amount, gross_amount = compute_tax_breakdown(
        base_value, (tax_treatment or "NONE"), rate_pct
    )
    tax_account = defaults.get("tax")
    if tax_amount and tax_amount != 0 and not tax_account:
        raise ValueError("Configure a sales tax account to post tax.")

    entry = JournalEntry.objects.create(
        business=business,
        date=tx_date,
        description=(description or "Bank feed income")[:255],
    )
    JournalLine.objects.create(
        journal_entry=entry,
        account=cash_account,
        debit=gross_amount,
        credit=Decimal("0.00"),
        description="Bank feed deposit",
    )
    JournalLine.objects.create(
        journal_entry=entry,
        account=income_account,
        debit=Decimal("0.00"),
        credit=net_amount,
        description="Income recognition",
    )
    if tax_amount and tax_account:
        JournalLine.objects.create(
            journal_entry=entry,
            account=tax_account,
            debit=Decimal("0.00"),
            credit=tax_amount,
            description="Tax collected",
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


def _invoice_preview(form, business=None) -> dict:
    amount = _decimal_from_form(form, "total_amount")
    tax = _decimal_from_form(form, "tax_amount")

    # Auto-compute tax from selected rate when present so the preview mirrors save logic.
    tax_rate_id = None
    if form is not None:
        if form.is_bound:
            tax_rate_id = form.data.get("tax_rate") or form.data.get("tax_rate_id")
        else:
            tax_rate_id = form.initial.get("tax_rate")

    if tax_rate_id:
        try:
            tax_qs = form.fields["tax_rate"].queryset
            rate = tax_qs.get(pk=tax_rate_id)
            tax = (amount * (rate.percentage / Decimal("100"))).quantize(Decimal("0.01"))
        except Exception:
            # Leave tax as entered if lookup fails
            pass

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
    errors: list[str] = []
    initial_email = ""
    initial_business_name = ""
    form = SignupForm()

    if request.method == "POST":
        data = request.POST.copy()
        initial_email = data.get("email", "").strip()
        initial_business_name = data.get("business_name", "").strip()

        if "password1" in data:
            data["password"] = data["password1"]
        if "password2" in data:
            data["password_confirm"] = data["password2"]
        if not data.get("username"):
            data["username"] = data.get("email", "")

        form = SignupForm(data)
        accept_tos = data.get("accept_tos") in {"on", "true", "1"}

        if form.is_valid() and accept_tos:
            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
            )
            full_name = (request.POST.get("full_name") or "").strip()
            if full_name:
                parts = full_name.split()
                user.first_name = parts[0]
                user.last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
                user.save(update_fields=["first_name", "last_name"])
            login(request, user)
            request.session["signup_business_name"] = initial_business_name
            return redirect("business_setup")

        if not accept_tos:
            errors.append("Please accept the Terms of Use and Privacy Policy.")
        for field_errors in form.errors.values():
            errors.extend(str(err) for err in field_errors)
        for err in form.non_field_errors():
            errors.append(str(err))

    signup_payload = json.dumps(
        {
            "action": request.path,
            "csrfToken": get_token(request),
            "errors": errors,
            "initialEmail": initial_email,
            "initialBusinessName": initial_business_name,
        },
        cls=DjangoJSONEncoder,
    )
    return render(request, "signup.html", {"signup_payload": signup_payload})


def _resolve_next_url(request):
    candidate = request.GET.get("next") or request.POST.get("next")
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
    ):
        return candidate
    return reverse("dashboard")


def _append_query_param(url: str, key: str, value: str | int) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query[key] = [str(value)]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def login_view(request):
    """
    Clean Django-only login view with remember-me behaviour.
    """
    next_url = _resolve_next_url(request)

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        remember = request.POST.get("remember") == "on"

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if remember:
                request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days
            else:
                request.session.set_expiry(0)
            return redirect(next_url)

        messages.error(request, "Invalid email/username or password.")

    dashboard_url = reverse("dashboard")
    next_field_value = "" if next_url == dashboard_url else next_url

    stored_messages = list(messages.get_messages(request))
    error_messages = [m.message for m in stored_messages if m.level_tag == "error"]

    login_payload = json.dumps(
        {
            "action": request.path,
            "csrfToken": get_token(request),
            "nextUrl": next_field_value,
            "next": next_field_value,
            "errors": error_messages,
        }
    )

    context = {
        "login_payload": login_payload,
        "next": next_field_value,
        "messages": [m.message for m in stored_messages],
    }
    return render(request, "login.html", context)


@require_http_methods(["GET", "POST"])
@login_required
def logout_view(request):
    logout(request)
    candidate_next = request.GET.get("next") or request.POST.get("next")
    if candidate_next and url_has_allowed_host_and_scheme(candidate_next, allowed_hosts={request.get_host()}):
        redirect_to = candidate_next
    else:
        redirect_to = reverse("login")

    wants_json = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest" or "application/json" in request.headers.get("Accept", "")
    if wants_json:
        return JsonResponse({"detail": "Logged out", "redirect": redirect_to})

    return redirect(redirect_to)


@login_required
def business_setup(request):
    business = get_current_business(request.user)
    if business is None:
        # Auto-create business if it doesn't exist
        business_name = request.session.get("signup_business_name") or "My Business"
        # Ensure name is unique for the user (or globally unique if constraint requires)
        # The model has unique=True globally. We might need to handle duplicates.
        # For now, let's try to create it.
        base_name = business_name
        counter = 1
        while Business.objects.filter(name=business_name).exists():
            business_name = f"{base_name} ({counter})"
            counter += 1
            
        business = Business.objects.create(
            owner_user=request.user,
            name=business_name,
            currency="CAD", # Default
            fiscal_year_start="01-01"
        )
        # Ensure default accounts
        ensure_default_accounts(business)
        
    if business.bank_setup_completed and request.GET.get("force") != "true":
        return redirect("workspace_home")

    # New onboarding flow: render the Bank Setup React shell.
    return render(request, "bank_setup.html")


@login_required
def account_settings(request):
    business = get_current_business(request.user)
    profile_form = UserProfileForm(instance=request.user, prefix="user")
    business_form = BusinessProfileForm(instance=business, prefix="business") if business else None
    password_form = PasswordChangeForm(request.user, prefix="password")

    if request.method == "POST":
        form_id = request.POST.get("form_id")
        if form_id == "profile":
            profile_form = UserProfileForm(request.POST, instance=request.user, prefix="user")
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Your profile details were updated.")
                return redirect("account_settings")
        elif form_id == "business" and business:
            business_form = BusinessProfileForm(request.POST, instance=business, prefix="business")
            if business_form.is_valid():
                business_form.save()
                messages.success(request, "Business settings updated.")
                return redirect("account_settings")
        elif form_id == "password":
            password_form = PasswordChangeForm(request.user, request.POST, prefix="password")
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, "Password updated successfully.")
                return redirect("account_settings")

    for form in (profile_form, business_form, password_form):
        if form is not None:
            setattr(form, "action", request.path)
            setattr(form, "method", "post")

    try:
        logout_all_url = reverse("logout_all")
    except NoReverseMatch:
        logout_all_url = "#"

    payload = {
        "csrfToken": get_token(request),
        "profileForm": _serialize_form(profile_form, "profile"),
        "businessForm": _serialize_form(business_form, "business"),
        "passwordForm": _serialize_form(password_form, "password"),
        "sessions": {
            "current_ip": request.META.get("REMOTE_ADDR", ""),
            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        },
        "postUrls": {
            "profile": request.path,
            "business": request.path,
            "password": request.path,
            "logoutAll": logout_all_url,
        },
        "messages": _messages_payload(request),
        "taxSettings": {
            "is_tax_registered": business.is_tax_registered if business else False,
            "tax_country": business.tax_country if business else "CA",
            "tax_region": business.tax_region if business else "",
            "tax_rates": [
                _tax_rate_payload(rate)
                for rate in TaxRate.objects.filter(business=business).order_by("name")
            ]
            if business
            else [],
        },
    }

    return render(
        request,
        "account_settings.html",
        {
            "account_settings_payload": json.dumps(payload, cls=DjangoJSONEncoder),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def api_tax_settings(request):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"detail": "No business"}, status=400)

    if request.method == "GET":
        tax_rates = list(
            TaxRate.objects.filter(business=business).order_by("name")
        )
        return JsonResponse(
            {
                "is_tax_registered": business.is_tax_registered,
                "tax_country": business.tax_country,
                "tax_region": business.tax_region,
                "tax_rates": [_tax_rate_payload(rate) for rate in tax_rates],
            }
        )

    payload = _json_from_body(request)
    country = (payload.get("tax_country") or business.tax_country or "CA").upper()
    region = (payload.get("tax_region") or "").upper()
    is_tax_registered = bool(payload.get("is_tax_registered"))
    if country not in {"CA", "US"}:
        return JsonResponse({"detail": "Unsupported country."}, status=400)

    business.is_tax_registered = is_tax_registered
    business.tax_country = country
    business.tax_region = region
    business.save(update_fields=["is_tax_registered", "tax_country", "tax_region"])

    tax_rates = list(
        TaxRate.objects.filter(business=business).order_by("name")
    )
    return JsonResponse(
        {
            "is_tax_registered": business.is_tax_registered,
            "tax_country": business.tax_country,
            "tax_region": business.tax_region,
            "tax_rates": [_tax_rate_payload(rate) for rate in tax_rates],
        }
    )


def _tax_rate_from_payload(business: Business, payload: dict, *, existing: TaxRate | None = None) -> dict:
    name = (payload.get("name") or "").strip()
    code = (payload.get("code") or slugify(name) or "").upper().replace("-", "_")
    if not name:
        raise ValidationError("Tax rate name is required.")
    if not code:
        raise ValidationError("Tax rate code is required.")

    percentage = None
    if "rate" in payload or "percentage" in payload:
        percentage = _percentage_from_rate_value(payload.get("rate") if "rate" in payload else payload.get("percentage"))
    elif existing is None:
        raise ValidationError("Tax rate percentage is required.")

    country = (payload.get("country") or business.tax_country or "CA").upper()
    region = (payload.get("region") or "").upper()
    applies_to_sales = bool(payload.get("applies_to_sales", True))
    applies_to_purchases = bool(payload.get("applies_to_purchases", True))
    is_active = payload.get("is_active")
    is_default_sales_rate = payload.get("is_default_sales_rate")
    is_default_purchase_rate = payload.get("is_default_purchase_rate")

    return {
        "name": name,
        "code": code[:20],
        "percentage": percentage,
        "country": country,
        "region": region[:10],
        "applies_to_sales": applies_to_sales,
        "applies_to_purchases": applies_to_purchases,
        "is_active": bool(is_active) if is_active is not None else None,
        "is_default_sales_rate": bool(is_default_sales_rate) if is_default_sales_rate is not None else None,
        "is_default_purchase_rate": bool(is_default_purchase_rate) if is_default_purchase_rate is not None else None,
    }


@login_required
@require_http_methods(["GET", "POST"])
def api_tax_rates(request):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"detail": "No business"}, status=400)

    if request.method == "GET":
        qs = TaxRate.objects.filter(business=business)
        if request.GET.get("active") == "1":
            qs = qs.filter(is_active=True)
        tax_rates = [_tax_rate_payload(rate) for rate in qs.order_by("name")]
        return JsonResponse({"tax_rates": tax_rates})

    payload = _json_from_body(request)
    try:
        parsed = _tax_rate_from_payload(business, payload)
    except ValidationError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)

    if TaxRate.objects.filter(business=business, code__iexact=parsed["code"]).exists():
        return JsonResponse({"detail": "A tax rate with this code already exists."}, status=400)

    with db_transaction.atomic():
        if parsed["is_default_sales_rate"]:
            _clear_default_tax_flags(business, sales=True)
        if parsed["is_default_purchase_rate"]:
            _clear_default_tax_flags(business, purchases=True)

        rate = TaxRate.objects.create(
            business=business,
            name=parsed["name"],
            code=parsed["code"],
            percentage=parsed["percentage"],
            country=parsed["country"],
            region=parsed["region"],
            applies_to_sales=parsed["applies_to_sales"],
            applies_to_purchases=parsed["applies_to_purchases"],
            is_active=True,
            is_default_sales=bool(parsed["is_default_sales_rate"]),
            is_default_purchases=bool(parsed["is_default_purchase_rate"]),
            is_default_sales_rate=bool(parsed["is_default_sales_rate"]),
            is_default_purchase_rate=bool(parsed["is_default_purchase_rate"]),
        )

    return JsonResponse({"tax_rate": _tax_rate_payload(rate)}, status=201)


@login_required
@require_http_methods(["PATCH", "DELETE"])
def api_tax_rate_detail(request, rate_id):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"detail": "No business"}, status=400)

    rate = TaxRate.objects.filter(pk=rate_id, business=business).first()
    if not rate:
        return JsonResponse({"detail": "Tax rate not found."}, status=404)

    if request.method == "DELETE":
        rate.is_active = False
        rate.is_default_sales = False
        rate.is_default_purchases = False
        rate.is_default_sales_rate = False
        rate.is_default_purchase_rate = False
        rate.save(
            update_fields=[
                "is_active",
                "is_default_sales",
                "is_default_purchases",
                "is_default_sales_rate",
                "is_default_purchase_rate",
            ]
        )
        return JsonResponse({"tax_rate": _tax_rate_payload(rate)})

    payload = _json_from_body(request)
    try:
        parsed = _tax_rate_from_payload(business, payload, existing=rate)
    except ValidationError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)

    if (
        parsed["code"]
        and parsed["code"].lower() != (rate.code or "").lower()
        and TaxRate.objects.filter(business=business, code__iexact=parsed["code"])
        .exclude(pk=rate.id)
        .exists()
    ):
        return JsonResponse({"detail": "A tax rate with this code already exists."}, status=400)

    with db_transaction.atomic():
        if parsed["is_default_sales_rate"]:
            _clear_default_tax_flags(business, sales=True, exclude_id=rate.id)
        if parsed["is_default_purchase_rate"]:
            _clear_default_tax_flags(business, purchases=True, exclude_id=rate.id)

        update_fields = []
        for field in ("name", "code", "country", "region", "applies_to_sales", "applies_to_purchases"):
            new_val = parsed[field]
            if new_val is not None and getattr(rate, field) != new_val:
                setattr(rate, field, new_val)
                update_fields.append(field)
        if parsed["percentage"] is not None and rate.percentage != parsed["percentage"]:
            rate.percentage = parsed["percentage"]
            update_fields.append("percentage")
        if parsed["is_active"] is not None and rate.is_active != parsed["is_active"]:
            rate.is_active = parsed["is_active"]
            update_fields.append("is_active")
        if parsed["is_default_sales_rate"] is not None:
            rate.is_default_sales = parsed["is_default_sales_rate"]
            rate.is_default_sales_rate = parsed["is_default_sales_rate"]
            update_fields.extend(["is_default_sales", "is_default_sales_rate"])
        if parsed["is_default_purchase_rate"] is not None:
            rate.is_default_purchases = parsed["is_default_purchase_rate"]
            rate.is_default_purchase_rate = parsed["is_default_purchase_rate"]
            update_fields.extend(["is_default_purchases", "is_default_purchase_rate"])

        if update_fields:
            rate.save(update_fields=list(dict.fromkeys(update_fields)))

    return JsonResponse({"tax_rate": _tax_rate_payload(rate)})


@login_required
def dashboard(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    empty_workspace = is_empty_workspace(business)
    start_books_url = reverse("customer_create")
    bank_import_url = reverse("bank_import")

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

    # Build cashflow from actual BankTransaction cash movement
    for i in range(6):
        month_start = _add_months(start_month, i)
        next_month_start = _add_months(month_start, 1)
        month_end = next_month_start - timedelta(days=1)

        labels.append(month_start.strftime("%b %Y"))

        # Get all bank transactions for this month
        month_transactions = BankTransaction.objects.filter(
            bank_account__business=business,
            date__gte=month_start,
            date__lte=month_end,
        )

        # Sum inflows (positive amounts = deposits)
        inflows = (
            month_transactions.filter(amount__gte=0).aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )

        # Sum outflows (negative amounts = withdrawals, take absolute value)
        outflows_sum = (
            month_transactions.filter(amount__lt=0).aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )
        outflows = abs(outflows_sum)

        income_series.append(float(inflows))
        expense_series.append(float(outflows))

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
    supplier_ids = [s.id for s in supplier_stats_qs]  # type: ignore[attr-defined]
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

    recent_suppliers = []
    for supplier in supplier_stats_qs:
        supplier.mtd_spend = supplier.mtd_spend or Decimal("0")  # type: ignore[attr-defined]
        supplier.payment_count = supplier.payment_count or 0  # type: ignore[attr-defined]
        supplier.default_category_name = supplier_recent_category.get(supplier.id)  # type: ignore[attr-defined]
        recent_suppliers.append(supplier)

    if not recent_suppliers:
        fallback_suppliers = Supplier.objects.filter(business=business).order_by("-created_at")[:5]
        for supplier in fallback_suppliers:
            supplier.mtd_spend = Decimal("0")  # type: ignore[attr-defined]
            supplier.payment_count = 0  # type: ignore[attr-defined]
        recent_suppliers = list(fallback_suppliers)

    unpaid_expenses_total = (
        expenses_all_qs.filter(status__in=[Expense.Status.UNPAID, Expense.Status.PARTIAL]).aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )

    cash_balances = account_balances_for_business(business)
    cash_on_hand = Decimal("0")
    for account in cash_balances["accounts"]:
        if account["type"] == Account.AccountType.ASSET:
            cash_on_hand += account["balance"]

    open_invoices_qs = invoices_qs.filter(status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL])
    open_invoices_total = open_invoices_qs.aggregate(total=Sum("grand_total"))["total"] or Decimal("0")
    open_invoices_count = open_invoices_qs.count()

    bank_feed_items = (
        BankTransaction.objects.filter(bank_account__business=business).order_by("-date", "-id")[:5]
    )
    bank_reco = []
    if business:
        for ba in BankAccount.objects.filter(business=business).select_related("account"):
            unreconciled = (
                BankTransaction.objects.filter(
                    bank_account=ba,
                    is_reconciled=False,
                )
                .exclude(status=BankTransaction.TransactionStatus.EXCLUDED)
                .count()
            )
            bank_reco.append(
                {
                    "id": ba.id,
                    "name": ba.name,
                    "unreconciled": unreconciled,
                    "account_code": ba.account.code if ba.account else "",
                }
            )

    def _decimal_to_float(value):
        if value is None:
            return 0.0
        if isinstance(value, Decimal):
            return float(value)
        return float(value)

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
        recent_invoices_payload.append(
            {
                "number": inv.invoice_number,
                "customer": inv.customer.name if inv.customer else "",
                "status": inv.status,
                "issue_date": inv.issue_date.isoformat() if inv.issue_date else "",
                "amount": _decimal_to_float(inv.grand_total),
                "due_label": due_label,
                "url": reverse("invoice_update", args=[inv.pk]),
            }
        )

    bank_feed_payload = []
    for tx in bank_feed_items:
        note_value = getattr(tx, "status_label", None)
        if note_value is None:
            note_value = getattr(tx, "statusLabel", tx.status)
        direction = "in" if (tx.amount or Decimal("0")) >= 0 else "out"
        bank_feed_payload.append(
            {
                "description": tx.description,
                "note": note_value,
                "amount": _decimal_to_float(tx.amount),
                "direction": direction,
                "date": tx.date.isoformat() if tx.date else "",
            }
        )

    expense_summary_payload = [
        {
            "name": row["name"],
            "total": _decimal_to_float(row["total"]),
        }
        for row in expense_summary
    ]

    tax_position = {"sales_tax_payable": Decimal("0.00"), "recoverable_tax_asset": Decimal("0.00"), "net_tax": Decimal("0.00")}
    tax_position_label = ""
    if business:
        tax_position = net_tax_position(business)
        if tax_position["net_tax"] > 0:
            tax_position_label = "Estimated tax owing"
        elif tax_position["net_tax"] < 0:
            tax_position_label = "Estimated tax refund receivable"
        else:
            tax_position_label = "Net tax is balanced"

    dashboard_payload = json.dumps(
        {
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
                "unpaid_expenses_total": _decimal_to_float(unpaid_expenses_total),
                "revenue_month": _decimal_to_float(total_income_month),
                "expenses_month": _decimal_to_float(total_expenses_month),
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
            "expenseSummary": expense_summary_payload,
            "cashflow": {
                "labels": labels,
                "income": income_series,
                "expenses": expense_series,
            },
            "topSuppliers": [
                {
                    "name": supplier.name,
                    "mtdSpend": _decimal_to_float(getattr(supplier, "mtd_spend", Decimal("0"))),
                    "paymentCount": getattr(supplier, "payment_count", 0),
                    "category": getattr(supplier, "default_category_name", None) or "",
                }
                for supplier in recent_suppliers
            ],
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
        },
        cls=DjangoJSONEncoder,
    )

    context = {
        "business": business,
        "empty_workspace": empty_workspace,
        "start_books_url": start_books_url,
        "import_csv_url": bank_import_url,
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
        "tax_position": tax_position,
        "tax_position_label": tax_position_label,
        "bank_reconciliation": bank_reco,
        "dashboard_payload": dashboard_payload,
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
            supplier_any = cast(Any, supplier)
            expenses_all_qs = supplier_any.expenses.all()
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
            supplier_any = cast(Any, supplier)
            supplier_any._ytd_spend_cache = ytd  # cache for percent calcs
            supplier_any.mtd_spend = mtd
            supplier_any.default_category_name = default_category
            supplier_any.initials = self._initials(supplier.name)
            supplier_any.open_balance = open_balance

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
            selected_supplier_any = cast(Any, selected_supplier)
            ytd_percent = int(
                (selected_supplier_any._ytd_spend_cache / total_ytd * Decimal("100")).quantize(Decimal("1"))
            )
        if selected_supplier and total_mtd > 0:
            mtd_percent = int(
                (cast(Any, selected_supplier).mtd_spend / total_mtd * Decimal("100")).quantize(Decimal("1"))
            )

        avg_monthly_selected = Decimal("0")
        if selected_supplier and months_so_far > 0:
            avg_monthly_selected = (
                cast(Any, selected_supplier)._ytd_spend_cache / Decimal(months_so_far)
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
            
            # Handle ?next= redirect
            next_url = request.POST.get("next") or request.GET.get("next")
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}
            ):
                return redirect(next_url)
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
            
            # Handle ?next= redirect
            next_url = request.POST.get("next") or request.GET.get("next")
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}
            ):
                return redirect(next_url)
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
            
            # Handle ?next= redirect
            next_url = request.POST.get("next") or request.GET.get("next")
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}
            ):
                return redirect(next_url)
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
    tax_rate_field = cast(ModelChoiceField, form.fields["tax_rate"])
    return render(
        request,
        "invoice_form.html",
        {
            "business": business,
            "form": form,
            "invoice": None,
            "invoice_preview": _invoice_preview(form),
            "tax_rates": list(
                tax_rate_field.queryset.values("id", "name", "percentage")
            ),
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
    tax_rate_field = cast(ModelChoiceField, form.fields["tax_rate"])
    return render(
        request,
        "invoice_form.html",
        {
            "business": business,
            "form": form,
            "invoice": invoice,
            "invoice_preview": _invoice_preview(form),
            "tax_rates": list(
                tax_rate_field.queryset.values("id", "name", "percentage")
            ),
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


def invoice_public_view(request, token):
    invoice = get_object_or_404(Invoice.objects.select_related("business", "customer"), email_token=token)
    return render(request, "invoices/public_invoice.html", {"invoice": invoice})


def invoice_email_open_view(request, token):
    log = get_object_or_404(InvoiceEmailLog, open_token=token)
    if log.opened_at is None:
        log.opened_at = timezone.now()
        log.opened_ip = request.META.get("REMOTE_ADDR")
        log.opened_user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:512]
        log.save(update_fields=["opened_at", "opened_ip", "opened_user_agent"])
    return HttpResponse(b"", content_type="image/gif")


@login_required
def invoice_pdf_view(request, pk):
    """Secure PDF download view for internal users, scoped to their business."""
    business = get_current_business(request.user)
    if business is None:
        return HttpResponseBadRequest("No business context")
    
    # Scope by business to prevent unauthorized access
    invoice = get_object_or_404(
        Invoice.objects.select_related("business", "customer"),
        pk=pk,
        business=business,
    )
    
    # Render PDF using the same template as email attachments
    html_content = render_to_string(
        "invoices/public_invoice_pdf.html",
        {"invoice": invoice},
        request=request,
    )
    
    pdf_io = io.BytesIO()
    if HTML:
        try:
            HTML(string=html_content, base_url=request.build_absolute_uri("/")).write_pdf(pdf_io)
            pdf_io.seek(0)
            safe_number = getattr(invoice, "invoice_number", None) or f"{invoice.pk}"
            response = HttpResponse(pdf_io.read(), content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="Invoice-{safe_number}.pdf"'
            return response
        except Exception as exc:
            # If PDF generation fails, return a helpful error
            return HttpResponseBadRequest(f"PDF generation failed: {str(exc)}")
    else:
        return HttpResponseBadRequest("PDF generation unavailable: WeasyPrint not installed")


@login_required
@require_POST
def invoice_send_email_view(request, pk):
    import smtplib
    
    business = get_current_business(request.user)
    if business is None:
        return HttpResponseBadRequest("No business context")

    invoice = get_object_or_404(Invoice.objects.select_related("business", "customer"), pk=pk, business=business)

    to_email = request.POST.get("to_email") or getattr(invoice.customer, "email", None)
    if not to_email:
        return HttpResponseBadRequest("No email address provided")
    
    # Determine from_email and reply_to from business or settings/user fallback
    from_email = (
        business.email_from
        or getattr(settings, "DEFAULT_FROM_EMAIL", None)
        or getattr(business.owner_user, "email", None)
        or getattr(request.user, "email", None)
    )
    reply_to_email = business.reply_to_email or from_email
    
    # Require a configured sender email
    if not from_email:
        error_msg = "No sender email is configured. Add a business email in Account settings before sending invoices."
        invoice.email_last_error = error_msg
        invoice.save(update_fields=["email_last_error"])
        return JsonResponse({"ok": False, "error": error_msg}, status=400)

    public_url = request.build_absolute_uri(reverse("invoice_public_view", args=[invoice.email_token]))
    business_name = getattr(invoice.business, "name", "Our Company")
    customer_name = getattr(invoice.customer, "name", "")
    amount = (
        getattr(invoice, "grand_total", None)
        or getattr(invoice, "net_total", None)
        or getattr(invoice, "total_amount", None)
        or getattr(invoice, "total", None)
    )

    default_subject = f"Invoice {getattr(invoice, 'invoice_number', None) or invoice.pk} from {business_name}"
    default_body_text = (
        f"Hi {customer_name},\n\n"
        f"You have a new invoice from {business_name}.\n"
        f"Total: {amount}\n\n"
        f"You can view it here: {public_url}\n\n"
        f"Thank you."
    )
    default_body_html = f"""
        <p>Hi {customer_name},</p>
        <p>You have a new invoice from <strong>{business_name}</strong>.</p>
        <p><strong>Total:</strong> {amount}</p>
        <p><a href="{public_url}">View your invoice</a></p>
        <p>Thank you.</p>
    """

    ctx = {
        "invoice": invoice,
        "business": invoice.business,
        "customer": invoice.customer,
        "public_url": public_url,
    }
    template = getattr(invoice.business, "invoice_email_template", None)
    if template:
        subject = template.render_subject(ctx, default_subject)
        text_body = template.render_body(ctx, default_body_text)
        html_body = template.render_body(ctx, default_body_html)
    else:
        subject = default_subject
        text_body = default_body_text
        html_body = default_body_html

    # Optional CC flag from caller
    cc_me_flag = request.POST.get("cc_me") in {"1", "true", "on", "yes"}

    # Render PDF attachment
    pdf_content = None
    if HTML:
        try:
            html_invoice = render_to_string("invoices/public_invoice_pdf.html", {"invoice": invoice}, request=request)
            pdf_io = io.BytesIO()
            HTML(string=html_invoice, base_url=request.build_absolute_uri("/")).write_pdf(pdf_io)
            pdf_io.seek(0)
            pdf_content = pdf_io.read()
        except Exception as pdf_exc:  # pragma: no cover - avoid blocking send on PDF errors
            invoice.email_last_error = str(pdf_exc)
            invoice.save(update_fields=["email_last_error"])
            logger = logging.getLogger(__name__)
            logger.info("Skipping invoice PDF attachment because rendering failed: %s", pdf_exc)
    else:
        logging.getLogger(__name__).info("Skipping invoice PDF attachment because weasyprint is unavailable.")

    log = InvoiceEmailLog.objects.create(
        invoice=invoice,
        to_email=to_email,
        subject=subject,
        status=InvoiceEmailLog.STATUS_SENT,
        message_preview=text_body[:500],
        cc_me=bool(cc_me_flag),
    )

    tracking_url = request.build_absolute_uri(reverse("invoice_email_open", args=[log.open_token]))
    tracking_img = (
        f'<img src="{tracking_url}" alt="" width="1" height="1" style="display:none;border:0;" />'
    )

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email,
            to=[to_email],
            cc=[invoice.business.owner_user.email] if cc_me_flag and getattr(invoice.business, "owner_user", None) else None,
            reply_to=[reply_to_email] if reply_to_email else None,
        )
        if pdf_content:
            msg.attach(
                filename=f"Invoice-{getattr(invoice, 'invoice_number', None) or invoice.pk}.pdf",
                content=pdf_content,
                mimetype="application/pdf",
            )
        msg.attach_alternative(html_body + tracking_img, "text/html")
        msg.send()
        invoice.mark_email_sent(to_email)
        return JsonResponse({"status": "ok", "sent_to": to_email})
    except (smtplib.SMTPException, OSError) as exc:
        # Map connection errors to friendly messages
        error_message = str(exc)
        friendly_message = "Email delivery failed: unable to connect to email server. Check your email settings."
        invoice.email_last_error = error_message
        invoice.save(update_fields=["email_last_error"])
        log.status = InvoiceEmailLog.STATUS_ERROR
        log.error_message = error_message
        log.save(update_fields=["status", "error_message"])
        return JsonResponse({"ok": False, "error": friendly_message}, status=502)
    except Exception as exc:  # pragma: no cover - other unexpected errors
        error_message = str(exc)
        invoice.email_last_error = error_message
        invoice.save(update_fields=["email_last_error"])
        log.status = InvoiceEmailLog.STATUS_ERROR
        log.error_message = error_message
        log.save(update_fields=["status", "error_message"])
        return JsonResponse({"ok": False, "error": error_message}, status=500)


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
def cashflow_report_view(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    today = timezone.localdate()
    qs = (
        BankTransaction.objects.filter(bank_account__business=business)
        .select_related("category")
        .order_by("date")
    )

    start_date = _add_months(today.replace(day=1), -5)
    qs = qs.filter(date__gte=start_date)

    periods: OrderedDict[tuple[int, int], dict[str, Decimal]] = OrderedDict()
    cursor = start_date
    for _ in range(6):
        key = (cursor.year, cursor.month)
        periods[key] = {"inflows": Decimal("0.00"), "outflows": Decimal("0.00")}
        cursor = _add_months(cursor, 1)

    for tx in qs:
        key = (tx.date.year, tx.date.month)
        if key not in periods:
            continue
        amount = tx.amount or Decimal("0.00")
        if amount >= 0:
            periods[key]["inflows"] += amount
        else:
            periods[key]["outflows"] += abs(amount)

    total_inflows = Decimal("0.00")
    total_outflows = Decimal("0.00")
    trend: list[dict[str, object]] = []
    for (year, month), aggregates in periods.items():
        inflows = aggregates["inflows"]
        outflows = aggregates["outflows"]
        net = inflows - outflows
        total_inflows += inflows
        total_outflows += outflows
        label = date(year, month, 1).strftime("%b %Y")
        trend.append(
            {
                "periodLabel": label,
                "inflows": float(inflows),
                "outflows": float(outflows),
                "net": float(net),
            }
        )

    net_change = total_inflows - total_outflows

    activities = {
        "operating": float(net_change),
        "investing": 0.0,
        "financing": 0.0,
    }

    driver_rows = (
        qs.values("category__name")
        .annotate(net=Sum("amount"))
        .order_by("-net")[:5]
    )
    drivers: list[dict[str, object]] = []
    for row in driver_rows:
        label = row["category__name"] or "Uncategorized"
        amount = row["net"] or Decimal("0.00")
        driver_id = slugify(label) or f"driver-{len(drivers) + 1}"
        drivers.append(
            {
                "id": driver_id,
                "label": label,
                "amount": float(amount),
                "type": "inflow" if amount >= 0 else "outflow",
            }
        )

    current_cash = (
        BankTransaction.objects.filter(bank_account__business=business).aggregate(total=Sum("amount"))[
            "total"
        ]
        or Decimal("0.00")
    )

    avg_monthly_burn = (
        (total_outflows - total_inflows) / Decimal(len(periods))
        if total_outflows > total_inflows
        else Decimal("0.00")
    )
    runway_label = None
    if avg_monthly_burn > 0 and current_cash > 0:
        months = current_cash / avg_monthly_burn
        runway_label = f"{months.quantize(Decimal('0.1'))} months"

    payload = {
        "username": request.user.first_name or request.user.username,
        "asOfLabel": today.strftime("As of %b %d, %Y"),
        "baseCurrency": business.currency or "USD",
        "summary": {
            "netChange": float(net_change),
            "totalInflows": float(total_inflows),
            "totalOutflows": float(total_outflows),
            "runwayLabel": runway_label,
        },
        "trend": trend,
        "activities": activities,
        "topDrivers": drivers,
        "bankingUrl": reverse("banking_accounts_feed"),
        "invoicesUrl": reverse("invoice_list"),
        "expensesUrl": reverse("expense_list"),
    }

    context = {
        "cashflow_data_json": json.dumps(payload, cls=DjangoJSONEncoder),
    }
    return render(request, "reports/cashflow_report.html", context)


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

    return_to = (
        request.POST.get("return_to")
        or request.GET.get("returnTo")
        or request.GET.get("return_to")
    )

    if request.method == "POST":
        form = BankAccountForm(request.POST, business=business)
        if form.is_valid():
            bank_account = form.save()
            messages.success(request, "Bank account created.")
            if return_to and url_has_allowed_host_and_scheme(
                return_to, allowed_hosts={request.get_host()}
            ):
                redirect_url = _append_query_param(return_to, "bank_account", bank_account.id)
                return redirect(redirect_url)
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
            "return_to": return_to,
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
        bank_account_qs = form.fields["bank_account"].queryset
        bank_account_count = bank_account_qs.count()
        add_bank_account_url = f"{reverse('bank_account_create')}?{urlencode({'returnTo': request.get_full_path()})}"
        return render(
            request,
            self.template_name,
            {
                "business": business,
                "form": form,
                "bank_account_count": bank_account_count,
                "add_bank_account_url": add_bank_account_url,
            },
        )

    def post(self, request, *args, **kwargs):
        business = get_current_business(request.user)
        if business is None:
            return redirect("business_setup")

        form = BankStatementImportForm(request.POST, request.FILES, business=business)
        if not form.is_valid():
            bank_account_qs = form.fields["bank_account"].queryset
            bank_account_count = bank_account_qs.count()
            add_bank_account_url = f"{reverse('bank_account_create')}?{urlencode({'returnTo': request.get_full_path()})}"
            return render(
                request,
                self.template_name,
                {
                    "business": business,
                    "form": form,
                    "bank_account_count": bank_account_count,
                    "add_bank_account_url": add_bank_account_url,
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
                                expense.journalentry_set.order_by("-date", "-id").first()  # type: ignore[attr-defined]
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
                    tx.status = BankTransaction.TransactionStatus.LEGACY_CREATED
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
                    invoice.journalentry_set.filter(description__icontains="Invoice paid")  # type: ignore[attr-defined]
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
                "status_label": cast(Any, tx).get_status_display(),  # type: ignore[attr-defined]
                "reconciliation_status": tx.reconciliation_status
                or BankTransaction.RECO_STATUS_UNRECONCILED,
                "allocated_amount": float(tx.allocated_amount or Decimal("0.00")),
                "side": "IN" if tx.amount >= 0 else "OUT",
                "category": tx.category.name if tx.category else "",
                "category_id": tx.category_id,  # type: ignore[attr-defined]
                "counterparty": counterparty,
                "customer": getattr(tx.customer, "name", ""),
                "supplier": getattr(tx.supplier, "name", ""),
                "matched_invoice_id": tx.matched_invoice_id,  # type: ignore[attr-defined]
                "matched_expense_id": tx.matched_expense_id,  # type: ignore[attr-defined]
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
            kind_raw = str(raw["type"]).upper()
            amount = Decimal(str(raw["amount"]))
        except (KeyError, TypeError, InvalidOperation, ValueError):
            raise ValidationError("Invalid allocation payload.")
        allowed_kinds: tuple[AllocationKind, ...] = (
            "INVOICE",
            "BILL",
            "DIRECT_INCOME",
            "DIRECT_EXPENSE",
            "CREDIT_NOTE",
        )
        if kind_raw not in allowed_kinds:
            raise ValidationError("Invalid allocation type.")
        tax_treatment = _normalize_tax_treatment(raw.get("tax_treatment"))
        if tax_treatment and tax_treatment not in ("NONE", "INCLUDED", "ON_TOP"):
            raise ValidationError("Invalid tax treatment.")
        tax_rate_id = raw.get("tax_rate_id")
        if tax_rate_id not in (None, "", 0, "0"):
            try:
                tax_rate_id = int(tax_rate_id)
            except (TypeError, ValueError):
                raise ValidationError("Invalid tax rate id.")
        else:
            tax_rate_id = None
        return Allocation(
            kind=cast(AllocationKind, kind_raw),
            id=raw.get("id"),
            account_id=raw.get("account_id"),
            amount=amount,
            tax_treatment=tax_treatment,
            tax_rate_id=tax_rate_id,
        )

    try:
        allocation_items = payload.get("allocations") or []
        allocations = [_build_allocation(item) for item in allocation_items]

        has_active_tax_rates = (
            TaxRate.objects.filter(business=business, is_active=True).exists()
        )
        for alloc in allocations:
            alloc.tax_treatment = _normalize_tax_treatment(alloc.tax_treatment)
            if alloc.tax_treatment != "NONE":
                if not has_active_tax_rates:
                    raise ValidationError("No active tax rates are configured for this business.")
                if not alloc.tax_rate_id:
                    raise ValidationError("Select a tax rate when tax is enabled.")
                _load_tax_rate(
                    business,
                    alloc.tax_rate_id,
                    require_sales=alloc.kind == "DIRECT_INCOME",
                    require_purchases=alloc.kind == "DIRECT_EXPENSE",
                )

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
                "status_label": cast(Any, bank_tx).get_status_display(),  # type: ignore[attr-defined]
                "allocated_amount": str(bank_tx.allocated_amount or Decimal("0.00")),
            },
        }
    )


@login_required
def api_banking_feed_metadata(request):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"detail": "No business"}, status=400)

    defaults = ensure_default_accounts(business)

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
    expense_accounts = list(
        Account.objects.filter(business=business, type=Account.AccountType.EXPENSE)
        .order_by("code", "name")
        .values("id", "name", "code")
    )
    income_accounts = list(
        Account.objects.filter(business=business, type=Account.AccountType.INCOME)
        .order_by("code", "name")
        .values("id", "name", "code")
    )
    equity_accounts = list(
        Account.objects.filter(business=business, type=Account.AccountType.EQUITY)
        .order_by("code", "name")
        .values("id", "name", "code")
    )
    tax_rates = [
        _tax_rate_payload(rate)
        for rate in TaxRate.objects.filter(business=business, is_active=True).order_by("name")
    ]
    return JsonResponse(
        {
            "expense_categories": expense_categories,
            "income_categories": income_categories,
            "suppliers": suppliers,
            "customers": customers,
            "expense_accounts": expense_accounts,
            "income_accounts": income_accounts,
            "equity_accounts": equity_accounts,
            "tax_rates": tax_rates,
            "tax_accounts": {
                "sales_tax_payable_id": getattr(defaults.get("tax"), "id", None),
                "tax_recoverable_id": getattr(defaults.get("tax_recoverable"), "id", None),
            },
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
    tax_treatment = _normalize_tax_treatment(payload.get("tax_treatment"))
    if tax_treatment not in ("NONE", "INCLUDED", "ON_TOP"):
        return JsonResponse({"detail": "Invalid tax treatment."}, status=400)
    tax_rate_id = payload.get("tax_rate_id")
    if tax_treatment != "NONE" and tax_rate_id in (None, "", 0, "0"):
        return JsonResponse({"detail": "Select a tax code when tax is enabled."}, status=400)
    amount_override = payload.get("amount")

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

        has_active_tax_rates = TaxRate.objects.filter(business=business, is_active=True).exists()
        tax_rate = None
        if tax_treatment != "NONE":
            if not has_active_tax_rates:
                return JsonResponse(
                    {"detail": "No active tax rates are configured for this business."},
                    status=400,
                )
            try:
                tax_rate = _load_tax_rate(
                    business,
                    tax_rate_id,
                    require_sales=bank_tx.amount > 0,
                    require_purchases=bank_tx.amount < 0,
                )
            except ValidationError as exc:
                return JsonResponse({"detail": str(exc)}, status=400)

        bank_abs = abs(bank_tx.amount)
        try:
            base_amount = Decimal(
                str(amount_override if amount_override not in (None, "", "0") else bank_abs)
            )
        except (InvalidOperation, ValueError):
            return JsonResponse({"detail": "Invalid amount."}, status=400)
        rate_pct = tax_rate.percentage if tax_rate else Decimal("0.00")
        if tax_treatment == "ON_TOP" and amount_override in (None, "", "0"):
            divisor = Decimal("1.00") + (rate_pct / Decimal("100"))
            if divisor != 0:
                base_amount = (bank_abs / divisor).quantize(Decimal("0.01"))
        try:
            net_amount, tax_amount, gross_amount = compute_tax_breakdown(
                base_amount, tax_treatment, rate_pct
            )
        except Exception as exc:
            return JsonResponse({"detail": str(exc)}, status=400)
        if (gross_amount - bank_abs).copy_abs() > Decimal("0.01"):
            return JsonResponse(
                {"detail": "Amounts do not reconcile with the bank transaction."}, status=400
            )

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
                amount=net_amount,
                status=Expense.Status.PAID,
                paid_date=bank_tx.date,
            )
            expense.tax_rate = tax_rate  # type: ignore[assignment]  # assign FK directly
            try:
                expense.save()
            except Exception as exc:  # pragma: no cover - surfaced to UI
                return JsonResponse(
                    {"detail": f"Unable to save expense: {exc}"},
                    status=400,
                )
            journal_entry = expense.journalentry_set.order_by("-date", "-id").first()  # type: ignore[attr-defined]
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
            if journal_entry:
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
                    tax_treatment=tax_treatment,
                    tax_rate=tax_rate,
                    base_amount=base_amount,
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
            invoice.journalentry_set.filter(description__icontains="Invoice paid")  # type: ignore[attr-defined]
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
            journal_entry = expense.journalentry_set.order_by("-date", "-id").first()  # type: ignore[attr-defined]

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
        if journal_entry:
            add_bank_match(bank_tx, journal_entry)
        else:
            recompute_bank_transaction_status(bank_tx)

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
@require_POST
def api_banking_feed_add_entry(request, tx_id):
    """
    Add a simple one-line ledger posting for the bank transaction (bank + category + optional tax).
    """
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"detail": "No business"}, status=400)

    payload = _json_from_body(request)
    if not isinstance(payload, dict):
        return JsonResponse({"detail": "Invalid payload."}, status=400)

    direction_raw = str(payload.get("direction") or "").upper()
    account_id = payload.get("account_id")
    if not account_id:
        return JsonResponse({"detail": "account_id is required"}, status=400)
    try:
        account = Account.objects.get(pk=int(account_id), business=business)
    except (Account.DoesNotExist, ValueError, TypeError):
        return JsonResponse({"detail": "Account not found"}, status=404)

    tax_treatment = _normalize_tax_treatment(payload.get("tax_treatment"))
    if tax_treatment not in ("NONE", "INCLUDED", "ON_TOP"):
        return JsonResponse({"detail": "Invalid tax treatment."}, status=400)
    tax_rate_id = payload.get("tax_rate_id")
    if tax_treatment != "NONE" and tax_rate_id in (None, "", 0, "0"):
        return JsonResponse({"detail": "Select a tax code when tax is enabled."}, status=400)

    memo = (payload.get("memo") or "").strip()
    contact_customer_id = payload.get("customer_id")
    contact_supplier_id = payload.get("supplier_id")
    customer = None
    supplier = None
    if contact_customer_id:
        try:
            customer = Customer.objects.get(pk=int(contact_customer_id), business=business)
        except (Customer.DoesNotExist, ValueError, TypeError):
            return JsonResponse({"detail": "Customer not found."}, status=404)
    if contact_supplier_id:
        try:
            supplier = Supplier.objects.get(pk=int(contact_supplier_id), business=business)
        except (Supplier.DoesNotExist, ValueError, TypeError):
            return JsonResponse({"detail": "Supplier not found."}, status=404)

    with db_transaction.atomic():
        bank_tx = _get_bank_tx_for_business(business, tx_id, for_update=True)
        if not bank_tx:
            return JsonResponse({"detail": "Transaction not found"}, status=404)
        if bank_tx.status not in (
            BankTransaction.TransactionStatus.NEW,
            BankTransaction.TransactionStatus.PARTIAL,
        ):
            return JsonResponse({"detail": "Only new transactions can be added."}, status=400)

        bank_abs = abs(bank_tx.amount or Decimal("0.00"))
        if bank_abs == 0:
            return JsonResponse({"detail": "Transaction amount is zero."}, status=400)

        direction = direction_raw or ("IN" if bank_tx.amount >= 0 else "OUT")
        if direction not in ("IN", "OUT"):
            return JsonResponse({"detail": "Invalid direction."}, status=400)
        if bank_tx.amount >= 0 and direction == "OUT":
            return JsonResponse({"detail": "Deposit cannot be posted as money out."}, status=400)
        if bank_tx.amount < 0 and direction == "IN":
            return JsonResponse({"detail": "Withdrawal cannot be posted as money in."}, status=400)

        has_active_tax_rates = TaxRate.objects.filter(business=business, is_active=True).exists()
        tax_rate = None
        if tax_treatment != "NONE":
            if not has_active_tax_rates:
                return JsonResponse(
                    {"detail": "No active tax rates are configured for this business."},
                    status=400,
                )
            try:
                tax_rate = _load_tax_rate(
                    business,
                    tax_rate_id,
                    require_sales=direction == "IN",
                    require_purchases=direction == "OUT",
                )
            except ValidationError as exc:
                return JsonResponse({"detail": str(exc)}, status=400)

        amount_override = payload.get("amount")
        try:
            # Sanitize amount input: remove commas to support locale formatting (e.g., "1,234.50" or "15,50")
            amount_str = str(amount_override if amount_override not in (None, "", "0") else bank_abs)
            amount_str = amount_str.replace(",", "")
            base_amount = Decimal(amount_str)
        except (InvalidOperation, ValueError):
            return JsonResponse({"detail": "Invalid amount."}, status=400)
        rate_pct = tax_rate.percentage if tax_rate else Decimal("0.00")
        if tax_treatment == "ON_TOP" and amount_override in (None, "", "0"):
            divisor = Decimal("1.00") + (rate_pct / Decimal("100"))
            if divisor != 0:
                base_amount = (bank_abs / divisor).quantize(Decimal("0.01"))
        try:
            net_amount, tax_amount, gross_amount = compute_tax_breakdown(
                base_amount, tax_treatment, rate_pct
            )
        except Exception as exc:
            return JsonResponse({"detail": str(exc)}, status=400)

        if (gross_amount - bank_abs).copy_abs() > Decimal("0.01"):
            return JsonResponse(
                {"detail": "Amounts do not reconcile with the bank transaction."}, status=400
            )

        defaults = ensure_default_accounts(business)
        bank_account = bank_tx.bank_account.account or defaults.get("cash")
        if bank_account is None:
            return JsonResponse({"detail": "Link this bank account to a ledger account."}, status=400)
        tax_account = defaults.get("tax")
        recoverable_account = defaults.get("tax_recoverable") or tax_account
        if direction == "IN" and tax_amount and tax_amount != 0 and not tax_account:
            return JsonResponse({"detail": "Configure a sales tax account before posting tax."}, status=400)
        if direction == "OUT" and tax_amount and tax_amount != 0 and not recoverable_account:
            return JsonResponse({"detail": "Configure a recoverable tax account before posting tax."}, status=400)

        entry = JournalEntry.objects.create(
            business=business,
            date=bank_tx.date,
            description=(memo or bank_tx.description or "Bank entry")[:255],
        )
        if direction == "IN":
            JournalLine.objects.create(
                journal_entry=entry,
                account=bank_account,
                debit=gross_amount,
                credit=Decimal("0.00"),
                description="Bank deposit",
            )
            JournalLine.objects.create(
                journal_entry=entry,
                account=account,
                debit=Decimal("0.00"),
                credit=net_amount,
                description="Category",
            )
            if tax_amount and tax_account:
                JournalLine.objects.create(
                    journal_entry=entry,
                    account=tax_account,
                    debit=Decimal("0.00"),
                    credit=tax_amount,
                    description="Tax",
                )
        else:
            JournalLine.objects.create(
                journal_entry=entry,
                account=account,
                debit=net_amount,
                credit=Decimal("0.00"),
                description="Category",
            )
            if tax_amount and recoverable_account:
                JournalLine.objects.create(
                    journal_entry=entry,
                    account=recoverable_account,
                    debit=tax_amount,
                    credit=Decimal("0.00"),
                    description="Tax",
                )
            JournalLine.objects.create(
                journal_entry=entry,
                account=bank_account,
                debit=Decimal("0.00"),
                credit=gross_amount,
                description="Bank withdrawal",
            )
        entry.check_balance()

        BankReconciliationMatch.objects.create(
            bank_transaction=bank_tx,
            journal_entry=entry,
            match_type="ONE_TO_ONE",
            match_confidence=Decimal("1.00"),
            matched_amount=gross_amount,
            reconciled_by=request.user,
        )

        bank_tx.posted_journal_entry = entry
        bank_tx.category = None
        bank_tx.customer = customer
        bank_tx.supplier = supplier
        bank_tx.is_reconciled = True
        bank_tx.reconciled_at = timezone.now()
        bank_tx.status = BankTransaction.TransactionStatus.MATCHED_SINGLE
        bank_tx.allocated_amount = bank_tx.amount
        bank_tx.save(
            update_fields=[
                "posted_journal_entry",
                "category",
                "customer",
                "supplier",
                "is_reconciled",
                "reconciled_at",
                "status",
                "allocated_amount",
            ]
        )
    return JsonResponse(
        {
            "success": True,
            "journal_entry_id": entry.id,
            "breakdown": {
                "net": str(net_amount),
                "tax": str(tax_amount),
                "gross": str(gross_amount),
            },
        }
    )


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
                expense.journalentry_set.order_by("-date", "-id").first()  # type: ignore[attr-defined]
            )

        expense.status = Expense.Status.PAID
        expense.paid_date = bank_tx.date
        expense.save()

        bank_tx.matched_expense = expense
        bank_tx.posted_journal_entry = journal_entry
        bank_tx.save(update_fields=["matched_expense", "posted_journal_entry"])
        if journal_entry:
            add_bank_match(bank_tx, journal_entry)
        else:
            recompute_bank_transaction_status(bank_tx)

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


@login_required(login_url="/internal-admin/login/")
def admin_spa(request):
    """Internal admin dashboard - React SPA."""
    profile = getattr(request.user, "internal_admin_profile", None)
    if not (request.user.is_staff or profile):
        return HttpResponseForbidden("You are not authorized to access internal admin.")
    return render(request, "admin_spa.html")


@login_required
def bank_setup_page(request):
    return render(request, "bank_setup.html")


@login_required
def workspace_home(request):
    return render(request, "workspace_home.html")


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
        account_any = cast(Any, account)
        payload.append(
            {
                "id": account_any.id,
                "code": account_any.code or "",
                "name": account_any.name,
                "type": account_any.type,
                "detailType": account_any.description or "",
                "isActive": account_any.is_active,
                "balance": float(balance_map.get(account_any.id) or 0),
                "favorite": account_any.is_favorite,
                "detailUrl": reverse("coa_account_detail", args=[account_any.id]),
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


@login_required
def reconciliation_entry(request):
    """
    Entry point for reconciliation - redirects to first available bank account.
    """
    business = get_current_business(request.user)
    if business is None:
        messages.warning(request, "Please create a business to start reconciling.")
        return redirect("business_setup")

    first_account = BankAccount.objects.filter(business=business).first()
    if first_account:
        return redirect("reconciliation_page", bank_account_id=first_account.id)
    # Render shell with no selection when no accounts exist.
    return render(request, "reconciliation/reconciliation_page.html", {"current": "reconciliation", "bank_account_id": ""})


@login_required
def reconciliation_page(request, bank_account_id):
    """
    Reconciliation workspace for a specific bank account.
    """
    business = get_current_business(request.user)
    if business is None:
        messages.warning(request, "Please create a business to start reconciling.")
        return redirect("business_setup")

    bank_account = get_object_or_404(BankAccount, id=bank_account_id, business=business)

    return render(
        request,
        "reconciliation/reconciliation_page.html",
        {
            "current": "reconciliation",
            "bank_account": bank_account,
            "bank_account_id": bank_account.id,
        },
    )


@require_POST
@login_required
def api_create_category(request):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "Business not found"}, status=404)

    data = _json_from_body(request)
    form = CategoryForm(data, business=business)
    if form.is_valid():
        category = form.save(commit=False)
        category.business = business
        category.save()
        return JsonResponse({
            "id": category.id,
            "name": category.name,
            "type": category.type,
            "account_id": category.account_id,
        })
    
    return JsonResponse({"errors": form.errors}, status=400)


@login_required
@require_POST
def api_bank_setup_save(request):
    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"detail": "No business found."}, status=400)

    payload = _json_from_body(request)
    accounts_data = payload.get("accounts", [])

    with db_transaction.atomic():
        for acc in accounts_data:
            name = (acc.get("accountName") or "Bank Account").strip()
            label = (acc.get("bankLabel") or "").strip()
            currency = (acc.get("currency") or "CAD").strip()
            opening_balance_str = acc.get("openingBalance") or "0"
            
            try:
                opening_balance = Decimal(opening_balance_str)
            except (InvalidOperation, ValueError):
                opening_balance = Decimal("0.00")

            # Create Ledger Account
            ledger_account = Account.objects.create(
                business=business,
                name=name,
                code=f"10{Account.objects.filter(business=business, code__startswith='10').count() + 1:02d}", # Simple auto-code
                type=Account.AccountType.ASSET,
                description=f"Bank account - {label}" if label else "Bank account",
                currency=currency
            )

            # Create Bank Account linked to it
            bank_account = BankAccount.objects.create(
                business=business,
                account=ledger_account,
                name=label or name,
                currency=currency,
                bank_name=label or "Manual Bank",
                account_number=acc.get("id")[-4:] # Dummy last 4
            )

            # Post Opening Balance if non-zero
            if opening_balance != 0:
                je = JournalEntry.objects.create(
                    business=business,
                    date=timezone.now().date(),
                    description="Opening Balance Migration",
                )
                # Debit Bank, Credit Opening Balance Equity (or Retained Earnings)
                defaults = ensure_default_accounts(business)
                equity_account = defaults.get("equity") # We might need a specific opening balance equity account
                
                if not equity_account:
                    # Fallback to creating one
                    equity_account = Account.objects.create(
                        business=business,
                        name="Opening Balance Equity",
                        code="3999",
                        type=Account.AccountType.EQUITY
                    )

                JournalLine.objects.create(
                    journal_entry=je,
                    account=ledger_account,
                    debit=opening_balance if opening_balance > 0 else Decimal("0"),
                    credit=abs(opening_balance) if opening_balance < 0 else Decimal("0"),
                    description="Opening Balance"
                )
                JournalLine.objects.create(
                    journal_entry=je,
                    account=equity_account,
                    debit=abs(opening_balance) if opening_balance < 0 else Decimal("0"),
                    credit=opening_balance if opening_balance > 0 else Decimal("0"),
                    description="Opening Balance Offset"
                )
                je.check_balance()

        business.bank_setup_completed = True
        business.save(update_fields=["bank_setup_completed"])

    return JsonResponse({"success": True})


@login_required
@require_POST
def api_bank_setup_skip(request):
    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"detail": "No business found."}, status=400)
    
    business.bank_setup_completed = True
    business.save(update_fields=["bank_setup_completed"])
    
    return JsonResponse({"success": True})
