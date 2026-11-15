"""Real native identity and actual hours remain common across selected packs."""
from datetime import date
from types import SimpleNamespace
from uuid import uuid4
import pytest
from app.branches.models import BranchGrant, BranchOwnership
from app.models.company import Branch, Company
from app.models.employee import Employee
from app.models.timesheet import Project
from tests.test_settings_hub import actor

@pytest.fixture
def core_case(client,db):
    headers,user=actor(db,role='core_self_'+uuid4().hex,permissions=['employee_view','timesheet_view'],grants={
        'hrms':{'enabled':True,'permissions':['employee_view','timesheet_view'],'actions':['view','create','edit'],'scope':'own'}})
    admin_headers,admin=actor(db,role='core_reviewer_'+uuid4().hex,permissions=['employee_view','timesheet_view','timesheet_approve','timesheet_manage'],grants={
        'hrms':{'enabled':True,'permissions':['employee_view','timesheet_view','timesheet_approve','timesheet_manage'],'actions':['view','create','edit','approve','delete'],'scope':'organization'}},admin=True)
    company=db.get(Company,1);company.country='India';company.email='core@example.test'
    branch=Branch(company_id=1,name='Canonical employment');db.add(branch);db.flush()
    for account in (user,admin):db.add(BranchGrant(company_id=1,branch_id=branch.id,user_id=account.id,can_write=True))
    employee=Employee(employee_id=uuid4().hex,first_name='Canonical',last_name='Specialist',date_of_joining=date(2020,1,1),user_id=user.id,branch_id=branch.id,status='Active')
    db.add(employee);db.flush()
    own=Project(code=uuid4().hex,name='Own native project',organization_id=1,created_by=user.id,owner_employee_id=employee.id)
    assigned=Project(code=uuid4().hex,name='HR assigned native project',organization_id=1,created_by=admin.id,owner_employee_id=employee.id)
    db.add_all([own,assigned]);db.flush()
    for row in (own,assigned):db.add(BranchOwnership(company_id=1,branch_id=branch.id,resource_table='projects',resource_key=str(row.id),source='core-native-fixture'))
    from app.branches.migration import backfill
    backfill(db.connection(),1);db.commit()
    for values in (headers,admin_headers):values.update({'X-Suite-Organization':'1','X-Suite-Branch':str(branch.id)})
    return SimpleNamespace(client=client,db=db,user=user,admin=admin,headers=headers,admin_headers=admin_headers,branch=branch,employee=employee,own=own,assigned=assigned)


def test_native_managed_own_project_picker_uses_canonical_assignment(core_case):
    n=core_case
    result=n.client.get('/api/v1/timesheets/projects',headers=n.headers)
    assert result.status_code==200,result.text
    visible={row['id'] for row in result.json()}
    assert n.own.id in visible
    assert n.assigned.id in visible


@pytest.mark.parametrize('selected', [False, True])
def test_self_time_legacy_permission_does_not_override_explicit_readonly_policy(core_case, selected):
    from app.access.models import AccessPolicy
    from app.models.timesheet import Timesheet
    n = core_case
    headers = dict(n.headers)
    if selected:
        headers['X-Suite-Pack-Context'] = str(select_pack(n).id)
    policy = n.db.query(AccessPolicy).filter_by(user_id=n.user.id).one()
    policy.grants = {'hrms': {**policy.grants['hrms'], 'actions': ['view']}}
    n.db.commit()
    before = n.db.query(Timesheet).count()
    result = n.client.post('/api/v1/timesheets/', headers=headers, json={
        'project_id': n.assigned.id, 'period_start': '2026-11-09', 'period_end': '2026-11-15'})
    assert result.status_code == 403, result.text
    assert n.db.query(Timesheet).count() == before


def test_legacy_self_time_permission_does_not_override_readonly_branch(core_case):
    from app.access.models import AccessPolicy
    from app.models.timesheet import Timesheet
    n = core_case
    n.db.query(AccessPolicy).filter_by(user_id=n.user.id).delete()
    grant = n.db.query(BranchGrant).filter_by(user_id=n.user.id, branch_id=n.branch.id).one()
    grant.can_write = False
    n.db.commit()
    before = n.db.query(Timesheet).count()
    result = n.client.post('/api/v1/timesheets/', headers=n.headers, json={
        'project_id': n.assigned.id, 'period_start': '2026-11-09', 'period_end': '2026-11-15'})
    assert result.status_code == 403, result.text
    assert n.db.query(Timesheet).count() == before


def select_pack(n,pack='hospital'):
    from app.business_packs.models import PackActivation,PackContext,PackUserGrant
    activation=PackActivation(company_id=1,pack_key=pack,pack_version=1,state='active');n.db.add(activation);n.db.flush()
    context=PackContext(company_id=1,branch_id=n.branch.id,activation_id=activation.id,pack_key=pack,pack_version=1,state='active');n.db.add(context);n.db.flush()
    for user,role in [(n.user,'doctor' if pack=='hospital' else 'stylist'),(n.admin,'hospital_manager' if pack=='hospital' else 'salon_manager')]:
        n.db.add(PackUserGrant(company_id=1,branch_id=n.branch.id,context_id=context.id,user_id=user.id,role=role))
    n.db.commit()
    return context


