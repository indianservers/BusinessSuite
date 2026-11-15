"""Retail incoming stock uses native GRNs, balances and immutable movements."""
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4
import pytest
from app.apps.srm.models import SRMGoodsReceipt, SRMGoodsReceiptLine, SRMInventoryBalance, SRMInventoryMovement, SRMProduct
from tests.test_retail_return_http import retail_setup, scenario, catalog, directory_identity
from tests.test_retail_workflows import cart

BASE = '/api/v1/srm/retail'


def receipt(setup):
    return {'request_key': str(uuid4()), 'product_id': setup[5], 'warehouse_id': setup[6],
            'quantity': '2.50', 'unit_cost': '20.00', 'received_date': date.today().isoformat()}


def test_native_receipt_replay_stock_projection_and_actual_daily_transactions(client, db, retail_setup):
    data = receipt(retail_setup)
    first = client.post(BASE + '/stock-receipts', headers=retail_setup[0], json=data)
    assert first.status_code == 201, first.text
    replay = client.post(BASE + '/stock-receipts', headers=retail_setup[0], json=data)
    assert replay.status_code == 201, replay.text
    assert replay.json() == first.json()
    changed = client.post(BASE + '/stock-receipts', headers=retail_setup[0], json={**data, 'quantity': '3'})
    assert changed.status_code == 409, changed.text
    assert db.query(SRMGoodsReceipt).count() == db.query(SRMGoodsReceiptLine).count() == 1
    assert db.query(SRMInventoryBalance).filter_by(product_id=retail_setup[5], warehouse_id=retail_setup[6]).one().quantity == Decimal('7.5')
    assert db.get(SRMProduct, retail_setup[5]).current_quantity == Decimal('7.5')
    sale = client.post('/api/v1/srm/service-checkout', headers=retail_setup[0], json=cart(retail_setup, 'card'))
    assert sale.status_code == 201, sale.text
    stock = client.get(BASE + '/stock', headers=retail_setup[0])
    assert stock.status_code == 200, stock.text
    item = next(row for row in stock.json()['items'] if row['product_id'] == retail_setup[5])
    assert Decimal(item['stock']['available_quantity']) == Decimal('6.5')
    report = client.get(BASE + '/reports/daily', headers=retail_setup[0], params={'day': date.today().isoformat()})
    assert report.status_code == 200, report.text
    assert report.json()['sales'] == [{'currency': 'INR', 'count': 1, 'gross': '118.00', 'tax': '18.00'}]
    assert report.json()['collections'] == [{'currency': 'INR', 'method': 'card', 'amount': '118.00'}]
    assert len(report.json()['stock_movements']) == 2


@pytest.mark.parametrize('case', ['future', 'missing_product', 'missing_warehouse', 'service', 'tracking'])
def test_invalid_receipt_has_no_stock_effects(client, db, retail_setup, case):
    data = receipt(retail_setup)
    if case == 'future': data['received_date'] = (date.today() + timedelta(days=1)).isoformat()
    elif case == 'missing_product': data['product_id'] = 999999
    elif case == 'missing_warehouse': data['warehouse_id'] = 999999
    else:
        product = db.get(SRMProduct, retail_setup[5])
        if case == 'service': product.product_type = 'service'
        else: product.serial_tracking = True
        db.commit()
    before = db.query(SRMInventoryMovement).count()
    response = client.post(BASE + '/stock-receipts', headers=retail_setup[0], json=data)
    assert response.status_code in (403, 404, 409, 422), response.text
    assert db.query(SRMGoodsReceipt).count() == 0
    assert db.query(SRMInventoryMovement).count() == before
    assert db.query(SRMInventoryBalance).filter_by(product_id=retail_setup[5], warehouse_id=retail_setup[6]).one().quantity == 5


@pytest.mark.parametrize('pack,role', [('hospital', 'doctor'), ('restaurant', 'chef'), ('construction', 'site_engineer')])
def test_other_pack_cannot_receive_or_report_retail_stock(client, db, retail_setup, pack, role):
    from tests.test_business_pack_http_integration import grant
    context, _ = grant(db, retail_setup[1], retail_setup[2], pack, role)
    headers = {**retail_setup[0], 'X-Suite-Pack-Context': str(context.id)}
    for path in ('/stock', '/reports/daily?day=' + date.today().isoformat()):
        response = client.get(BASE + path, headers=headers)
        assert response.status_code == 403, response.text
    response = client.post(BASE + '/stock-receipts', headers=headers, json=receipt(retail_setup))
    assert response.status_code == 403, response.text
    assert db.query(SRMGoodsReceipt).count() == 0


