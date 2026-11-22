"""Assigned clinicians use real native authentication, never JSON account hints."""
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Depends
from app.core.deps import get_current_user, get_db
from app.main import app
from app.business_packs.models import PackActivation, PackContext, PackUserGrant, PackRecordOwnership
from app.branches.models import BranchGrant
from app.models.company import Branch, Company
from app.models.employee import Employee
from app.apps.srm.industry_models import IndustryRecord
from tests.test_settings_hub import actor
from tests.test_business_pack_access import packs

BASE = '/api/v1/srm/industry'

@pytest.fixture(params=[("hospital", "own"), ("hospital", "assigned"), ("salon", "own")])
def assigned(client, db, request):
    clinical_pack, native_scope = request.param
    users, headers = {}, {}
    for name, scope in [('a',native_scope), ('b','organization'), ('reception','organization'), ('chef','organization')]:
        headers[name], users[name] = actor(db, role='assignment_'+name, permissions=['srm_admin'], grants={
            'srm': {'enabled':True,'permissions':['srm_admin'],'actions':['view','create','edit','approve'],'scope':scope}})
    company=db.get(Company,1);company.country='India';company.email='qa@example.test'
    actor(db, role='setup_admin', admin=True)
    branch = Branch(company_id=1, name='Clinical assignment'); db.add(branch); db.flush()
    for user in users.values(): db.add(BranchGrant(company_id=1,branch_id=branch.id,user_id=user.id,can_write=True))
    contexts = {}
    for key in (clinical_pack, 'restaurant'):
        activation=PackActivation(company_id=1,pack_key=key,pack_version=1,state='active');db.add(activation);db.flush()
        context=PackContext(company_id=1,branch_id=branch.id,activation_id=activation.id,pack_key=key,pack_version=1,state='active');db.add(context);db.flush();contexts[key]=context
    for name, role in [('a','doctor' if clinical_pack=='hospital' else 'stylist'),('b','doctor' if clinical_pack=='hospital' else 'stylist'),('reception','receptionist'),('chef','chef')]:
        context=contexts['restaurant' if name=='chef' else clinical_pack]
        db.add(PackUserGrant(company_id=1,branch_id=branch.id,context_id=context.id,user_id=users[name].id,role=role))
        headers[name].update({'X-Suite-Organization':'1','X-Suite-Branch':str(branch.id),'X-Suite-Pack-Context':str(context.id)})
    employees={}
    for name in ('a','b'):
        employee=Employee(employee_id=uuid4().hex,first_name='Doctor',last_name=name,date_of_joining=date(2020,1,1),branch_id=branch.id,user_id=users[name].id,status='Active')
        db.add(employee);db.flush();employees[name]=employee
    def record(kind, name, data, *, owner='reception', pack=None, status='checked_in'):
        row=IndustryRecord(organization_id=1,branch_id=branch.id,kind=kind,title=name,status=status,request_id=str(uuid4()),created_by=users[owner].id,data=data)
        db.add(row);db.flush()
        db.add(PackRecordOwnership(company_id=1,branch_id=branch.id,context_id=contexts[pack or clinical_pack].id,resource_table=row.__tablename__,resource_key=str(row.id)))
        return row
    providers={name:record('resource',name,{'resource_type':'doctor','employee_id':employee.id}) for name,employee in employees.items()}
    appts={}
    def booking(name, resource, **kw):
        return record('appointment',name,{'resource_ids':[resource.id],'starts_at':'2026-11-15T10:15:00+00:00','duration_minutes':30,'notes':'Clinical note','service_name':'Consultation','unit_price':'900','advance_reference':'Private financial reference','tax_rate':'18'},**kw)
    appts['a']=booking('A assigned',providers['a']);appts['b']=booking('B assigned',providers['b'])
    spoof=record('resource','Spoof',{'resource_type':'doctor','user_id':users['a'].id})
    appts['spoof']=booking('Creator alone is insufficient',spoof,owner='a')
    foreign=record('resource','Foreign provider',{'resource_type':'doctor','employee_id':employees['a'].id},pack='restaurant')
    appts['foreign_provider']=booking('Wrong provider context',foreign)
    appts['foreign_appointment']=booking('Wrong appointment context',providers['a'],pack='restaurant')
    from app.branches.migration import backfill
    backfill(db.connection(),1)
    db.commit()
    return SimpleNamespace(client=client,db=db,users=users,headers=headers,appts=appts,employees=employees,contexts=contexts)