@pytest.mark.parametrize("native_scope",["own","assigned"])
def test_selected_pack_actual_time_complete_native_lifecycle_without_pack_stamps(core_case,native_scope):
    from app.business_packs.models import PackRecordOwnership
    from app.models.timesheet import Timesheet,TimesheetEntry
    n=core_case
    if native_scope=='assigned':
        from app.access.models import AccessPolicy
        policy=n.db.query(AccessPolicy).filter_by(user_id=n.user.id).one()
        policy.grants={'hrms':{**policy.grants['hrms'],'scope':'assigned'}};n.db.commit()
    context=select_pack(n)
    headers={**n.headers,'X-Suite-Pack-Context':str(context.id)}
    admin_headers={**n.admin_headers,'X-Suite-Pack-Context':str(context.id)}
    before=n.db.query(PackRecordOwnership).count()
    projects=n.client.get('/api/v1/timesheets/projects',headers=headers)
    assert projects.status_code==200,projects.text
    assert n.assigned.id in {row['id'] for row in projects.json()}
    created=n.client.post('/api/v1/timesheets/',headers=headers,json={'project_id':n.assigned.id,'period_start':'2026-11-09','period_end':'2026-11-15'})
    assert created.status_code==201,created.text
    sheet_id=created.json()['id'];assert created.json()['employee_id']==n.employee.id
    added=n.client.post(f'/api/v1/timesheets/{sheet_id}/entries',headers=headers,json={'work_date':'2026-11-10','hours':'2.5','is_billable':True,'task_name':'Actual work'})
    assert added.status_code==201,added.text
    submitted=n.client.put(f'/api/v1/timesheets/{sheet_id}/submit',headers=headers)
    assert submitted.status_code==200,submitted.text
    assert submitted.json()['status']=='Submitted' and float(submitted.json()['total_hours'])==2.5
    reviewed=n.client.put(f'/api/v1/timesheets/{sheet_id}/review',headers=admin_headers,json={'status':'Approved','review_remarks':'Native review'})
    assert reviewed.status_code==200,reviewed.text
    assert reviewed.json()['status']=='Approved'
    assert n.db.query(PackRecordOwnership).count()==before
    assert n.db.query(Timesheet).filter_by(id=sheet_id,employee_id=n.employee.id).count()==1
    assert n.db.query(TimesheetEntry).filter_by(timesheet_id=sheet_id).count()==1
    other=select_pack(n,'salon')
    switched=n.client.get('/api/v1/timesheets/',headers={**n.headers,'X-Suite-Pack-Context':str(other.id)})
    assert switched.status_code==200,switched.text
    assert [row['id'] for row in switched.json()]==[sheet_id]
    assert n.db.query(PackRecordOwnership).count()==before


def adversarial_projects(n):
    from app.models.user import User
    n.db.add(Company(id=2,name='Foreign common employer'))
    foreign_branch=Branch(company_id=2,name='Foreign employer branch')
    other_branch=Branch(company_id=1,name='Other same-company branch')
    n.db.add_all([foreign_branch,other_branch]);n.db.flush()
    employee=Employee(employee_id=uuid4().hex,first_name='Other',last_name='Employee',date_of_joining=date(2020,1,1),branch_id=n.branch.id,status='Active')
    n.db.add(employee);n.db.flush()
    rows={
        'coworker':Project(code=uuid4().hex,name='Other employee assigned',organization_id=1,created_by=n.admin.id,owner_employee_id=employee.id),
        'branch':Project(code=uuid4().hex,name='Unauthorized native branch',organization_id=1,created_by=n.admin.id,owner_employee_id=n.employee.id),
        'company':Project(code=uuid4().hex,name='Unauthorized native company',organization_id=2,created_by=n.admin.id,owner_employee_id=n.employee.id),
    }
    n.db.add_all(rows.values());n.db.flush()
    for key,row in rows.items():
        company=2 if key=='company' else 1
        branch=foreign_branch.id if key=='company' else other_branch.id if key=='branch' else n.branch.id
        n.db.add(BranchOwnership(company_id=company,branch_id=branch,resource_table='projects',resource_key=str(row.id),source='core-negative-fixture'))
    n.db.commit()
    return rows


@pytest.mark.parametrize('selected',[False,True])
def test_native_assignment_never_bypasses_own_company_or_branch(core_case,selected):
    n=core_case;rows=adversarial_projects(n)
    headers=n.headers
    if selected:headers={**headers,'X-Suite-Pack-Context':str(select_pack(n).id)}
    response=n.client.get('/api/v1/timesheets/projects',headers=headers)
    assert response.status_code==200,response.text
    assert {row['id'] for row in response.json()}=={n.own.id,n.assigned.id}
    for row in rows.values():
        denied=n.client.post('/api/v1/timesheets/',headers=headers,json={'project_id':row.id,'period_start':'2026-11-09','period_end':'2026-11-15'})
        assert denied.status_code in {403,404},denied.text



def core_proof_route(n,monkeypatch,callback):
    from fastapi import Depends
    from app.core.deps import get_current_user,get_db
    from app.main import app
    from app.business_packs import common_core
    from types import MappingProxyType
    path='/api/v1/timesheets/common-core-proof'
    monkeypatch.setattr(common_core,'OPERATIONS',MappingProxyType({**common_core.OPERATIONS,
        ('GET',path):common_core.CoreOperation('view','timesheet_view')}))
    def endpoint(db=Depends(get_db),user=Depends(get_current_user)):return callback(db,user)
    app.add_api_route(path,endpoint,methods=['GET']);route=app.routes[-1]
    try:return n.client.get(path,headers={**n.headers,'X-Suite-Pack-Context':str(n.context.id)})
    finally:app.routes.remove(route)


