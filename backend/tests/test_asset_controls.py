from datetime import date
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.models.asset import Asset, AssetAssignment
from app.models.company import Company, Branch
from app.models.employee import Employee
from app.models.user import User
from app.models.notification import Notification
from app.models.approval_os import ApprovalRequest
from app.core.security import create_access_token
from app.services import asset_lifecycle as life
from app.schemas.asset import AssetInspection
from tests.rich_text_test_utils import organization_context
from tests.test_asset_lifecycle import assigned,receive,inspect,decide,create,person,B,TODAY


def test_foreign_tenant_asset_and_employee_are_hidden(client,db,superuser_headers):
    e,a,i=assigned(client,superuser_headers,db)
    company=Company(name='Foreign asset company');db.add(company);db.flush()
    branch=Branch(company_id=company.id,name='Foreign branch',code=uuid4().hex[:8]);db.add(branch);db.flush()
    foreign=Asset(name='Foreign asset',asset_tag=uuid4().hex,organization_id=company.id)
    employee=Employee(employee_id=uuid4().hex,first_name='Foreign',last_name='Person',status='Active',date_of_joining=TODAY,branch_id=branch.id)
    db.add_all([foreign,employee]);db.commit()
    assert client.get(B+f'/{foreign.id}',headers=superuser_headers).status_code==404
    assert client.put(B+f'/{foreign.id}',headers=superuser_headers,json={'name':'Hack'}).status_code==404
    result=client.post(B+'/assignments/batch',headers=superuser_headers,json={'employee_id':employee.id,'asset_ids':[a['id']],'assigned_date':str(TODAY),'request_key':uuid4().hex})
    assert result.status_code==404
    assert all(r['id']!=foreign.id for r in client.get(B+'/',headers=superuser_headers).json())


def test_ordinary_employee_cannot_manage_assets(client,db):
    from app.db.init_db import init_db
    init_db(db)
    login=client.post('/api/v1/auth/login',json={'email':'employee@aihrms.com','password':'Employee@123456'})
    h={'Authorization':'Bearer '+login.json()['access_token']}
    assert client.post(B+'/',headers=h,json={'name':'Unauthorized','asset_tag':uuid4().hex}).status_code==403
    assert client.post(B+'/reminders/run',headers=h).status_code==403
    assert client.post(B+'/policy',headers=h,json={}).status_code==403


def test_only_assigned_employee_acknowledges_and_ack_is_idempotent(client,db,superuser_headers):
    e,a,i=assigned(client,superuser_headers,db)
    from app.db.init_db import init_db
    init_db(db)
    login=client.post('/api/v1/auth/login',json={'email':'employee@aihrms.com','password':'Employee@123456'})
    h={'Authorization':'Bearer '+login.json()['access_token']}
    assert client.put(B+f'/assignments/{i}/acknowledge',headers=h).status_code in {403,404}
    assert client.put(B+f'/assignments/{i}/acknowledge',headers=superuser_headers).status_code==200
    first=db.get(AssetAssignment,i).acknowledged_at
    assert client.put(B+f'/assignments/{i}/acknowledge',headers=superuser_headers).status_code==200
    assert db.get(AssetAssignment,i).acknowledged_at==first


def test_cannot_bypass_inspection_by_generic_status_edit(client,db,superuser_headers):
    e,a,i=assigned(client,superuser_headers,db);receive(client,superuser_headers,i)
    assert client.put(B+f"/{a['id']}",headers=superuser_headers,json={'status':'Available'}).status_code==409
    assert client.delete(B+f"/{a['id']}",headers=superuser_headers).status_code==409


def test_inspection_approval_os_canonical_decision_updates_asset(client,db,superuser_headers):
    _,a,i=assigned(client,superuser_headers,db);receive(client,superuser_headers,i)
    r=inspect(client,superuser_headers,i);assert r.status_code==200,r.text
    result=client.put('/api/v1/approval-os/requests/'+str(r.json()['id'])+'/approve',headers=superuser_headers,json={'reason':'Checked inspection evidence'})
    assert result.status_code==200,result.text
    assert db.get(Asset,a['id']).status=='Available'


