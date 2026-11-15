from decimal import Decimal as D

import pytest
from fastapi import HTTPException

from app.business_packs.restaurant.bill_allocations import Charge, Part, allocate


def test_fractional_quantity_bills_preserve_original_price_tax_and_total():
    source = Charge(1, 7, D('3'), D('33.33'), D('18'), D('117.99'))
    parts = []
    for quantity in ('0.25', '1.25', '1.50'):
        parts.append(allocate(source, quantity, parts))
    assert [part.quantity for part in parts] == [D('.25'), D('1.25'), D('1.50')]
    assert [part.tax_amount for part in parts] == [D('1.50'), D('7.50'), D('9.00')]
    assert sum(part.line_total for part in parts) == source.line_total
    assert all(part.sales_order_line_id == 7 and part.unit_price == D('33.33') for part in parts)


def test_last_bill_receives_exact_remaining_original_tax_cent():
    source = Charge(1, 7, D('3'), D('1'), D('.01'), D('3.01'))
    parts = []
    for _ in range(3):
        parts.append(allocate(source, '1', parts))
    assert [part.tax_amount for part in parts] == [D('0'), D('.01'), D('0')]
    assert sum(part.line_total for part in parts) == D('3.01')
    with pytest.raises(HTTPException) as error:
        allocate(source, '.01', parts)
    assert error.value.status_code == 409


@pytest.mark.parametrize('quantity', ['0', '-1', '.001', 'NaN', 'Infinity', '10000000000'])
def test_invalid_quantities_never_create_a_charge(quantity):
    with pytest.raises(HTTPException) as error:
        allocate(Charge(1, 7, D('1'), D('100'), D('18'), D('118')), quantity)
    assert error.value.status_code == 422


def test_unrepresentable_half_cent_split_is_rejected_instead_of_adjusting_price():
    source = Charge(1, 7, D('1'), D('.01'), D('0'), D('.01'))
    with pytest.raises(HTTPException) as error:
        allocate(source, '.50')
    assert error.value.status_code == 409 and 'native invoice cents' in error.value.detail
    assert allocate(source, '1').line_total == D('.01')


@pytest.mark.parametrize('part', [
    Part(2, 7, D('1'), D('100'), D('18'), D('118')),
    Part(1, 8, D('1'), D('100'), D('18'), D('118')),
    Part(1, 7, D('1'), D('99'), D('18'), D('117')),
    Part(1, 7, D('1'), D('100'), D('17'), D('117')),
    Part(1, 7, D('1'), D('100'), D('18'), D('119')),
])
def test_foreign_or_changed_previous_allocations_fail_closed(part):
    with pytest.raises(HTTPException) as error:
        allocate(Charge(1, 7, D('2'), D('100'), D('36'), D('236')), '1', [part])
    assert error.value.status_code == 409
