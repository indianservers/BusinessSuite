from uuid import uuid4
import pytest
from sqlalchemy import insert, select
from app.models.company import Branch
from app.business_packs.first_activation import reasons
from tests.test_public_signup import platform_store,platform_headers,activate,login,PASSWORD

ROOT='/api/v1/access/settings/business-packs'

@pytest.fixture
def new_branch(db):
    row=Branch(company_id=1,name='Empty activation branch',code=uuid4().hex[:12],is_active=True)
    db.add(row);db.commit();return row

def test_empty_native_branch_inventory(db,new_branch):
    assert reasons(db,1,new_branch.id)==[]

def test_direct_unowned_native_row_blocks_cutover_without_adoption(db,new_branch):
    from app.apps.srm.industry_models import IndustryRecord
    from app.models.user import User
    actor=User(email='legacy-'+uuid4().hex+'@example.com',hashed_password='unused',is_active=True)
    db.add(actor);db.flush()
    row=IndustryRecord.__table__
    db.connection().execute(insert(row).values(organization_id=1,branch_id=new_branch.id,kind='appointment',
        title='Legacy record',status='cancelled',revision=1,request_id=str(uuid4()),data={},created_by=actor.id))
    assert reasons(db,1,new_branch.id)
    from app.business_packs.models import PackRecordOwnership
    assert db.query(PackRecordOwnership).count()==0

def test_inherited_unowned_leave_balance_is_not_an_empty_branch(db,new_branch):
    from app.models.employee import Employee
    from app.models.leave import LeaveType,LeaveBalance
    employee=Employee(employee_id=uuid4().hex,first_name='Canonical',last_name='Specialist',branch_id=new_branch.id,status='Active',date_of_joining=__import__('datetime').date(2026,1,1))
    typ=LeaveType(name='Native leave',code=uuid4().hex[:12],days_allowed=10)
    db.add_all([employee,typ]);db.flush()
    db.connection().execute(insert(LeaveBalance.__table__).values(employee_id=employee.id,leave_type_id=typ.id,year=2026,allocated=10))
    assert reasons(db,1,new_branch.id)

@pytest.mark.parametrize('fault',['operational','forged_setup_entity','forged_module','none'])
def test_only_exact_body_free_setup_audits_do_not_invent_history(db,new_branch,fault):
    from app.models.audit import AuditLog
    from app.models.user import User
    from app.branches.models import BranchOwnership
    actor=User(email=uuid4().hex+'@example.test',hashed_password='unused',is_active=True)
    db.add(actor);db.flush()
    audit=AuditLog(organization_id=1,user_id=actor.id,actor_authenticated=True,method='GET',endpoint='/access/me',module='access',status_code=200,action='GET')
    if fault=='operational':audit.method='POST';audit.endpoint='/srm/industry/appointments';audit.module='srm';audit.status_code=201
    elif fault=='forged_setup_entity':audit.entity_type='appointment';audit.entity_id=999
    elif fault=='forged_module':audit.module='srm'
    db.add(audit);db.flush()
    db.add(BranchOwnership(company_id=1,branch_id=new_branch.id,resource_table=audit.__tablename__,resource_key=str(audit.id),source='request-audit'))
    db.flush()
    assert bool(reasons(db,1,new_branch.id))==(fault!='none')


def test_unowned_business_child_of_company_owned_unlocated_master_is_ambiguous(db,new_branch):
    from app.models.employee import Employee
    from app.models.leave import LeaveType,LeaveBalance
    from app.models.security_boundary import SecurityResourceOwnership
    employee=Employee(employee_id=uuid4().hex,first_name='Unlocated',last_name='Canonical',branch_id=None,status='Active',date_of_joining=__import__('datetime').date(2026,1,1))
    typ=LeaveType(name='Unlocated policy',code=uuid4().hex[:12],days_allowed=10)
    db.add_all([employee,typ]);db.flush()
    db.add(SecurityResourceOwnership(resource_table=employee.__tablename__,resource_id=employee.id,company_id=1));db.flush()
    db.connection().execute(insert(LeaveBalance.__table__).values(employee_id=employee.id,leave_type_id=typ.id,year=2026,allocated=10))
    assert reasons(db,1,new_branch.id)


