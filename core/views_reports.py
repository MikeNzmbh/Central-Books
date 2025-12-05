from collections import OrderedDict
from datetime import date, timedelta
import json
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.urls import reverse

from .ledger_reports import ledger_pnl_for_period
from .ledger_services import compute_ledger_pl
from .services.ledger_metrics import get_pl_period_dates, PLPeriod, build_pl_diagnostics
from .services.periods import resolve_comparison, resolve_period
from .models import Account, BankTransaction, ReconciliationSession
from .utils import get_current_business


@login_required
def pnl_ledger_debug(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    today = timezone.localdate()
    start = date(today.year, today.month, 1)
    end = today

    pnl = ledger_pnl_for_period(business, start, end)

    return render(
        request,
        "reports/pnl_ledger_debug.html",
        {
            "business": business,
            "start": start,
            "end": end,
            "pnl": pnl,
        },
    )


# --- Shared helpers for report print payloads ---

def _add_months_local(d: date, months: int) -> date:
    month_index = (d.month - 1) + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def build_cashflow_payload(
    business,
    period_info: dict | None = None,
    comparison_info: dict | None = None,
) -> dict:
    today = timezone.localdate()
    period = period_info or resolve_period("last_6_months", today=today)
    comparison = comparison_info or resolve_comparison(period["start"], period["end"], "previous_period")
    start_date = period["start"]
    end_date = period["end"]

    qs = (
        BankTransaction.objects.filter(
            bank_account__business=business,
            date__gte=start_date,
            date__lte=end_date,
        )
        .select_related("category")
        .order_by("date")
    )

    periods: OrderedDict[tuple[int, int], dict[str, Decimal]] = OrderedDict()
    cursor = start_date.replace(day=1)
    final_month_start = end_date.replace(day=1)
    while cursor <= final_month_start:
        key = (cursor.year, cursor.month)
        periods[key] = {"inflows": Decimal("0.00"), "outflows": Decimal("0.00")}
        cursor = _add_months_local(cursor, 1)

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
        if total_outflows > total_inflows and len(periods) > 0
        else Decimal("0.00")
    )
    runway_label = None
    if avg_monthly_burn > 0 and current_cash > 0:
        months = current_cash / avg_monthly_burn
        runway_label = f"{months.quantize(Decimal('0.1'))} months"

    def _iso_or_none(value):
        return value.isoformat() if hasattr(value, "isoformat") else value

    compare_summary = None
    if comparison.get("compare_start") and comparison.get("compare_end"):
        comp_qs = BankTransaction.objects.filter(
            bank_account__business=business,
            date__gte=comparison["compare_start"],
            date__lte=comparison["compare_end"],
        )
        comp_inflows = Decimal("0.00")
        comp_outflows = Decimal("0.00")
        for tx in comp_qs:
            amt = tx.amount or Decimal("0.00")
            if amt >= 0:
                comp_inflows += amt
            else:
                comp_outflows += abs(amt)
        compare_summary = {
            "label": comparison.get("compare_label"),
            "start": _iso_or_none(comparison.get("compare_start")),
            "end": _iso_or_none(comparison.get("compare_end")),
            "totalInflows": float(comp_inflows),
            "totalOutflows": float(comp_outflows),
            "netChange": float(comp_inflows - comp_outflows),
        }

    payload = {
        "username": "",
        "asOfLabel": today.strftime("As of %b %d, %Y"),
        "baseCurrency": business.currency or "USD",
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "preset": period.get("preset"),
            "label": period.get("label"),
        },
        "comparison": compare_summary
        or {
            "label": comparison.get("compare_label"),
            "start": _iso_or_none(comparison.get("compare_start")),
            "end": _iso_or_none(comparison.get("compare_end")),
        },
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
    return payload


def _get_period_dates_local(period: str) -> tuple[date, date, str, str]:
    return get_pl_period_dates(period or PLPeriod.THIS_MONTH.value)


