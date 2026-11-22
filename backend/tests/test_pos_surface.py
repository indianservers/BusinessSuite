"""Selected POS reads never expose whole masters or other warehouse capacity."""
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import select
from tests.test_stock_resource import stock,scenario,catalog,directory_identity
from tests.test_business_pack_http_integration import native_actor,grant
from app.apps.srm.models import SRMProduct
from app.business_packs.models import PackMasterAvailability,PackContext
BASE='/api/v1/srm/pos'


def test_selected_catalog_uses_exact_available_warehouse_and_explicit_fields(client,db,stock):
    s=stock;db.connection().execute(SRMProduct.__table__.update().where(SRMProduct.id==s.product).values(current_quantity=999,average_cost=123,metadata_json={'secret':'must not leak'}));db.commit()
    response=client.get(BASE+'/catalog',headers=s.headers());assert response.status_code==200,response.text
    value=response.json();item=next(row for row in value['items'] if row['id']==s.product)
    assert Decimal(item['stock']['available_quantity'])==4
    assert item['stock']['warehouse_id']==s.warehouse
    assert not {'current_quantity','average_cost','metadata_json','default_warehouse','category'}&item.keys()
    assert 'must not leak' not in response.text
    assert value['features']['held_bills'] is False and value['features']['follow_ups'] is False
    assert value['features']['customers_register'] is True


def test_unenrolled_warehouse_is_not_projected_as_global_stock(client,db,stock):
    s=stock;row=db.query(PackMasterAvailability).filter_by(context_id=s.contexts['hospital'],resource_table='srm_warehouses').one();row.active=False;db.commit()
    response=client.get(BASE+'/catalog',headers=s.headers());assert response.status_code==200,response.text
    item=next(row for row in response.json()['items'] if row['id']==s.product)
    assert item['stock'] is None and item['checkout_supported'] is False
    assert 'warehouse_code' not in response.text


def test_selected_customer_directory_is_small_and_exact_context(client,db,stock):
    s=stock;response=client.get(BASE+'/customers',headers=s.headers());assert response.status_code==200,response.text
    assert [row['id'] for row in response.json()['items']]==[101]
    assert set(response.json()['items'][0])=={'id','name','phone','phone_country_code','email','address','city','state','country'}
    row=db.query(PackMasterAvailability).filter_by(context_id=s.contexts['hospital'],resource_table='crm_companies').one();row.active=False;db.commit()
    assert client.get(BASE+'/customers/101',headers=s.headers()).status_code==404
    assert client.get(BASE+'/customers',headers=s.headers()).json()['items']==[]


def test_receptionist_registers_and_finds_patients_without_checkout_access(client, db, stock):
    headers, actor = native_actor(db, stock.branch)
    context, _ = grant(db, actor, stock.branch, 'hospital', 'receptionist',
                       db.get(PackContext, stock.contexts['hospital']))
    headers['X-Suite-Pack-Context'] = str(context.id)
    assert client.get(BASE + '/catalog', headers=headers).status_code == 403
    schema = client.get(BASE + '/customer-schema', headers=headers)
    assert schema.status_code == 200, schema.text
    patient = {'name': 'Clinic QA Patient', 'address': 'QA address', 'state': 'Telangana',
               'country': 'IN', 'schema_fingerprint': schema.json()['schema_fingerprint']}
    created = client.post(BASE + '/customers', headers=headers, json=patient)
    assert created.status_code == 201, created.text
    patient_id = created.json()['id']
    found = client.get(BASE + '/customers', headers=headers, params={'search': 'clinic qa patient'})
    assert found.status_code == 200, found.text
    assert [row['id'] for row in found.json()['items']] == [patient_id]
    assert client.get(BASE + f'/customers/{patient_id}', headers=headers).status_code == 200
    assert client.post(BASE + '/customers', headers=headers, json=patient).status_code == 409


