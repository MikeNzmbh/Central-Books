from collections import defaultdict
from datetime import date as date_cls
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Iterable, List, Optional

from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction

from .models import TaxGroup, TaxRate, TransactionLineTaxDetail
from .sourcing import resolve_tax_jurisdiction_for_invoice, resolve_us_jurisdictions_for_invoice


@dataclass
class TaxComponentResult:
    tax_component_id: str
    tax_group_id: str
    amount_txn_currency: Decimal
    amount_home_currency_cad: Decimal
    taxable_base_txn_currency: Decimal
    taxable_base_home_currency_cad: Decimal
    rate_used: Decimal
    is_recoverable: bool
    jurisdiction_code: Optional[str]


def _q_cent(value: Decimal) -> Decimal:
    return (value or Decimal("0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


def _convert_to_home(amount: Decimal, currency: str, fx_rate: Optional[Decimal]) -> Decimal:
    if currency.upper() == "CAD":
        return _q_cent(amount)
    if fx_rate is None:
        raise ValueError("fx_rate is required when converting non-CAD amounts.")
    return _q_cent(amount * fx_rate)


def _get_applicable_rate(component, txn_date, product_category) -> Optional[TaxRate]:
    return (
        TaxRate.objects.filter(
            component=component,
            product_category=product_category,
            effective_from__lte=txn_date,
        )
        .filter(
            models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=txn_date)
        )
        .order_by("-effective_from")
        .first()
    )


def _resolve_jurisdiction_code(component, tax_group=None, business=None) -> Optional[str]:
    """
    Resolve a canonical jurisdiction code for the tax component/group.
    Preference:
    1. Explicit component.jurisdiction.code
    2. Tax group display name prefix (e.g., CA-ON)
    3. Component authority field
    4. Business tax_country/tax_region fallback
    """
    if component and getattr(component, "jurisdiction", None):
        code = getattr(component.jurisdiction, "code", None)
        if code:
            return code
    if tax_group and getattr(tax_group, "display_name", None):
        display_prefix = (tax_group.display_name or "").split(" ")[0]
        if "-" in display_prefix:
            return display_prefix
    authority = getattr(component, "authority", None)
    if authority:
        code = authority
    else:
        code = None
    if code in {"CRA", "RQ"}:
        country = (getattr(business, "tax_country", None) or "CA").upper()
        region = (getattr(business, "tax_region", "") or "").upper()
        if region:
            return f"{country}-{region}"
        return f"{country}-GENERAL"
    if code:
        return code
    country = (getattr(business, "tax_country", None) or "CA").upper()
    region = (getattr(business, "tax_region", "") or "").upper()
    if region:
        return f"{country}-{region}"
    return f"{country}-GENERAL"


class TaxEngine:
    @staticmethod
    @transaction.atomic
    def calculate_for_line(
        business,
        transaction_line,
        tax_group: TaxGroup,
        txn_date,
        currency: str,
        fx_rate: Optional[Decimal] = None,
        product_category: Optional[str] = None,
        amount_override: Optional[Decimal] = None,
        tax_treatment: Optional[str] = None,
        persist: bool = True,
    ) -> dict:
        """
        Calculate tax for a line and persist TransactionLineTaxDetail rows.

        - business: Business instance
        - transaction_line: model or object with `net_amount` and optional `product_category`
        - tax_group: TaxGroup selected on the line
        - txn_date: date used for effective rate lookup
        - currency: transaction currency code
        - fx_rate: Decimal FX rate to CAD when currency != CAD
        - product_category: optional override; defaults to "STANDARD"
        """
        if tax_group.business_id != getattr(business, "id", None):
            raise ValueError("Tax group does not belong to the provided business.")

        raw_amount = amount_override if amount_override is not None else getattr(transaction_line, "net_amount", None)
        if raw_amount is None:
            raise ValueError("transaction_line must expose net_amount (or pass amount_override).")

        product_category = product_category or getattr(
            transaction_line, "product_category", "STANDARD"
        )
        currency = currency.upper()
        treatment = (tax_treatment or getattr(tax_group, "tax_treatment", None) or TaxGroup.TaxTreatment.ON_TOP).upper()
        if treatment not in {TaxGroup.TaxTreatment.ON_TOP, TaxGroup.TaxTreatment.INCLUDED}:
            raise ValueError("Unsupported tax treatment for tax group.")

        details: List[TransactionLineTaxDetail] = []
        results: List[TaxComponentResult] = []
        accumulated_tax = Decimal("0.00")

        ct = None
        obj_id = None
        document_side = ""
        if persist and hasattr(transaction_line, "_meta") and getattr(transaction_line, "pk", None):
            ct = ContentType.objects.get_for_model(transaction_line)
            obj_id = transaction_line.pk
            try:
                model_name = (transaction_line._meta.model_name or "").lower()
                if model_name == "invoice":
                    document_side = TransactionLineTaxDetail.DocumentSide.SALE
                elif model_name == "expense":
                    document_side = TransactionLineTaxDetail.DocumentSide.PURCHASE
            except Exception:
                document_side = ""

        invoice_jurisdiction_code: Optional[str] = None
        invoice_jurisdictions: list[str] = []
        try:
            if transaction_line and getattr(transaction_line, "_meta", None) and transaction_line._meta.model_name == "invoice":
                invoice_jurisdiction_code = resolve_tax_jurisdiction_for_invoice(transaction_line, business)
                if invoice_jurisdiction_code and invoice_jurisdiction_code.startswith("US-"):
                    invoice_jurisdictions = resolve_us_jurisdictions_for_invoice(transaction_line, business)
                elif invoice_jurisdiction_code:
                    invoice_jurisdictions = [invoice_jurisdiction_code]
        except Exception:
            invoice_jurisdiction_code = None
            invoice_jurisdictions = []

        group_components = tax_group.group_components.select_related("component").all()
        rate_rows: list[dict] = []
        for gc in group_components:
            component = gc.component
            rate_row = _get_applicable_rate(component, txn_date, product_category)
            rate_to_use = rate_row.rate_decimal if rate_row else component.rate_percentage
            if rate_to_use is None:
                continue
            rate_rows.append({"component": component, "rate_to_use": rate_to_use})

        input_amount = Decimal(str(raw_amount))
        gross_amount = None
        base_amount = None
        if treatment == TaxGroup.TaxTreatment.INCLUDED:
            gross_amount = _q_cent(input_amount)
            factor = Decimal("1.00")
            if tax_group.calculation_method == TaxGroup.CalculationMethod.SIMPLE:
                total_rate = sum((row["rate_to_use"] for row in rate_rows), Decimal("0.00"))
                factor = Decimal("1.00") + total_rate
            else:
                for row in rate_rows:
                    factor *= (Decimal("1.00") + row["rate_to_use"])
            base_amount = gross_amount if factor == 0 else _q_cent(gross_amount / factor)
        else:
            base_amount = _q_cent(input_amount)
            gross_amount = None

        computed_rows: list[dict] = []
        expected_total_unrounded = Decimal("0.00")

        for component_index, row in enumerate(rate_rows):
            component = row["component"]
            rate_to_use = row["rate_to_use"]
            calc_base = base_amount
            if tax_group.calculation_method == TaxGroup.CalculationMethod.COMPOUND:
                calc_base = base_amount + accumulated_tax

            unrounded_tax = calc_base * rate_to_use
            tax_value_txn = _q_cent(unrounded_tax)
            expected_total_unrounded += unrounded_tax
            accumulated_tax += tax_value_txn

            taxable_home = _convert_to_home(calc_base, currency, fx_rate)
            tax_home = _convert_to_home(tax_value_txn, currency, fx_rate)

            jurisdiction_code = None
            if component and getattr(component, "jurisdiction", None):
                jurisdiction_code = getattr(component.jurisdiction, "code", None)
            if not jurisdiction_code and invoice_jurisdictions:
                # US local stacks:
                # - First component -> state-level jurisdiction
                # - Subsequent components -> subsequent local jurisdictions (if present), clamped to last
                # This is deterministic and relies on TaxGroupComponent.calculation_order.
                idx = min(component_index, len(invoice_jurisdictions) - 1)
                jurisdiction_code = invoice_jurisdictions[idx]
            if not jurisdiction_code and invoice_jurisdiction_code:
                jurisdiction_code = invoice_jurisdiction_code
            if not jurisdiction_code:
                jurisdiction_code = _jurisdiction_code_for_business(business)

            computed_rows.append(
                {
                    "component": component,
                    "rate_to_use": rate_to_use,
                    "calc_base": calc_base,
                    "tax_value_txn": tax_value_txn,
                    "taxable_home": taxable_home,
                    "tax_home": tax_home,
                    "jurisdiction_code": jurisdiction_code or "",
                }
            )

        # Dust-sweeper reconciliation:
        # If per-component rounding causes a 1¢ discrepancy vs the expected total, adjust the final component.
        if treatment == TaxGroup.TaxTreatment.INCLUDED:
            expected_total = _q_cent(gross_amount - base_amount)
        else:
            expected_total = _q_cent(expected_total_unrounded)
        actual_total = sum((row["tax_value_txn"] for row in computed_rows), Decimal("0.00"))
        diff = expected_total - actual_total
        if computed_rows and diff != 0 and diff.copy_abs() <= Decimal("0.01"):
            last = computed_rows[-1]
            adjusted = last["tax_value_txn"] + diff
            last["tax_value_txn"] = adjusted
            last["tax_home"] = _convert_to_home(adjusted, currency, fx_rate)

        for row in computed_rows:
            component = row["component"]
            tax_value_txn = row["tax_value_txn"]
            taxable_home = row["taxable_home"]
            tax_home = row["tax_home"]

            detail = None
            if persist and ct and obj_id:
                detail = TransactionLineTaxDetail.objects.create(
                    business=business,
                    tax_group=tax_group,
                    tax_component=component,
                    jurisdiction_code=row["jurisdiction_code"],
                    transaction_line_content_type=ct,
                    transaction_line_object_id=obj_id,
                    transaction_date=txn_date,
                    document_side=document_side,
                    taxable_amount_txn_currency=row["calc_base"],
                    taxable_amount_home_currency_cad=taxable_home,
                    tax_amount_txn_currency=tax_value_txn,
                    tax_amount_home_currency_cad=tax_home,
                    is_recoverable=component.is_recoverable,
                )
            if detail:
                details.append(detail)

            results.append(
                TaxComponentResult(
                    tax_component_id=str(component.id),
                    tax_group_id=str(tax_group.id),
                    amount_txn_currency=tax_value_txn,
                    amount_home_currency_cad=tax_home,
                    taxable_base_txn_currency=row["calc_base"],
                    taxable_base_home_currency_cad=taxable_home,
                    rate_used=row["rate_to_use"],
                    is_recoverable=component.is_recoverable,
                    jurisdiction_code=row["jurisdiction_code"],
                )
            )

        total_tax_txn = sum((r.amount_txn_currency for r in results), Decimal("0.00"))
        total_tax_home = sum((r.amount_home_currency_cad for r in results), Decimal("0.00"))
        gross_txn = gross_amount if treatment == TaxGroup.TaxTreatment.INCLUDED else _q_cent(base_amount + total_tax_txn)
        return {
            "details": details,
            "components": results,
            "total_tax_txn_currency": total_tax_txn,
            "total_tax_home_currency_cad": total_tax_home,
            "net_amount_txn_currency": base_amount,
            "gross_amount_txn_currency": gross_txn,
            "tax_treatment": treatment,
        }


# ---------------------------------------------------------------------------
# Deterministic Tax Engine v1 (period snapshots + anomalies)
# ---------------------------------------------------------------------------

import calendar  # noqa: E402

from core.models import Invoice, Expense  # noqa: E402
from taxes.models import TaxPeriodSnapshot, TaxAnomaly, TaxProductRule, TaxJurisdiction  # noqa: E402
from django.utils import timezone  # noqa: E402


def _period_range_from_key(period_key: str):
    """
    Resolve period_key (e.g., 2025Q2 or 2025-04) into (start_date, end_date).
    Defaults to monthly if format not recognized.
    """
    if not period_key:
        today = timezone.localdate()
        return today.replace(day=1), today
    try:
        if "Q" in period_key:
            year = int(period_key[:4])
            quarter = int(period_key.split("Q")[1])
            start_month = (quarter - 1) * 3 + 1
            start = timezone.datetime(year, start_month, 1).date()
            end_month = start_month + 2
            last_day = calendar.monthrange(year, end_month)[1]
            end = timezone.datetime(year, end_month, last_day).date()
            return start, end
        if "-" in period_key:
            year, month = period_key.split("-")
            year = int(year)
            month = int(month)
            start = timezone.datetime(year, month, 1).date()
            last_day = calendar.monthrange(year, month)[1]
            end = timezone.datetime(year, month, last_day).date()
            return start, end
    except Exception:
        pass
    today = timezone.localdate()
    return today.replace(day=1), today


def compute_tax_due_date(business, period_key: str) -> date_cls:
    """
    Compute filing due date for a business + period based on frequency and configured due day.
    Current rule: due day of the month following the period end.
    """
    _, end_date = _period_range_from_key(period_key)
    due_day = getattr(business, "tax_filing_due_day", 30) or 30
    due_month = end_date.month + 1
    due_year = end_date.year
    if due_month > 12:
        due_month = 1
        due_year += 1
    last_day = calendar.monthrange(due_year, due_month)[1]
    due_day = min(due_day, last_day)
    return date_cls(due_year, due_month, due_day)


def _jurisdiction_code_for_business(business):
    country = getattr(business, "tax_country", None) or getattr(business, "country", None) or "CA"
    region = getattr(business, "tax_region", "") or ""
    country = country.upper()
    region = region.upper()
    if region:
        return f"{country}-{region}"
    return f"{country}-GENERAL"


def _aggregate_from_tax_details(business, start_date, end_date, currency):
    """
    Use TransactionLineTaxDetail rows to aggregate by jurisdiction.
    """
    summary: dict[str, dict] = {}
    details_qs = (
        TransactionLineTaxDetail.objects.filter(
            business=business,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
        )
        .select_related("tax_component__jurisdiction", "tax_group")
        .all()
    )
    for detail in details_qs:
        component = getattr(detail, "tax_component", None)
        tax_group = getattr(detail, "tax_group", None)
        reporting_category = getattr(tax_group, "reporting_category", None) or TaxGroup.ReportingCategory.TAXABLE
        is_out_of_scope = reporting_category == TaxGroup.ReportingCategory.OUT_OF_SCOPE
        jurisdiction_code = detail.jurisdiction_code or _resolve_jurisdiction_code(
            component, tax_group, business
        )
        jurisdiction_code = jurisdiction_code or _jurisdiction_code_for_business(business)

        entry = summary.setdefault(
            jurisdiction_code,
            {
                "taxable_sales": Decimal("0.00"),
                "taxable_purchases": Decimal("0.00"),
                "tax_collected": Decimal("0.00"),
                "tax_on_purchases": Decimal("0.00"),
                "currency": currency,
                "source": "tax_details",
            },
        )
        taxable_amount = detail.taxable_amount_txn_currency or Decimal("0.00")
        tax_amount = detail.tax_amount_txn_currency or Decimal("0.00")
        ct = getattr(detail, "transaction_line_content_type", None)
        model_class = ct.model_class() if ct else None
        is_purchase = False
        side = (getattr(detail, "document_side", "") or "").upper()
        if side == TransactionLineTaxDetail.DocumentSide.PURCHASE:
            is_purchase = True
        elif side == TransactionLineTaxDetail.DocumentSide.SALE:
            is_purchase = False
        else:
            if model_class:
                try:
                    if issubclass(model_class, Expense):
                        is_purchase = True
                    elif issubclass(model_class, Invoice):
                        is_purchase = False
                except Exception:
                    is_purchase = detail.is_recoverable
            else:
                is_purchase = detail.is_recoverable

        if is_purchase:
            if not is_out_of_scope:
                entry["taxable_purchases"] += taxable_amount
            if detail.is_recoverable:
                entry["tax_on_purchases"] += tax_amount
        else:
            if not is_out_of_scope:
                entry["taxable_sales"] += taxable_amount
            entry["tax_collected"] += tax_amount

    for entry in summary.values():
        entry["net_tax"] = entry["tax_collected"] - entry["tax_on_purchases"]
    return summary


def _fallback_summary_from_documents(business, start_date, end_date, currency):
    """
    Fallback aggregation when tax detail rows are not available.
    """
    invoices = Invoice.objects.filter(business=business, issue_date__gte=start_date, issue_date__lte=end_date)
    expenses = Expense.objects.filter(business=business, date__gte=start_date, date__lte=end_date)

    summary: dict[str, dict] = {}

    def _get_entry(code: str):
        return summary.setdefault(
            code,
            {
                "taxable_sales": Decimal("0.00"),
                "taxable_purchases": Decimal("0.00"),
                "tax_collected": Decimal("0.00"),
                "tax_on_purchases": Decimal("0.00"),
                "currency": currency,
                "source": "fallback_totals",
            },
        )

    default_code = _jurisdiction_code_for_business(business)
    for inv in invoices:
        try:
            code = resolve_tax_jurisdiction_for_invoice(inv, business)
        except Exception:
            code = None
        entry = _get_entry(code or default_code)
        entry["taxable_sales"] += inv.net_total or Decimal("0.00")
        entry["tax_collected"] += inv.tax_total or inv.tax_amount or Decimal("0.00")

    for exp in expenses:
        entry = _get_entry(default_code)
        entry["taxable_purchases"] += exp.net_total or exp.amount or Decimal("0.00")
        entry["tax_on_purchases"] += exp.tax_total or exp.tax_amount or Decimal("0.00")

    for entry in summary.values():
        entry["net_tax"] = entry["tax_collected"] - entry["tax_on_purchases"]

    return summary


def _country_from_code(jurisdiction_code: str, default_country: str) -> str:
    if not jurisdiction_code:
        return default_country.upper()
    return (jurisdiction_code.split("-")[0] or default_country).upper()


def _build_line_mappings(summary: dict[str, dict], default_country: str):
    country_totals: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {
            "taxable_sales": Decimal("0.00"),
            "tax_collected": Decimal("0.00"),
            "tax_on_purchases": Decimal("0.00"),
            "net_tax": Decimal("0.00"),
        }
    )
    # GST/HST filing totals (CRA GST34-style): include federal CA + HST provinces only.
    ca_gst_totals: dict[str, Decimal] = {
        "taxable_sales": Decimal("0.00"),
        "tax_collected": Decimal("0.00"),
        "tax_on_purchases": Decimal("0.00"),
        "net_tax": Decimal("0.00"),
    }
    hst_codes = {"CA-ON", "CA-NB", "CA-NL", "CA-NS", "CA-PE"}
    qc_totals: dict[str, Decimal] = {
        "tax_collected": Decimal("0.00"),
        "itrs": Decimal("0.00"),
        "net_tax": Decimal("0.00"),
    }
    # US filing totals: avoid double counting taxable sales across stacked local jurisdictions
    # by summing only top-level state entries (US-CA, US-NY, ...).
    us_state_taxable_sales = Decimal("0.00")
    us_local_totals: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {
            "tax_collected": Decimal("0.00"),
            "tax_on_purchases": Decimal("0.00"),
            "net_tax": Decimal("0.00"),
        }
    )
    for jurisdiction_code, data in summary.items():
        country = _country_from_code(jurisdiction_code, default_country)
        country_entry = country_totals[country]
        country_entry["taxable_sales"] += Decimal(str(data.get("taxable_sales", 0)))
        country_entry["tax_collected"] += Decimal(str(data.get("tax_collected", 0)))
        country_entry["tax_on_purchases"] += Decimal(str(data.get("tax_on_purchases", 0)))
        country_entry["net_tax"] += Decimal(str(data.get("net_tax", 0)))
        if jurisdiction_code == "CA" or jurisdiction_code in hst_codes:
            ca_gst_totals["taxable_sales"] += Decimal(str(data.get("taxable_sales", 0)))
            ca_gst_totals["tax_collected"] += Decimal(str(data.get("tax_collected", 0)))
            ca_gst_totals["tax_on_purchases"] += Decimal(str(data.get("tax_on_purchases", 0)))
            ca_gst_totals["net_tax"] += Decimal(str(data.get("net_tax", 0)))
        if jurisdiction_code.startswith("CA-QC"):
            qc_totals["tax_collected"] += Decimal(str(data.get("tax_collected", 0)))
            qc_totals["itrs"] += Decimal(str(data.get("tax_on_purchases", 0)))
            qc_totals["net_tax"] += Decimal(str(data.get("net_tax", 0)))
        if jurisdiction_code.startswith("US-") and jurisdiction_code.count("-") == 1:
            us_state_taxable_sales += Decimal(str(data.get("taxable_sales", 0)))
        if jurisdiction_code.startswith("US-") and jurisdiction_code.count("-") >= 2:
            entry = us_local_totals[jurisdiction_code]
            entry["tax_collected"] += Decimal(str(data.get("tax_collected", 0)))
            entry["tax_on_purchases"] += Decimal(str(data.get("tax_on_purchases", 0)))
            entry["net_tax"] += Decimal(str(data.get("net_tax", 0)))

    line_mappings: dict[str, dict] = {}
    for country, data in country_totals.items():
        if country == "CA":
            line_mappings[country] = {
                "line_101": float(ca_gst_totals["taxable_sales"]),
                "line_103": float(ca_gst_totals["tax_collected"]),
                "line_105": float(ca_gst_totals["tax_collected"]),
                "line_108": float(ca_gst_totals["tax_on_purchases"]),
                "line_109": float(ca_gst_totals["net_tax"]),
                "line_104": float(ca_gst_totals["net_tax"]),
            }
        elif country == "US":
            taxable_sales = us_state_taxable_sales or data["taxable_sales"]
            line_mappings[country] = {
                "gross_sales": float(taxable_sales),
                "taxable_sales": float(taxable_sales),
                "tax_collected": float(data["tax_collected"]),
                "tax_on_purchases": float(data["tax_on_purchases"]),
                "net_tax": float(data["net_tax"]),
            }
            locals_payload: dict[str, dict] = {}
            for local_code, local_data in us_local_totals.items():
                if local_data["tax_collected"] == 0 and local_data["tax_on_purchases"] == 0:
                    continue
                locals_payload[local_code] = {
                    "tax_collected": float(local_data["tax_collected"]),
                    "tax_on_purchases": float(local_data["tax_on_purchases"]),
                    "net_tax": float(local_data["net_tax"]),
                }
            if locals_payload:
                line_mappings[country]["locals"] = locals_payload
    if qc_totals["tax_collected"] or qc_totals["itrs"]:
        line_mappings["CA_QC"] = {
            "line_205": float(qc_totals["tax_collected"]),
            "line_206": float(qc_totals["itrs"]),
            "line_209": float(qc_totals["net_tax"]),
        }
    return line_mappings


