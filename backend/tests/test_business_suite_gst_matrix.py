"""Configured fixture rates only; no assertion of current legal classifications."""
from decimal import Decimal, ROUND_HALF_UP
import pytest
from tests.fam_test_utils import fam_admin_headers


@pytest.mark.parametrize('rate', ['0', '5', '12', '18', '28'])
@pytest.mark.parametrize('taxable', ['0', '0.10', '99.99', '1000.25'])
@pytest.mark.parametrize('interstate', [False, True])
def test_tc031_039_configured_rate_components_and_decimal_rounding(client, db, rate, taxable, interstate):
    headers = fam_admin_headers(client, db)
    percentage, base = Decimal(rate), Decimal(taxable)
    response = client.post('/api/v1/fam/gst/calculate', headers=headers, json={
        'taxable_value': taxable, 'company_state_code': '29', 'place_of_supply_state': '27' if interstate else '29',
        'cgst_rate': str(percentage/2), 'sgst_rate': str(percentage/2), 'igst_rate': rate,
    })
    assert response.status_code == 200, response.text
    values = response.json()
    component = (base*percentage/(100 if interstate else 200)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    expected = component if interstate else component*2
    assert Decimal(str(values['total_tax'])) == expected
    assert Decimal(str(values['gross_amount'])) == base+expected
    assert Decimal(str(values['igst_amount'])) == (component if interstate else 0)
    assert Decimal(str(values['cgst_amount'])) == (0 if interstate else component)
    assert Decimal(str(values['sgst_amount'])) == (0 if interstate else component)


@pytest.mark.parametrize('classification', ['exempt', 'nil', 'zero_rated', 'out_of_scope'])
@pytest.mark.parametrize('interstate', [False, True])
def test_tc025_exempt_fixture_preserves_zero_tax(client, db, classification, interstate):
    headers = fam_admin_headers(client, db)
    response = client.post('/api/v1/fam/gst/calculate', headers=headers, json={
        'taxable_value': '100.25', 'company_state_code': '29', 'place_of_supply_state': '27' if interstate else '29',
        'cgst_rate': 9, 'sgst_rate': 9, 'igst_rate': 18, 'exempt_type': classification,
    })
    assert response.status_code == 200, response.text
    assert response.json()['total_tax'] == 0
    assert response.json()['gross_amount'] == 100.25


@pytest.mark.parametrize('field', ['cgst_rate', 'sgst_rate', 'igst_rate', 'cess_rate'])
@pytest.mark.parametrize('rate', [-1, 101])
def test_tc076_tax_rate_bounds_cannot_be_bypassed(client, db, field, rate):
    headers = fam_admin_headers(client, db)
    response = client.post('/api/v1/fam/gst/calculate', headers=headers, json={
        'taxable_value': 100, 'company_state_code': '29', 'place_of_supply_state': '29', field: rate,
    })
    # Preserve the existing configurable cess contract: a percentage above
    # 100 is not, by itself, malformed. These are mathematical fixtures only.
    if field == 'cess_rate' and rate == 101:
        assert response.status_code == 200, response.text
        assert response.json()['cess_amount'] == 101
    else:
        assert response.status_code == 422, response.text