@pytest.mark.parametrize('pack,role',[('hospital','doctor'),('restaurant','chef')])
def test_specialists_do_not_gain_pos_read_directory_or_create(client,db,stock,pack,role):
    s=stock;headers,actor=native_actor(db,s.branch)
    context,_=grant(db,actor,s.branch,pack,role,db.get(PackContext,s.contexts['hospital']) if pack=='hospital' else None)
    headers={**headers,'X-Suite-Pack-Context':str(context.id)}
    for path in ['/catalog','/customers','/customers/101']:
        assert client.get(BASE+path,headers=headers).status_code==403
    response=client.post(BASE+'/customers',headers=headers,json={'name':'No grant','address':'Genuine address','state':'Telangana','country':'IN'})
    assert response.status_code==403,response.text


def test_ordinary_customer_orm_birth_does_not_open_canonical_contact_directories(db,stock):
    from app.apps.crm.models import CRMCompany
    from fastapi import HTTPException
    from tests.test_srm_native_transaction_operations import native_writer
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    s=stock
    with native_writer(db,s.actor,s.branch):
        scope=resolve_context(db,s.actor,db.info['branch_context'],s.contexts['hospital']);cleanup=install(db,scope,policy=native_srm_policy('hospital').policy)
        try:
            db.add(CRMCompany(organization_id=1,branch_id=s.branch,name='Boundary birth reproduction',account_type='Customer',email='birth-proof@example.invalid'))
            with pytest.raises(HTTPException):db.flush()
            db.rollback()
        finally:cleanup()


def test_pos_customer_birth_is_real_canonical_identity_and_immediately_billable(client,db,stock):
    from app.apps.crm.models import CRMCompany,CRMContact
    from app.apps.crm.contact_identity import ContactIdentityLink
    from app.common.models import CommonPerson
    from app.models.user import User
    from app.models.employee import Employee
    from app.apps.srm.commercial_models import InvoiceContext
    s=stock;before=[db.query(model).count() for model in (CommonPerson,User,Employee)]
    data={'name':'New actual POS customer','address':'Customer provided billing address','city':'Hyderabad','state':'Telangana','country':'IN','email':'new-pos@example.com'}
    response=client.post(BASE+'/customers',headers=s.headers(),json=data);assert response.status_code==201,response.text
    ident=response.json()['id'];assert response.json()['address']==data['address']
    assert [db.query(model).count() for model in (CommonPerson,User,Employee)]==before
    contact=db.query(CRMContact).filter_by(company_id=ident).one();link=db.query(ContactIdentityLink).filter_by(account_id=ident).one()
    assert link.contact_id==contact.id and link.person_id is None and link.employee_id is None
    assert client.get(BASE+'/customers/'+str(ident),headers=s.headers('retail')).status_code==404
    payload=s.payload(mixed=False,payment='118');payload['customer_id']=ident
    result=client.post('/api/v1/srm/service-checkout',headers=s.headers(),json=payload);assert result.status_code==201,result.text
    ctx=db.get(InvoiceContext,result.json()['invoice']['id'])
    assert data['address'] in ctx.customer_snapshot['address'] and ctx.customer_snapshot['country']=='IN'
    duplicate=client.post(BASE+'/customers',headers=s.headers(),json=data);assert duplicate.status_code==409,duplicate.text
    assert str(ident) not in duplicate.text and data['email'] not in duplicate.text


def test_hidden_duplicate_does_not_reveal_or_enroll_other_context_account(client,db,stock):
    from app.business_packs.models import PackUserGrant
    s=stock;data={'name':'Exact private duplicate proof','address':'Actual supplied address','state':'Telangana','country':'IN','email':'hidden-pos@example.com'}
    first=client.post(BASE+'/customers',headers=s.headers(),json=data);assert first.status_code==201,first.text
    ident=first.json()['id']
    grant=db.query(PackUserGrant).filter_by(context_id=s.contexts['retail'],user_id=s.actor.id).one();grant.role='service_desk';db.commit()
    denied=client.post(BASE+'/customers',headers=s.headers('retail'),json=data)
    assert denied.status_code==409,denied.text
    assert data['name'] not in denied.text and data['email'] not in denied.text and 'matches' not in denied.text
    assert not db.query(PackMasterAvailability).filter_by(context_id=s.contexts['retail'],resource_table='crm_companies',resource_key=str(ident)).first()
    assert client.get(BASE+'/customers/'+str(ident),headers=s.headers('retail')).status_code==404


