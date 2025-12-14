from decimal import Decimal, ROUND_HALF_EVEN

TAX_TREATMENTS = {"NONE", "INCLUDED", "ON_TOP"}


def compute_tax_breakdown(amount: Decimal, treatment: str, rate_percent: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """
    Given a base amount and tax treatment, return (net, tax, gross) rounded to cents.

    - If treatment is NONE, the amount is both net and gross.
    - If INCLUDED, the amount is gross.
    - If ON_TOP, the amount is net and tax is added on top.
    """
    treatment_normalized = (treatment or "NONE").upper()
    if treatment_normalized not in TAX_TREATMENTS:
        raise ValueError("Unsupported tax treatment.")

    rate_decimal = (rate_percent or Decimal("0")) / Decimal("100")
    quantize_to_cent = lambda val: val.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)

    if treatment_normalized == "NONE" or rate_decimal == 0:
        net = quantize_to_cent(Decimal(amount))
        return net, Decimal("0.00"), net

    if treatment_normalized == "INCLUDED":
        gross = quantize_to_cent(Decimal(amount))
        divisor = Decimal("1") + rate_decimal
        net = quantize_to_cent(gross / divisor) if divisor != 0 else gross
        tax = quantize_to_cent(gross - net)
        return net, tax, gross

    # ON_TOP
    net = quantize_to_cent(Decimal(amount))
    tax = quantize_to_cent(net * rate_decimal)
    gross = quantize_to_cent(net + tax)
    return net, tax, gross


__all__ = ["compute_tax_breakdown", "TAX_TREATMENTS"]
