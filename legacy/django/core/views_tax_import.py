import csv
import io
import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.utils.dateparse import parse_date

from core.utils import get_current_business
from core.models import Business
from taxes.models import TaxComponent, TaxJurisdiction, TaxProductRule, TaxRate

logger = logging.getLogger(__name__)


def _require_staff(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({"error": "Forbidden"}, status=403)
    return None


def _get_staff_target_business(request):
    business = get_current_business(request.user)
    if business:
        return business
    raw = request.POST.get("business_id") or request.GET.get("business_id")
    if raw in (None, ""):
        return None
    try:
        business_id = int(raw)
    except Exception:
        return None
    return Business.objects.filter(id=business_id).first()


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    s = str(value or "").strip().lower()
    return s in ("1", "true", "t", "yes", "y", "on")


def _parse_payload_rows(uploaded_file) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]], Optional[str]]:
    """
    Return (format, rows, error). format is "csv" or "json".
    """
    if not uploaded_file:
        return None, None, "Missing file."

    name = (getattr(uploaded_file, "name", "") or "").lower()
    content_type = (getattr(uploaded_file, "content_type", "") or "").lower()
    raw = uploaded_file.read()

    is_json = name.endswith(".json") or "json" in content_type
    is_csv = name.endswith(".csv") or "csv" in content_type

    if not is_json and not is_csv:
        # Best effort: try JSON first.
        is_json = True

    try:
        if is_json:
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, dict) and isinstance(data.get("rows"), list):
                data = data["rows"]
            if not isinstance(data, list):
                return "json", None, "JSON must be an array of objects (or {rows:[...]})."
            rows = []
            for item in data:
                if not isinstance(item, dict):
                    return "json", None, "JSON array must contain objects."
                rows.append(item)
            return "json", rows, None

        text = raw.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            return "csv", None, "CSV missing header row."
        return "csv", list(reader), None
    except Exception as exc:
        logger.exception("Failed to parse import file: %s", exc)
        return None, None, "Failed to parse file. Please check the format and try again."


def _ranges_overlap(a_from, a_to, b_from, b_to) -> bool:
    if a_to is not None and a_to < b_from:
        return False
    if b_to is not None and b_to < a_from:
        return False
    return True


def _check_rate_overlap(*, component: TaxComponent, product_category: str, effective_from, effective_to, exclude_id=None) -> bool:
    qs = TaxRate.objects.filter(component=component, product_category=product_category)
    if exclude_id is not None:
        qs = qs.exclude(id=exclude_id)
    qs = qs.filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from))
    if effective_to is not None:
        qs = qs.filter(effective_from__lte=effective_to)
    return qs.exists()


def _check_product_rule_overlap(
    *, jurisdiction: TaxJurisdiction, product_code: str, valid_from, valid_to, exclude_id=None
) -> bool:
    qs = TaxProductRule.objects.filter(jurisdiction=jurisdiction, product_code=product_code)
    if exclude_id is not None:
        qs = qs.exclude(id=exclude_id)
    for existing in qs.only("valid_from", "valid_to"):
        if _ranges_overlap(valid_from, valid_to, existing.valid_from, existing.valid_to):
            return True
    return False


@dataclass
class PreviewRow:
    index: int
    raw: Dict[str, Any]
    status: str
    messages: List[str]
    would_create: bool
    would_update: bool
    target_id: Optional[str]

    def as_dict(self):
        return {
            "index": self.index,
            "raw": self.raw,
            "status": self.status,
            "messages": self.messages,
            "would_create": self.would_create,
            "would_update": self.would_update,
            "target_id": self.target_id,
        }


def _summary(preview_rows: List[PreviewRow]) -> dict:
    counts = {"ok": 0, "warning": 0, "error": 0}
    for r in preview_rows:
        counts[r.status] = counts.get(r.status, 0) + 1
    return {
        "total_rows": len(preview_rows),
        "ok": counts.get("ok", 0),
        "warnings": counts.get("warning", 0),
        "errors": counts.get("error", 0),
    }