def _current_tax_period_key() -> str:
    today = timezone.localdate()
    return f"{today.year}-{today.month:02d}"


def _product_code_for_detail(detail) -> str:
    txn_line = getattr(detail, "transaction_line", None)
    if txn_line:
        if hasattr(txn_line, "product_code"):
            return getattr(txn_line, "product_code") or "GENERAL"
        if hasattr(txn_line, "product_category"):
            return getattr(txn_line, "product_category") or "GENERAL"
    return "GENERAL"


def _us_state_code_from_jurisdiction_code(jurisdiction_code: str) -> str | None:
    if not jurisdiction_code:
        return None
    parts = jurisdiction_code.split("-")
    if len(parts) < 2:
        return None
    if parts[0].upper() != "US":
        return None
    state = parts[1].upper()
    if len(state) != 2 or not state.isalpha():
        return None
    return f"US-{state}"


def _build_us_ser_states(business, start_date, end_date, summary_by_jurisdiction: dict[str, dict]) -> dict[str, dict]:
    """
    Build a deterministic per-state SER-friendly breakdown for US activity.

    - Base amounts are computed per invoice (one Invoice per tax detail "line" in this app),
      avoiding local stack double-counting by taking the minimum taxable base across
      the invoice's component detail rows.
    - Exempt sales are determined by TaxProductRule for (state jurisdiction, product_code),
      using rules with rule_type in (EXEMPT, ZERO_RATED) valid on the invoice date.
    """
    invoice_ct = ContentType.objects.get_for_model(Invoice)
    invoice_details = (
        TransactionLineTaxDetail.objects.filter(
            business=business,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
            transaction_line_content_type=invoice_ct,
        )
        .select_related("tax_group")
        .only(
            "transaction_line_object_id",
            "jurisdiction_code",
            "transaction_date",
            "taxable_amount_txn_currency",
            "tax_group__reporting_category",
        )
        .order_by()
    )

    invoice_ctx: dict[int, dict] = {}
    for d in invoice_details:
        tax_group = getattr(d, "tax_group", None)
        reporting_category = getattr(tax_group, "reporting_category", None) or TaxGroup.ReportingCategory.TAXABLE
        if reporting_category == TaxGroup.ReportingCategory.OUT_OF_SCOPE:
            continue

        invoice_id = d.transaction_line_object_id
        if not invoice_id:
            continue
        state_code = _us_state_code_from_jurisdiction_code(d.jurisdiction_code or "")
        if not state_code:
            continue
        ctx = invoice_ctx.setdefault(
            invoice_id,
            {"state_code": None, "base": None, "txn_date": None},
        )
        if ctx["txn_date"] is None and d.transaction_date:
            ctx["txn_date"] = d.transaction_date
        base = d.taxable_amount_txn_currency or Decimal("0.00")
        if ctx["base"] is None:
            ctx["base"] = base
        else:
            ctx["base"] = min(ctx["base"], base)
        # Prefer an explicit state-level jurisdiction code when present.
        if d.jurisdiction_code and d.jurisdiction_code.count("-") == 1:
            ctx["state_code"] = d.jurisdiction_code
        elif ctx["state_code"] is None:
            ctx["state_code"] = state_code

    if not invoice_ctx:
        return {}

    invoices_by_id = Invoice.objects.select_related("item").in_bulk(invoice_ctx.keys())
    state_codes = {ctx["state_code"] for ctx in invoice_ctx.values() if ctx.get("state_code")}
    product_codes = {
        (inv.product_code if inv else "GENERAL")
        for inv in invoices_by_id.values()
    }

    exempt_rules_by_key: dict[tuple[str, str], list[TaxProductRule]] = defaultdict(list)
    if state_codes and product_codes:
        rules_qs = (
            TaxProductRule.objects.select_related("jurisdiction")
            .filter(
                jurisdiction__code__in=state_codes,
                product_code__in=product_codes,
                rule_type__in=[TaxProductRule.RuleType.EXEMPT, TaxProductRule.RuleType.ZERO_RATED],
                valid_from__lte=end_date,
            )
            .filter(models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=start_date))
            .order_by("jurisdiction__code", "product_code", "-valid_from")
        )
        for rule in rules_qs:
            exempt_rules_by_key[(rule.jurisdiction.code, rule.product_code)].append(rule)

    def _is_exempt(*, state_code: str, product_code: str, txn_date: date_cls) -> bool:
        rules = exempt_rules_by_key.get((state_code, product_code)) or []
        for rule in rules:
            if rule.valid_from <= txn_date and (rule.valid_to is None or rule.valid_to >= txn_date):
                return True
        return False

    totals: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {
            "gross_sales": Decimal("0.00"),
            "exempt_sales": Decimal("0.00"),
            "taxable_sales": Decimal("0.00"),
            "tax_collected": Decimal("0.00"),
            "tax_on_purchases": Decimal("0.00"),
            "net_tax": Decimal("0.00"),
        }
    )

    for invoice_id, ctx in invoice_ctx.items():
        inv = invoices_by_id.get(invoice_id)
        if not inv:
            continue
        state_code = ctx.get("state_code")
        if not state_code:
            continue
        base = ctx.get("base") or Decimal("0.00")
        txn_date = ctx.get("txn_date") or getattr(inv, "issue_date", None) or start_date
        product_code = getattr(inv, "product_code", None) or "GENERAL"

        entry = totals[state_code]
        entry["gross_sales"] += base
        if _is_exempt(state_code=state_code, product_code=product_code, txn_date=txn_date):
            entry["exempt_sales"] += base
        else:
            entry["taxable_sales"] += base

    # Taxes by state: roll up state + locals without re-counting taxable base.
    for jurisdiction_code, data in (summary_by_jurisdiction or {}).items():
        state_code = _us_state_code_from_jurisdiction_code(jurisdiction_code)
        if not state_code:
            continue
        entry = totals[state_code]
        entry["tax_collected"] += Decimal(str(data.get("tax_collected", 0)))
        entry["tax_on_purchases"] += Decimal(str(data.get("tax_on_purchases", 0)))
        entry["net_tax"] = entry["tax_collected"] - entry["tax_on_purchases"]

    payload: dict[str, dict] = {}
    for state_code, data in totals.items():
        if data["gross_sales"] == 0 and data["tax_collected"] == 0 and data["tax_on_purchases"] == 0:
            continue
        payload[state_code] = {
            "gross_sales": float(data["gross_sales"]),
            "exempt_sales": float(data["exempt_sales"]),
            "taxable_sales": float(data["taxable_sales"]),
            "tax_collected": float(data["tax_collected"]),
            "tax_on_purchases": float(data["tax_on_purchases"]),
            "net_tax": float(data["net_tax"]),
        }
    return payload


