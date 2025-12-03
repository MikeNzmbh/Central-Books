from collections import OrderedDict
from datetime import date, timedelta
import json
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.urls import reverse

from .ledger_reports import ledger_pnl_for_period
from .ledger_services import compute_ledger_pl
from .services.ledger_metrics import get_pl_period_dates, PLPeriod
from .models import BankTransaction, ReconciliationSession
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


def build_cashflow_payload(business) -> dict:
    today = timezone.localdate()
    qs = (
        BankTransaction.objects.filter(bank_account__business=business)
        .select_related("category")
        .order_by("date")
    )

    start_date = _add_months_local(today.replace(day=1), -5)
    qs = qs.filter(date__gte=start_date)

    periods: OrderedDict[tuple[int, int], dict[str, Decimal]] = OrderedDict()
    cursor = start_date
    for _ in range(6):
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
        if total_outflows > total_inflows
        else Decimal("0.00")
    )
    runway_label = None
    if avg_monthly_burn > 0 and current_cash > 0:
        months = current_cash / avg_monthly_burn
        runway_label = f"{months.quantize(Decimal('0.1'))} months"

    payload = {
        "username": "",
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
    return payload


def _get_period_dates_local(period: str) -> tuple[date, date, str, str]:
    return get_pl_period_dates(period or PLPeriod.THIS_MONTH.value)


def build_pl_payload(business, period: str = "this_month") -> dict:
    start_date, end_date, period_label, _normalized = _get_period_dates_local(period)
    ledger_pl = compute_ledger_pl(business, start_date, end_date)

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
        "periodLabel": period_label,
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

    return render(
        request,
        "reconciliation_report.html",
        {
            "session_id": session.id,
        },
    )


@login_required
def cashflow_report_print_view(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")

    payload = build_cashflow_payload(business)
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

    period_key = request.GET.get("period", "this_month")
    payload = build_pl_payload(business, period_key)
    pl_json = mark_safe(json.dumps(payload))

    return render(
        request,
        "pl_report_print.html",
        {
            "pl_json": pl_json,
        },
    )