def _preview_jurisdictions(rows: List[Dict[str, Any]]) -> List[PreviewRow]:
    results: List[PreviewRow] = []
    for idx, raw in enumerate(rows):
        messages: List[str] = []
        status = "ok"

        code = str(raw.get("code") or "").strip().upper()
        name = str(raw.get("name") or "").strip()
        jurisdiction_type = str(raw.get("jurisdiction_type") or "").strip().upper()
        country_code = str(raw.get("country_code") or "").strip().upper()
        region_code = str(raw.get("region_code") or "").strip().upper()
        sourcing_rule = str(raw.get("sourcing_rule") or "").strip().upper()
        parent_code = str(raw.get("parent_code") or "").strip().upper()
        is_active = raw.get("is_active")
        if is_active in (None, ""):
            is_active = True
        else:
            is_active = _boolish(is_active)

        if not code:
            status = "error"
            messages.append("code is required.")
        if not name:
            status = "error"
            messages.append("name is required.")
        if not jurisdiction_type:
            status = "error"
            messages.append("jurisdiction_type is required.")
        if not country_code:
            status = "error"
            messages.append("country_code is required.")

        existing = TaxJurisdiction.objects.select_related("parent").filter(code=code).first() if code else None
        would_create = existing is None
        would_update = existing is not None
        target_id = str(existing.id) if existing else None

        if parent_code and not TaxJurisdiction.objects.filter(code=parent_code).exists():
            status = "error"
            messages.append(f"parent_code '{parent_code}' not found.")

        if existing:
            is_custom = bool((existing.metadata or {}).get("is_custom"))
            # Existing jurisdictions: importer will only update name/is_active and sourcing_rule for custom.
            if name and name != existing.name:
                messages.append("Would update name.")
            if is_active != existing.is_active:
                messages.append("Would update is_active.")
            if sourcing_rule and sourcing_rule != existing.sourcing_rule:
                if is_custom:
                    if sourcing_rule not in TaxJurisdiction.SourcingRule.values:
                        status = "error"
                        messages.append("Invalid sourcing_rule.")
                    else:
                        messages.append("Would update sourcing_rule (custom jurisdiction).")
                else:
                    status = "warning" if status != "error" else status
                    messages.append("sourcing_rule change for seeded jurisdiction will be ignored.")

            # Flag attempts to modify protected attributes for seeded jurisdictions.
            if not is_custom:
                if country_code and country_code != existing.country_code:
                    status = "error"
                    messages.append("Cannot change country_code for seeded jurisdiction.")
                if jurisdiction_type and jurisdiction_type != existing.jurisdiction_type:
                    status = "error"
                    messages.append("Cannot change jurisdiction_type for seeded jurisdiction.")
                if region_code and region_code != (existing.region_code or ""):
                    status = "error"
                    messages.append("Cannot change region_code for seeded jurisdiction.")
                if parent_code:
                    existing_parent_code = existing.parent.code if existing.parent else ""
                    if parent_code != existing_parent_code:
                        status = "error"
                        messages.append("Cannot change parent_code for seeded jurisdiction.")
            else:
                # Custom jurisdiction: we still don't change parent/country/type via importer (v1 guardrail).
                if country_code and country_code != existing.country_code:
                    status = "warning" if status != "error" else status
                    messages.append("country_code change on existing jurisdiction will be ignored.")
                if jurisdiction_type and jurisdiction_type != existing.jurisdiction_type:
                    status = "warning" if status != "error" else status
                    messages.append("jurisdiction_type change on existing jurisdiction will be ignored.")
                if region_code and region_code != (existing.region_code or ""):
                    status = "warning" if status != "error" else status
                    messages.append("region_code change on existing jurisdiction will be ignored.")
                if parent_code:
                    existing_parent_code = existing.parent.code if existing.parent else ""
                    if parent_code != existing_parent_code:
                        status = "warning" if status != "error" else status
                        messages.append("parent_code change on existing jurisdiction will be ignored.")
        else:
            # Creation validations
            if jurisdiction_type and jurisdiction_type not in TaxJurisdiction.JurisdictionType.values:
                status = "error"
                messages.append("Invalid jurisdiction_type.")
            if sourcing_rule and sourcing_rule not in TaxJurisdiction.SourcingRule.values:
                status = "error"
                messages.append("Invalid sourcing_rule.")

        results.append(
            PreviewRow(
                index=idx,
                raw=raw,
                status=status,
                messages=messages,
                would_create=would_create,
                would_update=would_update,
                target_id=target_id,
            )
        )
    return results