def compute_tax_period_snapshot(business, period_key: str) -> TaxPeriodSnapshot:
    """
    Deterministically compute or update TaxPeriodSnapshot for the given business and period.
    Aggregates invoices/expenses in the period and stores summary_by_jurisdiction + line mappings.
    """
    start_date, end_date = _period_range_from_key(period_key)
    currency = getattr(business, "currency", None) or "USD"
    country = getattr(business, "tax_country", None) or "CA"

    summary_by_jurisdiction = _aggregate_from_tax_details(business, start_date, end_date, currency)
    if not summary_by_jurisdiction:
        summary_by_jurisdiction = _fallback_summary_from_documents(business, start_date, end_date, currency)

    summary_for_storage: dict[str, dict] = {}
    for code, data in summary_by_jurisdiction.items():
        summary_for_storage[code] = {
            "taxable_sales": float(data.get("taxable_sales", 0)),
            "taxable_purchases": float(data.get("taxable_purchases", 0)),
            "tax_collected": float(data.get("tax_collected", 0)),
            "tax_on_purchases": float(data.get("tax_on_purchases", 0)),
            "net_tax": float(data.get("net_tax", 0)),
            "currency": data.get("currency", currency),
            "source": data.get("source", "fallback_totals"),
        }

    line_mappings = _build_line_mappings(summary_by_jurisdiction, country)
    # Optional: include SER-friendly per-state breakdown for US data.
    if "US" in line_mappings:
        try:
            us_states = _build_us_ser_states(business, start_date, end_date, summary_by_jurisdiction)
        except Exception:
            us_states = {}
        if us_states:
            line_mappings.setdefault("US", {})["states"] = us_states

    snapshot, _ = TaxPeriodSnapshot.objects.update_or_create(
        business=business,
        period_key=period_key,
        defaults={
            "country": country.upper(),
            "status": TaxPeriodSnapshot.SnapshotStatus.COMPUTED,
            "summary_by_jurisdiction": summary_for_storage,
            "line_mappings": line_mappings,
        },
    )
    return snapshot


