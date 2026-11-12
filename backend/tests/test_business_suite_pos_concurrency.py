"""Competing real PostgreSQL transactions; no shared session or SQLite lock substitute."""
from uuid import uuid4
from tests.test_pms_workflow_postgresql import live, race
from app.apps.srm.models import SRMProduct, SRMSalesOrder, SRMInventoryMovement, SRMPOSReturn


def seed(live):
    headers = live.oh
    response = live.client.post('/api/v1/srm/inventory/warehouses', headers=headers,
                                json={'warehouse_name':'Race warehouse','warehouse_code':'RACE'})
    assert response.status_code == 201, response.text
    wid = response.json()['id']
    response = live.client.post('/api/v1/srm/inventory/items', headers=headers,
                               json={'sku':'RACE-ITEM','item_name':'Race item','track_inventory':True,
                                     'default_warehouse_id':wid,'sales_rate':100,'gst_rate':18})
    assert response.status_code == 201, response.text
    pid = response.json()['id']
    response = live.client.post('/api/v1/srm/inventory/opening-stock', headers=headers,
                               json={'product_id':pid,'warehouse_id':wid,'quantity':1,'rate':40})
    assert response.status_code == 201, response.text
    return pid


def sale(live, pid, key):
    return live.client.post('/api/v1/srm/sales-orders', headers=live.oh, json={
        'title':'Concurrent QA sale', 'order_number':'POS-'+key,
        'metadata_json':{'source':'pos','pos_sale_id':key},
        'lines':[{'product_id':pid,'description':'Race item','quantity':1,'unit_price':100,'tax_amount':18}],
    })


def test_tc059_two_checkouts_cannot_sell_the_last_unit_twice(live):
    pid = seed(live)
    results = race(lambda:sale(live,pid,str(uuid4())), lambda:sale(live,pid,str(uuid4())))
    assert sorted(row.status_code for row in results) == [201,409], [row.text for row in results]
    with live.factory() as session:
        assert session.get(SRMProduct,pid).current_quantity == 0
        assert session.query(SRMSalesOrder).count() == 1
        assert session.query(SRMInventoryMovement).filter_by(product_id=pid,movement_type='pos_sale').count() == 1


def test_tc082_duplicate_concurrent_checkout_has_one_order_and_stock_movement(live):
    pid, key = seed(live), str(uuid4())
    results = race(lambda:sale(live,pid,key),lambda:sale(live,pid,key))
    assert [row.status_code for row in results] == [201,201], [row.text for row in results]
    assert results[0].json()['id'] == results[1].json()['id']
    with live.factory() as session:
        assert session.query(SRMSalesOrder).count() == 1
        assert session.query(SRMInventoryMovement).filter_by(product_id=pid,movement_type='pos_sale').count() == 1


def test_tc030_concurrent_nonrestocked_refunds_cannot_exceed_original_sale(live):
    pid = seed(live)
    sold = sale(live,pid,str(uuid4()))
    assert sold.status_code == 201, sold.text
    order = sold.json()
    def refund():
        return live.client.post('/api/v1/srm/pos/returns',headers=live.oh,json={
            'sales_order_id':order['id'],'reason':'QA concurrency','lines':[{
                'sales_order_line_id':order['lines'][0]['id'],'quantity':1,'restock':False,
            }],
        })
    results = race(refund,refund)
    assert sorted(row.status_code for row in results) == [201,409], [row.text for row in results]
    with live.factory() as session:
        assert session.query(SRMPOSReturn).count() == 1
        assert session.get(SRMProduct,pid).current_quantity == 0
