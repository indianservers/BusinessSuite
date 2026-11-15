"""Table moves preserve actual canonical charges, money, stock and tickets."""
from uuid import uuid4
import pytest
from sqlalchemy import select
from app.apps.srm.models import SRMSalesOrder, SRMSalesOrderLine, SRMInvoice, SRMInvoiceLine, SRMReceipt, SRMReceiptAllocation, SRMInventoryMovement, SRMInventoryBalance
from app.apps.srm.service_checkout_models import POSServiceCheckout, POSCheckoutLine, POSCheckoutPayment
from app.business_packs.restaurant.models import RestaurantServiceOrder, RestaurantKitchenTicket, RestaurantKitchenLine, RestaurantKitchenIssue
from tests.test_restaurant_settlement import settlement, unpaid, scenario, catalog, directory_identity, bill_input
from tests.test_restaurant_tabs import BASE, data
from tests.test_restaurant_kitchen import post, staff


def canonical(db):
    return {model.__tablename__: [dict(row) for row in db.connection().execute(select(model.__table__).order_by(model.id)).mappings()]
        for model in (SRMSalesOrder,SRMSalesOrderLine,SRMInvoice,SRMInvoiceLine,SRMReceipt,SRMReceiptAllocation,
            POSServiceCheckout,POSCheckoutLine,POSCheckoutPayment,SRMInventoryMovement,SRMInventoryBalance,
            RestaurantKitchenTicket,RestaurantKitchenLine,RestaurantKitchenIssue)}


def destination(client,case):
    return post(client,case['headers'],'/tables',{'request_key':str(uuid4()),'name':'Destination '+uuid4().hex[:8],'capacity':4})


def transfer_body(order,table):
    return {'request_key':str(uuid4()),'expected_revision':order['revision'],
        'destination_table_id':table['id'],'expected_destination_revision':table['revision']}


@pytest.mark.parametrize('stage',['unbilled','billed','partial','paid'])
def test_transfer_preserves_same_native_source_money_and_kitchen_at_all_open_billing_stages(client,db,settlement,stage):
    case=settlement
    if stage!='unbilled':
        result=post(client,case['headers'],f"/tabs/{case['order']['id']}/bill",bill_input(case))
        if stage in ('partial','paid'):
            result=post(client,case['headers'],f"/tabs/{case['order']['id']}/payments",{
                'request_key':str(uuid4()),'expected_revision':result['checkout']['revision'],'pos_session_id':case['register'],
                'payment':{'payment_key':str(uuid4()),'method':'cash','amount':'50' if stage=='partial' else '118'}})
    order=client.get(BASE+f"/orders/{case['order']['id']}",headers=case['headers']).json()
    table=destination(client,case)
    before=canonical(db)
    digest=db.get(RestaurantServiceOrder,order['id']).source_sha256
    body=transfer_body(order,table)
    result=post(client,case['headers'],f"/tabs/{order['id']}/transfer",body,200)
    assert result['table_id']==table['id'] and result['sales_order_id']==order['sales_order_id']
    assert result['revision']==order['revision']+1 and result['items']==order['items']
    assert post(client,case['headers'],f"/tabs/{order['id']}/transfer",body,200)==result
    assert canonical(db)==before
    assert db.get(RestaurantServiceOrder,order['id']).source_sha256==digest
    occupancy={row['id']:row['occupied'] for row in client.get(BASE+'/tables',headers=case['headers']).json()['items']}
    assert occupancy[order['table_id']] is False and occupancy[table['id']] is True
    chef,_=staff(db,case,'chef')
    kitchen=client.get(BASE+'/kitchen',headers=chef)
    assert kitchen.status_code==200,kitchen.text
    ticket=next(item for item in kitchen.json()['items'] if item['id']==case['ticket']['id'])
    assert ticket['table']=={'id':table['id'],'name':table['name']}
    assert not {'invoice','customer','payments','total','currency'} & set(ticket)