def compute_tax_anomalies(business, period_key: str) -> List[TaxAnomaly]:
    """
    Run deterministic anomaly checks for the given business + period.
    """
    start_date, end_date = _period_range_from_key(period_key)
    snapshot = (
        TaxPeriodSnapshot.objects.filter(business=business, period_key=period_key).first()
        or compute_tax_period_snapshot(business, period_key)
    )

    anomalies: list[TaxAnomaly] = []
    summary = snapshot.summary_by_jurisdiction or {}
    for data in summary.values():
        tax_collected = Decimal(str(data.get("tax_collected", 0)))
        tax_on_purchases = Decimal(str(data.get("tax_on_purchases", 0)))
        net = tax_collected - tax_on_purchases
        if net < Decimal("0.00") - Decimal("0.01"):
            anomaly, _ = TaxAnomaly.objects.update_or_create(
                business=business,
                period_key=period_key,
                code="T6_NEGATIVE_BALANCE",
                defaults={
                    "severity": TaxAnomaly.AnomalySeverity.HIGH,
                    "status": TaxAnomaly.AnomalyStatus.OPEN,
                    "description": f"Net tax is negative ({net}) for period {period_key}.",
                    "task_code": "T2",
                },
            )
            anomalies.append(anomaly)
        # Missing tax for registered businesses with taxable sales but no tax collected.
        taxable_sales = Decimal(str(data.get("taxable_sales", 0)))
        if getattr(business, "is_tax_registered", False) and taxable_sales > Decimal("0.00") and tax_collected <= Decimal("0.01"):
            anomaly, _ = TaxAnomaly.objects.update_or_create(
                business=business,
                period_key=period_key,
                code="T3_MISSING_TAX",
                defaults={
                    "severity": TaxAnomaly.AnomalySeverity.MEDIUM,
                    "status": TaxAnomaly.AnomalyStatus.OPEN,
                    "description": f"Registered business with taxable sales {taxable_sales} but no tax collected in {period_key}.",
                    "task_code": "T1",
                },
            )
            anomalies.append(anomaly)
    # Rate mismatch: compare expected tax against detail amount beyond tolerance.
    tolerance = Decimal("0.01")
    detail_qs = TransactionLineTaxDetail.objects.filter(
        business=business,
        transaction_date__gte=start_date,
        transaction_date__lte=end_date,
    ).select_related("tax_component")

    # Document-level checks (rounding + missing components).
    doc_tax_totals: dict[tuple, Decimal] = defaultdict(lambda: Decimal("0.00"))
    doc_detail_counts: dict[tuple, int] = defaultdict(int)
    doc_ct_map: dict[tuple, ContentType | None] = {}
    for detail in detail_qs:
        if detail.transaction_line_content_type_id and detail.transaction_line_object_id:
            key = (detail.transaction_line_content_type_id, detail.transaction_line_object_id)
            doc_tax_totals[key] += detail.tax_amount_txn_currency or Decimal("0.00")
            doc_detail_counts[key] += 1
            doc_ct_map[key] = detail.transaction_line_content_type

    from types import SimpleNamespace

    currency = getattr(business, "currency", None) or "CAD"
    fx_rate = Decimal("1.00")

    for key, detail_tax_sum in doc_tax_totals.items():
        ct = doc_ct_map.get(key)
        obj_id = key[1]
        model_class = ct.model_class() if ct else None
        if not model_class:
            continue
        try:
            if not (issubclass(model_class, Invoice) or issubclass(model_class, Expense)):
                continue
        except Exception:
            continue
        try:
            doc = ct.get_object_for_this_type(pk=obj_id) if ct else None
        except Exception:
            doc = None
        if not doc:
            continue
        if not getattr(doc, "tax_group_id", None):
            continue
        base_amount = getattr(doc, "subtotal", None) or getattr(doc, "net_total", None) or getattr(doc, "amount", None) or Decimal("0.00")
        amount_for_engine = base_amount
        try:
            if getattr(doc.tax_group, "tax_treatment", None) == TaxGroup.TaxTreatment.INCLUDED:
                amount_for_engine = getattr(doc, "grand_total", None) or getattr(doc, "total_amount", None) or base_amount
        except Exception:
            pass
        expected_total = TaxEngine.calculate_for_line(
            business=business,
            transaction_line=SimpleNamespace(net_amount=Decimal(str(amount_for_engine))),
            tax_group=doc.tax_group,
            txn_date=getattr(doc, "issue_date", None) or getattr(doc, "date", None) or start_date,
            currency=currency,
            fx_rate=fx_rate,
            persist=False,
        )["total_tax_txn_currency"]
        diff = (expected_total - detail_tax_sum).copy_abs()
        if diff > tolerance:
            anomaly, _ = TaxAnomaly.objects.update_or_create(
                business=business,
                period_key=period_key,
                code="T4_ROUNDING_ANOMALY",
                linked_transaction_ct=ct,
                linked_transaction_id=obj_id,
                defaults={
                    "severity": TaxAnomaly.AnomalySeverity.MEDIUM,
                    "status": TaxAnomaly.AnomalyStatus.OPEN,
                    "description": (
                        f"Tax rounding mismatch of {diff} on document {obj_id}. "
                        f"Expected {expected_total} vs actual {detail_tax_sum}."
                    ),
                    "task_code": "T3",
                },
            )
            anomalies.append(anomaly)

    invoice_ct = ContentType.objects.get_for_model(Invoice)
    expense_ct = ContentType.objects.get_for_model(Expense)
    for invoice in Invoice.objects.filter(
        business=business,
        issue_date__gte=start_date,
        issue_date__lte=end_date,
        tax_group__isnull=False,
    ).select_related("tax_group"):
        expected_components = invoice.tax_group.group_components.count()
        actual = doc_detail_counts.get((invoice_ct.id, invoice.id), 0)
        if expected_components and actual < expected_components:
            anomaly, _ = TaxAnomaly.objects.update_or_create(
                business=business,
                period_key=period_key,
                code="T3_MISSING_COMPONENT",
                linked_transaction_ct=invoice_ct,
                linked_transaction_id=invoice.id,
                defaults={
                    "severity": TaxAnomaly.AnomalySeverity.MEDIUM,
                    "status": TaxAnomaly.AnomalyStatus.OPEN,
                    "description": (
                        f"Invoice {invoice.invoice_number} has tax group {invoice.tax_group.display_name} "
                        f"with {expected_components} components, but only {actual} tax details were recorded."
                    ),
                    "task_code": "T1",
                },
            )
            anomalies.append(anomaly)

    for expense in Expense.objects.filter(
        business=business,
        date__gte=start_date,
        date__lte=end_date,
        tax_group__isnull=False,
    ).select_related("tax_group"):
        expected_components = expense.tax_group.group_components.count()
        actual = doc_detail_counts.get((expense_ct.id, expense.id), 0)
        if expected_components and actual < expected_components:
            anomaly, _ = TaxAnomaly.objects.update_or_create(
                business=business,
                period_key=period_key,
                code="T3_MISSING_COMPONENT",
                linked_transaction_ct=expense_ct,
                linked_transaction_id=expense.id,
                defaults={
                    "severity": TaxAnomaly.AnomalySeverity.MEDIUM,
                    "status": TaxAnomaly.AnomalyStatus.OPEN,
                    "description": (
                        f"Expense {expense.id} has tax group {expense.tax_group.display_name} "
                        f"with {expected_components} components, but only {actual} tax details were recorded."
                    ),
                    "task_code": "T1",
                },
            )
            anomalies.append(anomaly)

    for detail in detail_qs:
        base = detail.taxable_amount_txn_currency or Decimal("0.00")
        tax_amount = detail.tax_amount_txn_currency or Decimal("0.00")
        if base == 0:
            continue
        txn_date = detail.transaction_date or start_date
        component = detail.tax_component
        expected_rate = Decimal("0.00")
        if component:
            rate_row = _get_applicable_rate(component, txn_date, getattr(component, "product_category", "STANDARD"))
            expected_rate = (rate_row.rate_decimal if rate_row else component.rate_percentage) or Decimal("0.00")
        expected_tax = _q_cent(base * expected_rate)
        if (expected_tax - tax_amount).copy_abs() > tolerance:
            code = "T1_RATE_MISMATCH"
            severity = TaxAnomaly.AnomalySeverity.MEDIUM
            if base > 0 and tax_amount > expected_tax:
                code = "T2_POSSIBLE_OVERCHARGE"
                severity = TaxAnomaly.AnomalySeverity.HIGH
            anomaly, _ = TaxAnomaly.objects.update_or_create(
                business=business,
                period_key=period_key,
                code=code,
                linked_transaction_ct=detail.transaction_line_content_type,
                linked_transaction_id=detail.transaction_line_object_id,
                defaults={
                    "severity": severity,
                    "status": TaxAnomaly.AnomalyStatus.OPEN,
                    "description": (
                        f"Applied tax {tax_amount} differs from expected {expected_tax} "
                        f"for component {getattr(component, 'name', '')} on {txn_date}."
                    ),
                    "task_code": "T1",
                },
            )
            anomalies.append(anomaly)
        # EXEMPT/ZERO-rated items incorrectly taxed
        jurisdiction_code = detail.jurisdiction_code or _jurisdiction_code_for_business(business)
        jurisdiction = TaxJurisdiction.objects.filter(code=jurisdiction_code).first()
        product_code = _product_code_for_detail(detail)
        if jurisdiction and tax_amount > Decimal("0.01"):
            rule = (
                TaxProductRule.objects.filter(
                    jurisdiction=jurisdiction,
                    product_code=product_code,
                    valid_from__lte=txn_date,
                )
                .filter(models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=txn_date))
                .order_by("-valid_from")
                .first()
            )
            if rule and rule.rule_type in [
                TaxProductRule.RuleType.EXEMPT,
                TaxProductRule.RuleType.ZERO_RATED,
            ]:
                anomaly, _ = TaxAnomaly.objects.update_or_create(
                    business=business,
                    period_key=period_key,
                    code="T5_EXEMPT_TAXED",
                    linked_transaction_ct=detail.transaction_line_content_type,
                    linked_transaction_id=detail.transaction_line_object_id,
                    defaults={
                        "severity": TaxAnomaly.AnomalySeverity.HIGH,
                        "status": TaxAnomaly.AnomalyStatus.OPEN,
                        "description": (
                            f"Exempt/zero-rated product {product_code} was taxed ({tax_amount}) in {jurisdiction.code}."
                        ),
                        "task_code": "T1",
                    },
                )
                anomalies.append(anomaly)
    # Late filing anomaly: snapshot not filed and past due date.
    try:
        due_date = compute_tax_due_date(business, period_key)
    except Exception:
        due_date = None
    if (
        due_date
        and snapshot.status != TaxPeriodSnapshot.SnapshotStatus.FILED
        and timezone.localdate() > due_date
    ):
        anomaly, _ = TaxAnomaly.objects.update_or_create(
            business=business,
            period_key=period_key,
            code="T7_LATE_FILING",
            defaults={
                "severity": TaxAnomaly.AnomalySeverity.HIGH,
                "status": TaxAnomaly.AnomalyStatus.OPEN,
                "description": f"Tax period {period_key} is past its filing due date ({due_date}).",
                "task_code": "T2",
            },
        )
        anomalies.append(anomaly)
    return anomalies
