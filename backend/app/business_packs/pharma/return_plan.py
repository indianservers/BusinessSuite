"""Exact original-lot return quantities; returned medicine awaits disposition.

This arithmetic grants no stock or financial authority. Callers must supply
verified original allocations and committed prior returns inside their locked
transaction before posting any native return or refund.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


class ReturnPlanError(ValueError):
    pass


@dataclass(frozen=True)
class SoldLot:
    allocation_id: int
    batch_id: int
    quantity: Decimal
    returned_quantity: Decimal


@dataclass(frozen=True)
class ReturnLot:
    allocation_id: int
    batch_id: int
    quantity: Decimal
    disposition: str = 'quarantine'


def _quantity(value, *, positive=False):
    # Floats and booleans must not introduce approximate stock quantities.
    if isinstance(value, (bool, float)) or not isinstance(value, (Decimal, int, str)):
        raise ReturnPlanError('Invalid return quantity')
    try:
        result = Decimal(value)
        if (not result.is_finite() or result < 0 or result > Decimal('99999999999.999')
                or (positive and result == 0) or result != result.quantize(Decimal('.001'))):
            raise ReturnPlanError('Invalid return quantity')
    except (InvalidOperation, ValueError, OverflowError) as exc:
        raise ReturnPlanError('Invalid return quantity') from exc
    return result


def plan_return(original: tuple[SoldLot, ...], requested: dict[int, Decimal]) -> tuple[ReturnLot, ...]:
    """Require explicit original allocation IDs, never substitute another lot."""
    if not isinstance(original, tuple) or not isinstance(requested, dict) or not requested:
        raise ReturnPlanError('Select original sale lots to return')
    sources = {}
    for source in original:
        if (type(source) is not SoldLot or type(source.allocation_id) is not int
                or type(source.batch_id) is not int or source.allocation_id <= 0
                or source.batch_id <= 0 or source.allocation_id in sources):
            raise ReturnPlanError('Original lot source requires reconciliation')
        sold = _quantity(source.quantity, positive=True)
        returned = _quantity(source.returned_quantity)
        if returned > sold:
            raise ReturnPlanError('Original lot source requires reconciliation')
        sources[source.allocation_id] = (source, sold - returned)
    result = []
    for allocation_id, quantity in requested.items():
        if type(allocation_id) is not int or allocation_id not in sources:
            raise ReturnPlanError('Return lot is not part of the original sale')
        source, remaining = sources[allocation_id]
        amount = _quantity(quantity, positive=True)
        if amount > remaining:
            raise ReturnPlanError('Return exceeds remaining original lot quantity')
        result.append(ReturnLot(allocation_id, source.batch_id, amount))
    return tuple(sorted(result, key=lambda item: item.allocation_id))