def test_unknown_physical_native_source_cannot_be_silently_omitted(db,new_branch):
    db.connection().exec_driver_sql('CREATE TABLE unreviewed_native_operational_source (id INTEGER PRIMARY KEY, company_id INTEGER, branch_id INTEGER)')
    from sqlalchemy import text
    try:
        db.connection().execute(text('INSERT INTO unreviewed_native_operational_source VALUES (1, 1, :branch)'),{'branch':new_branch.id})
        assert reasons(db,1,new_branch.id)
    finally:
        db.connection().exec_driver_sql('DROP TABLE unreviewed_native_operational_source')


@pytest.mark.parametrize('field',['endpoint','module','status_code','action'])
def test_nullable_setup_metadata_is_unknown_history_not_a_cutover_exemption(db,new_branch,field):
    from app.models.audit import AuditLog
    from app.models.user import User
    actor=User(email=uuid4().hex+'@example.test',hashed_password='unused',is_active=True)
    db.add(actor);db.flush()
    row=AuditLog(organization_id=1,user_id=actor.id,actor_authenticated=True,method='GET',endpoint='/access/me',
        module='access',status_code=200,action='GET')
    setattr(row,field,None);db.add(row);db.flush()
    from app.business_packs.first_activation import RECONCILE
    assert reasons(db,1,new_branch.id)==[RECONCILE]


