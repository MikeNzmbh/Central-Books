from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, List, Optional

from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction

from .models import TaxGroup, TaxRate, TransactionLineTaxDetail


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


def _convert_to_home(amount: Decimal, currency: str, fx_rate: Optional[Decimal]) -> Decimal:
    if currency.upper() == "CAD":
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if fx_rate is None:
        raise ValueError("fx_rate is required when converting non-CAD amounts.")
    return (amount * fx_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


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

        base_amount = getattr(transaction_line, "net_amount", None)
        if base_amount is None:
            raise ValueError("transaction_line must expose net_amount.")

        product_category = product_category or getattr(
            transaction_line, "product_category", "STANDARD"
        )
        currency = currency.upper()

        details: List[TransactionLineTaxDetail] = []
        results: List[TaxComponentResult] = []
        accumulated_tax = Decimal("0.00")

        ct = None
        obj_id = None
        if persist and hasattr(transaction_line, "_meta") and getattr(transaction_line, "pk", None):
            ct = ContentType.objects.get_for_model(transaction_line)
            obj_id = transaction_line.pk

        group_components = tax_group.group_components.select_related("component").all()

        for gc in group_components:
            component = gc.component
            rate_row = _get_applicable_rate(component, txn_date, product_category)
            rate_to_use = rate_row.rate_decimal if rate_row else component.rate_percentage
            if rate_to_use is None:
                continue

            calc_base = base_amount
            if tax_group.calculation_method == TaxGroup.CalculationMethod.COMPOUND:
                calc_base = base_amount + accumulated_tax

            tax_value_txn = (calc_base * rate_to_use).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            accumulated_tax += tax_value_txn

            taxable_home = _convert_to_home(calc_base, currency, fx_rate)
            tax_home = _convert_to_home(tax_value_txn, currency, fx_rate)

            detail = None
            if persist and ct and obj_id:
                detail = TransactionLineTaxDetail.objects.create(
                    business=business,
                    tax_group=tax_group,
                    tax_component=component,
                    transaction_line_content_type=ct,
                    transaction_line_object_id=obj_id,
                    transaction_date=txn_date,
                    taxable_amount_txn_currency=calc_base,
                    taxable_amount_home_currency_cad=taxable_home,
                    tax_amount_txn_currency=tax_value_txn,
                    tax_amount_home_currency_cad=tax_home,
                    is_recoverable=component.is_recoverable,
                )
            if detail:
                details.append(detail)

            jurisdiction_code = None
            if hasattr(component, "jurisdiction"):
                jurisdiction_code = getattr(component.jurisdiction, "code", None)
            if not jurisdiction_code:
                jurisdiction_code = getattr(component, "authority", None)

            results.append(
                TaxComponentResult(
                    tax_component_id=str(component.id),
                    tax_group_id=str(tax_group.id),
                    amount_txn_currency=tax_value_txn,
                    amount_home_currency_cad=tax_home,
                    taxable_base_txn_currency=calc_base,
                    taxable_base_home_currency_cad=taxable_home,
                    rate_used=rate_to_use,
                    is_recoverable=component.is_recoverable,
                    jurisdiction_code=jurisdiction_code,
                )
            )

        return {
            "details": details,
            "components": results,
            "total_tax_txn_currency": sum((r.amount_txn_currency for r in results), Decimal("0.00")),
            "total_tax_home_currency_cad": sum(
                (r.amount_home_currency_cad for r in results), Decimal("0.00")
            ),
        }