def _preview_rates(*, business, rows: List[Dict[str, Any]]) -> List[PreviewRow]:
    results: List[PreviewRow] = []
    for idx, raw in enumerate(rows):
        messages: List[str] = []
        status = "ok"

        provided_id = str(raw.get("id") or "").strip()
        jurisdiction_code = str(raw.get("jurisdiction_code") or "").strip().upper()
        tax_name = str(raw.get("tax_name") or "").strip()
        product_category = str(raw.get("product_category") or TaxRate.ProductCategory.STANDARD).strip().upper()
        is_compound = raw.get("is_compound", False)
        meta_data_raw = raw.get("meta_data")

        rate_decimal = None
        try:
            rate_decimal = Decimal(str(raw.get("rate_decimal")))
        except Exception:
            status = "error"
            messages.append("rate_decimal must be a number.")

        effective_from = parse_date(str(raw.get("valid_from") or raw.get("effective_from") or ""))
        if not effective_from:
            status = "error"
            messages.append("valid_from is required (YYYY-MM-DD).")

        valid_to_raw = raw.get("valid_to") or raw.get("effective_to")
        effective_to = None
        if valid_to_raw not in (None, "", "null"):
            effective_to = parse_date(str(valid_to_raw))
            if not effective_to:
                status = "error"
                messages.append("valid_to must be YYYY-MM-DD.")

        if effective_from and effective_to and effective_to < effective_from:
            status = "error"
            messages.append("valid_to must be on/after valid_from.")

        if not jurisdiction_code:
            status = "error"
            messages.append("jurisdiction_code is required.")
        jurisdiction = TaxJurisdiction.objects.filter(code=jurisdiction_code).first() if jurisdiction_code else None
        if jurisdiction_code and not jurisdiction:
            status = "error"
            messages.append("Unknown jurisdiction_code.")

        if not tax_name:
            status = "error"
            messages.append("tax_name is required (must match an existing TaxComponent.name).")
        component = (
            TaxComponent.objects.filter(business=business, name=tax_name).select_related("jurisdiction").first()
            if tax_name
            else None
        )
        if tax_name and not component:
            status = "error"
            messages.append("Tax component not found for this business.")
        elif component and jurisdiction:
            if component.jurisdiction_id and component.jurisdiction.code != jurisdiction_code:
                status = "error"
                messages.append("Tax component exists but is tied to a different jurisdiction.")

        if product_category not in TaxRate.ProductCategory.values:
            status = "error"
            messages.append("Invalid product_category.")

        if meta_data_raw not in (None, ""):
            if isinstance(meta_data_raw, dict):
                pass
            else:
                try:
                    parsed = json.loads(str(meta_data_raw))
                    if not isinstance(parsed, dict):
                        status = "error"
                        messages.append("meta_data must be a JSON object.")
                except Exception:
                    status = "error"
                    messages.append("meta_data must be valid JSON.")

        target_rate = None
        if provided_id:
            target_rate = TaxRate.objects.filter(id=provided_id, component__business=business).select_related("component").first()
            if not target_rate:
                status = "error"
                messages.append("Rate id not found for this business.")

        would_update = bool(target_rate)
        would_create = not would_update
        target_id = str(target_rate.id) if target_rate else None

        if status != "error" and component and effective_from:
            overlap = _check_rate_overlap(
                component=component,
                product_category=product_category,
                effective_from=effective_from,
                effective_to=effective_to,
                exclude_id=target_rate.id if target_rate else None,
            )
            if overlap:
                status = "error"
                messages.append("Overlapping rate ranges for this jurisdiction/tax_name/product_category.")

        if would_update:
            messages.append("Would update existing rate row (by id).")
        else:
            messages.append("Would create a new rate row.")

        results.append(
            PreviewRow(
                index=idx,
                raw=raw,
                status=status,
                messages=messages,
                would_create=would_create,
                would_update=would_update,
                target_id=target_id,
            )
        )
    return results