@pytest.mark.parametrize('fault',['same','stale_order','stale_destination','occupied','inactive','foreign_id','reused_key'])
def test_transfer_invalid_destinations_and_replays_are_atomic(client,db,settlement,fault):
    case=settlement;order=case['order'];table=destination(client,case);body=transfer_body(order,table)
    if fault=='same':body['destination_table_id']=order['table_id']
    elif fault=='stale_order':body['expected_revision']=999
    elif fault=='stale_destination':body['expected_destination_revision']=999
    elif fault=='foreign_id':body['destination_table_id']=99999999
    elif fault=='inactive':
        client.put(BASE+f"/tables/{table['id']}",headers=case['headers'],json={'request_key':str(uuid4()),
            'name':table['name'],'capacity':4,'active':False,'expected_revision':table['revision']})
    elif fault=='occupied':
        post(client,case['headers'],'/tabs',data(case,table_id=table['id'],expected_table_revision=table['revision']))
    elif fault=='reused_key':
        body['request_key']=str(uuid4())
        post(client,case['headers'],f"/tabs/{order['id']}/transfer",body,200)
        body['expected_revision']+=1
    before=canonical(db)
    current=client.get(BASE+f"/orders/{order['id']}",headers=case['headers']).json()
    response=client.post(BASE+f"/tabs/{order['id']}/transfer",headers=case['headers'],json=body)
    assert response.status_code==(404 if fault=='foreign_id' else 409),response.text
    assert canonical(db)==before
    assert client.get(BASE+f"/orders/{order['id']}",headers=case['headers']).json()==current


@pytest.mark.parametrize('role',['chef','server','cashier'])
def test_nonmanager_pack_roles_cannot_transfer_even_with_native_order_create(client,db,settlement,role):
    case=settlement;table=destination(client,case);headers,_=staff(db,case,role)
    before=canonical(db)
    response=client.post(BASE+f"/tabs/{case['order']['id']}/transfer",headers=headers,json=transfer_body(case['order'],table))
    assert response.status_code==403,response.text
    assert canonical(db)==before



def test_destination_in_another_genuine_context_is_not_visible_or_mutated(client,db,settlement):
    from tests.test_business_pack_http_integration import grant, native_actor
    from app.models.company import Branch
    from app.business_packs.models import PackContext
    case=settlement
    branch=Branch(company_id=1,name='Foreign Restaurant seating branch')
    db.add(branch);db.flush()
    origin=db.get(PackContext,case['context'])
    context=PackContext(company_id=1,branch_id=branch.id,activation_id=origin.activation_id,
        pack_key='restaurant',pack_version=1,state='active')
    db.add(context);db.commit()
    foreign_headers,foreign_actor=native_actor(db,branch.id)
    grant(db,foreign_actor,branch.id,'restaurant','restaurant_manager',context)
    foreign_headers={**foreign_headers,'X-Suite-Pack-Context':str(context.id)}
    table=post(client,foreign_headers,'/tables',{'request_key':str(uuid4()),'name':'Private other context','capacity':2})
    before=canonical(db)
    response=client.post(BASE+f"/tabs/{case['order']['id']}/transfer",headers=case['headers'],json=transfer_body(case['order'],table))
    assert response.status_code==404,response.text
    assert canonical(db)==before
    foreign=client.get(BASE+'/tables',headers=foreign_headers).json()['items'][0]
    assert foreign['revision']==1 and foreign['occupied'] is False



def test_fully_paid_and_served_closed_tab_cannot_move_or_reopen_table(client,db,settlement):
    case=settlement
    billed=post(client,case['headers'],f"/tabs/{case['order']['id']}/bill",bill_input(case))
    post(client,case['headers'],f"/tabs/{case['order']['id']}/payments",{
        'request_key':str(uuid4()),'expected_revision':billed['checkout']['revision'],'pos_session_id':case['register'],
        'payment':{'payment_key':str(uuid4()),'method':'cash','amount':'118'}})
    ticket=case['ticket']
    for action in ('prepare','ready','serve'):
        ticket=post(client,case['headers'],f"/tickets/{ticket['id']}/{action}",{
            'request_key':str(uuid4()),'expected_revision':ticket['revision']},200)
    order=client.get(BASE+f"/orders/{case['order']['id']}",headers=case['headers']).json()
    assert order['state']=='served'
    table=destination(client,case);before=canonical(db)
    response=client.post(BASE+f"/tabs/{order['id']}/transfer",headers=case['headers'],json=transfer_body(order,table))
    assert response.status_code==409,response.text
    assert canonical(db)==before
    assert all(not row['occupied'] for row in client.get(BASE+'/tables',headers=case['headers']).json()['items'])