def build_pl_payload(
    business,
    period: str = "this_month",
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    compare_to: str = "previous_period",
    fiscal_year_start=None,
) -> dict:
    period_info = resolve_period(period, start_date, end_date, fiscal_year_start)
    comparison_info = resolve_comparison(period_info["start"], period_info["end"], compare_to)
    ledger_pl = compute_ledger_pl(business, period_info["start"], period_info["end"])

    comparison_pl = {
        "total_income": Decimal("0.00"),
        "total_expense": Decimal("0.00"),
        "net": Decimal("0.00"),
    }
    def _iso_or_none(value):
        return value.isoformat() if hasattr(value, "isoformat") else value

    if comparison_info["compare_start"] and comparison_info["compare_end"]:
        comparison_pl = compute_ledger_pl(
            business, comparison_info["compare_start"], comparison_info["compare_end"]
        )

    income_items = [
        {
            "category": row.get("account__name") or row.get("account__code") or "Revenue",
            "amount": float(row.get("total") or Decimal("0.00")),
        }
        for row in ledger_pl.get("income_accounts", [])
    ]
    expense_items = [
        {
            "category": row.get("account__name") or row.get("account__code") or "Expense",
            "amount": float(row.get("total") or Decimal("0.00")),
        }
        for row in ledger_pl.get("expense_accounts", [])
    ]

    payload = {
        "periodLabel": period_info.get("label"),
        "period": {
            "label": period_info.get("label"),
            "start": period_info["start"].isoformat(),
            "end": period_info["end"].isoformat(),
            "preset": period_info.get("preset"),
        },
        "comparison": {
            "label": comparison_info.get("compare_label"),
            "start": _iso_or_none(comparison_info.get("compare_start")),
            "end": _iso_or_none(comparison_info.get("compare_end")),
            "totalRevenue": float(comparison_pl.get("total_income") or Decimal("0.00")),
            "totalExpenses": float(comparison_pl.get("total_expense") or Decimal("0.00")),
            "netIncome": float(comparison_pl.get("net") or Decimal("0.00")),
            "compare_to": comparison_info.get("compare_to"),
        },
        "currency": business.currency or "USD",
        "totalRevenue": float(ledger_pl.get("total_income") or Decimal("0.00")),
        "totalExpenses": float(ledger_pl.get("total_expense") or Decimal("0.00")),
        "netIncome": float(ledger_pl.get("net") or Decimal("0.00")),
        "revenueItems": income_items,
        "expenseItems": expense_items,
    }
    return payload


# --- Print views ---


@login_required
def reconciliation_report_view(request, session_id: int):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    session = get_object_or_404(
        ReconciliationSession.objects.select_related("bank_account"),
        id=session_id,
        business=business,
    )

    period_key = request.GET.get("period_preset") or request.GET.get("period") or "custom"
    start_param = request.GET.get("start_date") or session.statement_start_date
    end_param = request.GET.get("end_date") or session.statement_end_date
    compare_to = request.GET.get("compare_to") or "none"
    period_info = resolve_period(period_key, start_param, end_param, business.fiscal_year_start)
    comparison_info = resolve_comparison(period_info["start"], period_info["end"], compare_to)

    return render(
        request,
        "reconciliation_report.html",
        {
            "session_id": session.id,
            "period_start": period_info["start"].isoformat(),
            "period_end": period_info["end"].isoformat(),
            "period_preset": period_info.get("preset"),
            "compare_to": comparison_info.get("compare_to", "none"),
        },
    )