def test_core_cached_alias_expired_and_unknown_graph_reads_keep_all_native_guards(core_case,monkeypatch):
    from fastapi import HTTPException
    from sqlalchemy import select
    from sqlalchemy.orm import aliased
    from app.apps.srm.models import SRMInvoice
    n=core_case;rows=adversarial_projects(n);n.context=select_pack(n)
    own=n.own;own_id=own.id;foreign=rows['coworker'];foreign_id=foreign.id
    original_get=n.db.get;original_refresh=n.db.refresh
    def callback(db,user):
        Alias=aliased(Project)
        assert {row.id for row in db.query(Alias).all()}=={n.own.id,n.assigned.id}
        assert db.get(Project,foreign_id) is None
        with pytest.raises(HTTPException):db.refresh(foreign)
        db.expire(own)
        assert own.name=='Own native project'
        with pytest.raises(HTTPException):db.execute(select(Project.__table__.c.name)).all()
        with pytest.raises(HTTPException):db.query(SRMInvoice).all()
        assert db.get(SRMInvoice,1) is None
        return {'own':db.get(Project,own_id).id,'guarded':True}
    response=core_proof_route(n,monkeypatch,callback)
    assert response.status_code==200,response.text
    assert response.json()=={'own':own_id,'guarded':True}
    assert n.db.info.get('business_common_core_scope') is None
    assert n.db.get==original_get and n.db.refresh==original_refresh
    assert n.db.get(Project,foreign_id) is foreign


def test_private_anchor_cannot_be_reused_as_common_project_even_in_same_pack(core_case,monkeypatch):
    from fastapi import HTTPException
    from app.business_packs.models import PackRecordOwnership
    n=core_case;n.context=select_pack(n)
    ident=n.own.id;cached=n.own
    n.db.add(PackRecordOwnership(company_id=1,branch_id=n.branch.id,context_id=n.context.id,resource_table='projects',resource_key=str(ident)));n.db.commit()
    def callback(db,user):
        assert db.get(Project,ident) is None
        with pytest.raises(HTTPException):db.refresh(cached)
        assert ident not in {row.id for row in db.query(Project).all()}
        return {'private_excluded':True}
    response=core_proof_route(n,monkeypatch,callback)
    assert response.status_code==200,response.text
    assert response.json()['private_excluded']


@pytest.mark.parametrize('change',['pack','policy','branch','identity','role','role_name'])
def test_native_authority_change_is_rechecked_but_pack_grants_are_not_core_authority(core_case,monkeypatch,change):
    from sqlalchemy import update,delete
    from app.access.models import AccessPolicy
    from app.business_packs.models import PackUserGrant
    from app.models.user import role_permissions
    n=core_case;n.context=select_pack(n)
    def callback(db,user):
        if change=='pack':db.connection().execute(update(PackUserGrant).where(PackUserGrant.user_id==user.id).values(active=False))
        elif change=='policy':db.connection().execute(update(AccessPolicy).where(AccessPolicy.user_id==user.id).values(status='suspended'))
        elif change=='branch':db.connection().execute(update(BranchGrant).where(BranchGrant.user_id==user.id).values(can_write=False))
        elif change=='identity':db.connection().execute(update(Employee).where(Employee.user_id==user.id).values(reporting_manager_id=n.employee.id))
        elif change=='role':db.connection().execute(delete(role_permissions).where(role_permissions.c.role_id==user.role_id))
        elif change=='role_name':
            from app.models.user import Role
            db.connection().execute(update(Role).where(Role.id==user.role_id).values(name='changed_'+uuid4().hex))
        projects=db.query(Project).all()
        if change=='pack':return {'core_projects':[row.id for row in projects]}
        raise AssertionError('Changed native authority was not rejected')
    response=core_proof_route(n,monkeypatch,callback)
    assert response.status_code==(200 if change=='pack' else 403),response.text
    assert n.db.info.get('business_common_core_scope') is None


@pytest.mark.parametrize("pack_role",["doctor","hospital_manager"])
def test_common_core_does_not_enable_native_hrms_or_promote_pack_roles(core_case,pack_role):
    from app.access.models import AccessPolicy
    n=core_case;context=select_pack(n)
    from app.business_packs.models import PackUserGrant
    grant=n.db.query(PackUserGrant).filter_by(user_id=n.user.id,context_id=context.id).one();grant.role=pack_role
    policy=n.db.query(AccessPolicy).filter_by(user_id=n.user.id).one()
    policy.grants={'hrms':{**policy.grants['hrms'],'enabled':False}};n.db.commit()
    response=n.client.get('/api/v1/timesheets/projects',headers={**n.headers,'X-Suite-Pack-Context':str(context.id)})
    assert response.status_code==403,response.text


def test_native_managed_actions_are_not_inferred_from_view_permission(core_case):
    from app.access.models import AccessPolicy
    n=core_case;context=select_pack(n)
    policy=n.db.query(AccessPolicy).filter_by(user_id=n.user.id).one()
    policy.grants={'hrms':{**policy.grants['hrms'],'actions':['view']}};n.db.commit()
    headers={**n.headers,'X-Suite-Pack-Context':str(context.id)}
    assert n.client.get('/api/v1/timesheets/projects',headers=headers).status_code==200
    response=n.client.post('/api/v1/timesheets/',headers=headers,json={'project_id':n.assigned.id,'period_start':'2026-11-09','period_end':'2026-11-15'})
    assert response.status_code==403,response.text


