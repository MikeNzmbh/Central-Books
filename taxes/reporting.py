from collections import defaultdict
from decimal import Decimal
from typing import Dict, Iterable, Optional

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import F, Sum, DateField
from django.db.models.functions import Coalesce

from core.models import Account, Expense, Invoice, JournalLine
from .models import TaxComponent, TransactionLineTaxDetail


def _coalesce_date(field_name: str):
    return Coalesce(field_name, F("created_at"), output_field=DateField())


def gst_hst_summary(
    business,
    start_date,
    end_date,
    jurisdiction: Optional[str] = None,
) -> Dict:
    """
    Compute CRA/QST lines using tax detail + ledger balances.

    - jurisdiction: None/"ALL" → include CRA + RQ blocks
                   "CRA" → GST/HST only
                   "RQ" → QST only
    """
    liability_codes = ["2300", "2200"]  # support legacy 2200 for historical data
    recoverable_codes = ["1400"]

    def _authority_filter(qs):
        if jurisdiction in {None, "", "ALL"}:
            return qs
        return qs.filter(tax_component__authority=jurisdiction)

    details_qs = (
        TransactionLineTaxDetail.objects.filter(
            business=business,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
        )
        .annotate(tx_date=_coalesce_date("transaction_date"))
        .select_related("tax_component")
    )

    details_qs = _authority_filter(details_qs)

    # Line 101: sum unique invoice bases so we don't double count multi-component groups.
    line_101_total = Decimal("0.00")
    seen_invoice_base = {}
    invoice_ct = ContentType.objects.get_for_model(Invoice)
    for row in details_qs.filter(transaction_line_content_type=invoice_ct):
        key = row.transaction_line_object_id
        if key not in seen_invoice_base:
            seen_invoice_base[key] = row.taxable_amount_home_currency_cad
    line_101_total = sum(seen_invoice_base.values(), Decimal("0.00"))

    # Line 105: tax collected on invoices (liability side)
    line_105 = (
        details_qs.filter(transaction_line_content_type=invoice_ct).aggregate(
            total=Sum("tax_amount_home_currency_cad")
        )["total"]
        or Decimal("0.00")
    )

    # Line 108: ITCs (recoverable) on expenses
    expense_ct = ContentType.objects.get_for_model(Expense)
    line_108 = (
        details_qs.filter(
            transaction_line_content_type=expense_ct, is_recoverable=True
        ).aggregate(total=Sum("tax_amount_home_currency_cad"))["total"]
        or Decimal("0.00")
    )

    line_109 = line_105 - line_108

    # Ledger-aware balances (includes legacy 2200)
    ledger_tax = JournalLine.objects.filter(
        journal_entry__business=business,
        journal_entry__date__gte=start_date,
        journal_entry__date__lte=end_date,
        account__code__in=liability_codes + recoverable_codes,
    ).annotate(account_code=F("account__code"))

    ledger_liability = Decimal("0.00")
    ledger_recoverable = Decimal("0.00")
    for jl in ledger_tax:
        if jl.account_code in liability_codes:
            ledger_liability += (jl.credit or Decimal("0.00")) - (jl.debit or Decimal("0.00"))
        elif jl.account_code in recoverable_codes:
            ledger_recoverable += (jl.debit or Decimal("0.00")) - (jl.credit or Decimal("0.00"))

    details_rows = _build_detail_rows(details_qs)

    return {
        "jurisdiction": jurisdiction or "ALL",
        "line_101_taxable_sales": line_101_total,
        "line_105_tax_collected": line_105,
        "line_108_itcs": line_108,
        "line_109_net_tax": line_109,
        "ledger_liability": ledger_liability,
        "ledger_recoverable": ledger_recoverable,
        "details": details_rows,
    }