def _preview_product_rules(rows: List[Dict[str, Any]]) -> List[PreviewRow]:
    results: List[PreviewRow] = []
    for idx, raw in enumerate(rows):
        messages: List[str] = []
        status = "ok"

        provided_id = str(raw.get("id") or "").strip()
        jurisdiction_code = str(raw.get("jurisdiction_code") or "").strip().upper()
        product_code = str(raw.get("product_code") or "").strip().upper()
        rule_type = str(raw.get("rule_type") or "").strip().upper()
        notes = str(raw.get("notes") or "").strip()

        valid_from = parse_date(str(raw.get("valid_from") or ""))
        if not valid_from:
            status = "error"
            messages.append("valid_from is required (YYYY-MM-DD).")

        valid_to_raw = raw.get("valid_to")
        valid_to = None
        if valid_to_raw not in (None, "", "null"):
            valid_to = parse_date(str(valid_to_raw))
            if not valid_to:
                status = "error"
                messages.append("valid_to must be YYYY-MM-DD.")

        if valid_from and valid_to and valid_to < valid_from:
            status = "error"
            messages.append("valid_to must be on/after valid_from.")

        if not jurisdiction_code:
            status = "error"
            messages.append("jurisdiction_code is required.")
        jurisdiction = TaxJurisdiction.objects.filter(code=jurisdiction_code).first() if jurisdiction_code else None
        if jurisdiction_code and not jurisdiction:
            status = "error"
            messages.append("Unknown jurisdiction_code.")

        if not product_code:
            status = "error"
            messages.append("product_code is required.")

        if rule_type not in TaxProductRule.RuleType.values:
            status = "error"
            messages.append("Invalid rule_type.")

        special_rate = None
        if rule_type == TaxProductRule.RuleType.REDUCED:
            try:
                special_rate = Decimal(str(raw.get("special_rate")))
                if special_rate <= 0:
                    raise ValueError()
            except Exception:
                status = "error"
                messages.append("special_rate is required and must be > 0 for REDUCED.")

        target_rule = None
        if provided_id:
            target_rule = TaxProductRule.objects.filter(id=provided_id).select_related("jurisdiction").first()
            if not target_rule:
                status = "error"
                messages.append("Rule id not found.")

        would_update = bool(target_rule)
        would_create = not would_update
        target_id = str(target_rule.id) if target_rule else None

        if status != "error" and jurisdiction and valid_from:
            overlap = _check_product_rule_overlap(
                jurisdiction=jurisdiction,
                product_code=product_code,
                valid_from=valid_from,
                valid_to=valid_to,
                exclude_id=target_rule.id if target_rule else None,
            )
            if overlap:
                status = "error"
                messages.append("Overlapping rule ranges for this jurisdiction/product_code.")

        if would_update:
            messages.append("Would update existing product rule row (by id).")
        else:
            messages.append("Would create a new product rule row.")

        results.append(
            PreviewRow(
                index=idx,
                raw=raw,
                status=status,
                messages=messages,
                would_create=would_create,
                would_update=would_update,
                target_id=target_id,
            )
        )
    return results


def _preview(import_type: str, *, business, rows: List[Dict[str, Any]]) -> List[PreviewRow]:
    if import_type == "jurisdictions":
        return _preview_jurisdictions(rows)
    if import_type == "rates":
        if not business:
            raise ValueError("business_id is required for rates import.")
        return _preview_rates(business=business, rows=rows)
    if import_type == "product_rules":
        return _preview_product_rules(rows)
    raise ValueError("Unknown import_type.")


