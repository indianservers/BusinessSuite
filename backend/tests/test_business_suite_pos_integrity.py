"""P0 regression scenarios against the real POS API and isolated database."""
from decimal import Decimal
from uuid import uuid4
import pytest
from tests.test_contact_directory import directory_identity
from app.apps.srm.models import SRMProduct, SRMSalesOrder, SRMInventoryMovement


@pytest.fixture
def catalog(client, db, superuser_headers):
    headers = superuser_headers
    warehouse = client.post('/api/v1/srm/inventory/warehouses', headers=headers,
                            json={'warehouse_name': 'QA isolated warehouse', 'warehouse_code': 'QA-POS'})
    assert warehouse.status_code == 201, warehouse.text
    wid = warehouse.json()['id']
    items = []
    for sku, kind, tracked in [('QA-STOCK', 'stock', True), ('QA-SERVICE', 'service', False), ('QA-OTHER', 'stock', True)]:
        response = client.post('/api/v1/srm/inventory/items', headers=headers, json={
            'sku': sku, 'item_name': sku, 'product_type': kind, 'track_inventory': tracked,
            'default_warehouse_id': wid, 'sales_rate': 100, 'gst_rate': 18,
        })
        assert response.status_code == 201, response.text
        items.append(response.json()['id'])
        if tracked:
            opened = client.post('/api/v1/srm/inventory/opening-stock', headers=headers,
                                 json={'product_id': items[-1], 'warehouse_id': wid, 'quantity': 5, 'rate': 40})
            assert opened.status_code == 201, opened.text
    return headers, wid, items


def sell(client, catalog, index=0, **overrides):
    headers, _, items = catalog
    line = {'product_id': items[index], 'description': 'QA canonical sale', 'service_type': 'product' if index != 1 else 'service',
            'quantity': 1, 'unit_price': 100, 'tax_amount': 18, **overrides}
    key = str(uuid4())
    return client.post('/api/v1/srm/sales-orders', headers=headers, json={
        'title': 'QA isolated POS sale', 'order_number': 'POS-QA-'+key,
        'metadata_json': {'source': 'pos', 'pos_sale_id': key}, 'lines': [line],
    })


def refund(client, catalog, sale, **overrides):
    return client.post('/api/v1/srm/pos/returns', headers=catalog[0], json={
        'sales_order_id': sale['id'], 'reason': 'Isolated QA return',
        'lines': [{'sales_order_line_id': sale['lines'][0]['id'], 'quantity': 1, **overrides}],
    })


def test_tc054_stock_type_cannot_be_spoofed_as_service(client, db, catalog):
    response = sell(client, catalog, service_type='service')
    assert response.status_code == 201, response.text
    db.expire_all()
    assert db.get(SRMProduct, catalog[2][0]).current_quantity == Decimal('4')


@pytest.mark.parametrize('quantity', [-1, 0])
def test_tc106_invalid_quantity_is_atomic(client, db, catalog, quantity):
    response = sell(client, catalog, quantity=quantity)
    assert response.status_code == 422, response.text
    assert db.query(SRMSalesOrder).count() == 0
    assert db.get(SRMProduct, catalog[2][0]).current_quantity == Decimal('5')


@pytest.mark.parametrize('field', ['unit_price', 'tax_amount', 'discount_amount'])
def test_tc107_negative_money_is_rejected(client, db, catalog, field):
    response = sell(client, catalog, **{field: -1})
    assert response.status_code == 422, response.text
    assert db.query(SRMSalesOrder).count() == 0


def test_tc076_pos_totals_and_tax_are_server_authoritative(client, db, catalog):
    response = sell(client, catalog, tax_amount=0, line_total=1)
    assert response.status_code == 201, response.text
    assert Decimal(str(response.json()['total_amount'])) == Decimal('118')
    assert Decimal(str(response.json()['tax_amount'])) == Decimal('18')


def test_tc060_service_does_not_move_stock(client, db, catalog):
    before = db.query(SRMInventoryMovement).count()
    response = sell(client, catalog, index=1, service_type='product')
    assert response.status_code == 201, response.text
    assert db.query(SRMInventoryMovement).count() == before


def test_tc059_oversell_rolls_back_order_and_stock(client, db, catalog):
    response = sell(client, catalog, quantity=6)
    assert response.status_code == 409, response.text
    assert db.query(SRMSalesOrder).count() == 0
    assert db.get(SRMProduct, catalog[2][0]).current_quantity == Decimal('5')


def test_tc030_nonrestocked_return_still_consumes_refundable_quantity(client, db, catalog):
    sale = sell(client, catalog).json()
    first = refund(client, catalog, sale, restock=False)
    assert first.status_code == 201, first.text
    second = refund(client, catalog, sale, restock=False)
    assert second.status_code == 409, second.text