def test_assigned_http_list_is_filtered_before_pagination_and_redacts_money(assigned):
    p=assigned
    before=(p.appts['a'].revision,p.appts['a'].updated_at)
    response=p.client.get(BASE+'/records',params={'kind':'appointment','limit':1},headers=p.headers['a'])
    assert response.status_code==200,response.text
    items=response.json()['items'];assert [r['id'] for r in items]==[p.appts['a'].id]
    row=items[0]
    assert row['created_by']==p.users['reception'].id
    assert row['data']['notes']=='Clinical note'
    assert not {'unit_price','advance_reference','tax_rate'} & row['data'].keys()
    assert 'invoice_id' not in row and 'stock_movement_id' not in row
    p.db.refresh(p.appts['a']);assert (p.appts['a'].revision,p.appts['a'].updated_at)==before


def test_receptionist_lists_resources_and_appointments_with_project_management_installed(assigned):
    from app.module_registry import is_app_enabled

    assert is_app_enabled('project_management')
    resources = assigned.client.get(BASE + '/records', params={'kind': 'resource'},
                                    headers=assigned.headers['reception'])
    assert resources.status_code == 200, resources.text
    names = {row['title'] for row in resources.json()['items']}
    assert {'a', 'b'} <= names
    assert 'Foreign provider' not in names
    appointments = assigned.client.get(BASE + '/records', params={'kind': 'appointment'},
                                       headers=assigned.headers['reception'])
    assert appointments.status_code == 200, appointments.text
    ids = {row['id'] for row in appointments.json()['items']}
    assert assigned.appts['a'].id in ids
    assert assigned.appts['foreign_appointment'].id not in ids
    found = assigned.client.get(BASE + f"/appointments/{assigned.appts['a'].id}", headers=assigned.headers['reception'])
    assert found.status_code == 200, found.text
    hidden = assigned.client.get(BASE + f"/appointments/{assigned.appts['foreign_appointment'].id}",
                                 headers=assigned.headers['reception'])
    assert hidden.status_code == 404


def test_broad_native_doctor_still_sees_only_exact_canonical_assignment(assigned):
    p=assigned
    response=p.client.get(BASE+'/records',params={'kind':'appointment'},headers=p.headers['b'])
    assert response.status_code==200,response.text
    assert [r['id'] for r in response.json()['items']]==[p.appts['b'].id]


def test_assigned_doctor_can_start_complete_without_reassigning_creator(assigned):
    p=assigned;ident=p.appts['a'].id
    for status,revision in [('in_service',1),('completed',2)]:
        response=p.client.post(f'{BASE}/records/{ident}/transition',headers=p.headers['a'],json={'status':status,'expected_revision':revision})
        assert response.status_code==200,response.text
        assert response.json()['status']==status and response.json()['created_by']==p.users['reception'].id
        assert 'unit_price' not in response.json()['data']


def test_wrong_doctor_chef_and_forbidden_action_fail(assigned):
    p=assigned;ident=p.appts['a'].id
    response=p.client.post(f'{BASE}/records/{ident}/transition',headers=p.headers['b'],json={'status':'in_service','expected_revision':1})
    assert response.status_code==404,response.text
    response=p.client.get(BASE+'/records',params={'kind':'appointment'},headers=p.headers['chef'])
    assert response.status_code==403,response.text
    response=p.client.post(f'{BASE}/records/{ident}/transition',headers=p.headers['a'],json={'status':'cancelled','reason':'No authority','expected_revision':1})
    assert response.status_code==403,response.text


def test_selected_context_and_live_canonical_employee_are_required(assigned):
    p=assigned
    foreign={**p.headers['a'],'X-Suite-Pack-Context':str(p.contexts['restaurant'].id)}
    assert p.client.get(BASE+'/records',params={'kind':'appointment'},headers=foreign).status_code==403
    p.employees['a'].status='Inactive';p.db.commit()
    response=p.client.get(BASE+'/records',params={'kind':'appointment'},headers=p.headers['a'])
    assert response.status_code==200,response.text
    assert response.json()['items']==[]


def test_doctor_native_finance_permission_does_not_grant_pack_billing(assigned):
    p=assigned;ident=p.appts['a'].id
    response=p.client.get(f'{BASE}/appointments/{ident}/billing',headers=p.headers['a'])
    assert response.status_code==403,response.text
    response=p.client.post(f'{BASE}/records/{ident}/invoice',headers=p.headers['a'],json={'expected_revision':1})
    assert response.status_code==403,response.text
    response=p.client.post(f'{BASE}/appointments/{ident}/payments',headers=p.headers['a'],json={'request_id':str(uuid4()),'expected_revision':1,'amount':'1','payment_method':'cash'})
    assert response.status_code==403,response.text
    response=p.client.post(f'{BASE}/appointments/{ident}/apply-advances',headers=p.headers['a'],json={'expected_revision':1})
    assert response.status_code==403,response.text


