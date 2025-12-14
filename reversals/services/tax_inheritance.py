from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from taxes.models import TransactionLineTaxDetail
from taxes.services import TaxEngine


def _q_cent(value: Decimal) -> Decimal:
    return (value or Decimal("0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


def _delete_tax_details_for_obj(*, business, obj) -> None:
    ct = ContentType.objects.get_for_model(obj.__class__)
    TransactionLineTaxDetail.objects.filter(
        business=business,
        transaction_line_content_type=ct,
        transaction_line_object_id=obj.pk,
    ).delete()


@transaction.atomic
def replace_credit_memo_tax_details_from_invoice(*, credit_memo, invoice) -> Decimal:
    """
    Copy tax DNA from an invoice onto a credit memo using a net-based ratio.

    Persists signed (negative) TransactionLineTaxDetail rows linked to the credit memo.
    Returns the absolute tax total (txn currency) for the credit memo.
    """
    if not credit_memo.pk:
        raise ValueError("credit_memo must be saved before persisting tax details.")
    if not invoice.pk:
        raise ValueError("invoice must be saved before reading tax details.")
    if credit_memo.business_id != invoice.business_id:
        raise ValueError("Invoice does not belong to the same business.")

    invoice_net = invoice.net_total or invoice.total_amount or Decimal("0.00")
    if invoice_net <= 0:
        raise ValueError("Source invoice net total must be positive.")
    credit_net = credit_memo.net_total or Decimal("0.00")
    if credit_net <= 0:
        raise ValueError("Credit memo net total must be positive.")

    ratio = credit_net / invoice_net
    if ratio <= 0:
        raise ValueError("Invalid ratio for credit memo.")
    if ratio > 1:
        raise ValueError("Credit memo cannot exceed source invoice net total.")

    invoice_ct = ContentType.objects.get_for_model(invoice.__class__)
    invoice_details = list(
        TransactionLineTaxDetail.objects.filter(
            business=invoice.business,
            transaction_line_content_type=invoice_ct,
            transaction_line_object_id=invoice.pk,
        ).select_related("tax_component", "tax_group")
    )

    _delete_tax_details_for_obj(business=credit_memo.business, obj=credit_memo)
    if not invoice_details:
        return Decimal("0.00")

    credit_ct = ContentType.objects.get_for_model(credit_memo.__class__)
    created: list[TransactionLineTaxDetail] = []
    for detail in invoice_details:
        created.append(
            TransactionLineTaxDetail.objects.create(
                business=credit_memo.business,
                tax_group=detail.tax_group,
                tax_component=detail.tax_component,
                jurisdiction_code=detail.jurisdiction_code or "",
                transaction_line_content_type=credit_ct,
                transaction_line_object_id=credit_memo.pk,
                transaction_date=credit_memo.posting_date,
                document_side=TransactionLineTaxDetail.DocumentSide.SALE,
                taxable_amount_txn_currency=_q_cent(-_q_cent((detail.taxable_amount_txn_currency or Decimal("0.00")) * ratio)),
                taxable_amount_home_currency_cad=_q_cent(-_q_cent((detail.taxable_amount_home_currency_cad or Decimal("0.00")) * ratio)),
                tax_amount_txn_currency=_q_cent(-_q_cent((detail.tax_amount_txn_currency or Decimal("0.00")) * ratio)),
                tax_amount_home_currency_cad=_q_cent(-_q_cent((detail.tax_amount_home_currency_cad or Decimal("0.00")) * ratio)),
                is_recoverable=bool(detail.is_recoverable),
            )
        )

    tax_total_signed = sum((d.tax_amount_txn_currency or Decimal("0.00") for d in created), Decimal("0.00"))
    return tax_total_signed.copy_abs()


@transaction.atomic
def replace_credit_memo_tax_details_by_recompute(*, credit_memo) -> Decimal:
    """
    Compute tax deterministically for a credit memo (no source invoice).

    Persists signed (negative) TransactionLineTaxDetail rows linked to the credit memo.
    Returns the absolute tax total (txn currency) for the credit memo.
    """
    if not credit_memo.pk:
        raise ValueError("credit_memo must be saved before persisting tax details.")
    if not credit_memo.tax_group_id:
        _delete_tax_details_for_obj(business=credit_memo.business, obj=credit_memo)
        return Decimal("0.00")

    net = credit_memo.net_total or Decimal("0.00")
    if net <= 0:
        raise ValueError("Credit memo net total must be positive.")

    # We compute on a signed amount to generate negative component rows.
    result = TaxEngine.calculate_for_line(
        business=credit_memo.business,
        transaction_line=type("Line", (), {"net_amount": -net})(),
        tax_group=credit_memo.tax_group,
        txn_date=credit_memo.posting_date,
        currency=getattr(credit_memo.business, "currency", "CAD") or "CAD",
        fx_rate=Decimal("1.00"),
        persist=False,
    )

    _delete_tax_details_for_obj(business=credit_memo.business, obj=credit_memo)

    credit_ct = ContentType.objects.get_for_model(credit_memo.__class__)
    for component in result.get("components") or []:
        TransactionLineTaxDetail.objects.create(
            business=credit_memo.business,
            tax_group=credit_memo.tax_group,
            tax_component_id=component.tax_component_id,
            jurisdiction_code=component.jurisdiction_code or "",
            transaction_line_content_type=credit_ct,
            transaction_line_object_id=credit_memo.pk,
            transaction_date=credit_memo.posting_date,
            document_side=TransactionLineTaxDetail.DocumentSide.SALE,
            taxable_amount_txn_currency=_q_cent(component.taxable_base_txn_currency),
            taxable_amount_home_currency_cad=_q_cent(component.taxable_base_home_currency_cad),
            tax_amount_txn_currency=_q_cent(component.amount_txn_currency),
            tax_amount_home_currency_cad=_q_cent(component.amount_home_currency_cad),
            is_recoverable=bool(component.is_recoverable),
        )

    total_tax_signed = result.get("total_tax_txn_currency") or Decimal("0.00")
    return total_tax_signed.copy_abs()
