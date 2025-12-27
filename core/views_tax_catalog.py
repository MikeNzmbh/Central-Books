import json
import re
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils.dateparse import parse_date

from core.utils import get_current_business
from core.models import Business
from core.permissions import has_permission
from taxes.models import TaxJurisdiction, TaxProductRule, TaxRate, TaxComponent, TaxGroup


def _require_catalog_permission(request, business=None, *, write=False):
    """
    RBAC-based permission check for Tax Catalog endpoints.
    - write=False -> requires tax.catalog.view
    - write=True -> requires tax.catalog.manage
    """
    if not request.user.is_staff:
        return JsonResponse({"error": "Forbidden"}, status=403)

    if business is None:
        business = get_current_business(request.user)
    if not business:
        # Staff without business context can still operate if they have the permission via their role
        # Check if user has the global permission
        if write:
            return JsonResponse({"error": "Forbidden"}, status=403)
        return None  # Allow view without business for staff listing endpoints
    action = "tax.catalog.manage" if write else "tax.catalog.view"
    if not has_permission(request.user, business, action):
        return JsonResponse({"error": "Forbidden"}, status=403)
    return None


def _parse_int(value, *, default: int, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return max(min_value, min(max_value, parsed))


def _get_staff_target_business(request, *, payload: dict | None = None):
    """
    Staff-only catalog endpoints sometimes operate on business-scoped models
    (TaxGroup/TaxComponent/TaxRate). Staff users may not have a current business
    context, so allow explicitly targeting a business via `business_id`.
    """
    business = get_current_business(request.user)
    if business:
        return business

    raw = None
    if isinstance(payload, dict):
        raw = payload.get("business_id")
    raw = raw or request.GET.get("business_id")
    if raw in (None, ""):
        return None
    try:
        business_id = int(raw)
    except Exception:
        return None
    return Business.objects.filter(id=business_id).first()


def _serialize_jurisdiction(j: TaxJurisdiction) -> dict:
    return {
        "id": str(j.id),
        "code": j.code,
        "name": j.name,
        "jurisdiction_type": j.jurisdiction_type,
        "country_code": j.country_code,
        "region_code": j.region_code,
        "sourcing_rule": j.sourcing_rule,
        "parent_code": j.parent.code if j.parent else None,
        "is_active": j.is_active,
        "is_custom": bool((j.metadata or {}).get("is_custom")),
    }


def _serialize_rate(r: TaxRate) -> dict:
    component = r.component
    jurisdiction_code = None
    if getattr(component, "jurisdiction", None):
        jurisdiction_code = component.jurisdiction.code
    elif getattr(component, "authority", None):
        jurisdiction_code = component.authority
    return {
        "id": str(r.id),
        "jurisdiction_code": jurisdiction_code,
        "tax_name": component.name,
        "rate_decimal": float(r.rate_decimal),
        "is_compound": bool(getattr(r, "is_compound", False)),
        "valid_from": r.effective_from.isoformat() if r.effective_from else None,
        "valid_to": r.effective_to.isoformat() if r.effective_to else None,
        "product_category": r.product_category,
        "meta_data": getattr(r, "meta_data", {}) or {},
    }


def _serialize_product_rule(rule: TaxProductRule) -> dict:
    return {
        "id": str(rule.id),
        "jurisdiction_code": rule.jurisdiction.code,
        "product_code": rule.product_code,
        "rule_type": rule.rule_type,
        "special_rate": float(rule.special_rate) if rule.special_rate is not None else None,
        "ssuta_code": getattr(rule, "ssuta_code", "") or "",
        "valid_from": rule.valid_from.isoformat() if rule.valid_from else None,
        "valid_to": rule.valid_to.isoformat() if rule.valid_to else None,
        "notes": rule.notes or "",
    }


def _serialize_tax_group(group: TaxGroup) -> dict:
    return {
        "id": str(group.id),
        "display_name": group.display_name,
        "calculation_method": group.calculation_method,
        "tax_treatment": getattr(group, "tax_treatment", None),
        "reporting_category": getattr(group, "reporting_category", TaxGroup.ReportingCategory.TAXABLE),
        "is_system_locked": bool(group.is_system_locked),
        "component_count": int(getattr(group, "component_count", 0) or 0),
    }


def _ranges_overlap(a_from, a_to, b_from, b_to) -> bool:
    if a_to is not None and a_to < b_from:
        return False
    if b_to is not None and b_to < a_from:
        return False
    return True


def _check_rate_overlap(*, component: TaxComponent, product_category: str, effective_from, effective_to, exclude_id=None):
    qs = TaxRate.objects.filter(component=component, product_category=product_category)
    if exclude_id is not None:
        qs = qs.exclude(id=exclude_id)
    qs = qs.filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from))
    if effective_to is not None:
        qs = qs.filter(effective_from__lte=effective_to)
    return qs.exists()


