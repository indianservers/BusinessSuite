from decimal import Decimal

import pytest

from app.business_packs.pharma.return_plan import SoldLot, ReturnPlanError, plan_return


def test_return_preserves_original_lots_and_quarantines_without_fefo_replacement():
    original = (SoldLot(2, 90, Decimal('3'), Decimal('1')),
                SoldLot(1, 91, Decimal('2.125'), Decimal('.125')))
    result = plan_return(original, {2: Decimal('1.5'), 1: Decimal('2')})
    assert [(r.allocation_id, r.batch_id, r.quantity, r.disposition) for r in result] == [
        (1, 91, Decimal('2'), 'quarantine'), (2, 90, Decimal('1.5'), 'quarantine')]
    assert original[0].returned_quantity == Decimal('1')


@pytest.mark.parametrize('amount', ['0', '-1', '.0001', 'NaN', 'Infinity', '1e100', True, 0.1, None])
def test_invalid_or_imprecise_return_quantity_is_rejected(amount):
    with pytest.raises(ReturnPlanError):
        plan_return((SoldLot(1, 2, Decimal('2'), Decimal('0')),), {1: amount})


def test_cannot_borrow_remaining_quantity_from_another_lot():
    with pytest.raises(ReturnPlanError, match='exceeds remaining'):
        plan_return((SoldLot(1, 2, Decimal('2'), Decimal('1.5')),
                     SoldLot(2, 3, Decimal('100'), Decimal('0'))), {1: Decimal('1')})


@pytest.mark.parametrize('allocation', [999, True, '1'])
def test_foreign_or_ambiguous_allocation_is_rejected(allocation):
    with pytest.raises(ReturnPlanError, match='not part'):
        plan_return((SoldLot(1, 2, Decimal('2'), Decimal('0')),), {allocation: Decimal('1')})


@pytest.mark.parametrize('original', [
    (SoldLot(1, 2, Decimal('2'), Decimal('3')),),
    (SoldLot(1, 2, Decimal('2'), Decimal('0')), SoldLot(1, 3, Decimal('2'), Decimal('0'))),
    (SoldLot(True, 2, Decimal('2'), Decimal('0')),),
])
def test_inconsistent_original_source_is_rejected(original):
    with pytest.raises(ReturnPlanError):
        plan_return(original, {1: Decimal('1')})


def test_empty_selection_is_rejected():
    with pytest.raises(ReturnPlanError):
        plan_return((), {})