def _build_detail_rows(details_qs) -> list[dict]:
    """
    Collapse TransactionLineTaxDetail rows by document to feed filing table / CSV.
    """
    grouped: dict[tuple, dict] = {}
    for row in details_qs:
        key = (row.transaction_line_content_type_id, row.transaction_line_object_id)
        bucket = grouped.setdefault(
            key,
            {
                "date": row.transaction_date or row.created_at.date(),
                "document_type": row.transaction_line_content_type.model,
                "document_id": row.transaction_line_object_id,
                "customer_or_vendor": "",
                "net_amount": Decimal("0.00"),
                "tax_components": [],
            },
        )
        bucket["net_amount"] = row.taxable_amount_home_currency_cad
        bucket["tax_components"].append(
            {
                "name": row.tax_component.name,
                "authority": row.tax_component.authority,
                "amount": row.tax_amount_home_currency_cad,
            }
        )

    for bucket in grouped.values():
        bucket["total_tax"] = sum((c["amount"] for c in bucket["tax_components"]), Decimal("0.00"))
    return list(grouped.values())


def net_tax_position(business) -> Dict[str, Decimal]:
    """
    Return balances for 2300/2200 and 1400.
    """
    liability_codes = ["2300", "2200"]
    recoverable_codes = ["1400"]

    def _balance_for(code_list: Iterable[str]) -> Decimal:
        accounts = Account.objects.filter(business=business, code__in=code_list)
        total = Decimal("0.00")
        for acc in accounts:
            agg = JournalLine.objects.filter(account=acc).aggregate(
                debit=Sum("debit"), credit=Sum("credit")
            )
            debit = agg["debit"] or Decimal("0.00")
            credit = agg["credit"] or Decimal("0.00")
            if acc.type in (Account.AccountType.ASSET, Account.AccountType.EXPENSE):
                total += debit - credit
            else:
                total += credit - debit
        return total

    payable = _balance_for(liability_codes)
    recoverable = _balance_for(recoverable_codes)
    net = payable - recoverable
    return {
        "sales_tax_payable": payable,
        "recoverable_tax_asset": recoverable,
        "net_tax": net,
    }


def get_us_sales_tax_summary(business, start_date, end_date) -> dict:
    """
    Per-jurisdiction US sales tax collected summary.
    """
    invoice_ct = ContentType.objects.get_for_model(Invoice)
    qs = (
        TransactionLineTaxDetail.objects.filter(
            business=business,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
            transaction_line_content_type=invoice_ct,
        )
        .select_related("tax_component")
        .annotate(tx_date=_coalesce_date("transaction_date"))
    )
    qs = qs.filter(
        models.Q(tax_component__authority__startswith="US")
        | models.Q(tax_component__authority__iexact="US")
    )

    jurisdictions: dict[str, dict] = {}
    for row in qs:
        code = row.tax_component.authority or "US-UNKNOWN"
        bucket = jurisdictions.setdefault(
            code,
            {
                "code": code,
                "name": code.replace("-", " "),
                "gross_taxable_sales_txn": Decimal("0.00"),
                "gross_taxable_sales_home": Decimal("0.00"),
                "tax_collected_txn": Decimal("0.00"),
                "tax_collected_home": Decimal("0.00"),
            },
        )
        bucket["gross_taxable_sales_txn"] += row.taxable_amount_txn_currency
        bucket["gross_taxable_sales_home"] += row.taxable_amount_home_currency_cad
        bucket["tax_collected_txn"] += row.tax_amount_txn_currency
        bucket["tax_collected_home"] += row.tax_amount_home_currency_cad

    totals = {
        "gross_taxable_sales_txn": sum((v["gross_taxable_sales_txn"] for v in jurisdictions.values()), Decimal("0.00")),
        "gross_taxable_sales_home": sum((v["gross_taxable_sales_home"] for v in jurisdictions.values()), Decimal("0.00")),
        "tax_collected_txn": sum((v["tax_collected_txn"] for v in jurisdictions.values()), Decimal("0.00")),
        "tax_collected_home": sum((v["tax_collected_home"] for v in jurisdictions.values()), Decimal("0.00")),
    }

    return {
        "period": {"start": start_date, "end": end_date},
        "jurisdictions": list(jurisdictions.values()),
        "totals": totals,
        "disclaimer": "Tracking only. Users must manage nexus/taxability and rate accuracy.",
    }