def _check_product_rule_overlap(*, jurisdiction: TaxJurisdiction, product_code: str, valid_from, valid_to, exclude_id=None):
    qs = TaxProductRule.objects.filter(jurisdiction=jurisdiction, product_code=product_code)
    if exclude_id is not None:
        qs = qs.exclude(id=exclude_id)
    for existing in qs.only("valid_from", "valid_to"):
        if _ranges_overlap(valid_from, valid_to, existing.valid_from, existing.valid_to):
            return True
    return False


@login_required
def api_tax_catalog_jurisdictions(request):
    # VIEW for GET, MANAGE for POST
    is_write = request.method == "POST"
    forbidden = _require_catalog_permission(request, write=is_write)
    if forbidden:
        return forbidden

    if request.method == "GET":
        country_code = (request.GET.get("country_code") or "").strip().upper()
        region_code = (request.GET.get("region_code") or "").strip().upper()
        jurisdiction_type = (request.GET.get("jurisdiction_type") or "").strip().upper()

        limit = _parse_int(request.GET.get("limit"), default=200, min_value=1, max_value=500)
        offset = _parse_int(request.GET.get("offset"), default=0, min_value=0, max_value=1000000)

        qs = TaxJurisdiction.objects.select_related("parent").all()
        if country_code:
            qs = qs.filter(country_code=country_code)
        if region_code:
            qs = qs.filter(region_code=region_code)
        if jurisdiction_type:
            qs = qs.filter(jurisdiction_type=jurisdiction_type)

        count = qs.count()
        rows = [_serialize_jurisdiction(j) for j in qs.order_by("country_code", "code")[offset : offset + limit]]
        next_offset = offset + limit if (offset + limit) < count else None
        return JsonResponse(
            {"count": count, "results": rows, "limit": limit, "offset": offset, "next_offset": next_offset}
        )

    if request.method != "POST":
        return HttpResponseBadRequest("GET or POST required")

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}

    errors = {}
    code = (payload.get("code") or "").strip().upper()
    name = (payload.get("name") or "").strip()
    jurisdiction_type = (payload.get("jurisdiction_type") or "").strip().upper()
    country_code = (payload.get("country_code") or "").strip().upper()
    region_code = (payload.get("region_code") or "").strip().upper()
    sourcing_rule = (payload.get("sourcing_rule") or TaxJurisdiction.SourcingRule.DESTINATION).strip().upper()
    parent_code = (payload.get("parent_code") or "").strip().upper() or None
    is_active = bool(payload.get("is_active", True))

    if not code:
        errors["code"] = "code is required."
    elif not re.match(r"^[A-Z0-9-]+$", code):
        errors["code"] = "code must be alphanumeric with dashes only."

    if not name:
        errors["name"] = "name is required."
    if jurisdiction_type not in TaxJurisdiction.JurisdictionType.values:
        errors["jurisdiction_type"] = "Invalid jurisdiction_type."
    if not country_code or len(country_code) != 2:
        errors["country_code"] = "country_code must be 2-letter ISO (e.g., CA, US)."
    if sourcing_rule not in TaxJurisdiction.SourcingRule.values:
        errors["sourcing_rule"] = "Invalid sourcing_rule."

    parent = None
    if parent_code:
        parent = TaxJurisdiction.objects.filter(code=parent_code).first()
        if not parent:
            errors["parent_code"] = "parent_code not found."

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    metadata = {"is_custom": True, "created_via": "catalog_api"}
    try:
        jurisdiction = TaxJurisdiction.objects.create(
            code=code,
            name=name,
            jurisdiction_type=jurisdiction_type,
            country_code=country_code,
            region_code=region_code,
            sourcing_rule=sourcing_rule,
            parent=parent,
            is_active=is_active,
            metadata=metadata,
        )
    except Exception:
        return JsonResponse({"error": "Unable to create jurisdiction (code may already exist)."}, status=400)

    return JsonResponse(_serialize_jurisdiction(jurisdiction), status=201)


