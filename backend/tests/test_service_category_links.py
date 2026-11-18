import pytest
from app.apps.srm.service_checkout_models import ServiceBookingPolicy
from app.apps.srm.models import SRMProduct
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer

URL='/api/v1/access/services/employee-categories'
TREE=[{'id':'stylist','name':'Stylist','children':[{'id':'senior','name':'Senior stylist'}]},{'id':'neuro','name':'Neurologist','children':[]}]

def test_service_create_and_bidirectional_assignments(client,db,scenario):
    actor,branch,source,_=scenario;headers=source[0]
    r=client.put(URL,headers=headers,json={'version':0,'categories':TREE})
    assert r.status_code==200,r.text
    payload={'kind':'service','name':'Hair styling','code':'HAIR-STYLE','price':500,'unit':'session','service_scheduling':{'mode':'required','duration':45,'employee_categories':['Stylist']}}
    r=client.post('/api/v1/catalog/items?source=srm',headers=headers,json=payload)
    assert r.status_code==201,r.text
    product=r.json();assert product['service_scheduling']['expected_revision']==1
    r=client.get('/api/v1/access/services/employee-category-services',headers=headers,params={'search':'Hair styling'})
    assert r.status_code==200,r.text
    row=r.json()['items'][0];assert row['category_ids']==['stylist'] and row['duration']==45
    r=client.put(URL,headers=headers,json={'version':1,'categories':TREE,'service_links':[{'service_id':product['id'],'category_ids':['neuro'],'expected_revision':1}]})
    assert r.status_code==200,r.text
    with native_writer(db,actor,branch):
        policy=db.query(ServiceBookingPolicy).filter_by(service_product_id=product['id']).one()
        assert policy.employee_categories==['Neurologist'] and policy.booking_required and policy.default_duration_minutes==45
        revision=policy.revision
    # A category-side update is immediately visible in service-side scheduling.
    r=client.get('/api/v1/srm/service-checkout/options',headers=headers,params={'service_id':product['id']})
    assert r.status_code==200,r.text
    assert r.json()['policy']['employee_categories']==['Neurologist']
    body={k:v for k,v in product.items() if k not in {'id','service_scheduling'}}
    body['service_scheduling']={'mode':'optional','duration':60,'employee_categories':['Stylist > Senior stylist'],'expected_revision':revision}
    r=client.put(f"/api/v1/catalog/items/service/{product['id']}?source=srm",headers=headers,json=body)
    assert r.status_code==200,r.text
    revision=r.json()['service_scheduling']['expected_revision']
    r=client.get('/api/v1/access/services/employee-category-services',headers=headers,params={'search':'Hair styling'})
    assert r.json()['items'][0]['category_ids']==['senior']
    # Delete the relationship without changing timing or deleting the service.
    r=client.put(URL,headers=headers,json={'version':2,'categories':TREE,'service_links':[{'service_id':product['id'],'category_ids':[],'expected_revision':revision}]})
    assert r.status_code==200,r.text
    with native_writer(db,actor,branch):
        policy=db.query(ServiceBookingPolicy).filter_by(service_product_id=product['id']).one()
        assert policy.employee_categories==[] and policy.default_duration_minutes==60 and policy.active


def test_invalid_assignment_rolls_back_service_and_category_changes(client,db,scenario):
    actor,branch,source,_=scenario;headers=source[0]
    payload={'kind':'service','name':'Must roll back','code':'ROLLBACK-SERVICE','price':5,'service_scheduling':{'mode':'optional','duration':30,'employee_categories':['Unknown category']}}
    r=client.post('/api/v1/catalog/items?source=srm',headers=headers,json=payload)
    assert r.status_code==422,r.text
    with native_writer(db,actor,branch):assert db.query(SRMProduct).filter_by(sku='ROLLBACK-SERVICE').first() is None
    # A bad service target must not leave the newly created taxonomy behind.
    r=client.put(URL,headers=headers,json={'version':0,'categories':TREE,'service_links':[{'service_id':999999,'category_ids':['stylist'],'expected_revision':None}]})
    assert r.status_code in (403,404),r.text
    r=client.get(URL,headers=headers)
    assert r.json()['version']==0


def test_category_crud_and_stale_service_revision(client,db,scenario):
    actor,branch,source,_=scenario;headers=source[0]
    r=client.put(URL,headers=headers,json={'version':0,'categories':TREE})
    assert r.status_code==200,r.text
    renamed=[{**TREE[0],'name':'Hair stylist'},TREE[1]]
    r=client.put(URL,headers=headers,json={'version':1,'categories':renamed})
    assert r.status_code==200,r.text
    service_id=source[2][1]
    with native_writer(db,actor,branch):revision=db.query(ServiceBookingPolicy).filter_by(service_product_id=service_id).one().revision
    r=client.put(URL,headers=headers,json={'version':2,'categories':renamed,'service_links':[{'service_id':service_id,'category_ids':['stylist'],'expected_revision':revision+5}]})
    assert r.status_code==409,r.text
    assert client.get(URL,headers=headers).json()['version']==2
    r=client.put(URL,headers=headers,json={'version':2,'categories':[renamed[0]]})
    assert r.status_code==200,r.text
    r=client.put(URL,headers=headers,json={'version':3,'categories':[]})
    assert r.status_code==200,r.text


def test_stale_service_save_rolls_back_item_update(client,db,scenario):
    actor,branch,source,_=scenario;headers=source[0];ident=source[2][1]
    before=client.get(f'/api/v1/catalog/items/service/{ident}?source=srm',headers=headers)
    assert before.status_code==200,before.text
    original=before.json();body={k:v for k,v in original.items() if k!='id'}
    body.update(name='Must not be saved',service_scheduling={'mode':'optional','duration':30,'employee_categories':[],'expected_revision':99999})
    r=client.put(f'/api/v1/catalog/items/service/{ident}?source=srm',headers=headers,json=body)
    assert r.status_code==409,r.text
    after=client.get(f'/api/v1/catalog/items/service/{ident}?source=srm',headers=headers).json()
    assert after['name']==original['name'] and after['version']==original['version']


def test_no_booking_service_still_sells_and_cannot_book(client,db,scenario):
    from app.shared.service_category_links import save_scheduling,SchedulingInput
    from app.apps.srm.service_checkout import checkout
    from app.apps.srm.service_checkout_schemas import CheckoutInput
    from fastapi import HTTPException
    actor,branch,source,basket=scenario;ident=source[2][1]
    with native_writer(db,actor,branch):
        policy=db.query(ServiceBookingPolicy).filter_by(service_product_id=ident).one()
        save_scheduling(db,actor,ident,SchedulingInput(mode='none',duration=30,employee_categories=[],expected_revision=policy.revision))
        db.commit()
        # Disabling appointments must not disable an active service's sale.
        data=basket(False).model_dump(mode='json');data['lines']=data['lines'][1:2]
        data['lines'][0].update(line_kind='unscheduled_service',booking=None)
        result=checkout(CheckoutInput.model_validate(data),db,actor)
        assert result['lines'][0]['appointment_id'] is None
        # Existing booking selections cannot bypass the disabled scheduling policy.
        with pytest.raises(HTTPException) as denied:checkout(basket(False),db,actor)
        assert denied.value.status_code==409