def _apply_jurisdictions(preview_rows: List[PreviewRow]) -> Tuple[int, int, int, List[str]]:
    created = updated = skipped = 0
    warnings: List[str] = []
    for pr in preview_rows:
        raw = pr.raw
        code = str(raw.get("code") or "").strip().upper()
        name = str(raw.get("name") or "").strip()
        jurisdiction_type = str(raw.get("jurisdiction_type") or "").strip().upper()
        country_code = str(raw.get("country_code") or "").strip().upper()
        region_code = str(raw.get("region_code") or "").strip().upper()
        sourcing_rule = str(raw.get("sourcing_rule") or "").strip().upper()
        parent_code = str(raw.get("parent_code") or "").strip().upper()
        is_active = raw.get("is_active")
        if is_active in (None, ""):
            is_active = True
        else:
            is_active = _boolish(is_active)

        existing = TaxJurisdiction.objects.select_related("parent").filter(code=code).first()
        if existing:
            is_custom = bool((existing.metadata or {}).get("is_custom"))
            update_fields = []
            if name and name != existing.name:
                existing.name = name
                update_fields.append("name")
            if is_active != existing.is_active:
                existing.is_active = is_active
                update_fields.append("is_active")
            if is_custom and sourcing_rule and sourcing_rule in TaxJurisdiction.SourcingRule.values and sourcing_rule != existing.sourcing_rule:
                existing.sourcing_rule = sourcing_rule
                update_fields.append("sourcing_rule")
            if update_fields:
                existing.save(update_fields=update_fields)
                updated += 1
            else:
                skipped += 1
            continue

        parent = TaxJurisdiction.objects.filter(code=parent_code).first() if parent_code else None
        metadata = {"is_custom": True, "created_via": "import"}
        if sourcing_rule and sourcing_rule not in TaxJurisdiction.SourcingRule.values:
            sourcing_rule = TaxJurisdiction.SourcingRule.DESTINATION
        TaxJurisdiction.objects.create(
            code=code,
            name=name,
            jurisdiction_type=jurisdiction_type,
            country_code=country_code,
            region_code=region_code,
            sourcing_rule=sourcing_rule or TaxJurisdiction.SourcingRule.DESTINATION,
            parent=parent,
            is_active=is_active,
            metadata=metadata,
        )
        created += 1
    return created, updated, skipped, warnings


def _apply_rates(preview_rows: List[PreviewRow], *, business) -> Tuple[int, int, int, List[str]]:
    created = updated = skipped = 0
    warnings: List[str] = []
    for pr in preview_rows:
        raw = pr.raw
        provided_id = str(raw.get("id") or "").strip()
        jurisdiction_code = str(raw.get("jurisdiction_code") or "").strip().upper()
        tax_name = str(raw.get("tax_name") or "").strip()
        product_category = str(raw.get("product_category") or TaxRate.ProductCategory.STANDARD).strip().upper()
        rate_decimal = Decimal(str(raw.get("rate_decimal")))
        effective_from = parse_date(str(raw.get("valid_from") or raw.get("effective_from") or ""))
        valid_to_raw = raw.get("valid_to") or raw.get("effective_to")
        effective_to = None
        if valid_to_raw not in (None, "", "null"):
            effective_to = parse_date(str(valid_to_raw))

        is_compound = _boolish(raw.get("is_compound", False))
        meta_data_raw = raw.get("meta_data")
        meta_data = {}
        if isinstance(meta_data_raw, dict):
            meta_data = meta_data_raw
        elif meta_data_raw not in (None, ""):
            meta_data = json.loads(str(meta_data_raw))
        jurisdiction = TaxJurisdiction.objects.filter(code=jurisdiction_code).first()
        component = TaxComponent.objects.filter(business=business, name=tax_name).select_related("jurisdiction").first()

        # Safe enrichment: attach jurisdiction to component if missing.
        if component and jurisdiction and component.jurisdiction_id is None:
            component.jurisdiction = jurisdiction
            component.save(update_fields=["jurisdiction"])

        if provided_id:
            target = TaxRate.objects.filter(id=provided_id, component__business=business).select_related("component").first()
        else:
            target = None

        if target:
            target.rate_decimal = rate_decimal
            target.effective_from = effective_from
            target.effective_to = effective_to
            target.product_category = product_category
            target.is_compound = is_compound
            target.meta_data = meta_data
            target.save()
            updated += 1
        else:
            TaxRate.objects.create(
                component=component,
                rate_decimal=rate_decimal,
                effective_from=effective_from,
                effective_to=effective_to,
                product_category=product_category,
                is_compound=is_compound,
                meta_data=meta_data,
            )
            created += 1
    return created, updated, skipped, warnings


