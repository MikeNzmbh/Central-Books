from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone

from .ledger_reports import ledger_pnl_for_period
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