@login_required
def cashflow_report_print_view(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    period_key = request.GET.get("period_preset") or request.GET.get("period") or request.GET.get("cf_month") or "last_6_months"
    start_param = request.GET.get("start_date")
    end_param = request.GET.get("end_date")
    compare_to = request.GET.get("compare_to") or "previous_period"
    period_info = resolve_period(period_key, start_param, end_param, business.fiscal_year_start)
    comparison_info = resolve_comparison(period_info["start"], period_info["end"], compare_to)

    payload = build_cashflow_payload(business, period_info, comparison_info)
    payload["username"] = request.user.first_name or request.user.username

    cashflow_json = mark_safe(json.dumps(payload))
    return render(
        request,
        "cashflow_report_print.html",
        {
            "cashflow_json": cashflow_json,
        },
    )


@login_required
def pl_report_print_view(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    period_key = request.GET.get("period_preset") or request.GET.get("period") or "this_month"
    start_param = request.GET.get("start_date")
    end_param = request.GET.get("end_date")
    compare_to = request.GET.get("compare_to") or "previous_period"
    payload = build_pl_payload(
        business,
        period_key,
        start_date=start_param,
        end_date=end_param,
        compare_to=compare_to,
        fiscal_year_start=business.fiscal_year_start,
    )
    pl_json = mark_safe(json.dumps(payload))

    return render(
        request,
        "pl_report_print.html",
        {
            "pl_json": pl_json,
        },
    )


# --- P&L Report API ---

def _is_cogs_account(account) -> bool:
    """
    Determine if an account should be classified as COGS.
    Convention: accounts with code 50xx-59xx or name containing 'cost of goods'.
    """
    if not account:
        return False
    code = getattr(account, "code", "") or ""
    name = (getattr(account, "name", "") or "").lower()
    # Check if code starts with 5 and second digit is 0-9 (5xxx range for COGS)
    if code and len(code) >= 2:
        if code[0] == "5" and code[1] in "0123456789":
            # 50xx through 59xx are considered COGS
            return True
    # Also check name patterns
    cogs_keywords = ["cost of goods", "cogs", "cost of sales", "direct cost"]
    return any(kw in name for kw in cogs_keywords)


def _pct_change(current: Decimal, previous: Decimal) -> float | None:
    """Calculate percentage change, handling divide-by-zero safely."""
    if previous == Decimal("0"):
        return None
    return float(((current - previous) / abs(previous)) * Decimal("100"))


@login_required
def pl_report_api(request):
    """
    API endpoint for React P&L report page.
    Returns COGS, gross profit, margins, and full breakdown.
    """
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business found"}, status=400)

    # Parse query params
    period_preset = request.GET.get("period_preset") or request.GET.get("period") or "this_month"
    start_param = request.GET.get("period_start") or request.GET.get("start_date")
    end_param = request.GET.get("period_end") or request.GET.get("end_date")
    compare_preset = request.GET.get("compare_preset") or request.GET.get("compare_to") or "previous_period"

    # Resolve periods
    period_info = resolve_period(period_preset, start_param, end_param, business.fiscal_year_start)
    comparison_info = resolve_comparison(period_info["start"], period_info["end"], compare_preset)

    # Get ledger P&L data
    ledger_pl = compute_ledger_pl(business, period_info["start"], period_info["end"])

    # Separate COGS from operating expenses
    income_rows = []
    cogs_rows = []
    expense_rows = []

    for row in ledger_pl.get("income", []):
        account = row.get("account")
        income_rows.append({
            "id": row.get("account__id") or (account.id if account else 0),
            "name": row.get("account__name") or (account.name if account else "Revenue"),
            "code": row.get("account__code") or (account.code if account else None),
            "group": "INCOME",
            "amount": float(row.get("amount") or Decimal("0")),
            "compare_amount": None,  # Will be filled if comparison active
        })

    for row in ledger_pl.get("expense", []):
        account = row.get("account")
        is_cogs = _is_cogs_account(account)
        row_data = {
            "id": row.get("account__id") or (account.id if account else 0),
            "name": row.get("account__name") or (account.name if account else "Expense"),
            "code": row.get("account__code") or (account.code if account else None),
            "group": "COGS" if is_cogs else "EXPENSE",
            "amount": float(row.get("amount") or Decimal("0")),
            "compare_amount": None,
        }
        if is_cogs:
            cogs_rows.append(row_data)
        else:
            expense_rows.append(row_data)

    # Calculate totals
    total_income = ledger_pl.get("total_income") or Decimal("0")
    total_cogs = sum(Decimal(str(r["amount"])) for r in cogs_rows)
    total_expenses = sum(Decimal(str(r["amount"])) for r in expense_rows)
    gross_profit = total_income - total_cogs
    net_income = gross_profit - total_expenses

    # Calculate margins
    gross_margin_pct = None
    net_margin_pct = None
    if total_income > Decimal("0"):
        gross_margin_pct = float((gross_profit / total_income) * Decimal("100"))
        net_margin_pct = float((net_income / total_income) * Decimal("100"))

    # Initialize comparison values
    compare_income = Decimal("0")
    compare_cogs = Decimal("0")
    compare_expenses = Decimal("0")
    compare_gross_profit = Decimal("0")
    compare_net_income = Decimal("0")
    compare_label = None

    # Get comparison data if active
    if comparison_info.get("compare_start") and comparison_info.get("compare_end") and compare_preset != "none":
        compare_label = comparison_info.get("compare_label")
        comparison_pl = compute_ledger_pl(
            business, comparison_info["compare_start"], comparison_info["compare_end"]
        )

        # Build lookup map for comparison amounts
        compare_income_map = {
            row.get("account__id"): row.get("amount") or Decimal("0")
            for row in comparison_pl.get("income", [])
        }
        compare_expense_map = {}
        for row in comparison_pl.get("expense", []):
            account = row.get("account")
            compare_expense_map[row.get("account__id")] = {
                "amount": row.get("amount") or Decimal("0"),
                "is_cogs": _is_cogs_account(account),
            }

        # Update income rows with comparison
        for r in income_rows:
            r["compare_amount"] = float(compare_income_map.get(r["id"]) or Decimal("0"))
        compare_income = comparison_pl.get("total_income") or Decimal("0")

        # Update COGS and expense rows
        for r in cogs_rows:
            comp_data = compare_expense_map.get(r["id"], {})
            r["compare_amount"] = float(comp_data.get("amount") or Decimal("0"))
        for r in expense_rows:
            comp_data = compare_expense_map.get(r["id"], {})
            r["compare_amount"] = float(comp_data.get("amount") or Decimal("0"))

        # Calculate comparison totals
        for acc_id, data in compare_expense_map.items():
            if data.get("is_cogs"):
                compare_cogs += data["amount"]
            else:
                compare_expenses += data["amount"]

        compare_gross_profit = compare_income - compare_cogs
        compare_net_income = compare_gross_profit - compare_expenses

    # Calculate percentage changes
    change_income_pct = _pct_change(total_income, compare_income) if compare_label else None
    change_cogs_pct = _pct_change(total_cogs, compare_cogs) if compare_label else None
    change_gross_profit_pct = _pct_change(gross_profit, compare_gross_profit) if compare_label else None
    change_expenses_pct = _pct_change(total_expenses, compare_expenses) if compare_label else None
    change_net_income_pct = _pct_change(net_income, compare_net_income) if compare_label else None

    # Get diagnostics
    diagnostics = build_pl_diagnostics(business, period_info["start"], period_info["end"])

    # Build response
    response = {
        "business_name": business.name,
        "currency": business.currency or "USD",
        "period_preset": period_info.get("preset") or period_preset,
        "period_label": period_info.get("label") or "",
        "period_start": period_info["start"].isoformat(),
        "period_end": period_info["end"].isoformat(),
        "compare_preset": compare_preset,
        "compare_label": compare_label,
        "kpi": {
            "income": float(total_income),
            "cogs": float(total_cogs),
            "gross_profit": float(gross_profit),
            "expenses": float(total_expenses),
            "net_income": float(net_income),
            "gross_margin_pct": gross_margin_pct,
            "net_margin_pct": net_margin_pct,
            "change_income_pct": change_income_pct,
            "change_cogs_pct": change_cogs_pct,
            "change_gross_profit_pct": change_gross_profit_pct,
            "change_expenses_pct": change_expenses_pct,
            "change_net_income_pct": change_net_income_pct,
        },
        "rows": income_rows + cogs_rows + expense_rows,
        "diagnostics": {
            "has_activity": diagnostics.get("has_activity", False),
            "reasons": diagnostics.get("reasons", []) if diagnostics.get("reason_message") else [],
        },
    }

    return JsonResponse(response)