def _apply_product_rules(preview_rows: List[PreviewRow]) -> Tuple[int, int, int, List[str]]:
    created = updated = skipped = 0
    warnings: List[str] = []
    for pr in preview_rows:
        raw = pr.raw
        provided_id = str(raw.get("id") or "").strip()
        jurisdiction_code = str(raw.get("jurisdiction_code") or "").strip().upper()
        product_code = str(raw.get("product_code") or "").strip().upper()
        rule_type = str(raw.get("rule_type") or "").strip().upper()
        notes = str(raw.get("notes") or "").strip()

        valid_from = parse_date(str(raw.get("valid_from") or ""))
        valid_to_raw = raw.get("valid_to")
        valid_to = None
        if valid_to_raw not in (None, "", "null"):
            valid_to = parse_date(str(valid_to_raw))

        special_rate = None
        if rule_type == TaxProductRule.RuleType.REDUCED:
            special_rate = Decimal(str(raw.get("special_rate")))

        jurisdiction = TaxJurisdiction.objects.filter(code=jurisdiction_code).first()
        if provided_id:
            target = TaxProductRule.objects.filter(id=provided_id).first()
        else:
            target = None

        if target:
            # Keep jurisdiction fixed on update (v1 guardrail).
            if target.product_code != product_code:
                target.product_code = product_code
            target.rule_type = rule_type
            target.special_rate = special_rate
            target.valid_from = valid_from
            target.valid_to = valid_to
            target.notes = notes
            target.save()
            updated += 1
        else:
            TaxProductRule.objects.create(
                jurisdiction=jurisdiction,
                product_code=product_code,
                rule_type=rule_type,
                special_rate=special_rate,
                valid_from=valid_from,
                valid_to=valid_to,
                notes=notes,
            )
            created += 1
    return created, updated, skipped, warnings


def _apply(import_type: str, *, business, preview_rows: List[PreviewRow]) -> Tuple[int, int, int, List[str]]:
    if import_type == "jurisdictions":
        return _apply_jurisdictions(preview_rows)
    if import_type == "rates":
        if not business:
            raise ValueError("business_id is required for rates import.")
        return _apply_rates(preview_rows, business=business)
    if import_type == "product_rules":
        return _apply_product_rules(preview_rows)
    raise ValueError("Unknown import_type.")


@login_required
def api_tax_catalog_import_preview(request):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    import_type = (request.POST.get("import_type") or "").strip()
    if import_type not in ("jurisdictions", "rates", "product_rules"):
        return JsonResponse({"error": "import_type must be jurisdictions, rates, or product_rules."}, status=400)

    business = None
    if import_type == "rates":
        business = _get_staff_target_business(request)
        if not business:
            return JsonResponse(
                {"error": "business_id is required for rates import (staff has no active business context)."},
                status=400,
            )

    fmt, rows, err = _parse_payload_rows(request.FILES.get("file"))
    if err:
        return JsonResponse({"error": err}, status=400)
    assert rows is not None

    preview_rows = _preview(import_type, business=business, rows=rows)
    return JsonResponse(
        {
            "import_type": import_type,
            "format": fmt,
            "rows": [r.as_dict() for r in preview_rows],
            "summary": _summary(preview_rows),
        }
    )


@login_required
def api_tax_catalog_import_apply(request):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    import_type = (request.POST.get("import_type") or "").strip()
    if import_type not in ("jurisdictions", "rates", "product_rules"):
        return JsonResponse({"error": "import_type must be jurisdictions, rates, or product_rules."}, status=400)

    business = None
    if import_type == "rates":
        business = _get_staff_target_business(request)
        if not business:
            return JsonResponse(
                {"error": "business_id is required for rates import (staff has no active business context)."},
                status=400,
            )

    fmt, rows, err = _parse_payload_rows(request.FILES.get("file"))
    if err:
        return JsonResponse({"error": err}, status=400)
    assert rows is not None

    preview_rows = _preview(import_type, business=business, rows=rows)
    errors = [r.as_dict() for r in preview_rows if r.status == "error"]
    warnings = [r.as_dict() for r in preview_rows if r.status == "warning"]
    if errors:
        return JsonResponse(
            {
                "error": "Import contains errors; fix and re-upload.",
                "import_type": import_type,
                "summary": _summary(preview_rows),
                "rows": errors + warnings,
            },
            status=400,
        )

    with transaction.atomic():
        created, updated, skipped, warnings_out = _apply(import_type, business=business, preview_rows=preview_rows)

    preview_warning_messages = [
        f"Row {r.index}: {m}"
        for r in preview_rows
        if r.status == "warning"
        for m in (r.messages or [])
    ]
    warnings_out = (warnings_out or []) + preview_warning_messages

    return JsonResponse(
        {
            "import_type": import_type,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "warnings": warnings_out,
        }
    )
