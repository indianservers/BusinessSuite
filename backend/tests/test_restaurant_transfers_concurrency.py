"""Independent real PostgreSQL transactions cannot double-seat a destination."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4
from sqlalchemy import select
from tests.test_pms_workflow_postgresql import live, race
from tests.test_restaurant_concurrency import configured
from app.apps.srm.models import SRMSalesOrderLine, SRMInventoryMovement, SRMInvoice, SRMReceipt
from app.business_packs.restaurant.models import RestaurantServiceOrder, RestaurantCommand
from app.access.models import AccessPolicy

BASE='/api/v1/srm/restaurant'


def seating(live):
    headers,original=configured(live,unpaid=True)
    with live.factory() as db:
        product=db.query(SRMSalesOrderLine).filter_by(sales_order_id=original['sales_order_id']).one().product_id
    tables=[]
    for name in ('Source A','Source B','Destination'):
        response=live.client.post(BASE+'/tables',headers=headers,json={'request_key':str(uuid4()),'name':name,'capacity':4})
        assert response.status_code==201,response.text
        tables.append(response.json())
    orders=[]
    for table in tables[:2]:
        response=live.client.post(BASE+'/tabs',headers=headers,json={'request_key':str(uuid4()),
            'table_id':table['id'],'expected_table_revision':table['revision'],
            'lines':[{'product_id':product,'quantity':'1','expected_unit_price':'100'}]})
        assert response.status_code==201,response.text
        orders.append(response.json())
    return headers,orders,tables[2]


def body(order,table):
    return {'request_key':str(uuid4()),'expected_revision':order['revision'],
        'destination_table_id':table['id'],'expected_destination_revision':table['revision']}


def proof(live,table):
    with live.factory() as db:
        assert db.query(RestaurantServiceOrder).filter_by(table_id=table['id'],state='open').count()==1
        assert db.query(RestaurantCommand).filter_by(action='tab.transfer').count()==1
        assert db.query(SRMInvoice).count()==db.query(SRMReceipt).count()==0
        assert db.query(SRMInventoryMovement).filter_by(movement_type='restaurant_kitchen').count()==0


def test_competing_tabs_cannot_move_onto_the_same_destination(live):
    headers,orders,table=seating(live)
    calls=[lambda order=order:live.client.post(BASE+f"/tabs/{order['id']}/transfer",headers=headers,json=body(order,table)) for order in orders]
    results=race(*calls)
    assert sorted(item.status_code for item in results)==[200,409],[item.text for item in results]
    proof(live,table)


def test_same_transfer_parallel_replay_has_one_seating_transition(live):
    headers,orders,table=seating(live);data=body(orders[0],table)
    call=lambda:live.client.post(BASE+f"/tabs/{orders[0]['id']}/transfer",headers=headers,json=data)
    results=race(call,call)
    assert [item.status_code for item in results]==[200,200],[item.text for item in results]
    assert results[0].json()==results[1].json()
    proof(live,table)


def test_native_transfer_rights_revoked_during_company_wait_do_not_move_tab(live,monkeypatch):
    from app.business_packs.restaurant import tabs
    from app.core.company_writer import lock_company_writer
    headers,orders,table=seating(live);order=orders[0]
    with live.factory() as db:
        actor=db.get(RestaurantServiceOrder,order['id']).created_by
    waiting=Event();original=tabs.lock_tenant
    def observed(db,actor):
        waiting.set();return original(db,actor)
    monkeypatch.setattr(tabs,'lock_tenant',observed)
    with live.factory() as blocker:
        lock_company_writer(blocker,1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(lambda:live.client.post(BASE+f"/tabs/{order['id']}/transfer",headers=headers,json=body(order,table)))
            assert waiting.wait(timeout=20),'Transfer did not reach actual company writer wait'
            policy=AccessPolicy.__table__
            row=blocker.connection().execute(select(policy.c.id,policy.c.grants).where(policy.c.company_id==1,policy.c.user_id==actor)).mappings().one()
            grants={**row['grants'],'srm':{**row['grants']['srm'],'actions':['view']}}
            blocker.connection().execute(policy.update().where(policy.c.id==row['id']).values(grants=grants,version=policy.c.version+1))
            blocker.commit()
            response=pending.result(timeout=40)
            assert response.status_code==403,response.text
    with live.factory() as db:
        assert db.get(RestaurantServiceOrder,order['id']).table_id==order['table_id']
        assert db.query(RestaurantCommand).filter_by(action='tab.transfer').count()==0