def test_loss_exception_and_recovery_blockers(client,db,superuser_headers):
    e,a,i=assigned(client,superuser_headers,db)
    assert receive(client,superuser_headers,i,'Lost',damage_description='Lost during documented transit').status_code==200
    r=inspect(client,superuser_headers,i,disposition='Lost',condition='Lost');assert r.status_code==200,r.text
    assert decide(client,superuser_headers,r.json()['id']).status_code==200
    actor=db.query(User).filter_by(email='testadmin@test.com').one();actor.organization_id=1
    assert any(issue['kind']=='Loss Exception Required' for issue in life.blockers_for_employee(db,actor,e.id))
    r=client.post(B+f'/assignments/{i}/exception',headers=superuser_headers,json={'reason':'Approved documented loss exception','policy_reference':'HR exception 1'});assert r.status_code==200,r.text
    assert decide(client,superuser_headers,r.json()['id']).status_code==200
    assert life.blockers_for_employee(db,actor,e.id)==[]
    assert db.get(Asset,a['id']).status=='Lost'


@pytest.mark.parametrize('extension,raw',[('svg',b'<svg/>'),('pdf',b'not a pdf'),('png',b'%PDF-1.4'),('jpg',b'')])
def test_upload_type_and_signature_guards(client,db,superuser_headers,extension,raw):
    a=create(client,superuser_headers)
    response=client.post('/api/v1/access/services/documents',headers=superuser_headers,data={'companyId':'1','module':'hrms','entity':'asset','entityId':str(a['id'])},files={'file':('evidence.'+extension,raw,'application/octet-stream')})
    assert response.status_code in {413,422}


def test_no_assets_exit_can_clear_without_completing_offboarding(client,db,superuser_headers):
    e=person(db)
    r=client.post('/api/v1/exit/records',headers=superuser_headers,json={'employee_id':e.id,'exit_type':'Retirement','last_working_date':str(TODAY)});assert r.status_code==201,r.text
    identity=r.json()['id']
    assert client.get(B+f'/exit-clearance/{identity}/certificate',headers=superuser_headers).status_code==409
    r=client.post(B+f'/exit-clearance/{identity}/complete-assets',headers=superuser_headers);assert r.status_code==200 and not r.json()['company_exit_completed']


def test_return_evidence_cannot_reference_another_asset(client,db,superuser_headers):
    _,a,i=assigned(client,superuser_headers,db)
    from app.shared.models import ServiceDocument
    other=create(client,superuser_headers)
    user=db.query(User).filter_by(email='testadmin@test.com').one()
    d=ServiceDocument(organization_id=1,module_key='hrms',entity_type='asset',entity_id=other['id'],document_key=uuid4().hex,version=1,name='proof.pdf',mime_type='application/pdf',size_bytes=4,storage_path='private',content_hash='abc',owner_id=user.id)
    db.add(d);db.commit()
    assert receive(client,superuser_headers,i,photo_document_ids=[d.id]).status_code==422

