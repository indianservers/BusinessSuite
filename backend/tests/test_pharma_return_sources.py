from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from app.business_packs.pharma.return_sources import original_lots
from tests.test_pharma_fefo import lots, sale, lot_quantities
from tests.test_pharma_receipts import pharma
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer


def test_actual_original_sale_return_lots_are_private_immutable_sources(client, db, lots):
    case, receipts, _ = lots
    response = client.post('/api/v1/srm/service-checkout', headers=case[0], json=sale(lots, paid=True))
    assert response.status_code == 201, response.text
    checkout_id = response.json()['id']
    before = lot_quantities(db, lots)
    discovery = client.get(f'/api/v1/srm/pharma/returns/sales/{checkout_id}/lots', headers=case[0])
    assert discovery.status_code == 200, discovery.text
    payload = discovery.json()
    assert payload['checkout_id'] == checkout_id
    assert len(payload['lots']) == 2
    assert set(payload['lots'][0]) == {'checkout_line_id', 'allocation_id', 'batch_id',
                                      'product_id', 'warehouse_id', 'batch_number', 'expiry_date', 'sold_quantity'}
    assert [Decimal(row['sold_quantity']) for row in payload['lots']] == [Decimal('3'), Decimal('1')]
    with native_writer(db, case[1], case[2]):
        scope = resolve_context(db, case[1], db.info['branch_context'], case[3])
        cleanup = install(db, scope, policy=native_srm_policy('pharma').policy)
        try:
            result = original_lots(db, case[1], checkout_id)
            assert [(r.batch_id, r.sold_quantity) for r in result] == [
                (receipts[1]['batch_id'], Decimal('3')), (receipts[0]['batch_id'], Decimal('1'))]
            assert all(type(r.allocation_id) is int and r.allocation_id > 0 for r in result)
            assert len({r.checkout_line_id for r in result}) == 1
            with pytest.raises(HTTPException) as missing:
                original_lots(db, case[1], checkout_id + 100000)
            assert missing.value.status_code == 404
            # Discovery neither commits the caller nor changes stock.
            assert db.in_transaction()
        finally:
            cleanup()
    assert lot_quantities(db, lots) == before


@pytest.mark.parametrize('pack,role', [('hospital', 'doctor'), ('restaurant', 'chef'),
                                      ('construction', 'site_engineer')])
def test_other_pack_specialists_cannot_discover_pharma_return_sources(client, db, pharma, pack, role):
    from tests.test_business_pack_http_integration import grant
    case = pharma
    selected, _ = grant(db, case[1], case[2], pack, role)
    denied_http = client.get('/api/v1/srm/pharma/returns/sales/1/lots',
                             headers={**case[0], 'X-Suite-Pack-Context': str(selected.id)})
    assert denied_http.status_code == 403, denied_http.text
    with native_writer(db, case[1], case[2]):
        scope = resolve_context(db, case[1], db.info['branch_context'], selected.id)
        cleanup = install(db, scope, policy=native_srm_policy(pack).policy)
        try:
            with pytest.raises(HTTPException) as denied:
                original_lots(db, case[1], 1)
            assert denied.value.status_code == 403
        finally:
            cleanup()
