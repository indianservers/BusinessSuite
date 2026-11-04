from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.apps.crm.models import CRMQuotation, CRMQuotationItem
from app.apps.crm.api.router import _apply_quote_line_calculation, _quotation_pdf_file_path


def line(**changes):
    return CRMQuotationItem(**{'name': 'Rounding case', 'quantity': Decimal('3'),
        'unit_price': Decimal('0.05'), 'discount_type': 'percent', 'discount_value': Decimal('10'),
        'tax_rate': Decimal('18'), 'estimated_cost': Decimal('0'), **changes})


def test_quote_discount_and_tax_are_rounded_once_per_line():
    value = line()
    _apply_quote_line_calculation(value)
    assert value.discount_amount == Decimal('0.02')
    assert value.line_total == Decimal('0.15')
    # Taxable 0.13 + rounded tax 0.02, not a binary-float approximation.
    assert value.line_total - (Decimal('0.15') - value.discount_amount) == Decimal('0.02')


@pytest.mark.parametrize('changes', [
    {'quantity': Decimal('0')}, {'quantity': Decimal('-1')},
    {'unit_price': Decimal('NaN')}, {'unit_price': Decimal('Infinity')},
    {'discount_value': Decimal('101')}, {'discount_type': 'amount', 'discount_value': Decimal('1')},
    {'tax_rate': Decimal('101')}, {'tax_rate': Decimal('-1')},
])
def test_invalid_quote_amounts_never_reach_accounting(changes):
    with pytest.raises(HTTPException) as error:
        _apply_quote_line_calculation(line(**changes))
    assert error.value.status_code == 422


def test_regenerated_quote_files_have_distinct_immutable_paths(tmp_path, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, 'UPLOAD_DIR', str(tmp_path))
    quote = CRMQuotation(id=5, organization_id=1, quote_number='QT/2026/1', version_number=1)
    first = _quotation_pdf_file_path(quote)
    repeated = _quotation_pdf_file_path(quote)
    quote.version_number = 2
    revised = _quotation_pdf_file_path(quote)
    assert len({first[0], repeated[0], revised[0]}) == 3
    assert '-v1-' in first[1] and '-v2-' in revised[1]