def test_employee_detail_and_self_leave_integrated_but_360_payroll_remain_unreleased(core_case):
    n=core_case;context=select_pack(n);headers={**n.headers,'X-Suite-Pack-Context':str(context.id)}
    detail=n.client.get(f'/api/v1/employees/{n.employee.id}',headers=headers)
    assert detail.status_code==200,detail.text
    assert detail.json()['id']==n.employee.id
    leave=n.client.get('/api/v1/leave/my-requests',headers=headers)
    assert leave.status_code==200,leave.text
    assert leave.json()==[]
    encash=n.client.get('/api/v1/hrms/leave-encashment',headers=headers)
    assert encash.status_code==200,encash.text
    assert encash.json()==[]
    for path in (f'/api/v1/employees/{n.employee.id}/360','/api/v1/payroll/my-payslips','/api/v1/hrms/payroll/lwp-feed'):
        response=n.client.get(path,headers=headers)
        assert response.status_code==503,response.text
        assert response.json()['detail']['code']=='business_pack_integration_unavailable'


@pytest.mark.parametrize('own_scope',[False,True])
def test_native_project_maintenance_preserves_company_and_assignment(core_case,own_scope):
    from app.access.models import AccessPolicy
    n=core_case
    if own_scope:
        policy=n.db.query(AccessPolicy).filter_by(user_id=n.user.id).one()
        policy.grants={'hrms':{**policy.grants['hrms'],'permissions':['employee_view','timesheet_view','timesheet_manage'],'actions':['view','create','edit','delete']}}
        n.db.commit()
    context=select_pack(n)
    headers={**(n.headers if own_scope else n.admin_headers),'X-Suite-Pack-Context':str(context.id)}
    # An assigned native manager may edit an HR-created project while retaining
    # its actual employment owner, without changing native company/branch scope.
    target=n.assigned
    updated=n.client.put(f'/api/v1/timesheets/projects/{target.id}',headers=headers,json={'code':target.code,'name':'Updated assigned project','owner_employee_id':n.employee.id})
    assert updated.status_code==200,updated.text
    assert updated.json()['name']=='Updated assigned project'
    created=n.client.post('/api/v1/timesheets/projects',headers=headers,json={'code':uuid4().hex,'name':'Native new project','owner_employee_id':n.employee.id})
    assert created.status_code==201,created.text
    ident=created.json()['id']
    read=n.client.get(f'/api/v1/timesheets/projects/{ident}',headers=headers)
    assert read.status_code==200,read.text
    removed=n.client.delete(f'/api/v1/timesheets/projects/{ident}',headers=headers)
    assert removed.status_code==204,removed.text


def test_native_team_review_does_not_become_company_or_payroll_authority(core_case):
    from app.access.models import AccessPolicy,AccessMembership
    from app.models.timesheet import Timesheet
    n=core_case;rows=adversarial_projects(n)
    actor(n.db,role='core_setup_'+uuid4().hex,admin=True)
    membership=n.db.query(AccessMembership).filter_by(user_id=n.admin.id,company_id=1).one();membership.is_admin=False
    policy=n.db.query(AccessPolicy).filter_by(user_id=n.admin.id).one();policy.grants={'hrms':{**policy.grants['hrms'],'scope':'team'}}
    manager=Employee(employee_id=uuid4().hex,first_name='Native',last_name='Reviewer',date_of_joining=date(2020,1,1),user_id=n.admin.id,branch_id=n.branch.id,status='Active')
    n.db.add(manager);n.db.flush();n.employee.reporting_manager_id=manager.id
    other=Employee(employee_id=uuid4().hex,first_name='Unrelated',last_name='Employee',date_of_joining=date(2020,1,1),branch_id=n.branch.id,status='Active');n.db.add(other);n.db.flush()
    own=Timesheet(employee_id=n.employee.id,project_id=n.assigned.id,period_start=date(2026,11,9),period_end=date(2026,11,15),status='Submitted')
    foreign=Timesheet(employee_id=other.id,project_id=rows['coworker'].id,period_start=date(2026,11,9),period_end=date(2026,11,15),status='Submitted')
    n.db.add_all([own,foreign]);n.db.flush()
    for row in (own,foreign):n.db.add(BranchOwnership(company_id=1,branch_id=n.branch.id,resource_table='timesheets',resource_key=str(row.id),source='core-team-fixture'))
    n.db.commit();context=select_pack(n)
    headers={**n.admin_headers,'X-Suite-Pack-Context':str(context.id)}
    response=n.client.get('/api/v1/timesheets/',headers=headers)
    assert response.status_code==200,response.text
    assert [row['id'] for row in response.json()]==[own.id]
    denied=n.client.put(f'/api/v1/timesheets/{foreign.id}/review',headers=headers,json={'status':'Approved'})
    assert denied.status_code==404,denied.text
    reviewed=n.client.put(f'/api/v1/timesheets/{own.id}/review',headers=headers,json={'status':'Approved'})
    assert reviewed.status_code==200,reviewed.text
    assert not n.admin.is_superuser
    assert n.db.query(AccessMembership).filter_by(user_id=n.admin.id,is_admin=True).count()==0