def test_native_view_only_role_cannot_register_even_with_pack_capability(client,db,stock):
    s=stock;headers,actor=native_actor(db,s.branch,actions=('view',))
    context,_=grant(db,actor,s.branch,'hospital','service_desk',db.get(PackContext,s.contexts['hospital']))
    headers={**headers,'X-Suite-Pack-Context':str(context.id)}
    response=client.get(BASE+'/customers',headers=headers);assert response.status_code==200,response.text
    assert response.json()['features']['customers_register'] is False
    response=client.post(BASE+'/customers',headers=headers,json={'name':'Native ceiling denied','address':'Actual supplied address','state':'Telangana','country':'IN'})
    assert response.status_code==403,response.text


@pytest.mark.parametrize('extra',[{'id':101},{'pack_context_id':2},{'roles':['Admin']},{'tax_registrations':[{'number':'spoof'}]}])
def test_birth_input_cannot_adopt_identity_or_promote_configuration(client,db,stock,extra):
    data={'name':'Strict new account','address':'Actual supplied address','state':'Telangana','country':'IN',**extra}
    response=client.post(BASE+'/customers',headers=stock.headers(),json=data)
    assert response.status_code==422,response.text


def test_required_followup_catalogue_item_is_explicitly_unavailable(client,db,stock):
    s=stock;db.connection().execute(SRMProduct.__table__.update().where(SRMProduct.id==s.product).values(metadata_json={'follow_up':{'required':True,'assigned_user_id':999},'private_supplier_note':'never expose'}));db.commit()
    response=client.get(BASE+'/catalog',headers=s.headers());assert response.status_code==200,response.text
    item=next(row for row in response.json()['items'] if row['id']==s.product)
    assert item['checkout_supported'] is False and 'follow-up' in item['unsupported_reason']
    assert 'follow_up' not in item and 'private_supplier_note' not in response.text and 'assigned_user_id' not in response.text


def test_native_readonly_branch_reports_registration_unavailable(client,db,stock):
    from app.branches.models import BranchGrant
    s=stock;headers,actor=native_actor(db,s.branch)
    context,_=grant(db,actor,s.branch,'hospital','service_desk',db.get(PackContext,s.contexts['hospital']))
    native_grant=db.query(BranchGrant).filter_by(company_id=1,branch_id=s.branch,user_id=actor.id).one();native_grant.can_write=False;db.commit()
    headers={**headers,'X-Suite-Pack-Context':str(context.id)}
    response=client.get(BASE+'/customers',headers=headers);assert response.status_code==200,response.text
    assert response.json()['features']['customers_register'] is False
    assert response.json()['features']['appointments_schedule'] is False
    response=client.post(BASE+'/customers',headers=headers,json={'name':'Readonly branch denied','address':'Actual address','state':'Telangana','country':'IN'})
    assert response.status_code==403,response.text


def test_cashier_sees_booking_requirement_without_provider_details_and_sells_unscheduled(client,db,stock):
    from app.apps.srm.service_checkout import save_policy
    from app.apps.srm.service_checkout_schemas import PolicyInput
    from tests.test_srm_native_transaction_operations import native_writer
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    from app.business_packs.models import PackUserGrant
    s=stock
    # Native manager configures an ordinary optional service in Retail context.
    with native_writer(db,s.actor,s.branch):
        scope=resolve_context(db,s.actor,db.info['branch_context'],s.contexts['retail']);cleanup=install(db,scope,policy=native_srm_policy('retail').policy)
        try:policy=save_policy(PolicyInput(service_product_id=s.service,booking_required=False,default_duration_minutes=30,min_duration_minutes=5,max_duration_minutes=120),db,s.actor)
        finally:cleanup()
    role=db.query(PackUserGrant).filter_by(context_id=s.contexts['retail'],user_id=s.actor.id).one();role.role='cashier';db.commit()
    response=client.get(BASE+'/catalog',headers=s.headers('retail'));assert response.status_code==200,response.text
    assert response.json()['features']['appointments_schedule'] is False
    item=next(row for row in response.json()['items'] if row['id']==s.service)
    assert item['booking_policy']=={'required':False,'active':True,'revision':policy['revision']}
    assert item['checkout_supported'] is True and 'specialists' not in response.text and 'employee_name' not in response.text
    data=s.payload('retail',payment='118');data['lines']=data['lines'][1:]
    result=client.post('/api/v1/srm/service-checkout',headers=s.headers('retail'),json=data);assert result.status_code==201,result.text
    # Requirement changes are server-authoritative even when the cart has an old DTO.
    table=__import__('app.apps.srm.service_checkout_models',fromlist=['ServiceBookingPolicy']).ServiceBookingPolicy.__table__
    db.connection().execute(table.update().where(table.c.id==policy['id']).values(booking_required=True,revision=policy['revision']+1));db.commit()
    response=client.get(BASE+'/catalog',headers=s.headers('retail'));assert response.status_code==200,response.text
    item=next(row for row in response.json()['items'] if row['id']==s.service)
    assert item['checkout_supported'] is False and 'permission' in item['unsupported_reason']
    data['request_id']=str(uuid4());data['payments'][0]['payment_key']=str(uuid4())
    denied=client.post('/api/v1/srm/service-checkout',headers=s.headers('retail'),json=data)
    assert denied.status_code==422,denied.text