def test_receipt_late_failure_is_atomic_and_retryable(client, db, retail_setup, monkeypatch):
    from fastapi import HTTPException
    from app.apps.srm.services import commercial_numbering
    original = commercial_numbering.reserve_number
    def refused(*args, **kwargs):
        raise HTTPException(409, 'Synthetic stock posting failure')
    data = receipt(retail_setup)
    monkeypatch.setattr(commercial_numbering, 'reserve_number', refused)
    failed = client.post(BASE + '/stock-receipts', headers=retail_setup[0], json=data)
    assert failed.status_code == 409, failed.text
    assert db.query(SRMGoodsReceipt).count() == db.query(SRMGoodsReceiptLine).count() == 0
    assert db.query(SRMInventoryBalance).filter_by(product_id=retail_setup[5], warehouse_id=retail_setup[6]).one().quantity == 5
    monkeypatch.setattr(commercial_numbering, 'reserve_number', original)
    retried = client.post(BASE + '/stock-receipts', headers=retail_setup[0], json=data)
    assert retried.status_code == 201, retried.text


def test_receipt_sources_cannot_be_rewritten_through_pack_orm(client, db, retail_setup):
    from fastapi import HTTPException
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    from tests.test_srm_native_transaction_operations import native_writer
    response = client.post(BASE + '/stock-receipts', headers=retail_setup[0], json=receipt(retail_setup))
    assert response.status_code == 201, response.text
    with native_writer(db, retail_setup[1], retail_setup[2]):
        scope = resolve_context(db, retail_setup[1], db.info['branch_context'], retail_setup[3])
        cleanup = install(db, scope, policy=native_srm_policy('retail').policy)
        try:
            source = db.get(SRMGoodsReceipt, response.json()['id'])
            source.total_amount = 1
            with pytest.raises(HTTPException): db.flush()
            db.rollback()
        finally: cleanup()


def test_storekeeper_receives_without_checkout_or_financial_rights(client, db, retail_setup):
    from app.business_packs.models import PackUserGrant
    assignment = db.query(PackUserGrant).filter_by(context_id=retail_setup[3], user_id=retail_setup[1].id).one()
    assignment.role = 'storekeeper'
    db.commit()
    response = client.post(BASE + '/stock-receipts', headers=retail_setup[0], json=receipt(retail_setup))
    assert response.status_code == 201, response.text
    report = client.get(BASE + '/reports/daily', headers=retail_setup[0], params={'day': date.today().isoformat()})
    assert report.status_code == 403, report.text
    sale = client.post('/api/v1/srm/service-checkout', headers=retail_setup[0], json=cart(retail_setup))
    assert sale.status_code == 403, sale.text


def test_stock_summary_includes_other_eligible_native_branch_warehouse(client, db, retail_setup):
    from app.apps.srm.models import SRMWarehouse
    from app.business_packs.models import PackMasterAvailability
    from tests.test_srm_native_transaction_operations import native_writer
    with native_writer(db, retail_setup[1], retail_setup[2]):
        warehouse = SRMWarehouse(organization_id=1, warehouse_code='RETAIL-SECOND', warehouse_name='Second native store', active=True)
        db.add(warehouse); db.commit()
        warehouse_id = warehouse.id
    db.add(PackMasterAvailability(company_id=1, branch_id=retail_setup[2], context_id=retail_setup[3],
        resource_table='srm_warehouses', resource_key=str(warehouse_id), active=True))
    db.commit()
    data = {**receipt(retail_setup), 'warehouse_id': warehouse_id}
    received = client.post(BASE + '/stock-receipts', headers=retail_setup[0], json=data)
    assert received.status_code == 201, received.text
    response = client.get(BASE + '/stock', headers=retail_setup[0])
    assert response.status_code == 200, response.text
    product = next(row for row in response.json()['items'] if row['product_id'] == retail_setup[5])
    assert Decimal(product['branch_quantity']) == Decimal('7.5')
    assert {row['warehouse_id']: Decimal(row['available_quantity']) for row in product['warehouses']} == {
        retail_setup[6]: Decimal('5'), warehouse_id: Decimal('2.5')}
    assert Decimal(product['stock']['available_quantity']) == 5


def test_nested_receipt_cannot_commit_an_outer_stock_command(client, db, retail_setup, monkeypatch):
    from app.business_packs.retail import stock_receipts
    from app.apps.srm.services import commercial_numbering
    original = commercial_numbering.reserve_number
    data = receipt(retail_setup)
    nested = stock_receipts.ReceiptInput.model_validate(receipt(retail_setup))
    def recurse(*args, **kwargs):
        return stock_receipts.create(nested, db, retail_setup[1])
    monkeypatch.setattr(commercial_numbering, 'reserve_number', recurse)
    failed = client.post(BASE + '/stock-receipts', headers=retail_setup[0], json=data)
    assert failed.status_code == 409, failed.text
    assert 'nest' in failed.text
    assert db.query(SRMGoodsReceipt).count() == db.query(SRMGoodsReceiptLine).count() == 0
    assert db.query(SRMInventoryBalance).filter_by(product_id=retail_setup[5], warehouse_id=retail_setup[6]).one().quantity == 5
    assert db not in stock_receipts._ACTIVE
    monkeypatch.setattr(commercial_numbering, 'reserve_number', original)
    retry = client.post(BASE + '/stock-receipts', headers=retail_setup[0], json=data)
    assert retry.status_code == 201, retry.text