def test_tc073_return_cannot_substitute_another_product(client, db, catalog):
    sale = sell(client, catalog).json()
    response = refund(client, catalog, sale, product_id=catalog[2][2])
    assert response.status_code == 422, response.text
    db.expire_all()
    assert db.get(SRMProduct, catalog[2][2]).current_quantity == Decimal('5')


def test_tc040_refund_uses_original_discount_and_tax_snapshot(client, db, catalog):
    response = sell(client, catalog, discount_amount=10, tax_amount=16.2)
    assert response.status_code == 201, response.text
    sale = response.json()
    db.get(SRMProduct, catalog[2][0]).gst_rate = 28
    db.commit()
    returned = refund(client, catalog, sale)
    assert returned.status_code == 201, returned.text
    assert Decimal(str(returned.json()['refund_amount'])) == Decimal(str(sale['total_amount']))
    assert Decimal(str(returned.json()['tax_amount'])) == Decimal('16.2')


def test_tc108_refund_cannot_exceed_original_sale_value(client, db, catalog):
    sale = sell(client, catalog).json()
    response = refund(client, catalog, sale, line_total=10000, tax_amount=9000)
    assert response.status_code == 422, response.text


def test_tc109_inactive_catalog_item_cannot_be_sold(client, db, catalog):
    db.get(SRMProduct, catalog[2][0]).active = False
    db.commit()
    response = sell(client, catalog)
    assert response.status_code in {404, 409, 422}, response.text


def test_tc110_malformed_warehouse_is_validation_error(client, db, catalog):
    response = sell(client, catalog, metadata_json={'warehouse_id': 'not-an-id'})
    assert response.status_code == 422, response.text


def test_tc027_bill_discount_is_allocated_before_each_item_tax(client, db, catalog):
    db.get(SRMProduct,catalog[2][1]).gst_rate = 5
    db.commit()
    response = client.post('/api/v1/srm/sales-orders', headers=catalog[0], json={
        'title':'Mixed discounted POS order', 'discount_amount':20,
        'metadata_json':{'source':'pos','pos_sale_id':str(uuid4())},
        'lines':[{'product_id':pid,'description':'Mixed item','quantity':1,'unit_price':100,'tax_amount':999,'line_total':999} for pid in catalog[2][:2]],
    })
    assert response.status_code == 201, response.text
    assert Decimal(str(response.json()['total_amount'])) == Decimal('200.70')
    assert [Decimal(str(row['tax_amount'])) for row in response.json()['lines']] == [Decimal('16.20'),Decimal('4.50')]


@pytest.mark.parametrize('quantity',['0.001','1.234'])
def test_tc111_unsupported_sale_precision_cannot_be_silently_truncated(client, db, catalog, quantity):
    response = sell(client,catalog,quantity=quantity)
    assert response.status_code == 422, response.text


def test_tc071_foreign_customer_cannot_be_attached_to_pos_order(client, db, catalog):
    from app.apps.crm.models import CRMCompany
    foreign = CRMCompany(organization_id=2,name='Different tenant buyer')
    db.add(foreign);db.commit()
    response = client.post('/api/v1/srm/sales-orders',headers=catalog[0],json={
        'title':'Foreign buyer attempt','customer_id':foreign.id,
        'metadata_json':{'source':'pos','pos_sale_id':str(uuid4())},
        'lines':[{'product_id':catalog[2][0],'description':'Own stock','quantity':1,'unit_price':100}],
    })
    assert response.status_code in {403,404,422}, response.text
    assert db.query(SRMSalesOrder).count() == 0


def test_tc073_return_customer_cannot_be_replaced(client, db, catalog):
    sale = sell(client,catalog).json()
    response = client.post('/api/v1/srm/pos/returns',headers=catalog[0],json={
        'sales_order_id':sale['id'],'customer_id':999999,
        'lines':[{'sales_order_line_id':sale['lines'][0]['id'],'quantity':1}],
    })
    assert response.status_code == 422, response.text


def test_tc092_zero_price_product_is_zero_billed_but_still_issues_stock(client, db, catalog):
    response = sell(client,catalog,unit_price=0,tax_amount=99,line_total=99)
    assert response.status_code == 201, response.text
    assert Decimal(str(response.json()['total_amount'])) == 0
    assert Decimal(str(response.json()['tax_amount'])) == 0
    db.expire_all()
    assert db.get(SRMProduct,catalog[2][0]).current_quantity == Decimal('4')


def test_tc093_fractional_quantity_stock_and_money_remain_consistent(client, db, catalog):
    response = sell(client,catalog,quantity='0.50',tax_amount=0,line_total=1)
    assert response.status_code == 201, response.text
    assert Decimal(str(response.json()['lines'][0]['quantity'])) == Decimal('.50')
    assert Decimal(str(response.json()['total_amount'])) == Decimal('59')
    db.expire_all()
    assert db.get(SRMProduct,catalog[2][0]).current_quantity == Decimal('4.50')