def test_core_scope_is_distinct_immutable_and_uses_native_purpose_binding(core_case,monkeypatch):
    from dataclasses import FrozenInstanceError
    from fastapi import HTTPException
    from app.business_packs.common_core import CommonCoreScope,install
    from app.business_packs.access import PackScope
    from app.business_packs.common_binding import CoreRequestBinding,MARKER
    n=core_case;n.context=select_pack(n)
    def callback(db,user):
        core=db.info['business_common_core_scope'];pack=db.info['business_pack_scope']
        assert isinstance(core,CommonCoreScope) and pack is None
        assert isinstance(core.binding,CoreRequestBinding) and not isinstance(core.binding,PackScope)
        assert db.info[MARKER]==core.binding
        assert core.company_id==1 and core.user_id==user.id
        with pytest.raises(FrozenInstanceError):core.company_id=2
        with pytest.raises(HTTPException):install(db,user,pack)
        return {'distinct':True}
    response=core_proof_route(n,monkeypatch,callback)
    assert response.status_code==200,response.text


def test_all_common_core_routes_are_exact_actual_native_decorators():
    import ast,inspect
    from pathlib import Path
    from fastapi.routing import APIRoute,iter_route_contexts
    from app.main import app
    from app.business_packs.common_core import OPERATIONS
    for (method,path),operation in OPERATIONS.items():
        context=next((r for r in iter_route_contexts(app.router.routes) if r.path==path and method in(r.methods or ())),None)
        assert context and isinstance(context.original_route,APIRoute),(method,path)
        function=context.endpoint
        parsed=ast.parse(Path(inspect.getsourcefile(function)).read_text(encoding='utf-8-sig'))
        assert any(isinstance(node,ast.FunctionDef) and node.name==function.__name__ and any(
            isinstance(dec,ast.Call) and isinstance(dec.func,ast.Attribute) and dec.func.attr==method.lower()
            and dec.args and isinstance(dec.args[0],ast.Constant) and path.endswith(dec.args[0].value)
            for dec in node.decorator_list) for node in parsed.body)


@pytest.mark.parametrize('selected',[False,True])
def test_approved_own_actual_history_survives_project_owner_reassignment(core_case,selected):
    from app.models.timesheet import Timesheet,TimesheetEntry
    n=core_case
    other=Employee(employee_id=uuid4().hex,first_name='Reassigned',last_name='Owner',date_of_joining=date(2020,1,1),branch_id=n.branch.id,status='Active');n.db.add(other);n.db.flush()
    sheet=Timesheet(employee_id=n.employee.id,project_id=n.assigned.id,period_start=date(2026,11,9),period_end=date(2026,11,15),status='Approved',total_hours=2.5,billable_hours=2.5,non_billable_hours=0)
    n.db.add(sheet);n.db.flush();n.db.add(TimesheetEntry(timesheet_id=sheet.id,work_date=date(2026,11,10),hours=2.5,is_billable=True))
    from app.branches.migration import backfill
    backfill(n.db.connection(),1);n.db.commit();ident=sheet.id
    headers=n.headers;admin=n.admin_headers
    if selected:
        context=select_pack(n);headers={**headers,'X-Suite-Pack-Context':str(context.id)};admin={**admin,'X-Suite-Pack-Context':str(context.id)}
    before=n.client.get('/api/v1/timesheets/',headers=headers)
    assert before.status_code==200,before.text
    assert ident in {row['id'] for row in before.json()}
    changed=n.client.put(f'/api/v1/timesheets/projects/{n.assigned.id}',headers=admin,json={'code':n.assigned.code,'name':n.assigned.name,'owner_employee_id':other.id})
    assert changed.status_code==200,changed.text
    historical=n.client.get('/api/v1/timesheets/',headers=headers)
    assert historical.status_code==200,historical.text
    assert ident in {row['id'] for row in historical.json()}
    row=next(row for row in historical.json() if row['id']==ident)
    assert float(row['total_hours'])==2.5 and len(row['entries'])==1
    project=n.client.get(f'/api/v1/timesheets/projects/{n.assigned.id}',headers=headers)
    assert project.status_code==404,project.text
    n.db.refresh(sheet);assert sheet.status=='Approved' and float(sheet.total_hours)==2.5


@pytest.mark.parametrize('selected',[False,True])
def test_historical_read_does_not_authorize_new_hours_on_reassigned_project(core_case,selected):
    from app.models.timesheet import Timesheet,TimesheetEntry
    n=core_case
    other=Employee(employee_id=uuid4().hex,first_name='New',last_name='Owner',date_of_joining=date(2020,1,1),branch_id=n.branch.id,status='Active');n.db.add(other);n.db.flush()
    sheet=Timesheet(employee_id=n.employee.id,project_id=n.assigned.id,period_start=date(2026,11,9),period_end=date(2026,11,15),status='Draft')
    n.db.add(sheet);n.db.flush()
    from app.branches.migration import backfill
    backfill(n.db.connection(),1);n.db.commit()
    headers=n.headers;admin=n.admin_headers
    if selected:
        context=select_pack(n);headers={**headers,'X-Suite-Pack-Context':str(context.id)};admin={**admin,'X-Suite-Pack-Context':str(context.id)}
    changed=n.client.put(f'/api/v1/timesheets/projects/{n.assigned.id}',headers=admin,json={'code':n.assigned.code,'name':n.assigned.name,'owner_employee_id':other.id})
    assert changed.status_code==200,changed.text
    denied=n.client.post(f'/api/v1/timesheets/{sheet.id}/entries',headers=headers,json={'work_date':'2026-11-10','hours':'1','is_billable':True})
    assert denied.status_code==403,denied.text
    new=n.client.post('/api/v1/timesheets/',headers=headers,json={'project_id':n.assigned.id,'period_start':'2026-11-16','period_end':'2026-11-22'})
    assert new.status_code in {403,404},new.text
    assert n.db.query(TimesheetEntry).filter_by(timesheet_id=sheet.id).count()==0
    n.db.refresh(sheet);assert float(sheet.total_hours)==0


