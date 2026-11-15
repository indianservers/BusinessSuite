"""Exact native quantity chain; currency retains canonical cent rounding."""
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

import pytest
from app.apps.srm.models import SRMSalesOrderLine, SRMInvoiceLine, SRMInventoryMovement, SRMReceipt
from app.apps.srm.service_checkout_models import POSCheckoutLine
from app.business_packs.pharma.models import PharmaBatchAllocation
from tests.test_pharma_fefo import lots, sale, lot_quantities
from tests.test_pharma_receipts import pharma, balance, counts
from tests.test_service_checkout import scenario, catalog, directory_identity


@pytest.mark.parametrize('quantity', ['0.001', '0.125', '3.125'])
def test_three_decimal_paid_dispensing_preserves_every_native_source_and_replay(client, db, lots, quantity):
    case = lots[0]
    amount = Decimal(quantity)
    base = (amount * 100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    tax = (base * Decimal('.18')).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    total = base + tax
    payload = sale(lots, quantity)
    payload['expected_total'] = str(total)
    payload['payments'] = [{'payment_key': str(uuid4()), 'method': 'cash', 'amount': str(total)}]
    stock = balance(db, case)
    response = client.post('/api/v1/srm/service-checkout', headers=case[0], json=payload)
    assert response.status_code == 201, response.text
    result = response.json()
    assert Decimal(result['invoice']['total']) == Decimal(result['invoice']['paid']) == total
    assert Decimal(result['invoice']['balance']) == 0
    assert Decimal(result['lines'][0]['quantity']) == amount
    db.expire_all()
    mapped = db.query(POSCheckoutLine).filter_by(checkout_id=result['id']).one()
    source = db.get(SRMSalesOrderLine, mapped.sales_order_line_id)
    charge = db.get(SRMInvoiceLine, mapped.invoice_line_id)
    assert source.quantity == charge.quantity == mapped.quantity == amount
    assert source.line_total == charge.line_total == total
    allocations = db.query(PharmaBatchAllocation).filter_by(sales_order_line_id=source.id).order_by(PharmaBatchAllocation.id).all()
    assert sum((row.quantity for row in allocations), Decimal(0)) == amount
    assert [(row.batch_id, row.quantity) for row in allocations] == (
        [(lots[1][1]['batch_id'], amount)] if amount <= 3 else
        [(lots[1][1]['batch_id'], Decimal(3)), (lots[1][0]['batch_id'], amount - 3)])
    movement = db.get(SRMInventoryMovement, allocations[0].movement_id)
    assert movement.quantity_out == amount and movement.quantity_in == 0
    assert movement.value == base
    assert db.query(SRMReceipt).one().amount == total
    assert balance(db, case) == stock - amount
    assert lot_quantities(db, lots) == [Decimal(2) - max(amount-3, Decimal(0)), max(Decimal(3)-amount, Decimal(0))]
    before = counts(db), lot_quantities(db, lots), db.query(PharmaBatchAllocation).count()
    replay = client.post('/api/v1/srm/service-checkout', headers=case[0], json=payload)
    assert replay.status_code == 201 and replay.json() == result
    assert (counts(db), lot_quantities(db, lots), db.query(PharmaBatchAllocation).count()) == before


@pytest.mark.parametrize('quantity', ['0.0001', '0.1255', 'NaN', 'Infinity', '0', '-0.001'])
def test_unsupported_dispensing_precision_has_no_native_side_effects(client, db, lots, quantity):
    before = counts(db), lot_quantities(db, lots), balance(db, lots[0])
    response = client.post('/api/v1/srm/service-checkout', headers=lots[0][0], json=sale(lots, quantity))
    assert response.status_code == 422, response.text
    assert (counts(db), lot_quantities(db, lots), balance(db, lots[0])) == before


@pytest.mark.parametrize('path', ['checkout', 'order'])
def test_legacy_non_pharma_contract_does_not_gain_third_decimal(client, db, scenario, path):
    from app.apps.srm.models import SRMSalesOrder, SRMInventoryBalance
    headers = scenario[2][0]
    product = scenario[2][2][0]
    before = [(row.id, row.quantity) for row in db.query(SRMInventoryBalance).order_by(SRMInventoryBalance.id)]
    if path == 'checkout':
        payload = scenario[3](payments=False).model_dump(mode='json')
        payload['lines'] = [{**payload['lines'][0], 'quantity': '0.125'}]
        response = client.post('/api/v1/srm/service-checkout', headers=headers, json=payload)
    else:
        response = client.post('/api/v1/srm/sales-orders', headers=headers,
                               json={'title': 'Legacy precision remains unchanged', 'customer_id': 101,
                                     'lines': [{'product_id': product, 'quantity': '0.125', 'unit_price': '100'}]})
    assert response.status_code == 422, response.text
    assert db.query(SRMSalesOrder).count() == 0
    assert [(row.id, row.quantity) for row in db.query(SRMInventoryBalance).order_by(SRMInventoryBalance.id)] == before


def test_pharma_service_does_not_inherit_medicine_quantity_precision(client, db, lots):
    from app.apps.srm.models import SRMProduct
    from app.business_packs.models import PackMasterAvailability
    case = lots[0]
    product = db.query(SRMProduct).filter_by(product_type='service').one()
    db.add(PackMasterAvailability(company_id=1, branch_id=case[2], context_id=case[3],
                                  resource_table='srm_products', resource_key=str(product.id), active=True))
    db.commit()
    payload = sale(lots, '0.125')
    payload['lines'][0].update(product_id=product.id, line_kind='unscheduled_service')
    before = counts(db), balance(db, case)
    response = client.post('/api/v1/srm/service-checkout', headers=case[0], json=payload)
    assert response.status_code == 422, response.text
    assert (counts(db), balance(db, case)) == before


@pytest.mark.parametrize('quantity', ['0.125', '0.0001'])
@pytest.mark.parametrize('operation', ['add', 'update'])
def test_native_public_line_writes_reject_unsupported_quantity_before_mutation(client, db, scenario, quantity, operation):
    from app.apps.srm.models import SRMSalesOrder, SRMInventoryBalance
    headers = scenario[2][0]
    product = scenario[2][2][0]
    created = client.post('/api/v1/srm/sales-orders', headers=headers,
                          json={'title': 'Legacy line precision guard', 'customer_id': 101,
                                'lines': [{'product_id': product, 'quantity': '1', 'unit_price': '100'}]})
    assert created.status_code == 201, created.text
    order = created.json()
    before = [(row.id, row.quantity) for row in db.query(SRMInventoryBalance).order_by(SRMInventoryBalance.id)]
    original = db.get(SRMSalesOrderLine, order['lines'][0]['id']).quantity
    url = f"/api/v1/srm/sales-orders/{order['id']}/lines"
    if operation == 'add':
        response = client.post(url, headers=headers, json={'product_id': product, 'quantity': quantity, 'unit_price': '100'})
    else:
        response = client.patch(url+f"/{order['lines'][0]['id']}", headers=headers, json={'quantity': quantity})
    assert response.status_code == 422, response.text
    db.expire_all()
    assert len(db.get(SRMSalesOrder, order['id']).lines) == 1
    assert db.get(SRMSalesOrderLine, order['lines'][0]['id']).quantity == original
    assert [(row.id, row.quantity) for row in db.query(SRMInventoryBalance).order_by(SRMInventoryBalance.id)] == before


@pytest.mark.parametrize('model', ['order', 'checkout'])
def test_public_quantity_contract_documents_pharma_only_precision_and_keeps_maximum(model):
    from pydantic import ValidationError
    from app.apps.srm.schemas import SRMSalesOrderLineInput
    from app.apps.srm.service_checkout_schemas import CheckoutLineInput
    cls = SRMSalesOrderLineInput if model == 'order' else CheckoutLineInput
    schema = cls.model_json_schema()['properties']['quantity']
    assert 'only for authorized Pharma' in schema['description']
    values = {} if model == 'order' else {'client_line_key': str(uuid4()), 'line_kind': 'product', 'product_id': 1}
    assert cls.model_validate({**values, 'quantity': '1000000000'}).quantity == Decimal('1000000000')
    for bad in ['1000000000.001', '0.0001', 'NaN', 'Infinity']:
        with pytest.raises(ValidationError):
            cls.model_validate({**values, 'quantity': bad})


def test_native_update_preserves_historical_ten_digit_integer_capacity(client, db, scenario):
    headers = scenario[2][0]
    service = scenario[2][2][1]
    created = client.post('/api/v1/srm/sales-orders', headers=headers,
                          json={'title': 'Historical native quantity range', 'customer_id': 101,
                                'lines': [{'product_id': service, 'quantity': '1', 'unit_price': '0'}]})
    assert created.status_code == 201, created.text
    order = created.json()
    ident = order['lines'][0]['id']
    url = f"/api/v1/srm/sales-orders/{order['id']}/lines/{ident}"
    response = client.patch(url, headers=headers, json={'quantity': '9999999999.99'})
    assert response.status_code == 200, response.text
    db.expire_all()
    assert db.get(SRMSalesOrderLine, ident).quantity == Decimal('9999999999.99')
    for invalid in ['10000000000', '9999999999.999', '0.0001']:
        denied = client.patch(url, headers=headers, json={'quantity': invalid})
        assert denied.status_code == 422, denied.text
        db.expire_all()
        assert db.get(SRMSalesOrderLine, ident).quantity == Decimal('9999999999.99')
