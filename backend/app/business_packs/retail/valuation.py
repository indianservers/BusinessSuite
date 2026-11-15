"""Pure allocation of issued line charges; no client prices or tax calculation."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal('0.01')


@dataclass(frozen=True)
class ReturnCharge:
    quantity: Decimal
    net: Decimal
    tax: Decimal
    gross: Decimal


def allocate_return(*, sold_quantity, issued_gross, issued_tax, prior_quantity,
                    prior_gross, prior_tax, requested_quantity):
    values = tuple(Decimal(value) for value in (
        sold_quantity, issued_gross, issued_tax, prior_quantity,
        prior_gross, prior_tax, requested_quantity))
    if any(not value.is_finite() for value in values):
        raise ValueError('Return charges must be finite')
    sold, gross, tax, prior, paid_back, tax_back, requested = values
    if sold <= 0 or requested <= 0 or min(gross, tax, prior, paid_back, tax_back) < 0:
        raise ValueError('Invalid issued or returned quantities and charges')
    if tax > gross or prior + requested > sold or paid_back > gross or tax_back > tax:
        raise ValueError('Return exceeds the original sale')
    remaining_gross, remaining_tax = gross - paid_back, tax - tax_back
    if prior + requested == sold:
        refund, refund_tax = remaining_gross, remaining_tax
    else:
        refund = min(remaining_gross, (gross * requested / sold).quantize(CENT, rounding=ROUND_HALF_UP))
        refund_tax = min(remaining_tax, (tax * requested / sold).quantize(CENT, rounding=ROUND_HALF_UP))
    if refund_tax > refund:
        raise ValueError('Original return charge history is inconsistent')
    return ReturnCharge(requested, refund - refund_tax, refund_tax, refund)