def test_customer_birth_late_failure_rolls_back_all_canonical_intrinsics(client,db,stock,monkeypatch):
    from app.apps.crm.models import CRMCompany,CRMContact
    from app.apps.crm.contact_identity import ContactIdentityLink
    from app.shared.master_data_models import CompanyMasterDetails,ContactChannel,BusinessRelationship
    from app.apps.srm.api import router as native
    from fastapi import HTTPException
    s=stock;models=(CRMCompany,CRMContact,ContactIdentityLink,CompanyMasterDetails,ContactChannel,BusinessRelationship,PackMasterAvailability)
    counts=[db.query(model).count() for model in models]
    def denied(*args,**kwargs):raise HTTPException(409,'Synthetic late audit failure')
    monkeypatch.setattr(native,'_audit',denied)
    response=client.post(BASE+'/customers',headers=s.headers(),json={'name':'Rollback customer birth','address':'Real supplied address','state':'Telangana','country':'IN','email':'rollback-pos@example.com'})
    assert response.status_code==409,response.text
    assert [db.query(model).count() for model in models]==counts


def test_required_native_company_fields_cannot_be_bypassed_by_pos_birth(client,db,stock):
    from app.apps.crm.models import CRMCustomField,CRMCompany
    db.add(CRMCustomField(organization_id=1,entity='companies',field_key='required_account_code',label='Private field label',is_required=True,is_active=True));db.commit()
    before=db.query(CRMCompany).count()
    response=client.get(BASE+'/customers',headers=stock.headers());assert response.status_code==200,response.text
    assert response.json()['features']['customers_register'] is True
    response=client.post(BASE+'/customers',headers=stock.headers(),json={'name':'Do not skip required fields','address':'Actual address','state':'Telangana','country':'IN'})
    assert response.status_code==409,response.text
    assert 'Private field label' not in response.text and db.query(CRMCompany).count()==before


def test_foreign_billing_country_does_not_invent_personal_contact_jurisdiction(client,db,stock):
    from app.apps.crm.models import CRMCompany,CRMContact
    response=client.post(BASE+'/customers',headers=stock.headers(),json={'name':'Foreign billing account','address':'Actual supplied US billing address','state':'California','country':'US'})
    assert response.status_code==201,response.text
    row=db.get(CRMCompany,response.json()['id']);contact=db.query(CRMContact).filter_by(company_id=row.id).one()
    assert row.country=='US' and contact.country is None and contact.address is None


def test_catalog_exposes_only_public_images_not_private_metadata(client, db, stock):
    s = stock
    db.connection().execute(SRMProduct.__table__.update().where(SRMProduct.id == s.product).values(
        metadata_json={'images':['https://example.com/catalog.png'], 'private_supplier_note':'must not leak'}))
    db.commit()
    response = client.get('/api/v1/srm/pos/catalog', headers=s.headers())
    assert response.status_code == 200, response.text
    item = next(row for row in response.json()['items'] if row['id'] == s.product)
    assert item['images'] == ['https://example.com/catalog.png']
    assert 'private_supplier_note' not in response.text
    assert 'metadata_json' not in item