def test_signup_platform_approval_native_login_draft_enrollment_first_activation(client,db,platform_store,platform_headers,monkeypatch):
    from app.db.init_db import init_db
    from app.core.config import settings
    monkeypatch.setattr(settings,'BOOTSTRAP_ADMIN_EMAIL','bootstrap-native@example.com')
    monkeypatch.setattr(settings,'BOOTSTRAP_ADMIN_PASSWORD',PASSWORD)
    init_db(db,seed_demo=False)  # Actual deployed catalog/bootstrap; no demo accounts or actor grants.
    email='first-clinic-'+uuid4().hex[:8]+'@example.com'
    submitted=client.post('/api/v1/auth/signup',json={'applicant_type':'company','name':'Clinic Owner',
        'company_name':'First Clinic','email':email,'phone':'+919876543210','requested_modules':['hrms','srm'],'consent':True})
    assert submitted.status_code==202,submitted.text
    from app.platform_owner.models import PlatformSignupRequest
    row=platform_store.query(PlatformSignupRequest).filter_by(email=email).one()
    pending=client.post('/api/v1/auth/login',json={'email':email,'password':PASSWORD})
    assert pending.status_code==401,pending.text
    assert 'access_token' not in pending.json()
    approved=client.post(f'/api/v1/platform/signups/{row.id}/review',headers=platform_headers,json={'decision':'approve',
        'reason':'Reviewed native first clinic setup','version':row.version,'modules':['hrms','srm'],
        'checklist':{'identity':True,'duplicates':True,'modules':True}})
    assert approved.status_code==200,approved.text
    activate(client,approved.json())
    headers=login(client,email)
    platform_store.refresh(row);company=row.company_id
    headers.update({'X-Suite-Organization':str(company)})
    identity=client.get('/api/v1/access/me',headers=headers);assert identity.status_code==200,identity.text
    current=identity.json()
    # Native Company Admin control only; no implicit operational pack grant.
    branch=client.post('/api/v1/branches',headers=headers,json={'name':'New clinic operations','code':'CLINIC','reason':'Explicit empty branch setup'})
    assert branch.status_code==201,branch.text
    native_branch=db.connection().execute(select(Branch.company_id,Branch.is_active).where(Branch.id==branch.json()['id'])).one()
    assert tuple(native_branch)==(company,True)
    bid=branch.json()['id'];headers['X-Suite-Branch']=str(bid)
    draft=client.post(ROOT+'/activations',headers=headers,json={'pack_key':'hospital','expected_revision':0,'reason':'Prepare clinic workflows'})
    assert draft.status_code==201,draft.text
    a=draft.json()
    context=client.post(ROOT+'/contexts',headers=headers,json={'activation_id':a['id'],'activation_revision':a['revision'],
        'branch_id':bid,'expected_revision':0,'reason':'Prepare exact clinic context'})
    assert context.status_code==201,context.text
    c=context.json()
    service=client.post('/api/v1/srm/inventory/items',headers=headers,json={'sku':'CONS-'+uuid4().hex[:10],
        'item_name':'General consultation','product_type':'service','track_inventory':False,'sales_rate':100,'gst_rate':18})
    assert service.status_code==201,service.text
    from app.models.audit import AuditLog
    native_audit=db.connection().execute(select(AuditLog.entity_type,AuditLog.entity_id).where(
        AuditLog.organization_id==company,AuditLog.endpoint=='/srm/inventory/items',AuditLog.method=='POST')).one()
    assert tuple(native_audit)==('canonical:srm_product_created',service.json()['id'])
    shared=client.put(ROOT+f"/contexts/{c['id']}/masters",headers=headers,json={'kind':'products','id':service.json()['id'],
        'active':True,'expected_context_revision':c['revision'],'expected_revision':0,'reason':'Explicit consultation availability'})
    assert shared.status_code==200,shared.text
    config=client.get(ROOT+'/configuration',headers=headers);assert config.status_code==200,config.text
    c=next(x for x in config.json()['contexts'] if x['id']==c['id'])
    from app.models.user import User
    user=db.query(User).filter_by(email=email).one()
    granted=client.put(ROOT+f"/contexts/{c['id']}/grants/{user.id}",headers=headers,json={'context_revision':c['revision'],
        'role':'hospital_manager','active':True,'expected_revision':0,'reason':'Explicit operational manager grant'})
    assert granted.status_code==200,granted.text
    ready=client.get(ROOT+'/readiness',headers=headers,params={'pack_key':'hospital','branch_id':bid})
    assert ready.status_code==200 and ready.json()['ready'],ready.text
    parent=client.post(ROOT+f"/activations/{a['id']}/activate",headers=headers,json={'expected_revision':a['revision'],'reason':'Activate reviewed clinic release'})
    assert parent.status_code==200,parent.text
    enabled=client.post(ROOT+f"/contexts/{c['id']}/activate",headers=headers,json={'expected_revision':c['revision'],
        'activation_revision':parent.json()['revision'],'reason':'Activate verified empty clinic branch'})
    assert enabled.status_code==200,enabled.text
    selected={**headers,'X-Suite-Pack-Context':str(c['id'])}
    actual=client.get('/api/v1/srm/industry/capabilities',headers=selected)
    assert actual.status_code==200,actual.text
    assert actual.json()['operational_scope']['context_id']==c['id']
    assert actual.json()['operational_scope']['pack_key']=='hospital'
    assert actual.json()['checkout_create'] is True

    # Repair must remain reachable when a configured branch is later inactive.
    from sqlalchemy import update
    db.connection().execute(update(Branch.__table__).where(Branch.id==bid).values(is_active=False))
    db.commit()
    revoked=client.put(ROOT+f"/contexts/{c['id']}/grants/{user.id}",headers={**headers,'X-Suite-Pack-Context':'invalid-stale-selector'},json={
        'context_revision':enabled.json()['revision'],'role':'hospital_manager','active':False,
        'expected_revision':granted.json()['revision'],'reason':'Revoke access after branch retirement'})
    assert revoked.status_code==200,revoked.text
    assert revoked.json()['active'] is False
