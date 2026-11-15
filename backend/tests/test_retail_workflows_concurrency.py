"""Independent committed sessions prove Retail retries and duplicate stock receipt."""
from datetime import date
from uuid import uuid4
from fastapi import HTTPException
from tests.test_pms_workflow_postgresql import live, race
from tests.test_stock_resource_concurrency import configured
from app.apps.srm.models import SRMGoodsReceipt, SRMGoodsReceiptLine, SRMInventoryBalance, SRMInventoryMovement, SRMInvoice, SRMReceipt, SRMSalesOrder
from app.apps.srm.service_checkout_models import POSServiceCheckout


def test_concurrent_receipt_replay_creates_one_native_grn(live):
    product, warehouse, headers, _ = configured(live)
    data = {'request_key': str(uuid4()), 'product_id': product, 'warehouse_id': warehouse,
            'quantity': '2', 'unit_cost': '20', 'received_date': date.today().isoformat()}
    call = lambda: live.client.post('/api/v1/srm/retail/stock-receipts', headers=headers, json=data)
    results = race(call, call)
    assert [row.status_code for row in results] == [201, 201], [row.text for row in results]
    assert results[0].json() == results[1].json()
    with live.factory() as db:
        assert db.query(SRMGoodsReceipt).count() == db.query(SRMGoodsReceiptLine).count() == 1
        assert db.query(SRMInventoryMovement).filter_by(movement_type='retail_receipt').count() == 1
        assert db.query(SRMInventoryBalance).filter_by(product_id=product, warehouse_id=warehouse).one().quantity == 3


def test_split_failure_then_identical_retry_in_independent_requests(live, monkeypatch):
    from app.apps.srm.api import router as native
    product, warehouse, headers, payload = configured(live)
    data = payload()
    data['payments'][0]['amount'] = '40'
    data['payments'].append({'payment_key': str(uuid4()), 'method': 'card', 'amount': '78'})
    models = (SRMInvoice, SRMReceipt, SRMSalesOrder, SRMInventoryMovement, POSServiceCheckout)
    with live.factory() as db:
        before = {model: db.query(model).count() for model in models}
    original = native.create_receipt_operation
    calls = []
    def refused(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise HTTPException(409, 'Synthetic second terminal payment failure')
        return original(*args, **kwargs)
    monkeypatch.setattr(native, 'create_receipt_operation', refused)
    failed = live.client.post('/api/v1/srm/service-checkout', headers=headers, json=data)
    assert failed.status_code == 409, failed.text
    with live.factory() as db:
        assert {model: db.query(model).count() for model in models} == before
        assert db.query(SRMInventoryBalance).filter_by(product_id=product, warehouse_id=warehouse).one().quantity == 1
    monkeypatch.setattr(native, 'create_receipt_operation', original)
    retried = live.client.post('/api/v1/srm/service-checkout', headers=headers, json=data)
    assert retried.status_code == 201, retried.text
    replay = live.client.post('/api/v1/srm/service-checkout', headers=headers, json=data)
    assert replay.status_code == 201, replay.text
    assert replay.json() == retried.json()
    with live.factory() as db:
        assert db.query(SRMReceipt).count() == before[SRMReceipt] + 2
        assert db.query(POSServiceCheckout).count() == before[POSServiceCheckout] + 1
        assert db.query(SRMInventoryBalance).filter_by(product_id=product, warehouse_id=warehouse).one().quantity == 0