@pytest.mark.parametrize('selected',[False,True])
@pytest.mark.parametrize('status',['Submitted','Approved','Rejected'])
def test_submit_retries_never_downgrade_reviewed_actual_time(core_case,selected,status):
    from datetime import datetime,timezone
    from app.models.timesheet import Timesheet,TimesheetEntry
    n=core_case
    sheet=Timesheet(employee_id=n.employee.id,project_id=n.assigned.id,period_start=date(2026,11,9),period_end=date(2026,11,15),status=status,total_hours=2,billable_hours=2,non_billable_hours=0,submitted_at=datetime(2026,11,15,10,0,tzinfo=timezone.utc))
    n.db.add(sheet);n.db.flush();n.db.add(TimesheetEntry(timesheet_id=sheet.id,work_date=date(2026,11,10),hours=2,is_billable=True))
    from app.branches.migration import backfill
    backfill(n.db.connection(),1);n.db.commit()
    headers=n.headers
    if selected:headers={**headers,'X-Suite-Pack-Context':str(select_pack(n).id)}
    before=n.client.get('/api/v1/timesheets/',headers=headers)
    assert before.status_code==200,before.text
    original=next(row for row in before.json() if row['id']==sheet.id)
    updated=sheet.updated_at
    response=n.client.put(f'/api/v1/timesheets/{sheet.id}/submit',headers=headers)
    assert response.status_code==(200 if status=='Submitted' else 409),response.text
    after=n.client.get('/api/v1/timesheets/',headers=headers)
    assert after.status_code==200,after.text
    assert next(row for row in after.json() if row['id']==sheet.id)==original
    n.db.refresh(sheet);assert sheet.status==status and sheet.updated_at==updated


@pytest.mark.parametrize('selected',[False,True])
def test_project_delete_cannot_cascade_hidden_other_employee_actuals(core_case,selected):
    from app.access.models import AccessPolicy
    from app.models.timesheet import Timesheet,TimesheetEntry
    n=core_case
    policy=n.db.query(AccessPolicy).filter_by(user_id=n.user.id).one()
    policy.grants={'hrms':{**policy.grants['hrms'],'permissions':['employee_view','timesheet_view','timesheet_manage'],'actions':['view','create','edit','delete']}}
    other=Employee(employee_id=uuid4().hex,first_name='Historical',last_name='Worker',date_of_joining=date(2020,1,1),branch_id=n.branch.id,status='Active');n.db.add(other);n.db.flush()
    sheet=Timesheet(employee_id=other.id,project_id=n.own.id,period_start=date(2026,11,9),period_end=date(2026,11,15),status='Approved',total_hours=3,billable_hours=3,non_billable_hours=0)
    n.db.add(sheet);n.db.flush();n.db.add(TimesheetEntry(timesheet_id=sheet.id,work_date=date(2026,11,10),hours=3,is_billable=True))
    from app.branches.migration import backfill
    backfill(n.db.connection(),1);n.db.commit()
    sheet_id=sheet.id;project_id=n.own.id;empty_id=n.assigned.id
    headers=n.headers
    if selected:headers={**headers,'X-Suite-Pack-Context':str(select_pack(n).id)}
    visible=n.client.get('/api/v1/timesheets/',headers=headers)
    assert visible.status_code==200 and visible.json()==[],visible.text
    project=n.client.get(f'/api/v1/timesheets/projects/{project_id}',headers=headers)
    assert project.status_code==200,project.text
    refused=n.client.delete(f'/api/v1/timesheets/projects/{project_id}',headers=headers)
    assert refused.status_code==409,refused.text
    assert n.db.get(Project,project_id) is not None
    assert n.db.get(Timesheet,sheet_id).status=='Approved'
    assert n.db.query(TimesheetEntry).filter_by(timesheet_id=sheet_id).count()==1
    empty=n.client.delete(f'/api/v1/timesheets/projects/{empty_id}',headers=headers)
    assert empty.status_code==204,empty.text



def test_actual_native_company_admin_read_ceiling_is_preserved_without_write_promotion(core_case):
    from app.access.models import AccessPolicy
    n=core_case
    policy=n.db.query(AccessPolicy).filter_by(user_id=n.admin.id).one()
    policy.grants={'hrms':{**policy.grants['hrms'],'enabled':False,'permissions':[],'actions':[],'scope':'own'}};n.db.commit()
    legacy=n.client.get('/api/v1/timesheets/projects',headers=n.admin_headers)
    assert legacy.status_code==200,legacy.text
    context=select_pack(n);headers={**n.admin_headers,'X-Suite-Pack-Context':str(context.id)}
    selected=n.client.get('/api/v1/timesheets/projects',headers=headers)
    assert selected.status_code==200,selected.text
    assert selected.json()==legacy.json()
    denied=n.client.post('/api/v1/timesheets/projects',headers=headers,json={'code':uuid4().hex,'name':'No native write authority'})
    assert denied.status_code==403,denied.text


