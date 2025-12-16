from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from taxes.models import TaxJurisdiction


@dataclass(frozen=True)
class ResolvedInvoiceLocation:
    ship_from: Optional[str]
    ship_to: Optional[str]
    customer_location: Optional[str]


def _normalize_code(code: str | None) -> str | None:
    if not code:
        return None
    normalized = str(code).strip().upper()
    return normalized or None


def _rollup_to_state_or_province(code: str | None) -> str | None:
    """
    Roll up a jurisdiction code to the top-level state/province when a nested code is present.
    Examples:
    - "US-CA-LA" -> "US-CA"
    - "CA-QC-MTL" -> "CA-QC"
    - "US-CA" -> "US-CA"
    """
    normalized = _normalize_code(code)
    if not normalized:
        return None
    parts = normalized.split("-")
    if len(parts) >= 2:
        return "-".join(parts[:2])
    return normalized


def _clamp_country(code: str | None, *, country_code: str) -> str | None:
    """
    Return a state/province-level code if it matches the expected country.
    """
    rolled = _rollup_to_state_or_province(code)
    if not rolled:
        return None
    if rolled == country_code.upper() or rolled.startswith(country_code.upper() + "-"):
        return rolled
    return None


def _invoice_location(invoice, *, country_code: str) -> ResolvedInvoiceLocation:
    return ResolvedInvoiceLocation(
        ship_from=_clamp_country(getattr(invoice, "ship_from_jurisdiction_code", None), country_code=country_code),
        ship_to=_clamp_country(getattr(invoice, "ship_to_jurisdiction_code", None), country_code=country_code),
        customer_location=_clamp_country(
            getattr(invoice, "customer_location_jurisdiction_code", None), country_code=country_code
        ),
    )


def _place_of_supply_kind(invoice) -> str:
    """
    Returns:
      - "TPP" for tangible goods
      - "SERVICE" for services / IPP
    """
    hint = _normalize_code(getattr(invoice, "place_of_supply_hint", None)) or "AUTO"
    if hint == "TPP":
        return "TPP"
    if hint in {"SERVICE", "IPP"}:
        return "SERVICE"

    item = getattr(invoice, "item", None)
    item_type = _normalize_code(getattr(item, "type", None))
    if item_type == "PRODUCT":
        return "TPP"
    return "SERVICE"


def resolve_ca_jurisdiction_for_invoice(invoice, business) -> str:
    """
    Canada place-of-supply rules at province/territory granularity.

    Blueprint:
    - TPP (goods): delivery location province (ship_to); if unavailable, ship_from.
    - Services/IPP: customer location province (customer_location); fallback to ship_to.
    - Fallback: business tax_country/tax_region.
    """
    loc = _invoice_location(invoice, country_code="CA")
    kind = _place_of_supply_kind(invoice)
    region = (getattr(business, "tax_region", "") or "").strip().upper()
    fallback = f"CA-{region}" if region else "CA-GENERAL"

    if kind == "TPP":
        return loc.ship_to or loc.ship_from or fallback
    return loc.customer_location or loc.ship_to or fallback


def _get_us_state_sourcing_rule(state_code: str | None) -> str:
    if not state_code or not state_code.startswith("US-"):
        return TaxJurisdiction.SourcingRule.DESTINATION
    row = (
        TaxJurisdiction.objects.filter(code=state_code, jurisdiction_type=TaxJurisdiction.JurisdictionType.STATE)
        .only("sourcing_rule")
        .first()
    )
    return (row.sourcing_rule if row else TaxJurisdiction.SourcingRule.DESTINATION) or TaxJurisdiction.SourcingRule.DESTINATION


_LOCAL_DISTRICT_HINTS: dict[str, list[str]] = {
    # Example: if a sale is delivered to San Francisco, also include an example district for demonstration/testing.
    "US-CA-SF": ["US-CA-DIST-1"],
}


def _jurisdiction_exists(code: str) -> bool:
    return TaxJurisdiction.objects.filter(code=code).exists()