@login_required
def api_tax_catalog_jurisdiction_detail(request, code: str):
    is_write = request.method in ("POST", "PATCH", "DELETE")
    forbidden = _require_catalog_permission(request, write=is_write)
    if forbidden:
        return forbidden

    code = (code or "").strip().upper()
    jurisdiction = TaxJurisdiction.objects.select_related("parent").filter(code=code).first()
    if not jurisdiction:
        return JsonResponse({"error": "Not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(_serialize_jurisdiction(jurisdiction))

    if request.method != "PATCH":
        return HttpResponseBadRequest("GET or PATCH required")

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}

    forbidden_fields = {"code", "country_code", "jurisdiction_type", "region_code", "parent_code", "parent"}
    attempted = forbidden_fields.intersection(payload.keys())
    if attempted:
        return JsonResponse({"errors": {k: "Field cannot be modified." for k in attempted}}, status=400)

    is_custom = bool((jurisdiction.metadata or {}).get("is_custom"))
    updates = {}
    errors = {}

    if "name" in payload:
        name = (payload.get("name") or "").strip()
        if not name:
            errors["name"] = "name cannot be empty."
        else:
            updates["name"] = name

    if "is_active" in payload:
        updates["is_active"] = bool(payload.get("is_active"))

    if "sourcing_rule" in payload:
        if not is_custom:
            errors["sourcing_rule"] = "sourcing_rule can only be edited for custom jurisdictions."
        else:
            sr = (payload.get("sourcing_rule") or "").strip().upper()
            if sr not in TaxJurisdiction.SourcingRule.values:
                errors["sourcing_rule"] = "Invalid sourcing_rule."
            else:
                updates["sourcing_rule"] = sr

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    for k, v in updates.items():
        setattr(jurisdiction, k, v)
    if updates:
        jurisdiction.save(update_fields=list(updates.keys()))
    return JsonResponse(_serialize_jurisdiction(jurisdiction))


@login_required
def api_tax_catalog_groups(request):
    is_write = request.method in ("POST", "PATCH", "DELETE")
    forbidden = _require_catalog_permission(request, write=is_write)
    if forbidden:
        return forbidden
    business = _get_staff_target_business(request)
    if not business:
        return JsonResponse({"error": "business_id is required (staff has no active business context)."}, status=400)

    if request.method != "GET":
        return HttpResponseBadRequest("GET required")

    q = (request.GET.get("q") or "").strip()
    limit = _parse_int(request.GET.get("limit"), default=200, min_value=1, max_value=500)
    offset = _parse_int(request.GET.get("offset"), default=0, min_value=0, max_value=1000000)

    qs = TaxGroup.objects.filter(business=business).annotate(component_count=Count("components"))
    if q:
        qs = qs.filter(display_name__icontains=q)

    count = qs.count()
    rows = [_serialize_tax_group(g) for g in qs.order_by("display_name")[offset : offset + limit]]
    next_offset = offset + limit if (offset + limit) < count else None
    return JsonResponse({"count": count, "results": rows, "limit": limit, "offset": offset, "next_offset": next_offset})


@login_required
def api_tax_catalog_group_detail(request, group_id):
    is_write = request.method in ("POST", "PATCH", "DELETE")
    forbidden = _require_catalog_permission(request, write=is_write)
    if forbidden:
        return forbidden
    business = _get_staff_target_business(request)
    if not business:
        return JsonResponse({"error": "business_id is required (staff has no active business context)."}, status=400)

    group = (
        TaxGroup.objects.filter(business=business, id=group_id)
        .annotate(component_count=Count("components"))
        .first()
    )
    if not group:
        return JsonResponse({"error": "Not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(_serialize_tax_group(group))

    if request.method != "PATCH":
        return HttpResponseBadRequest("GET or PATCH required")

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}

    errors = {}
    updates = {}

    if "reporting_category" in payload:
        category = (payload.get("reporting_category") or "").strip().upper()
        if category not in TaxGroup.ReportingCategory.values:
            errors["reporting_category"] = "Invalid reporting_category."
        else:
            updates["reporting_category"] = category

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    for k, v in updates.items():
        setattr(group, k, v)
    if updates:
        group.save(update_fields=list(updates.keys()))
    return JsonResponse(_serialize_tax_group(group))


@login_required
def api_tax_catalog_rates(request):
    is_write = request.method in ("POST", "PATCH", "DELETE")
    forbidden = _require_catalog_permission(request, write=is_write)
    if forbidden:
        return forbidden
    business = _get_staff_target_business(request)
    if not business:
        return JsonResponse({"error": "business_id is required (staff has no active business context)."}, status=400)

    if request.method == "GET":
        jurisdiction_code = (request.GET.get("jurisdiction_code") or "").strip().upper()
        tax_name = (request.GET.get("tax_name") or "").strip()
        active_on_raw = (request.GET.get("active_on") or "").strip()
        active_on = parse_date(active_on_raw) if active_on_raw else None

        limit = _parse_int(request.GET.get("limit"), default=200, min_value=1, max_value=500)
        offset = _parse_int(request.GET.get("offset"), default=0, min_value=0, max_value=1000000)

        qs = TaxRate.objects.select_related("component", "component__jurisdiction").filter(component__business=business)
        if jurisdiction_code:
            qs = qs.filter(Q(component__jurisdiction__code=jurisdiction_code) | Q(component__authority=jurisdiction_code))
        if tax_name:
            qs = qs.filter(component__name__icontains=tax_name)
        if active_on:
            qs = qs.filter(effective_from__lte=active_on).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=active_on))

        count = qs.count()
        rows = [_serialize_rate(r) for r in qs.order_by("-effective_from")[offset : offset + limit]]
        next_offset = offset + limit if (offset + limit) < count else None
        return JsonResponse({"count": count, "results": rows, "limit": limit, "offset": offset, "next_offset": next_offset})

    if request.method != "POST":
        return HttpResponseBadRequest("GET or POST required")

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}

    errors = {}
    jurisdiction_code = (payload.get("jurisdiction_code") or "").strip().upper()
    tax_name = (payload.get("tax_name") or "").strip()
    product_category = (payload.get("product_category") or TaxRate.ProductCategory.STANDARD).strip().upper()

    try:
        rate_decimal = Decimal(str(payload.get("rate_decimal")))
    except Exception:
        rate_decimal = None
        errors["rate_decimal"] = "rate_decimal must be a number."

    effective_from = parse_date(payload.get("valid_from") or "")
    if not effective_from:
        errors["valid_from"] = "valid_from must be YYYY-MM-DD."

    valid_to_raw = payload.get("valid_to")
    effective_to = None
    if valid_to_raw not in (None, "", "null"):
        effective_to = parse_date(str(valid_to_raw))
        if not effective_to:
            errors["valid_to"] = "valid_to must be YYYY-MM-DD."

    if effective_from and effective_to and effective_to < effective_from:
        errors["valid_to"] = "valid_to must be on/after valid_from."

    if product_category not in TaxRate.ProductCategory.values:
        errors["product_category"] = "Invalid product_category."

    if not jurisdiction_code:
        errors["jurisdiction_code"] = "jurisdiction_code is required."
    if not tax_name:
        errors["tax_name"] = "tax_name is required."

    jurisdiction = TaxJurisdiction.objects.filter(code=jurisdiction_code).first() if jurisdiction_code else None
    if jurisdiction_code and not jurisdiction:
        errors["jurisdiction_code"] = "Unknown jurisdiction_code."

    component = TaxComponent.objects.filter(business=business, name=tax_name).select_related("jurisdiction").first() if tax_name else None
    if tax_name and not component:
        errors["tax_name"] = "Tax component not found for this business (create the component first)."
    elif component and jurisdiction:
        if component.jurisdiction_id and component.jurisdiction.code != jurisdiction_code:
            errors["tax_name"] = "Tax component exists but is tied to a different jurisdiction."

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    # If component exists but lacks a jurisdiction link, attach it (safe enrichment).
    if component and jurisdiction and component.jurisdiction_id is None:
        component.jurisdiction = jurisdiction
        component.save(update_fields=["jurisdiction"])

    if _check_rate_overlap(
        component=component,
        product_category=product_category,
        effective_from=effective_from,
        effective_to=effective_to,
    ):
        return JsonResponse({"error": "Overlapping rate ranges for this jurisdiction/tax_name/product_category."}, status=400)

    is_compound = bool(payload.get("is_compound", False))
    meta_data = payload.get("meta_data") if isinstance(payload.get("meta_data"), dict) else {}

    rate = TaxRate.objects.create(
        component=component,
        rate_decimal=rate_decimal,
        effective_from=effective_from,
        effective_to=effective_to,
        product_category=product_category,
        is_compound=is_compound,
        meta_data=meta_data,
    )
    return JsonResponse(_serialize_rate(rate), status=201)