def test_no_hrms_permissions_or_pack_grant_are_created(assigned):
    p=assigned
    response=p.client.get('/api/v1/employees/',headers=p.headers['a'])
    assert response.status_code==403,response.text
    grant=p.db.query(PackUserGrant).filter_by(user_id=p.users['a'].id).one()
    grant.active=False;p.db.commit()
    assert p.client.get(BASE+'/records',params={'kind':'appointment'},headers=p.headers['a']).status_code==403


def test_employee_branch_identity_cannot_be_borrowed(assigned):
    p=assigned
    other=Branch(company_id=1,name='Other clinical branch');p.db.add(other);p.db.flush()
    p.employees['a'].branch_id=other.id;p.db.commit()
    response=p.client.get(BASE+'/records',params={'kind':'appointment'},headers=p.headers['a'])
    assert response.status_code==200,response.text
    assert response.json()['items']==[]


@pytest.mark.parametrize('foreign_company',[True,False])
def test_assigned_transition_cannot_validate_foreign_native_customer(assigned, foreign_company):
    from app.apps.crm.models import CRMCompany
    from app.business_packs.models import PackMasterAvailability
    p=assigned
    if foreign_company:p.db.add(Company(id=2,name='Foreign native customer company'))
    customer=CRMCompany(organization_id=2 if foreign_company else 1,name='Inaccessible patient')
    p.db.add(customer);p.db.flush()
    if not foreign_company:
        context=p.contexts['restaurant']
        p.db.add(PackMasterAvailability(company_id=1,branch_id=context.branch_id,context_id=context.id,
            resource_table='crm_companies',resource_key=str(customer.id),active=True))
    p.appts['a'].customer_id=customer.id;p.db.commit()
    response=p.client.post(f"{BASE}/records/{p.appts['a'].id}/transition",headers=p.headers['a'],json={'status':'in_service','expected_revision':1})
    assert response.status_code==403,response.text
    p.db.refresh(p.appts['a'])
    assert p.appts['a'].status=='checked_in' and p.appts['a'].revision==1


def test_cached_get_and_refresh_keep_native_own_and_pack_intersection(assigned, monkeypatch):
    from fastapi import HTTPException
    p=assigned
    own_id=p.appts['a'].id;other_id=p.appts['b'].id
    cached_other=p.appts['b']
    path=BASE+'/assignment-cache-proof'
    from types import MappingProxyType
    from app.business_packs import request_operations
    monkeypatch.setattr(request_operations,'RULES',MappingProxyType({
        **request_operations.RULES, ('GET',path):request_operations.RequestOperation(('appointments.view',))}))
    def endpoint(db=Depends(get_db), user=Depends(get_current_user)):
        assert db.get(IndustryRecord,own_id) is not None
        assert db.get(IndustryRecord,other_id) is None
        with pytest.raises(HTTPException) as error:db.refresh(cached_other)
        assert error.value.status_code==403
        return {'own_visible':True,'other_get_hidden':True,'other_refresh_denied':True}
    app.add_api_route(path,endpoint,methods=['GET'])
    route=app.routes[-1]
    try:
        response=p.client.get(path,headers=p.headers['a'])
        assert response.status_code==200,response.text
        assert response.json()=={'own_visible':True,'other_get_hidden':True,'other_refresh_denied':True}
    finally:app.routes.remove(route)


def test_missing_ownership_schema_never_falls_back_selected_clinician_to_creator(packs, monkeypatch):
    from sqlalchemy import select
    from app.business_packs import industry_assignment
    from app.business_packs.access import resolve_context
    p=packs
    monkeypatch.setattr(industry_assignment,'inspect',lambda _:SimpleNamespace(has_table=lambda _:False))
    _,gate=industry_assignment.clauses(p.db,p.users['doctor'],1,IndustryRecord)
    assert p.db.connection().scalar(select(gate)) is True
    p.db.info['business_pack_scope']=resolve_context(p.db,p.users['doctor'],p.ctx())
    try:assert p.db.connection().scalar(select(gate)) is False
    finally:p.db.info.pop('business_pack_scope',None)