@pytest.mark.parametrize('changed',['role_id','is_superuser'])
def test_initial_actor_role_race_cannot_capture_fresh_hash_with_stale_permissions(core_case,monkeypatch,changed):
    from sqlalchemy import update
    from app.models.user import User,Role
    from app.business_packs import common_core
    n=core_case;context=select_pack(n)
    other=Role(name='core_race_'+uuid4().hex,permissions=[]);n.db.add(other);n.db.commit()
    original=common_core._native_authority
    changed_once=False
    def raced(db,user,company):
        nonlocal changed_once
        old=(user.role_id,user.is_superuser)  # Ensure native actor is the cached pre-change identity.
        if not changed_once:
            changed_once=True
            db.connection().execute(update(User).where(User.id==user.id).values(**{changed:other.id if changed=='role_id' else True}))
        return original(db,user,company)
    monkeypatch.setattr(common_core,'_native_authority',raced)
    response=n.client.get('/api/v1/timesheets/projects',headers={**n.headers,'X-Suite-Pack-Context':str(context.id)})
    assert response.status_code==403,response.text
    assert 'actor role changed' in response.text


def test_initial_unmanaged_role_permission_revocation_rejects_stale_compiled_permissions(core_case,monkeypatch):
    from sqlalchemy import delete
    from app.access.models import AccessPolicy
    from app.models.user import Permission,role_permissions
    from app.business_packs import common_core
    n=core_case
    n.db.query(AccessPolicy).filter_by(user_id=n.user.id).delete();n.db.commit()
    permission=n.db.query(Permission).filter_by(name='timesheet_view').one()
    original=common_core._native_authority
    changed=False
    def raced(db,user,company,**kwargs):
        nonlocal changed
        if not changed:
            changed=True
            assert user._suite_grants is None
            assert 'timesheet_view' in {item.name for item in user._suite_permission_objects}
            db.connection().execute(delete(role_permissions).where(role_permissions.c.role_id==user.role_id,role_permissions.c.permission_id==permission.id))
        return original(db,user,company,**kwargs)
    monkeypatch.setattr(common_core,'_native_authority',raced)
    result=n.client.get('/api/v1/timesheets/projects',headers=n.headers)
    assert result.status_code==403,result.text
    assert 'native role permissions changed' in result.text



def test_initial_native_admin_revocation_denies_instead_of_falling_back_to_own_view(core_case,monkeypatch):
    from sqlalchemy import update
    from app.access.models import AccessPolicy,AccessMembership
    from app.business_packs import common_core
    n=core_case
    policy=n.db.query(AccessPolicy).filter_by(user_id=n.admin.id).one()
    policy.grants={'hrms':{**policy.grants['hrms'],'scope':'own'}};n.db.commit()
    context=select_pack(n)
    original=common_core._native_operation_access
    revoked=False
    def raced(db,user,company,operation):
        nonlocal revoked
        assert user._suite_admin_read and db.info['admin_read_company']==company
        if not revoked:
            revoked=True
            db.connection().execute(update(AccessMembership).where(AccessMembership.user_id==user.id,AccessMembership.company_id==company).values(is_admin=False))
        return original(db,user,company,operation)
    monkeypatch.setattr(common_core,'_native_operation_access',raced)
    response=n.client.get('/api/v1/timesheets/projects',headers={**n.admin_headers,'X-Suite-Pack-Context':str(context.id)})
    assert response.status_code==403,response.text
    assert 'Fresh native administrative read authority' in response.text


def test_initial_policy_version_race_rejects_old_compiled_native_grants(core_case,monkeypatch):
    from sqlalchemy import update
    from app.access.models import AccessPolicy
    from app.business_packs import common_core
    n=core_case;context=select_pack(n)
    original=common_core._native_authority
    changed=False
    def raced(db,user,company):
        nonlocal changed
        if not changed:
            changed=True
            assert user._suite_policy_version is not None
            db.connection().execute(update(AccessPolicy).where(AccessPolicy.user_id==user.id,AccessPolicy.company_id==company).values(version=user._suite_policy_version+1))
        return original(db,user,company)
    monkeypatch.setattr(common_core,'_native_authority',raced)
    response=n.client.get('/api/v1/timesheets/projects',headers={**n.headers,'X-Suite-Pack-Context':str(context.id)})
    assert response.status_code==403,response.text
    assert 'policy changed' in response.text