@login_required
def api_tax_catalog_rate_detail(request, rate_id):
    is_write = request.method in ("POST", "PATCH", "DELETE")
    forbidden = _require_catalog_permission(request, write=is_write)
    if forbidden:
        return forbidden
    business = _get_staff_target_business(request)
    if not business:
        return JsonResponse({"error": "business_id is required (staff has no active business context)."}, status=400)

    rate = TaxRate.objects.select_related("component", "component__jurisdiction").filter(id=rate_id, component__business=business).first()
    if not rate:
        return JsonResponse({"error": "Not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(_serialize_rate(rate))

    if request.method != "PATCH":
        return HttpResponseBadRequest("GET or PATCH required")

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}

    updates = {}
    errors = {}

    if "rate_decimal" in payload:
        try:
            updates["rate_decimal"] = Decimal(str(payload.get("rate_decimal")))
        except Exception:
            errors["rate_decimal"] = "rate_decimal must be a number."

    if "valid_from" in payload:
        ef = parse_date(payload.get("valid_from") or "")
        if not ef:
            errors["valid_from"] = "valid_from must be YYYY-MM-DD."
        else:
            updates["effective_from"] = ef

    if "valid_to" in payload:
        raw = payload.get("valid_to")
        if raw in (None, "", "null"):
            updates["effective_to"] = None
        else:
            et = parse_date(str(raw))
            if not et:
                errors["valid_to"] = "valid_to must be YYYY-MM-DD."
            else:
                updates["effective_to"] = et

    if "product_category" in payload:
        pc = (payload.get("product_category") or "").strip().upper()
        if pc not in TaxRate.ProductCategory.values:
            errors["product_category"] = "Invalid product_category."
        else:
            updates["product_category"] = pc

    if "is_compound" in payload:
        updates["is_compound"] = bool(payload.get("is_compound"))

    if "meta_data" in payload:
        if payload.get("meta_data") is None:
            updates["meta_data"] = {}
        elif not isinstance(payload.get("meta_data"), dict):
            errors["meta_data"] = "meta_data must be an object."
        else:
            updates["meta_data"] = payload.get("meta_data")

    effective_from = updates.get("effective_from", rate.effective_from)
    effective_to = updates.get("effective_to", rate.effective_to)
    product_category = updates.get("product_category", rate.product_category)

    if effective_from and effective_to and effective_to < effective_from:
        errors["valid_to"] = "valid_to must be on/after valid_from."

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    if _check_rate_overlap(
        component=rate.component,
        product_category=product_category,
        effective_from=effective_from,
        effective_to=effective_to,
        exclude_id=rate.id,
    ):
        return JsonResponse({"error": "Overlapping rate ranges for this jurisdiction/tax_name/product_category."}, status=400)

    for k, v in updates.items():
        setattr(rate, k, v)
    if updates:
        rate.save(update_fields=list(updates.keys()))
    return JsonResponse(_serialize_rate(rate))


@login_required
def api_tax_catalog_product_rules(request):
    is_write = request.method in ("POST", "PATCH", "DELETE")
    forbidden = _require_catalog_permission(request, write=is_write)
    if forbidden:
        return forbidden

    if request.method == "GET":
        jurisdiction_code = (request.GET.get("jurisdiction_code") or "").strip().upper()
        product_code = (request.GET.get("product_code") or "").strip().upper()
        limit = _parse_int(request.GET.get("limit"), default=200, min_value=1, max_value=500)
        offset = _parse_int(request.GET.get("offset"), default=0, min_value=0, max_value=1000000)

        qs = TaxProductRule.objects.select_related("jurisdiction").all()
        if jurisdiction_code:
            qs = qs.filter(jurisdiction__code=jurisdiction_code)
        if product_code:
            qs = qs.filter(product_code=product_code)

        count = qs.count()
        rows = [_serialize_product_rule(r) for r in qs.order_by("jurisdiction__code", "product_code", "-valid_from")[offset : offset + limit]]
        next_offset = offset + limit if (offset + limit) < count else None
        return JsonResponse({"count": count, "results": rows, "limit": limit, "offset": offset, "next_offset": next_offset})

    if request.method != "POST":
        return HttpResponseBadRequest("GET or POST required")

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}

    errors = {}
    jurisdiction_code = (payload.get("jurisdiction_code") or "").strip().upper()
    product_code = (payload.get("product_code") or "").strip().upper()
    rule_type = (payload.get("rule_type") or "").strip().upper()
    notes = (payload.get("notes") or "").strip()
    ssuta_code = (payload.get("ssuta_code") or "").strip()
    if ssuta_code and len(ssuta_code) > 64:
        errors["ssuta_code"] = "ssuta_code must be 64 characters or fewer."

    valid_from = parse_date(payload.get("valid_from") or "")
    if not valid_from:
        errors["valid_from"] = "valid_from must be YYYY-MM-DD."

    valid_to_raw = payload.get("valid_to")
    valid_to = None
    if valid_to_raw not in (None, "", "null"):
        valid_to = parse_date(str(valid_to_raw))
        if not valid_to:
            errors["valid_to"] = "valid_to must be YYYY-MM-DD."

    if valid_from and valid_to and valid_to < valid_from:
        errors["valid_to"] = "valid_to must be on/after valid_from."

    if not jurisdiction_code:
        errors["jurisdiction_code"] = "jurisdiction_code is required."
    if not product_code:
        errors["product_code"] = "product_code is required."
    if rule_type not in TaxProductRule.RuleType.values:
        errors["rule_type"] = "Invalid rule_type."

    jurisdiction = TaxJurisdiction.objects.filter(code=jurisdiction_code).first() if jurisdiction_code else None
    if jurisdiction_code and not jurisdiction:
        errors["jurisdiction_code"] = "Unknown jurisdiction_code."

    special_rate = None
    if rule_type == TaxProductRule.RuleType.REDUCED:
        try:
            special_rate = Decimal(str(payload.get("special_rate")))
        except Exception:
            special_rate = None
            errors["special_rate"] = "special_rate is required for REDUCED and must be a number."
        if special_rate is None or special_rate <= 0:
            errors["special_rate"] = "special_rate is required for REDUCED and must be > 0."
    else:
        if "special_rate" in payload and payload.get("special_rate") not in (None, "", "null"):
            try:
                special_rate = Decimal(str(payload.get("special_rate")))
            except Exception:
                errors["special_rate"] = "special_rate must be a number."

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    if _check_product_rule_overlap(
        jurisdiction=jurisdiction,
        product_code=product_code,
        valid_from=valid_from,
        valid_to=valid_to,
    ):
        return JsonResponse({"error": "Overlapping product rule ranges for this jurisdiction/product_code."}, status=400)

    rule = TaxProductRule.objects.create(
        jurisdiction=jurisdiction,
        product_code=product_code,
        rule_type=rule_type,
        special_rate=special_rate,
        ssuta_code=ssuta_code,
        valid_from=valid_from,
        valid_to=valid_to,
        notes=notes,
    )
    return JsonResponse(_serialize_product_rule(rule), status=201)


