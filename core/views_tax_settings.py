import json
import re

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest

from .models import Business
from .utils import get_current_business


def _serialize_settings(business: Business) -> dict:
    tax_country = (business.tax_country or "").strip().upper()
    return {
        "tax_country": business.tax_country or "",
        "tax_region": business.tax_region or "",
        "tax_regime_ca": business.tax_regime_ca if tax_country == "CA" else None,
        "tax_filing_frequency": business.tax_filing_frequency,
        "tax_filing_due_day": business.tax_filing_due_day,
        "gst_hst_number": business.gst_hst_number or "",
        "qst_number": business.qst_number or "",
        "us_sales_tax_id": business.us_sales_tax_id or "",
        "default_nexus_jurisdictions": business.default_nexus_jurisdictions or [],
        "is_country_locked": bool(business.tax_country),
    }


def _clean_registration(value: str, max_length: int) -> str:
    return (value or "").strip()[:max_length]


def _parse_nexus(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


@login_required
def api_tax_settings(request):
    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    if request.method == "GET":
        return JsonResponse(_serialize_settings(business))

    if request.method != "PATCH":
        return HttpResponseBadRequest("PATCH required")

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}

    updates = {}
    errors = {}

    # Country immutability
    new_country = payload.get("tax_country")
    if new_country is not None:
        new_country = (new_country or "").strip().upper()
        if business.tax_country and new_country and new_country != business.tax_country:
            errors["tax_country"] = "Tax country is locked and cannot be changed."
        else:
            updates["tax_country"] = new_country or business.tax_country

    new_region = payload.get("tax_region")
    if new_region is not None:
        updates["tax_region"] = (new_region or "").strip().upper()

    if "tax_regime_ca" in payload:
        raw = payload.get("tax_regime_ca")
        if raw in (None, "", "null"):
            updates["tax_regime_ca"] = None
        else:
            regime = str(raw).strip().upper()
            if regime not in Business.TaxRegimeCA.values:
                errors["tax_regime_ca"] = "Invalid tax_regime_ca."
            else:
                effective_country = (updates.get("tax_country") or business.tax_country or "").strip().upper()
                if effective_country != "CA":
                    # Only meaningful for Canadian businesses; ignore/clear otherwise.
                    updates["tax_regime_ca"] = None
                else:
                    updates["tax_regime_ca"] = regime

    if "tax_country" in updates and (updates["tax_country"] or "").strip().upper() != "CA":
        updates["tax_regime_ca"] = None

    if "tax_filing_frequency" in payload:
        freq = (payload.get("tax_filing_frequency") or "").upper()
        if freq not in Business.TaxFilingFrequency.values:
            errors["tax_filing_frequency"] = "Invalid filing frequency."
        else:
            updates["tax_filing_frequency"] = freq

    if "tax_filing_due_day" in payload:
        try:
            due_day = int(payload.get("tax_filing_due_day"))
            if not 1 <= due_day <= 31:
                raise ValueError()
            updates["tax_filing_due_day"] = due_day
        except Exception:
            errors["tax_filing_due_day"] = "Due day must be between 1 and 31."

    if "gst_hst_number" in payload:
        value = _clean_registration(payload.get("gst_hst_number"), 20)
        if value and not re.match(r"^[A-Za-z0-9-]+$", value):
            errors["gst_hst_number"] = "Invalid GST/HST number format."
        else:
            updates["gst_hst_number"] = value

    if "qst_number" in payload:
        value = _clean_registration(payload.get("qst_number"), 20)
        if value and not re.match(r"^[A-Za-z0-9-]+$", value):
            errors["qst_number"] = "Invalid QST number format."
        else:
            updates["qst_number"] = value

    if "us_sales_tax_id" in payload:
        updates["us_sales_tax_id"] = _clean_registration(payload.get("us_sales_tax_id"), 40)

    if "default_nexus_jurisdictions" in payload:
        updates["default_nexus_jurisdictions"] = _parse_nexus(payload.get("default_nexus_jurisdictions"))

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    for field, value in updates.items():
        setattr(business, field, value)
    update_fields = list(updates.keys()) if updates else None
    business.save(update_fields=update_fields)

    return JsonResponse(_serialize_settings(business))
