"""Native issued precision must serialize identically before and after reload."""
from decimal import Decimal
import pytest
from app.business_packs.pharma.returns import quantity_text,money_text

@pytest.mark.parametrize('assigned,reloaded,expected',[
    ('1','1.000','1.000'),('0.001','0.001','0.001'),('2.5','2.500','2.500'),('10000000000','10000000000.000','10000000000.000')])
def test_quantity_matches_native_three_decimal_reload(assigned,reloaded,expected):
    assert quantity_text(Decimal(assigned))==quantity_text(Decimal(reloaded))==expected

@pytest.mark.parametrize('assigned,reloaded,expected',[('1','1.00','1.00'),('0','0.00','0.00'),('118.5','118.50','118.50'),('0.12','0.12','0.12')])
def test_money_matches_native_two_decimal_reload(assigned,reloaded,expected):
    assert money_text(Decimal(assigned))==money_text(Decimal(reloaded))==expected