@login_required
def api_tax_catalog_product_rule_detail(request, rule_id):
    is_write = request.method in ("POST", "PATCH", "DELETE")
    forbidden = _require_catalog_permission(request, write=is_write)
    if forbidden:
        return forbidden

    rule = TaxProductRule.objects.select_related("jurisdiction").filter(id=rule_id).first()
    if not rule:
        return JsonResponse({"error": "Not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(_serialize_product_rule(rule))

    if request.method != "PATCH":
        return HttpResponseBadRequest("GET or PATCH required")

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}

    errors = {}
    updates = {}

    if "rule_type" in payload:
        rt = (payload.get("rule_type") or "").strip().upper()
        if rt not in TaxProductRule.RuleType.values:
            errors["rule_type"] = "Invalid rule_type."
        else:
            updates["rule_type"] = rt

    if "special_rate" in payload or updates.get("rule_type") == TaxProductRule.RuleType.REDUCED:
        sr_raw = payload.get("special_rate")
        if updates.get("rule_type", rule.rule_type) == TaxProductRule.RuleType.REDUCED:
            try:
                sr = Decimal(str(sr_raw))
            except Exception:
                sr = None
            if sr is None or sr <= 0:
                errors["special_rate"] = "special_rate is required for REDUCED and must be > 0."
            else:
                updates["special_rate"] = sr
        else:
            if sr_raw in (None, "", "null"):
                updates["special_rate"] = None
            else:
                try:
                    updates["special_rate"] = Decimal(str(sr_raw))
                except Exception:
                    errors["special_rate"] = "special_rate must be a number."

    if "valid_from" in payload:
        vf = parse_date(payload.get("valid_from") or "")
        if not vf:
            errors["valid_from"] = "valid_from must be YYYY-MM-DD."
        else:
            updates["valid_from"] = vf

    if "valid_to" in payload:
        raw = payload.get("valid_to")
        if raw in (None, "", "null"):
            updates["valid_to"] = None
        else:
            vt = parse_date(str(raw))
            if not vt:
                errors["valid_to"] = "valid_to must be YYYY-MM-DD."
            else:
                updates["valid_to"] = vt

    if "notes" in payload:
        updates["notes"] = (payload.get("notes") or "").strip()

    if "ssuta_code" in payload:
        sc = (payload.get("ssuta_code") or "").strip()
        if sc and len(sc) > 64:
            errors["ssuta_code"] = "ssuta_code must be 64 characters or fewer."
        else:
            updates["ssuta_code"] = sc

    if "product_code" in payload:
        pc = (payload.get("product_code") or "").strip().upper()
        if not pc:
            errors["product_code"] = "product_code cannot be empty."
        else:
            updates["product_code"] = pc

    valid_from = updates.get("valid_from", rule.valid_from)
    valid_to = updates.get("valid_to", rule.valid_to)
    product_code = updates.get("product_code", rule.product_code)

    if valid_from and valid_to and valid_to < valid_from:
        errors["valid_to"] = "valid_to must be on/after valid_from."

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    if _check_product_rule_overlap(
        jurisdiction=rule.jurisdiction,
        product_code=product_code,
        valid_from=valid_from,
        valid_to=valid_to,
        exclude_id=rule.id,
    ):
        return JsonResponse({"error": "Overlapping product rule ranges for this jurisdiction/product_code."}, status=400)

    for k, v in updates.items():
        setattr(rule, k, v)
    if updates:
        rule.save(update_fields=list(updates.keys()))
    return JsonResponse(_serialize_product_rule(rule))
