from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.business_packs.retail.schemas import ReturnInput
from app.business_packs.retail.valuation import allocate_return


def test_partial_returns_preserve_the_issued_charge_and_tax_to_last_cent():
    history = [Decimal(0), Decimal(0), Decimal(0)]
    charges = []
    for _ in range(3):
        charge = allocate_return(sold_quantity=3, issued_gross='1.00', issued_tax='.05',
            prior_quantity=history[0], prior_gross=history[1], prior_tax=history[2], requested_quantity=1)
        history = [history[0]+charge.quantity, history[1]+charge.gross, history[2]+charge.tax]
        charges.append(charge)
    assert [charge.gross for charge in charges] == [Decimal('.33'), Decimal('.33'), Decimal('.34')]
    assert sum(charge.tax for charge in charges) == Decimal('.05')
    assert sum(charge.net for charge in charges) == Decimal('.95')


@pytest.mark.parametrize('change', [
    {'requested_quantity': '2.0000000001'}, {'requested_quantity': 0},
    {'requested_quantity': 'NaN'}, {'prior_gross': '11'}, {'prior_tax': '2'},
    {'issued_tax': '11'},
])
def test_invalid_or_excess_returns_cannot_allocate_money(change):
    values=dict(sold_quantity=3, issued_gross='10', issued_tax='1', prior_quantity=1,
        prior_gross='3.33', prior_tax='.33', requested_quantity=1)
    with pytest.raises(ValueError):
        allocate_return(**{**values, **change})


def test_return_command_rejects_duplicate_lines_and_client_financial_authority():
    payload=dict(checkout_id=1,expected_checkout_revision=1,
        request_key='64cd7c61-0ff4-4545-ad00-2e9a50e74d21',
        lines=[{'checkout_line_id':1,'quantity':1}],
        refund={'method':'cash','session_id':1},reason='Unopened item')
    assert ReturnInput.model_validate(payload).lines[0].quantity == 1
    for change in ({'lines':payload['lines']*2}, {'refund_amount':1}, {'customer_id':2}):
        with pytest.raises(ValidationError):
            ReturnInput.model_validate({**payload,**change})