@pytest.mark.parametrize('relative',['alembic/versions/20261110_075_asset_lifecycle.py','alembic_postgresql/versions/pg_20261110_092_asset_lifecycle.py'])
def test_additive_migration_preserves_existing_records(relative):
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine,inspect,text
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE assets (id INTEGER PRIMARY KEY, asset_tag TEXT, name TEXT)')
        connection.exec_driver_sql('CREATE TABLE asset_assignments (id INTEGER PRIMARY KEY, asset_id INTEGER, is_active BOOLEAN, remarks TEXT)')
        connection.exec_driver_sql("INSERT INTO assets VALUES (1,'LEGACY-1','Retained asset')")
        connection.exec_driver_sql("INSERT INTO asset_assignments VALUES (1,1,0,'Retained handover')")
        path=Path(__file__).resolve().parents[1]/relative
        spec=importlib.util.spec_from_file_location('asset_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.op=Operations(MigrationContext.configure(connection));module.upgrade();module.upgrade()
        assert connection.execute(text('SELECT name FROM assets WHERE id=1')).scalar()=='Retained asset'
        assert connection.execute(text('SELECT remarks FROM asset_assignments WHERE id=1')).scalar()=='Retained handover'
        assert connection.execute(text('SELECT inspection_status FROM asset_assignments WHERE id=1')).scalar()=='Not Required'
        assert any(i['name']=='uq_asset_active_custody' and i['unique'] for i in inspect(connection).get_indexes('asset_assignments'))
    engine.dispose()


def test_independent_approver_cannot_approve_own_inspection(db):
    from app.models.user import Role,Permission
    from app.schemas.asset import AssetInspection
    role=Role(name='asset_qa_manager',description='Asset manager')
    permission=db.query(Permission).filter_by(name='asset_manage').first()
    if not permission:permission=Permission(name='asset_manage',description='Manage assets',module='asset');db.add(permission)
    role.permissions=[permission];db.add(role);db.flush()
    user=User(email=uuid4().hex+'@test.local',hashed_password='no-login',role_id=role.id,is_active=True,is_superuser=False)
    db.add(user);db.flush();user.organization_id=1
    request=ApprovalRequest(organization_id=1,source_module='hrms',approval_type='asset_inspection',entity_type='asset_assignment',entity_id=1,title='Inspection',requester_user_id=user.id,assigned_to_user_id=user.id,context_json={'asset_lifecycle':'inspection'})
    db.add(request);db.flush()
    with pytest.raises(HTTPException) as error:life.apply_approval(db,user,request,'approve','Own approval attempt')
    assert error.value.status_code==403


def test_partial_multi_asset_return_keeps_exit_blocked(client,db,superuser_headers):
    from tests.test_asset_lifecycle import batch
    e=person(db);items=[create(client,superuser_headers) for _ in range(2)]
    r=batch(client,superuser_headers,e,[a['id'] for a in items]);assert r.status_code==201,r.text
    i=r.json()['assignment_ids'][0];receive(client,superuser_headers,i)
    proposal=inspect(client,superuser_headers,i).json();decide(client,superuser_headers,proposal['id'])
    actor=db.query(User).filter_by(email='testadmin@test.com').one();actor.organization_id=1
    issues=life.blockers_for_employee(db,actor,e.id);assert len(issues)==1 and issues[0]['kind']=='Awaiting Return'


@pytest.mark.parametrize('format',['csv','xlsx'])
def test_exports_include_all_records_and_neutralize_formulas(client,db,superuser_headers,format):
    a=create(client,superuser_headers,name='=DANGEROUS()',serial_number='SER-EXP')
    r=client.get(B+'/export',headers=superuser_headers,params={'format':format})
    assert r.status_code==200,r.text[:100]
    if format=='csv':assert "'=DANGEROUS()" in r.content.decode('utf-8-sig')
    else:
        from openpyxl import load_workbook
        from io import BytesIO
        book=load_workbook(BytesIO(r.content));assert book.active['B2'].value=="'=DANGEROUS()"


def test_paged_register_and_employee_profile(client,db,superuser_headers):
    e,a,i=assigned(client,superuser_headers,db)
    r=client.get(B+'/assignments',headers=superuser_headers,params={'paged':True,'limit':1,'search':'Work laptop'})
    assert r.status_code==200 and r.json()['total']==1 and len(r.json()['items'])==1
    r=client.get(B+f'/employees/{e.id}/profile',headers=superuser_headers);assert r.status_code==200,r.text
    assert r.json()['assignments'][0]['id']==i


def test_large_actual_database_aggregate_and_unassigned_custodian_detection(client,db,superuser_headers):
    from test_identity_utils import own_workflow_records
    rows=[Asset(name=f'Large inventory {i}',asset_tag=uuid4().hex,organization_id=1,status='Available') for i in range(1001)]
    db.add_all(rows);db.flush();own_workflow_records(db,*rows);db.commit()
    assert client.get(B+'/summary',headers=superuser_headers).json()['total']==1001
    r=client.get(B+'/',headers=superuser_headers,params={'offset':1000,'limit':200});assert len(r.json())==1
    assert client.get(B+'/insights',headers=superuser_headers).json()['without_custodian']==0

def test_asset_reads_follow_selected_branch_and_revocation(db):
    from app.branches.models import BranchOwnership,BranchGrant,BranchPolicy
    from app.branches.service import context
    from app.branches.boundary import install
    from test_identity_utils import attach_test_identity,attach_workflow_branch
    if not db.get(Company,1):db.add(Company(id=1,name='Branch QA'));db.flush()
    user=User(email=uuid4().hex+'@branch.test',hashed_password='no-login',is_active=True,is_superuser=False)
    db.add(user);db.flush();attach_test_identity(db,user);home=attach_workflow_branch(db,user)
    other=Branch(company_id=1,name='Other asset branch',code=uuid4().hex[:8]);db.add(other);db.flush()
    db.add(BranchOwnership(resource_table='branches',resource_key=str(other.id),company_id=1,branch_id=other.id,source='qa'))
    own=Asset(name='Home asset',asset_tag=uuid4().hex,organization_id=1)
    hidden=Asset(name='Hidden asset',asset_tag=uuid4().hex,organization_id=1)
    db.add_all([own,hidden]);db.flush()
    for row,branch in [(own,home),(hidden,other)]:db.add(BranchOwnership(resource_table='assets',resource_key=str(row.id),company_id=1,branch_id=branch.id,source='qa'))
    db.commit();user.organization_id=1
    cleanup=install(db,user,context(db,user,1,home.id))
    try:
        assert life.asset(db,user,own.id).id==own.id
        with pytest.raises(HTTPException) as denied:life.asset(db,user,hidden.id)
        assert denied.value.status_code==404
    finally:cleanup()
    db.query(BranchGrant).filter_by(user_id=user.id,branch_id=home.id).delete()
    db.add(BranchPolicy(user_id=user.id,company_id=1,use_home_branch=False,all_branches=False));db.commit()
    with pytest.raises(HTTPException):context(db,user,1,home.id)



def test_zero_recovery_cap_means_no_configured_maximum(client,db,superuser_headers):
    _,_,i=assigned(client,superuser_headers,db)
    receive(client,superuser_headers,i,'Damaged')
    r=client.post(B+'/policy',headers=superuser_headers,json={'recovery_enabled':True,'recovery_limit':'0'})
    assert r.status_code==200,r.text
    r=client.post(B+f'/assignments/{i}/recovery',headers=superuser_headers,json={'amount':'125.01','reason':'Documented damage assessment','policy_reference':'HR policy 42'})
    assert r.status_code==200,r.text



def test_background_reminder_worker_uses_scoped_policy_and_deduplicates(client,db,superuser_headers):
    assigned(client,superuser_headers,db)
    r=client.post(B+'/policy',headers=superuser_headers,json={'reminders_enabled':True})
    assert r.status_code==200,r.text
    from app.services.asset_reminders import enqueue_all_asset_reminders
    first=enqueue_all_asset_reminders(db,limit=10)
    assert first>=1
    assert enqueue_all_asset_reminders(db,limit=10)==0



def test_handover_and_return_evidence_are_preserved_separately(client,db,superuser_headers,tmp_path,monkeypatch):
    from app.core.config import settings
    from tests.test_asset_lifecycle import batch
    monkeypatch.setattr(settings,'UPLOAD_DIR',str(tmp_path))
    e=person(db);a=create(client,superuser_headers)
    r=client.post('/api/v1/access/services/documents',headers=superuser_headers,data={'companyId':'1','module':'hrms','entity':'asset','entityId':str(a['id'])},files={'file':('handover.pdf',b'%PDF-1.4 handover photo record','application/pdf')})
    assert r.status_code==201,r.text
    document=r.json()['id']
    r=batch(client,superuser_headers,e,[a['id']],handover_document_ids={str(a['id']):[document]})
    assert r.status_code==201,r.text
    identity=r.json()['assignment_ids'][0]
    assert receive(client,superuser_headers,identity).status_code==200
    details=db.get(AssetAssignment,identity).return_details
    assert details['at_handover']['photo_document_ids']==[document]
    assert details['photo_document_ids']==[]



def test_managed_hrms_asset_role_can_submit_native_approval_without_unrelated_module_access(client,db,superuser_headers):
    _,a,i=assigned(client,superuser_headers,db);receive(client,superuser_headers,i)
    from app.models.user import Role,Permission
    from app.access.scope import install_scope
    from test_identity_utils import attach_test_identity,attach_workflow_branch
    role=Role(name='asset_only_qa',description='Asset-only HRMS role')
    permissions=[]
    for name in ['asset_view','asset_manage']:
        permission=db.query(Permission).filter_by(name=name).first()
        if not permission:permission=Permission(name=name,description=name,module='asset');db.add(permission)
        permissions.append(permission)
    role.permissions=permissions;db.add(role);db.flush()
    actor=User(email=uuid4().hex+'@asset.test',hashed_password='no-login',role_id=role.id,is_active=True,is_superuser=False)
    db.add(actor);db.flush();attach_test_identity(db,actor);attach_workflow_branch(db,actor);db.commit()
    actor.organization_id=1;actor._suite_current_module='hrms'
    grants={'hrms':{'enabled':True,'scope':'organization','permissions':['asset_view','asset_manage'],'actions':['view','create','edit','assign']}}
    cleanup=install_scope(db,actor,1,grants)
    try:
        row,item=life.assignment(db,actor,i,lock=True)
        request=life.submit_inspection(db,actor,row,item,AssetInspection(comments='Verified by asset-only manager',disposition='Available',condition='Good'))
        db.flush()
        assert request.source_module=='hrms' and request.approval_type=='asset_inspection'
        assert db.query(ApprovalRequest).filter_by(id=request.id).first() is not None
        assert db.query(ApprovalRequest).filter(ApprovalRequest.source_module!='hrms').count()==0
    finally:cleanup()


def test_postgres_incremental_migration_preserves_legacy_rows_and_adds_foreign_keys(db_engine):
    if db_engine.dialect.name!='postgresql':pytest.skip('Incremental PostgreSQL DDL validation')
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect,text
    schema='asset_upgrade_'+uuid4().hex
    with db_engine.begin() as connection:
        connection.exec_driver_sql('CREATE SCHEMA '+schema)
        try:
            connection.exec_driver_sql('SET LOCAL search_path TO '+schema)
            connection.exec_driver_sql('CREATE TABLE assets (id INTEGER PRIMARY KEY, asset_tag TEXT, name TEXT)')
            connection.exec_driver_sql('CREATE TABLE approval_requests (id INTEGER PRIMARY KEY)')
            connection.exec_driver_sql('CREATE TABLE asset_assignments (id INTEGER PRIMARY KEY, asset_id INTEGER, is_active BOOLEAN, remarks TEXT)')
            connection.exec_driver_sql("INSERT INTO assets VALUES (1,'LEGACY-PG','Retained legacy asset')")
            connection.exec_driver_sql("INSERT INTO asset_assignments VALUES (1,1,false,'Retained custody evidence')")
            path=Path(__file__).resolve().parents[1]/'alembic_postgresql/versions/pg_20261110_092_asset_lifecycle.py'
            spec=importlib.util.spec_from_file_location('asset_pg_upgrade',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            module.op=Operations(MigrationContext.configure(connection));module.upgrade()
            assert connection.execute(text('SELECT remarks FROM asset_assignments')).scalar()=='Retained custody evidence'
            keys=inspect(connection).get_foreign_keys('asset_assignments')
            assert {fk['constrained_columns'][0] for fk in keys}>={'inspection_approval_id','recovery_approval_id'}
            assert connection.execute(text('SELECT inspection_status FROM asset_assignments')).scalar()=='Not Required'
        finally:
            connection.exec_driver_sql('SET LOCAL search_path TO public')
            connection.exec_driver_sql('DROP SCHEMA '+schema+' CASCADE')



def test_employee_reminders_link_to_the_existing_self_service_assets(client,db,superuser_headers):
    e,a,i=assigned(client,superuser_headers,db)
    actor=db.query(User).filter_by(email='testadmin@test.com').one()
    e.user_id=actor.id;db.commit()
    r=client.post(B+'/policy',headers=superuser_headers,json={'reminders_enabled':True});assert r.status_code==200,r.text
    r=client.post(B+'/reminders/run',headers=superuser_headers);assert r.status_code==200,r.text
    assert db.query(Notification).filter_by(user_id=actor.id,event_type='asset.handover_pending').one().action_url=='/hrms/ess'


def test_shared_asset_upload_cannot_use_unrelated_hrms_edit_permission(client,db,superuser_headers):
    from app.models.user import Role,Permission
    from test_identity_utils import attach_test_identity,attach_workflow_branch
    role=Role(name='asset_reader_other_hr_editor',description='Asset read and unrelated HR edit')
    permissions=[]
    for name in ['asset_view','employee_update']:
        permission=db.query(Permission).filter_by(name=name).first()
        if not permission:permission=Permission(name=name,description=name,module='asset' if name=='asset_view' else 'employee');db.add(permission)
        permissions.append(permission)
    role.permissions=permissions;db.add(role);db.flush()
    reader=User(email=uuid4().hex+'@asset.test',hashed_password='no-login',role_id=role.id,is_active=True)
    db.add(reader);db.flush();attach_test_identity(db,reader);attach_workflow_branch(db,reader);db.commit()
    a=create(client,superuser_headers)
    headers={'Authorization':'Bearer '+create_access_token(str(reader.id))}
    response=client.post('/api/v1/access/services/documents',headers=headers,data={'companyId':'1','module':'hrms','entity':'asset','entityId':str(a['id'])},files={'file':('proof.pdf',b'%PDF-1.4 denied evidence','application/pdf')})
    assert response.status_code==403,response.text