def resolve_us_jurisdictions_for_invoice(invoice, business) -> list[str]:
    """
    Return a list of jurisdiction codes ordered from broader to narrower, e.g.:

      ["US-CA", "US-CA-SF", "US-CA-DIST-1"]

    Notes:
    - The first element is always the resolved state-level jurisdiction.
    - Local jurisdictions are derived from ship-to (destination) unless:
      - The state is ORIGIN-based and the sale is intrastate (then locals use ship-from).
      - California HYBRID: state uses origin, locals use destination.
    - We only include local codes that exist in TaxJurisdiction (seeded subset); unknown codes are ignored.
    """
    state_code = resolve_us_jurisdiction_for_invoice(invoice, business)
    if not state_code or not state_code.startswith("US-") or state_code.count("-") != 1:
        return [state_code] if state_code else []

    loc = _invoice_location(invoice, country_code="US")
    ship_from_state = loc.ship_from
    ship_to_state = loc.ship_to or loc.customer_location
    intrastate = bool(ship_from_state and ship_to_state and ship_from_state == ship_to_state)

    state_sourcing_rule = _get_us_state_sourcing_rule(state_code)
    if state_sourcing_rule == TaxJurisdiction.SourcingRule.HYBRID and state_code == "US-CA":
        local_source_code = _normalize_code(getattr(invoice, "ship_to_jurisdiction_code", None)) or _normalize_code(
            getattr(invoice, "customer_location_jurisdiction_code", None)
        )
    elif state_sourcing_rule == TaxJurisdiction.SourcingRule.ORIGIN and intrastate:
        local_source_code = _normalize_code(getattr(invoice, "ship_from_jurisdiction_code", None))
    else:
        local_source_code = _normalize_code(getattr(invoice, "ship_to_jurisdiction_code", None)) or _normalize_code(
            getattr(invoice, "customer_location_jurisdiction_code", None)
        )

    locals_out: list[str] = []
    if local_source_code and local_source_code.startswith("US-") and local_source_code.count("-") >= 2:
        # Only include locals that roll up to the chosen state.
        if _rollup_to_state_or_province(local_source_code) == state_code and _jurisdiction_exists(local_source_code):
            locals_out.append(local_source_code)
            for district_code in _LOCAL_DISTRICT_HINTS.get(local_source_code, []):
                if _rollup_to_state_or_province(district_code) == state_code and _jurisdiction_exists(district_code):
                    locals_out.append(district_code)

    # De-dupe while preserving order.
    seen: set[str] = set()
    ordered = []
    for code in [state_code, *locals_out]:
        if code and code not in seen:
            seen.add(code)
            ordered.append(code)
    return ordered


def resolve_us_jurisdiction_for_invoice(invoice, business) -> str:
    """
    US state-level sourcing rules.

    - DESTINATION states: use ship_to (buyer) when available.
    - ORIGIN states: use ship_from (seller) for intrastate transactions; otherwise treat as destination-based (v1).
    - HYBRID (California): v1 returns state-level US-CA; local stacks are deferred.
    """
    loc = _invoice_location(invoice, country_code="US")

    ship_from_state = loc.ship_from
    ship_to_state = loc.ship_to or loc.customer_location

    region = (getattr(business, "tax_region", "") or "").strip().upper()
    business_state = _clamp_country(f"US-{region}" if region else None, country_code="US")

    candidate_state = ship_to_state or ship_from_state or business_state or "US-GENERAL"
    sourcing_rule = _get_us_state_sourcing_rule(candidate_state)

    if sourcing_rule == TaxJurisdiction.SourcingRule.ORIGIN:
        if ship_from_state and ship_to_state and ship_from_state == ship_to_state:
            return ship_from_state
        if ship_from_state and not ship_to_state:
            return ship_from_state
        return ship_to_state or ship_from_state or business_state or candidate_state

    if sourcing_rule == TaxJurisdiction.SourcingRule.HYBRID:
        if ship_to_state == "US-CA":
            return "US-CA"
        return ship_to_state or ship_from_state or business_state or candidate_state

    # DESTINATION
    return ship_to_state or ship_from_state or business_state or candidate_state


def resolve_tax_jurisdiction_for_invoice(invoice, business) -> str:
    """
    Return a canonical jurisdiction code like "CA-ON" or "US-CA" for invoice-level sourcing.
    """
    country = (_normalize_code(getattr(business, "tax_country", None)) or "CA").upper()
    if country == "US":
        return resolve_us_jurisdiction_for_invoice(invoice, business)
    return resolve_ca_jurisdiction_for_invoice(invoice, business)
