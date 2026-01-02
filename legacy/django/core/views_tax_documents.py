from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse, HttpResponseBadRequest

from core.utils import get_current_business
from taxes.models import TransactionLineTaxDetail, TaxAnomaly


def _period_key_from_date(d) -> str:
    if not d:
        return ""
    return f"{d:%Y-%m}"


def _severity_for_link(anomalies) -> str | None:
    severities = {a.severity for a in anomalies}
    if "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"
    if "low" in severities:
        return "low"
    return None


def _format_money(value: Decimal | None) -> str:
    if value is None:
        return "0.00"
    return f"{Decimal(value):.2f}"


def _detail_rate(detail: TransactionLineTaxDetail) -> str | None:
    base = detail.taxable_amount_txn_currency or Decimal("0.00")
    if base == 0:
        return None
    tax = detail.tax_amount_txn_currency or Decimal("0.00")
    return f"{(tax / base).quantize(Decimal('0.000001'))}"


def _build_document_payload(*, business, obj, obj_type: str) -> dict:
    """
    obj_type: "invoice" | "expense"
    """
    if obj_type == "invoice":
        doc_id = obj.id
        number = obj.invoice_number
        date_value = obj.issue_date
        currency = getattr(business, "currency", "CAD") or "CAD"
        description = (obj.description or "").strip() or f"Invoice {number}"
        net_total = obj.net_total
        tax_total = obj.tax_total
        gross_total = obj.grand_total
    else:
        doc_id = obj.id
        number = None
        date_value = obj.date
        currency = getattr(business, "currency", "CAD") or "CAD"
        description = (obj.description or "").strip() or f"Expense {doc_id}"
        net_total = obj.net_total
        tax_total = obj.tax_total
        gross_total = obj.grand_total

    period_key = _period_key_from_date(date_value)

    ct = ContentType.objects.get_for_model(obj.__class__)
    details_qs = (
        TransactionLineTaxDetail.objects.filter(
            business=business,
            transaction_line_content_type=ct,
            transaction_line_object_id=obj.id,
        )
        .select_related("tax_component", "tax_group")
        .order_by("created_at")
    )
    details = list(details_qs)

    anomalies = list(
        TaxAnomaly.objects.filter(
            business=business,
            linked_transaction_ct=ct,
            linked_transaction_id=obj.id,
        ).order_by("-created_at")
    )

    severity = _severity_for_link(anomalies)
    if period_key:
        tax_guardian_link = f"/ai-companion/tax?period={period_key}"
        if severity:
            tax_guardian_link += f"&severity={severity}"
    else:
        tax_guardian_link = "/ai-companion/tax"

    line_level_available = bool(details)
    breakdown_note = None
    if not line_level_available:
        breakdown_note = "Line-level tax breakdown unavailable for this document (no TransactionLineTaxDetail rows)."

    # Build a single synthetic line for v1 documents (Invoice/Expense are single-line).
    line_tax_details = []
    for d in details:
        line_tax_details.append(
            {
                "tax_component_name": getattr(d.tax_component, "name", ""),
                "jurisdiction_code": d.jurisdiction_code or "",
                "rate": _detail_rate(d),
                "tax_amount": _format_money(d.tax_amount_txn_currency),
                "is_recoverable": bool(d.is_recoverable),
            }
        )

    lines = [
        {
            "line_id": f"{obj_type}:{doc_id}",
            "description": description,
            "net_amount": _format_money(net_total),
            "tax_details": line_tax_details,
            "tax_group": getattr(getattr(obj, "tax_group", None), "display_name", None),
        }
    ]

    by_jurisdiction: dict[str, dict] = {}
    by_tax_group: dict[str, dict] = {}
    for d in details:
        j = d.jurisdiction_code or ""
        if j not in by_jurisdiction:
            by_jurisdiction[j] = {"jurisdiction_code": j, "taxable_base": Decimal("0.00"), "tax_total": Decimal("0.00")}
        # Avoid double-counting bases when multiple components exist for a jurisdiction.
        by_jurisdiction[j]["taxable_base"] = max(by_jurisdiction[j]["taxable_base"], d.taxable_amount_txn_currency or Decimal("0.00"))
        by_jurisdiction[j]["tax_total"] += d.tax_amount_txn_currency or Decimal("0.00")

        tg = getattr(getattr(d, "tax_group", None), "display_name", "") or ""
        if tg not in by_tax_group:
            by_tax_group[tg] = {"tax_group": tg, "tax_total": Decimal("0.00")}
        by_tax_group[tg]["tax_total"] += d.tax_amount_txn_currency or Decimal("0.00")

    breakdown = {
        "by_jurisdiction": [
            {"jurisdiction_code": j["jurisdiction_code"], "taxable_base": _format_money(j["taxable_base"]), "tax_total": _format_money(j["tax_total"])}
            for j in by_jurisdiction.values()
        ],
        "by_tax_group": [{"tax_group": tg["tax_group"], "tax_total": _format_money(tg["tax_total"])} for tg in by_tax_group.values()],
    }

    return {
        "document_type": obj_type,
        "id": doc_id,
        "number": number,
        "date": date_value.isoformat() if date_value else None,
        "currency": currency,
        "period_key": period_key,
        "totals": {
            "net_total": _format_money(net_total),
            "tax_total": _format_money(tax_total),
            "gross_total": _format_money(gross_total),
        },
        "breakdown": breakdown,
        "lines": lines,
        "anomalies": [
            {
                "id": str(a.id),
                "code": a.code,
                "severity": a.severity,
                "status": a.status,
                "description": a.description,
            }
            for a in anomalies
        ],
        "tax_guardian_link": tax_guardian_link,
        "line_level_available": line_level_available,
        "breakdown_note": breakdown_note,
    }


@login_required
def api_tax_document_invoice(request, invoice_id: int):
    if request.method != "GET":
        return HttpResponseBadRequest("GET required")

    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    from core.models import Invoice

    invoice = Invoice.objects.filter(business=business, id=invoice_id).select_related("tax_group").first()
    if not invoice:
        return JsonResponse({"error": "Not found"}, status=404)

    return JsonResponse(_build_document_payload(business=business, obj=invoice, obj_type="invoice"))


@login_required
def api_tax_document_expense(request, expense_id: int):
    if request.method != "GET":
        return HttpResponseBadRequest("GET required")

    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    from core.models import Expense

    expense = Expense.objects.filter(business=business, id=expense_id).select_related("tax_group").first()
    if not expense:
        return JsonResponse({"error": "Not found"}, status=404)

    return JsonResponse(_build_document_payload(business=business, obj=expense, obj_type="expense"))

