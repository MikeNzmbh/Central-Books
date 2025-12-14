import json
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils.dateparse import parse_date

from core.utils import get_current_business
from taxes.models import TaxJurisdiction, TaxProductRule


def _serialize_rule(rule: TaxProductRule) -> dict:
    return {
        "id": str(rule.id),
        "jurisdiction_code": rule.jurisdiction.code,
        "jurisdiction_name": rule.jurisdiction.name,
        "product_code": rule.product_code,
        "rule_type": rule.rule_type,
        "special_rate": float(rule.special_rate) if rule.special_rate is not None else None,
        "valid_from": rule.valid_from.isoformat() if rule.valid_from else None,
        "valid_to": rule.valid_to.isoformat() if rule.valid_to else None,
        "notes": rule.notes or "",
    }


def _parse_decimal(value) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _validate_payload(payload: dict, *, is_create: bool, existing: TaxProductRule | None = None) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    updates: dict = {}

    if is_create:
        jurisdiction_code = (payload.get("jurisdiction_code") or "").strip().upper()
        if not jurisdiction_code:
            errors["jurisdiction_code"] = "jurisdiction_code is required."
        else:
            jurisdiction = TaxJurisdiction.objects.filter(code=jurisdiction_code).first()
            if not jurisdiction:
                errors["jurisdiction_code"] = "Unknown jurisdiction_code."
            else:
                updates["jurisdiction"] = jurisdiction

        product_code = (payload.get("product_code") or "").strip()
        if not product_code:
            errors["product_code"] = "product_code is required."
        else:
            updates["product_code"] = product_code.upper()

        valid_from = parse_date(payload.get("valid_from") or "")
        if not valid_from:
            errors["valid_from"] = "valid_from is required (YYYY-MM-DD)."
        else:
            updates["valid_from"] = valid_from

    if "rule_type" in payload or is_create:
        rule_type = (payload.get("rule_type") or "").strip().upper()
        if rule_type not in TaxProductRule.RuleType.values:
            errors["rule_type"] = "Invalid rule_type."
        else:
            updates["rule_type"] = rule_type

    if "special_rate" in payload or (updates.get("rule_type") == TaxProductRule.RuleType.REDUCED):
        try:
            special_rate = _parse_decimal(payload.get("special_rate"))
        except Exception:
            errors["special_rate"] = "special_rate must be a number."
            special_rate = None
        if updates.get("rule_type") == TaxProductRule.RuleType.REDUCED:
            if special_rate is None or special_rate <= 0:
                errors["special_rate"] = "special_rate is required for REDUCED and must be > 0."
            else:
                updates["special_rate"] = special_rate
        else:
            if "special_rate" in payload:
                updates["special_rate"] = special_rate

    if "valid_from" in payload and not is_create:
        valid_from = parse_date(payload.get("valid_from") or "")
        if not valid_from:
            errors["valid_from"] = "valid_from must be YYYY-MM-DD."
        else:
            updates["valid_from"] = valid_from

    if "valid_to" in payload:
        valid_to_raw = payload.get("valid_to")
        if valid_to_raw in (None, "", "null"):
            updates["valid_to"] = None
        else:
            valid_to = parse_date(str(valid_to_raw))
            if not valid_to:
                errors["valid_to"] = "valid_to must be YYYY-MM-DD."
            else:
                updates["valid_to"] = valid_to

    if "notes" in payload:
        updates["notes"] = (payload.get("notes") or "").strip()

    if "product_code" in payload and not is_create:
        product_code = (payload.get("product_code") or "").strip()
        if not product_code:
            errors["product_code"] = "product_code cannot be empty."
        else:
            updates["product_code"] = product_code.upper()

    # Cross-field validation
    vf = updates.get("valid_from") or (existing.valid_from if existing else None)
    vt = updates.get("valid_to") if "valid_to" in updates else (existing.valid_to if existing else None)
    if vf and vt and vt < vf:
        errors["valid_to"] = "valid_to must be on/after valid_from."

    if existing and "jurisdiction" in updates:
        errors["jurisdiction_code"] = "Jurisdiction cannot be changed."
        updates.pop("jurisdiction", None)

    return updates, errors


@login_required
def api_tax_product_rules(request):
    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    if request.method == "GET":
        jurisdiction = (request.GET.get("jurisdiction") or "").strip().upper()
        product_code = (request.GET.get("product_code") or "").strip().upper()
        qs = TaxProductRule.objects.select_related("jurisdiction").all()
        if jurisdiction:
            qs = qs.filter(jurisdiction__code=jurisdiction)
        if product_code:
            qs = qs.filter(product_code=product_code)
        if not jurisdiction and not product_code:
            nexus = business.default_nexus_jurisdictions or []
            if nexus:
                qs = qs.filter(jurisdiction__code__in=nexus)
        rules = [_serialize_rule(r) for r in qs.order_by("jurisdiction__code", "product_code", "-valid_from")[:500]]
        return JsonResponse({"rules": rules})

    if request.method != "POST":
        return HttpResponseBadRequest("GET or POST required")

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}
    updates, errors = _validate_payload(payload, is_create=True)
    if errors:
        return JsonResponse({"errors": errors}, status=400)

    try:
        rule = TaxProductRule.objects.create(**updates)
    except IntegrityError:
        return JsonResponse({"error": "Rule already exists for this jurisdiction/product/valid_from."}, status=400)

    return JsonResponse(_serialize_rule(rule), status=201)


@login_required
def api_tax_product_rule_detail(request, rule_id):
    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    rule = TaxProductRule.objects.select_related("jurisdiction").filter(id=rule_id).first()
    if not rule:
        return JsonResponse({"error": "Not found"}, status=404)

    if request.method == "DELETE":
        rule.delete()
        return JsonResponse({"status": "deleted"}, status=200)

    if request.method != "PATCH":
        return HttpResponseBadRequest("PATCH or DELETE required")

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}

    updates, errors = _validate_payload(payload, is_create=False, existing=rule)
    if errors:
        return JsonResponse({"errors": errors}, status=400)

    for k, v in updates.items():
        setattr(rule, k, v)
    try:
        rule.save()
    except IntegrityError:
        return JsonResponse({"error": "Rule already exists for this jurisdiction/product/valid_from."}, status=400)

    return JsonResponse(_serialize_rule(rule))