@pytest.mark.parametrize('administrator',[False,True])
def test_initial_managed_role_version_race_cannot_legalize_old_organization_scope(core_case,monkeypatch,administrator):
    from sqlalchemy import update,select
    from app.access.models import AccessPolicy,AccessRole
    from app.business_packs import common_core
    n=core_case;others=adversarial_projects(n)
    account=n.admin if administrator else n.user
    managed=AccessRole(company_id=1,module_key='hrms',name='core_managed_'+uuid4().hex,permissions=['employee_view','timesheet_view'],actions=['view'],scope='organization',active=True,version=1)
    n.db.add(managed);n.db.flush()
    policy=n.db.query(AccessPolicy).filter_by(user_id=account.id).one()
    policy.grants={'hrms':{'enabled':True,'roleId':managed.id}};n.db.commit()
    role_id=managed.id;context=select_pack(n)
    original=common_core._native_authority
    changed=False
    def raced(db,user,company):
        nonlocal changed
        assert user._suite_grants['hrms']['roleId']==role_id
        assert user._suite_grants['hrms']['roleVersion']==1
        if not changed:
            changed=True
            db.connection().execute(update(AccessRole).where(AccessRole.id==role_id).values(scope='own',version=2))
            assert db.connection().scalar(select(AccessPolicy.version).where(AccessPolicy.user_id==user.id))==user._suite_policy_version
        return original(db,user,company)
    monkeypatch.setattr(common_core,'_native_authority',raced)
    response=n.client.get('/api/v1/timesheets/projects',headers={**(n.admin_headers if administrator else n.headers),'X-Suite-Pack-Context':str(context.id)})
    assert response.status_code==(200 if administrator else 403),response.text
    if administrator:
        assert others['coworker'].id in {row['id'] for row in response.json()}
    else:assert 'managed role changed' in response.text



def test_postgres_project_delete_waits_for_inflight_actual_time_insert(db_engine):
    """Exercise the actual handler against two committed native transactions."""
    if db_engine.dialect.name!='postgresql':pytest.skip('Real PostgreSQL FK key-share/row-lock proof')
    from threading import Thread,Event
    from time import monotonic
    from sqlalchemy import insert,delete,select,text,event
    from sqlalchemy.orm import Session
    from fastapi import HTTPException
    from app.models.user import User
    from app.models.timesheet import Timesheet
    from app.api.v1.timesheets import delete_timesheet_project
    from app.db.base_class import Base
    suffix=uuid4().hex
    schema='core_lock_'+suffix
    with db_engine.begin() as connection:
        connection.exec_driver_sql('CREATE SCHEMA '+schema)
    isolated_engine=db_engine.execution_options(schema_translate_map={None:schema})
    tables={model.__table__ for model in (Company,Branch,User,Employee,Project,Timesheet)}
    while True:
        related={foreign.column.table for table in tables for foreign in table.foreign_keys}
        if related<=tables:break
        tables|=related
    Base.metadata.create_all(isolated_engine,tables=list(tables))
    with isolated_engine.begin() as connection:
        company=connection.execute(insert(Company).values(name='Concurrent employer '+suffix).returning(Company.id)).scalar_one()
        branch=connection.execute(insert(Branch).values(company_id=company,name='Concurrency branch').returning(Branch.id)).scalar_one()
        account=connection.execute(insert(User).values(email=suffix+'@example.invalid',hashed_password='unused',is_active=True,is_superuser=True).returning(User.id)).scalar_one()
        employee=connection.execute(insert(Employee).values(employee_id=suffix,first_name='Actual',last_name='Worker',date_of_joining=date(2020,1,1),branch_id=branch,user_id=account,status='Active').returning(Employee.id)).scalar_one()
        project=connection.execute(insert(Project).values(code=suffix,name='Locked native project',organization_id=company,created_by=account,owner_employee_id=employee).returning(Project.id)).scalar_one()
    attempted=Event();finished=Event();outcome={}
    def run_delete():
        try:
            with Session(bind=isolated_engine) as session:
                actor=session.get(User,account);actor.organization_id=company
                session.connection().execute(text("SET LOCAL lock_timeout = '15s'"))
                outcome['pid']=session.connection().scalar(text('SELECT pg_backend_pid()'))
                def before_execute(connection,cursor,statement,parameters,context,many):
                    if 'projects' in statement and 'FOR UPDATE' in statement:attempted.set()
                delete_connection=session.connection()
                event.listen(delete_connection,'before_cursor_execute',before_execute)
                try:delete_timesheet_project(project,session,actor)
                except HTTPException as error:outcome['status']=error.status_code;session.rollback()
                finally:event.remove(delete_connection,'before_cursor_execute',before_execute)
        except BaseException as error:outcome['error']=str(error)
        finally:finished.set()
    worker=None
    try:
        with isolated_engine.connect() as writer:
            transaction=writer.begin()
            writer.execute(insert(Timesheet).values(employee_id=employee,project_id=project,period_start=date(2026,11,9),period_end=date(2026,11,15),status='Approved',total_hours=3,billable_hours=3,non_billable_hours=0))
            worker=Thread(target=run_delete,daemon=True);worker.start()
            try:
                assert attempted.wait(5),'Actual delete handler did not issue its parent FOR UPDATE lock'
                deadline=monotonic()+5;waiting=False
                while monotonic()<deadline and not finished.is_set():
                    writer.execute(text('SELECT pg_stat_clear_snapshot()'))
                    waiting=writer.execute(text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"),{'pid':outcome['pid']}).scalar()=='Lock'
                    if waiting:break
                    finished.wait(.02)
                assert waiting and not finished.is_set(),outcome
            finally:transaction.commit()
            assert finished.wait(10),'Delete did not finish after the FK insert committed'
            assert 'error' not in outcome and outcome.get('status')==409,outcome
            assert writer.scalar(select(Project.id).where(Project.id==project))==project
            assert writer.scalar(select(Timesheet.id).where(Timesheet.project_id==project)) is not None
    finally:
        if worker:worker.join(10)
        # Own-schema cleanup cannot bypass or collide with the native branch
        # recovery trigger on the public tables used by the rest of the suite.
        with db_engine.begin() as connection:
            connection.exec_driver_sql('DROP SCHEMA '+schema+' CASCADE')
