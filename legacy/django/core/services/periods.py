from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Optional, Union

from django.utils import timezone
from django.utils.dateparse import parse_date

PeriodLike = Union[str, date, None]

PRESET_LABELS: dict[str, str] = {
    "this_month": "This Month",
    "last_month": "Last Month",
    "last_3_months": "Last 3 Months",
    "last_6_months": "Last 6 Months",
    "last_year": "Last Year",
    "last_30_days": "Last 30 Days",
    "last_90_days": "Last 90 Days",
    "this_quarter": "This Quarter",
    "last_quarter": "Last Quarter",
    "this_year": "Year to Date",
    "custom": "Custom",
}


def _coerce_date(value: PeriodLike) -> Optional[date]:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        return parse_date(value.strip())
    return None


def _format_range_label(start: date, end: date) -> str:
    return f"{start:%b %d, %Y} – {end:%b %d, %Y}"


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _month_end(d: date) -> date:
    last_day = calendar.monthrange(d.year, d.month)[1]
    return d.replace(day=last_day)


def _add_months(d: date, months: int) -> date:
    month_index = (d.month - 1) + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _month_span(start: date, end: date) -> Optional[int]:
    """
    If the range cleanly covers whole calendar months, return the number of months spanned.
    Otherwise return None.
    """
    if start.day != 1:
        return None
    if end != _month_end(end):
        return None
    months = (end.year - start.year) * 12 + end.month - start.month + 1
    if months <= 0:
        return None
    expected_end = _month_end(_add_months(start, months - 1))
    return months if expected_end == end else None


def _parse_fiscal_start(fiscal_year_start: Union[str, int, None]) -> tuple[int, int]:
    if isinstance(fiscal_year_start, int):
        return fiscal_year_start, 1
    if isinstance(fiscal_year_start, str) and "-" in fiscal_year_start:
        try:
            month_str, day_str = fiscal_year_start.split("-", 1)
            month = int(month_str)
            day = int(day_str)
            return month, day
        except Exception:
            pass
    return 1, 1


