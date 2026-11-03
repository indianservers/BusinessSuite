"""Branch head/employee ownership matrix, plus every mapped private read path.

The per-model sweep checks query enforcement, not every business workflow.
Representative persisted rows test actual visibility and mutation boundaries.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func, event, String, Integer, Numeric, Boolean, Date, DateTime, JSON, LargeBinary
from sqlalchemy.orm import aliased
from app.db.base_class import Base
from app.models.company import Company, Branch
from app.models.user import User
from app.models.employee import Employee
from app.common.models import CommonPerson, CommonProfile
from app.branches.models import BranchGrant, BranchPolicy, BranchOwnership
from app.branches.service import context
from app.branches.boundary import install
from app.branches.catalog import SHARED, resource_key
from tests.tenant_test_utils import assign_company


@pytest.fixture
def matrix(db):
    if not db.get(Company, 1): db.add(Company(id=1, name='Ownership matrix', is_active=True))
    db.flush()
    branches=[]
    for code in ('A','B','C'):
        row=Branch(company_id=1,name=f'Matrix {code}',code=f'MATRIX-{code}')
        db.add(row);db.flush();branches.append(row)
        db.add(BranchOwnership(resource_table='branches',resource_key=str(row.id),company_id=1,branch_id=row.id,source='matrix-fixture'))
    people={}
    for label,idx,head,all_access,superuser in [
        ('head_a',0,True,False,False),('head_b',1,True,False,False),
        ('employee_a',0,False,False,False),('employee_b',1,False,False,False),
        ('multi',0,False,False,False),('all_reader',None,False,True,False),
        ('super',None,True,True,True),('none',None,False,False,False)]:
        user=User(email=f'matrix.{label}@example.org',hashed_password='unused',is_active=True,is_superuser=superuser)
        db.add(user);db.flush();assign_company(db,user,1)
        db.add(BranchPolicy(user_id=user.id,company_id=1,use_home_branch=False,manage_access=head,all_branches=all_access))
        if idx is not None:
            db.add(BranchGrant(user_id=user.id,company_id=1,branch_id=branches[idx].id,can_write=head))
            employee=Employee(user_id=user.id,employee_id=f'MATRIX-{label}',first_name=label,last_name='Synthetic',date_of_joining=date(2026,1,1),branch_id=branches[idx].id,work_email=user.email)
            db.add(employee);db.flush()
            db.add(BranchOwnership(resource_table='employees',resource_key=str(employee.id),company_id=1,branch_id=branches[idx].id,source='matrix-fixture'))
        if label=='multi': db.add(BranchGrant(user_id=user.id,company_id=1,branch_id=branches[1].id,can_write=False))
        person=db.query(CommonPerson).filter_by(user_id=user.id).one()
        db.add(CommonProfile(person_id=person.id,bio=f'Synthetic profile {label}'))
        user.organization_id=1
        people[label]=user
    db.commit()
    return branches,people


def test_branch_head_roster_does_not_expose_other_branch_users_or_role_grants(db,matrix):
    from app.branches.api import users,read_policy
    branches,people=matrix
    head=people['head_a']
    roster={r['id'] for r in users(db,head)}
    assert people['employee_a'].id in roster
    assert people['multi'].id in roster
    assert people['employee_b'].id not in roster
    assert people['head_b'].id not in roster
    with pytest.raises(HTTPException) as denied:
        read_policy(people['employee_b'].id,db,head)
    assert denied.value.status_code==404
    response=read_policy(people['multi'].id,db,head)
    assert {g['branch_id'] for g in response['grants']}=={branches[0].id}


def test_branch_head_cannot_escalate_or_erase_hidden_multi_branch_grants(db,matrix):
    from starlette.requests import Request
    from app.branches.api import PolicyInput,save_policy,read_policy
    branches,people=matrix
    head=people['head_a']
    request=Request({'type':'http','method':'PUT','path':'/api/v1/branches/access','headers':[]})
    target=people['employee_a']
    before=read_policy(target.id,db,head)
    base={'expected_version':before['version'],'use_home_branch':False,'reason':'Privilege escalation test'}
    for patch in [
        {'all_branches':True}, {'manage_access':True},
        {'grants':[{'branch_id':branches[1].id,'can_write':True}]},
    ]:
        with pytest.raises(HTTPException) as denied:
            save_policy(target.id,PolicyInput(**{**base,**patch}),request,db,head)
        assert denied.value.status_code==403
    multi=people['multi']
    before=read_policy(multi.id,db,head)
    assert len(before['grants'])==1
    with pytest.raises(HTTPException) as denied:
        save_policy(multi.id,PolicyInput(expected_version=before['version'],use_home_branch=False,reason='Cannot erase the hidden branch'),request,db,head)
    assert denied.value.status_code==403
    assert db.query(BranchGrant).filter_by(user_id=multi.id).count()==2
    with pytest.raises(HTTPException):
        save_policy(head.id,PolicyInput(**base),request,db,head)


@pytest.mark.parametrize('actor,selection,visible',[
    ('head_a',0,{'head_a','employee_a','multi','all_reader','super'}),
    ('employee_a',0,{'head_a','employee_a','multi','all_reader','super'}),
    ('head_b',1,{'head_b','employee_b','multi','all_reader','super'}),
    ('multi',1,{'head_b','employee_b','multi','all_reader','super'}),
    ('all_reader','all',{'head_a','head_b','employee_a','employee_b','multi','all_reader','super'}),
    ('super','all',{'head_a','head_b','employee_a','employee_b','multi','all_reader','super','none'}),
    ('none',None,{'none'}),
])
def test_users_profiles_and_employees_follow_selected_branch(db,matrix,actor,selection,visible):
    branches,people=matrix
    selected=branches[selection].id if isinstance(selection,int) else selection
    cleanup=install(db,people[actor],context(db,people[actor],1,selected))
    try:
        actual={label for label,user in people.items() if db.get(User,user.id) is not None}
        assert actual==visible
        assert {r.user_id for r in db.query(CommonPerson)}=={people[label].id for label in visible}
        profile_labels=set(visible)
        if selection==1: profile_labels-={'head_a','employee_a','multi'}
        if selection==0: profile_labels-={'head_b','employee_b'}
        profile_labels.add(actor)  # Personal self-service remains available.
        assert db.query(CommonProfile).count()==len(profile_labels)
        employees=db.query(Employee).all()
        if isinstance(selection,int): assert {e.branch_id for e in employees}<={branches[selection].id}
        elif actor=='none': assert not employees
    finally: cleanup()


TABLES=[
    'audit_logs','ai_prompt_runs','analytics_dashboards','approval_requests',
    'automation_execution_logs','bos_lifecycle_events','communication_campaigns',
    'crm_companies','customization_records','fam_integrity_runs','suite_forms',
    'power_apps_resources','pms_workspaces','developer_apps','schedule_boards',
    'admin_audit_logs','srm_sales_orders','srm_collection_reminders','notifications',
]


def seed_probe(db,model,branch,user,marker):
    """Minimal valid synthetic root, with explicit trusted fixture ownership."""
    values={}
    table=model.__table__
    for column in table.c:
        if column.primary_key: continue
        if column.name in {'organization_id','company_id'}:
            # CRM company_id can mean customer; these selected roots use org/company tenants.
            values[column.name]=1;continue
        if column.name=='branch_id':values[column.name]=branch.id;continue
        if column.foreign_keys and any(fk.column.table.name=='users' for fk in column.foreign_keys):
            values[column.name]=user.id;continue
        if column.nullable or column.default is not None or column.server_default is not None:continue
        kind=column.type
        if isinstance(kind,Boolean):value=False
        elif isinstance(kind,Integer):value=1
        elif isinstance(kind,Numeric):value=Decimal('0')
        elif isinstance(kind,DateTime):value=datetime.now(timezone.utc)
        elif isinstance(kind,Date):value=date(2026,11,2)
        elif isinstance(kind,JSON):value={}
        elif isinstance(kind,LargeBinary):value=b'qa'
        elif isinstance(kind,String):value=marker[:kind.length] if kind.length else marker
        else:raise AssertionError((table.name,column.name,kind))
        values[column.name]=value
    for name in ('name','title','order_number','slug'):
        if name in table.c:values[name]=marker
    if 'environment' in table.c:values['environment']='development'
    if 'tenant_key' in table.c:values['tenant_key']='company:1'
    item=model(**values);db.add(item);db.flush()
    db.add(BranchOwnership(resource_table=table.name,resource_key=resource_key(table,{c.name:getattr(item,c.name) for c in table.primary_key}),company_id=1,branch_id=branch.id,source='matrix-fixture'))
    db.flush()
    return item


@pytest.mark.parametrize('table_name',TABLES)
def test_module_owned_records_lists_counts_ids_aliases_writes_and_superadmin(db,matrix,table_name):
    branches,people=matrix
    model=next(m.class_ for m in Base.registry.mappers if m.local_table.name==table_name)
    rows=[seed_probe(db,model,branch,people['head_a'],f'Matrix-{table_name}-{i}') for i,branch in enumerate(branches)]
    db.commit()
    ids=[row.id for row in rows]
    for actor,selection,expected in [('head_a',0,[ids[0]]),('employee_a',0,[ids[0]]),('head_b',1,[ids[1]]),('multi',1,[ids[1]]),('all_reader','all',ids),('super','all',ids),('super',1,[ids[1]]),('none',None,[])]:
        selected=branches[selection].id if isinstance(selection,int) else selection
        cleanup=install(db,people[actor],context(db,people[actor],1,selected))
        try:
            assert sorted(r.id for r in db.query(model))==sorted(expected),(actor,table_name)
            assert db.query(func.count(model.id)).scalar()==len(expected)
            alias=aliased(model)
            assert sorted(db.scalars(select(alias.id)))==sorted(expected)
            for ident in ids:assert (db.get(model,ident) is not None)==(ident in expected)
        finally:cleanup()
    # Identity-map contents from earlier privileged reads cannot authorize writes.
    cleanup=install(db,people['head_a'],context(db,people['head_a'],1,branches[0].id))
    try:
        db.delete(rows[1])
        with pytest.raises(HTTPException):db.flush()
        db.rollback()
    finally:cleanup()


def test_every_mapped_private_table_read_contains_ownership_guard(db,matrix):
    branches,people=matrix
    statements=[]
    def capture(connection,cursor,statement,parameters,context,many):statements.append(statement.lower())
    event.listen(db.connection(),'before_cursor_execute',capture)
    cleanup=install(db,people['head_a'],context(db,people['head_a'],1,branches[0].id))
    tested=[]
    try:
        for mapper in sorted(Base.registry.mappers,key=lambda m:m.local_table.name):
            if mapper.local_table.name in SHARED:continue
            statements.clear()
            db.execute(select(mapper.class_).limit(0)).all()
            assert statements and 'suite_branch_ownership' in statements[-1],mapper.local_table.name
            tested.append(mapper.local_table.name)
        assert len(tested)>=690
    finally:
        cleanup();event.remove(db.connection(),'before_cursor_execute',capture)


def test_explicit_srm_scope_overrides_native_role_without_cross_branch_reads(db,matrix):
    from app.apps.srm.models import SRMSalesOrder
    from app.apps.srm.access import sales_order_query
    branches,people=matrix
    rows=[seed_probe(db,SRMSalesOrder,b,people['employee_a'],f'Matrix-order-{i}') for i,b in enumerate(branches)]
    db.commit()
    head=people['head_a']
    head._suite_grants={'srm':{'enabled':True,'scope':'organization'}}
    cleanup=install(db,head,context(db,head,1,branches[0].id))
    try:
        assert [r.id for r in sales_order_query(db,head)]==[rows[0].id]
        head._suite_grants={'srm':{'enabled':True,'scope':'own'}}
        assert sales_order_query(db,head).count()==0
    finally:cleanup();head._suite_grants=None


def test_explicit_hr_role_can_manage_own_branch_profiles_but_not_other_branch(db,matrix):
    from app.models.user import Permission
    from app.access.scope import install_scope
    from app.common.services.profiles import authorized_user
    branches,people=matrix
    head=people['head_a']
    permissions=[Permission(name=n,module='employees') for n in ['employee_view','employee_update']]
    db.add_all(permissions);db.commit()
    grants={'hrms':{'enabled':True,'scope':'organization','permissions':[p.name for p in permissions],'actions':['view','edit']}}
    head._suite_grants=grants;head._suite_permission_objects=permissions
    scope=install_scope(db,head,1,grants)
    cleanup=install(db,head,context(db,head,1,branches[0].id))
    try:
        assert authorized_user(db,head,people['employee_a'].id).id==people['employee_a'].id
        with pytest.raises(HTTPException):authorized_user(db,head,people['employee_b'].id)
    finally:cleanup();scope();head._suite_grants=None;head._suite_permission_objects=None
    # The multi-branch identity is visible in B, but its employee/profile lives
    # in A. HR access to B must never reveal A's private onboarding fields.
    other=people['head_b'];other._suite_grants=grants;other._suite_permission_objects=permissions
    scope=install_scope(db,other,1,grants)
    cleanup=install(db,other,context(db,other,1,branches[1].id))
    try:
        assert db.get(User,people['multi'].id) is not None
        with pytest.raises(HTTPException):authorized_user(db,other,people['multi'].id)
        person=people['multi'].person
        assert db.query(CommonProfile).filter_by(person_id=person.id).first() is None
    finally:cleanup();scope();other._suite_grants=None;other._suite_permission_objects=None


def test_business_module_discovery_is_read_only_for_branch_heads(db,matrix):
    from app.apps.business_os.api.router import get_dynamic_dashboard
    from app.apps.business_os.models import BOSEnabledModule
    from app.apps.business_os.services.module_service import DEFAULT_ENABLED_MODULES
    from app.access.scope import install_scope
    branches,people=matrix
    head=people['head_a']
    grants={'business_os':{'enabled':True,'scope':'organization','permissions':[],'actions':['view']}}
    head._suite_grants=grants
    scope=install_scope(db,head,1,grants)
    cleanup=install(db,head,context(db,head,1,branches[0].id))
    try:
        response=get_dynamic_dashboard(db,head)
        assert set(response['enabled_modules'])==set(DEFAULT_ENABLED_MODULES)
        assert not db.new and not db.dirty
        assert db.connection().execute(select(func.count()).select_from(BOSEnabledModule)).scalar()==0
    finally:cleanup();scope();head._suite_grants=None


def test_branch_head_cannot_change_company_module_configuration(db,matrix):
    from app.apps.business_os.api.router import put_modules
    from app.apps.business_os.schemas import BOSModulesUpdate
    branches,people=matrix
    with pytest.raises(HTTPException) as denied:
        put_modules(BOSModulesUpdate(enabled_modules=['crm']),db,people['head_a'])
    assert denied.value.status_code==403


def test_skipped_handoff_evidence_stays_in_its_branch_without_a_live_parent(db,matrix):
    from app.apps.business_os.models import BOSLifecycleEvent
    branches,people=matrix
    cleanup=install(db,people['head_a'],context(db,people['head_a'],1,branches[0].id))
    try:
        record=BOSLifecycleEvent(company_id=1,module_key='crm',source_module='crm',target_module='srm',entity_type='deal',entity_id='9001',event_name='handoff_skipped',status='skipped',actor_user_id=people['head_a'].id)
        db.add(record);db.flush()
        assert db.query(BOSLifecycleEvent).count()==1
    finally:cleanup()
    db.commit()
    cleanup=install(db,people['head_b'],context(db,people['head_b'],1,branches[1].id))
    try:assert db.query(BOSLifecycleEvent).count()==0
    finally:cleanup()


@pytest.mark.parametrize('table_name',['ai_security_settings','tenant_subscriptions','crm_lead_management_config'])
def test_company_singleton_configuration_is_shared_across_branches_but_not_companies(db,matrix,table_name):
    from app.core.tenant_boundary import install as company_boundary
    branches,people=matrix
    db.add(Company(id=2,name='Other singleton tenant'));db.flush()
    model=next(m.class_ for m in Base.registry.mappers if m.local_table.name==table_name)
    tenant_field='organization_id' if 'organization_id' in model.__table__.c else 'company_id'
    own=model(**{tenant_field:1});foreign=model(**{tenant_field:2})
    db.add_all([own,foreign]);db.flush()
    from sqlalchemy import inspect
    own_id=inspect(own).identity[0];foreign_id=inspect(foreign).identity[0]
    db.add(BranchOwnership(company_id=1,branch_id=branches[0].id,resource_table=table_name,resource_key=str(own_id),source='old-main-migration'))
    db.commit()
    tenant=company_boundary(db,people['head_b'],1)
    cleanup=install(db,people['head_b'],context(db,people['head_b'],1,branches[1].id))
    try:
        assert db.query(model).one() is own
        assert db.get(model,foreign_id) is None
        if table_name=='ai_security_settings':
            from app.ai_agents.services.advanced_security import AiSecuritySettingsService
            assert AiSecuritySettingsService(db).get_or_create(1).id==own.id
            assert not db.new
    finally:cleanup();tenant()


def test_settings_discovery_uses_selected_branch_module_roles(db,matrix):
    from app.access.models import AccessPolicy
    from app.access.settings_hub import context as settings_context,allows,OPTIONS
    branches,people=matrix
    actor=people['multi']
    crm={'enabled':True,'role':'admin','permissions':['crm_admin'],'actions':['view','configure'],'scope':'organization'}
    srm={'enabled':True,'role':'admin','permissions':['srm_admin'],'actions':['view','configure'],'scope':'organization'}
    db.add(AccessPolicy(user_id=actor.id,company_id=1,status='active',grants={'crm':crm,'srm':srm}))
    db.query(BranchGrant).filter_by(user_id=actor.id,branch_id=branches[0].id).one().module_grants={'crm':crm}
    db.query(BranchGrant).filter_by(user_id=actor.id,branch_id=branches[0].id).one().can_write=True
    db.query(BranchGrant).filter_by(user_id=actor.id,branch_id=branches[1].id).one().module_grants={'srm':{**srm,'role':'viewer','actions':['view']}}
    db.commit()
    actor._suite_branch_id=branches[1].id
    options={o[0] for o in OPTIONS if allows(o,settings_context(db,actor))}
    assert 'crm' not in options and 'sales' not in options
    actor._suite_branch_id=branches[0].id
    options={o[0] for o in OPTIONS if allows(o,settings_context(db,actor))}
    assert 'crm' in options and 'sales' not in options
