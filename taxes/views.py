from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render

from core.utils import get_current_business
from .reporting import gst_hst_summary, get_us_sales_tax_summary


def _parse_date(value: str, default: date) -> date:
    try:
        return date.fromisoformat(value)
    except Exception:
        return default


@login_required
def gst_hst_report(request: HttpRequest) -> HttpResponse:
    business = get_current_business(request.user)
    if business is None:
        return render(request, "reports/gst_hst.html", {"error": "No business selected."})

    today = date.today()
    start_param = request.GET.get("start_date")
    end_param = request.GET.get("end_date")
    jurisdiction = (request.GET.get("jurisdiction") or "ALL").upper()

    start_date = _parse_date(start_param, today.replace(day=1)) if start_param else today.replace(day=1)
    end_date = _parse_date(end_param, today)

    summary = gst_hst_summary(
        business=business,
        start_date=start_date,
        end_date=end_date,
        jurisdiction=None if jurisdiction == "ALL" else jurisdiction,
    )

@login_required
def us_sales_tax_report(request: HttpRequest) -> HttpResponse:
    business = get_current_business(request.user)
    if business is None:
        return render(request, "reports/us_sales_tax.html", {"error": "No business selected."})

    today = date.today()
    start_param = request.GET.get("start_date")
    end_param = request.GET.get("end_date")

    start_date = _parse_date(start_param, today.replace(day=1)) if start_param else today.replace(day=1)
    end_date = _parse_date(end_param, today)

    summary = get_us_sales_tax_summary(
        business=business,
        start_date=start_date,
        end_date=end_date,
    )

    payload = {
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "jurisdictions": summary["jurisdictions"],
        "totals": summary["totals"],
        "disclaimer": summary["disclaimer"],
    }

    if request.headers.get("Accept") == "application/json" or request.GET.get("format") == "json":
        return JsonResponse(payload)

    return render(
        request,
        "reports/us_sales_tax.html",
        {
            "business": business,
            "period": payload["period"],
            "jurisdictions": summary["jurisdictions"],
            "totals": summary["totals"],
            "disclaimer": summary["disclaimer"],
        },
    )
    response_payload = {
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "jurisdiction": summary["jurisdiction"],
        "summary": {
            "line_101_taxable_sales": str(summary["line_101_taxable_sales"]),
            "line_105_tax_collected": str(summary["line_105_tax_collected"]),
            "line_108_itcs": str(summary["line_108_itcs"]),
            "line_109_net_tax": str(summary["line_109_net_tax"]),
        },
        "details": summary["details"],
    }

    if request.headers.get("Accept") == "application/json" or request.GET.get("format") == "json":
        return JsonResponse(response_payload)

    return render(
        request,
        "reports/gst_hst.html",
        {
            "business": business,
            "period": response_payload["period"],
            "jurisdiction": response_payload["jurisdiction"],
            "summary": summary,
            "details": summary["details"],
        },
    )