def resolve_period(
    preset: str | None,
    start_date: PeriodLike = None,
    end_date: PeriodLike = None,
    fiscal_year_start: Union[str, int, None] = None,
    *,
    today: date | None = None,
) -> dict:
    """
    Resolve a reporting period into concrete dates and a user-facing label.
    Supports presets and custom ranges.
    """
    ref_today = today or timezone.localdate()
    normalized = (preset or "").strip() or "this_month"
    parsed_start = _coerce_date(start_date)
    parsed_end = _coerce_date(end_date)

    # Treat YYYY-MM as a month selector for backwards compatibility.
    if "-" in normalized and len(normalized) == 7:
        try:
            year, month = map(int, normalized.split("-"))
            parsed_start = date(year, month, 1)
            parsed_end = _month_end(parsed_start)
            normalized = "custom"
        except Exception:
            normalized = "this_month"

    # Handle month_YYYY_MM format from dashboard P&L picker
    if normalized.startswith("month_"):
        try:
            parts = normalized.split("_")  # ["month", "2025", "12"]
            year = int(parts[1])
            month_num = int(parts[2])
            parsed_start = date(year, month_num, 1)
            parsed_end = _month_end(parsed_start)
            normalized = "custom"
        except Exception:
            normalized = "this_month"

    month, day = _parse_fiscal_start(fiscal_year_start)
    label_prefix = PRESET_LABELS.get(normalized, PRESET_LABELS["custom"])

    if normalized == "custom" or parsed_start or parsed_end:
        start = parsed_start or parsed_end or ref_today
        end = parsed_end or parsed_start or ref_today
        if start > end:
            start, end = end, start
        label = _format_range_label(start, end)
        normalized = "custom"
    elif normalized == "last_month":
        current_month_start = _month_start(ref_today)
        end = current_month_start - timedelta(days=1)
        start = _month_start(end)
        label = f"{label_prefix} · {_format_range_label(start, end)}"
    elif normalized == "last_3_months":
        current_month_start = _month_start(ref_today)
        end = current_month_start - timedelta(days=1)
        start = _add_months(current_month_start, -3)
        label = f"{label_prefix} · {_format_range_label(start, end)}"
    elif normalized == "last_6_months":
        current_month_start = _month_start(ref_today)
        end = current_month_start - timedelta(days=1)
        start = _add_months(current_month_start, -6)
        label = f"{label_prefix} · {_format_range_label(start, end)}"
    elif normalized == "last_year":
        current_fy_start = date(ref_today.year, month, day)
        if ref_today < current_fy_start:
            current_fy_start = date(ref_today.year - 1, month, day)
        start = date(current_fy_start.year - 1, month, day)
        end = current_fy_start - timedelta(days=1)
        label = f"{label_prefix} · {_format_range_label(start, end)}"
    elif normalized == "last_30_days":
        end = ref_today
        start = ref_today - timedelta(days=29)
        label = f"{label_prefix} · {_format_range_label(start, end)}"
    elif normalized == "last_90_days":
        end = ref_today
        start = ref_today - timedelta(days=89)
        label = f"{label_prefix} · {_format_range_label(start, end)}"
    elif normalized == "this_quarter":
        # Current quarter based on fiscal year start
        fy_start_month = month
        current_quarter = ((ref_today.month - fy_start_month) % 12) // 3
        quarter_start_month = fy_start_month + current_quarter * 3
        if quarter_start_month > 12:
            quarter_start_month -= 12
            start = date(ref_today.year, quarter_start_month, day)
        else:
            start = date(ref_today.year if quarter_start_month <= ref_today.month else ref_today.year - 1, quarter_start_month, day)
        end = min(_month_end(_add_months(start, 2)), ref_today)
        label = f"{label_prefix} · {_format_range_label(start, end)}"
    elif normalized == "last_quarter":
        # Previous quarter based on fiscal year start
        fy_start_month = month
        current_quarter = ((ref_today.month - fy_start_month) % 12) // 3
        prev_quarter = current_quarter - 1 if current_quarter > 0 else 3
        quarter_start_month = fy_start_month + prev_quarter * 3
        year_offset = 0 if current_quarter > 0 else -1
        if quarter_start_month > 12:
            quarter_start_month -= 12
            year_offset += 1
        start = date(ref_today.year + year_offset, quarter_start_month, day)
        end = _month_end(_add_months(start, 2))
        label = f"{label_prefix} · {_format_range_label(start, end)}"
    elif normalized == "this_year":
        # Year to date from fiscal year start
        current_fy_start = date(ref_today.year, month, day)
        if ref_today < current_fy_start:
            current_fy_start = date(ref_today.year - 1, month, day)
        start = current_fy_start
        end = ref_today
        label = f"{label_prefix} · {_format_range_label(start, end)}"
    else:  # this_month (default)
        start = _month_start(ref_today)
        end = min(_month_end(ref_today), ref_today)
        label = f"{PRESET_LABELS['this_month']} · {_format_range_label(start, end)}"
        normalized = "this_month"

    return {
        "start": start,
        "end": end,
        "preset": normalized,
        "label": label,
        "month_span": _month_span(start, end),
    }


def resolve_comparison(
    period_start: date,
    period_end: date,
    compare_to: str | None,
) -> dict:
    """
    Compute comparison period based on selected strategy.
    """
    normalized = (compare_to or "none").lower()
    alias_map = {
        "same_period_last_year": "previous_year",
    }
    normalized = alias_map.get(normalized, normalized)
    base = {"compare_start": None, "compare_end": None, "compare_label": None, "compare_to": normalized}
    if normalized == "none" or period_start is None or period_end is None:
        return base

    span_months = _month_span(period_start, period_end)
    if normalized == "previous_period":
        if span_months:
            compare_end = period_start - timedelta(days=1)
            compare_start = _add_months(period_start, -span_months)
        elif period_start.day == 1:
            # If we are partway through the month, still compare against the full prior month
            prev_month_end = _month_end(period_start - timedelta(days=1))
            compare_start = _month_start(prev_month_end)
            compare_end = prev_month_end
        else:
            days = (period_end - period_start).days + 1
            compare_end = period_start - timedelta(days=1)
            compare_start = compare_end - timedelta(days=days - 1)
        return {
            "compare_start": compare_start,
            "compare_end": compare_end,
            "compare_label": "Previous period",
            "compare_to": "previous_period",
        }

    if normalized == "previous_year":
        try:
            compare_start = period_start.replace(year=period_start.year - 1)
            compare_end = period_end.replace(year=period_end.year - 1)
        except ValueError:
            # Handle Feb 29 -> Feb 28, etc.
            compare_start = period_start - timedelta(days=365)
            compare_end = period_end - timedelta(days=365)
        return {
            "compare_start": compare_start,
            "compare_end": compare_end,
            "compare_label": "Previous year",
            "compare_to": "previous_year",
        }

    return base
