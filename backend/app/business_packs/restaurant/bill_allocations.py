"""Plan immutable quantities against original charges, never rewrite the order.

This module grants no billing authority. Callers must serialize the native
company writer and validate every source and previous allocation before use.
The native invoice normalizer remains authoritative for cent arithmetic.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from fastapi import HTTPException


CENT = Decimal('.01')


def fail(message, status=409):
    raise HTTPException(status, message)


def number(value, *, positive=False):
    try:
        result = Decimal(str(value))
        limit = Decimal('9999999999.99') if positive else Decimal('99999999999')
        valid = result.is_finite() and 0 <= result <= limit and result == result.quantize(CENT)
    except (InvalidOperation, ValueError, TypeError):
        valid = False
    if not valid or (positive and result <= 0):
        fail('Split quantities and charges must be finite positive two-decimal values', 422)
    return result


def cents(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Charge:
    snapshot_id: int
    sales_order_line_id: int
    quantity: Decimal
    unit_price: Decimal
    tax_amount: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class Part:
    snapshot_id: int
    sales_order_line_id: int
    quantity: Decimal
    unit_price: Decimal
    tax_amount: Decimal
    line_total: Decimal


def allocate(source: Charge, quantity, previous=()):
    """Return the next exact native-invoice charge or reject unrepresentable cents.

    Previous values must be the durable immutable allocations, not client input.
    Every prefix and its remainder must preserve both the original gross and
    the native quantity*price rounding. Tax follows cumulative quantity, with
    the final allocation taking precisely the remaining original tax cents.
    """
    if type(source) is not Charge or type(source.snapshot_id) is not int or type(source.sales_order_line_id) is not int or min(source.snapshot_id, source.sales_order_line_id) <= 0:
        fail('An original Restaurant charge is required')
    original = number(source.quantity, positive=True)
    price, tax, total = (number(value) for value in (source.unit_price, source.tax_amount, source.line_total))
    gross = cents(original * price)
    if total != gross + tax:
        fail('The original Restaurant charge requires reconciliation')
    used_quantity = used_gross = used_tax = Decimal(0)
    for part in previous:
        if (type(part) is not Part or (part.snapshot_id, part.sales_order_line_id, part.unit_price) !=
                (source.snapshot_id, source.sales_order_line_id, price)):
            fail('A split allocation has a different original source')
        qty = number(part.quantity, positive=True)
        part_tax, part_total = number(part.tax_amount), number(part.line_total)
        used_quantity += qty
        used_gross += cents(qty * price)
        used_tax += part_tax
        if (used_quantity > original or used_gross > gross or part_total != cents(qty * price) + part_tax
                or used_tax != cents(tax * used_quantity / original)
                or used_gross + cents((original - used_quantity) * price) != gross):
            fail('The immutable split allocation history requires reconciliation')
    qty = number(quantity, positive=True)
    if used_quantity + qty > original:
        fail('Split quantity exceeds the original unbilled quantity')
    base = cents(qty * price)
    left = original - used_quantity - qty
    if used_gross + base + cents(left * price) != gross:
        fail('This quantity split cannot preserve the original native invoice cents')
    part_tax = cents(tax * (used_quantity + qty) / original) - used_tax
    if part_tax < 0 or used_tax + part_tax > tax:
        fail('Split tax exceeds the original charge')
    return Part(source.snapshot_id, source.sales_order_line_id, qty, price, part_tax, base + part_tax)
