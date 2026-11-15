"""Production native auth proofs for the closed canonical Employee purpose."""
from types import MappingProxyType
from uuid import uuid4
from datetime import date
import pytest
from tests.test_business_pack_common_core import core_case,select_pack


@pytest.fixture
def employee_case(core_case,monkeypatch):
    from app.business_packs import common_core,employee_core
    from app.access.models import AccessPolicy
    from app.models.user import Permission
    n=core_case
    from app.models.company import Department,Designation
    department=Department(branch_id=n.branch.id,name='Native employee department');n.db.add(department);n.db.flush()
    designation=Designation(department_id=department.id,name='Native employee role');n.db.add(designation);n.db.flush()
    from app.branches.models import BranchOwnership
    for row in (department,designation):n.db.add(BranchOwnership(company_id=1,branch_id=n.branch.id,resource_table=row.__tablename__,resource_key=str(row.id),source='native-job-configuration'))
    n.department=department;n.designation=designation
    monkeypatch.setattr(common_core,'OPERATIONS',MappingProxyType({**common_core.OPERATIONS,**employee_core.candidate_operations(common_core.CoreOperation)}))
    for user in (n.user,n.admin):
        policy=n.db.query(AccessPolicy).filter_by(user_id=user.id).one()
        names=['employee_view','employee_create','employee_update','employee_sensitive_view']
        native=[]
        for name in names:
            item=n.db.query(Permission).filter_by(name=name).first()
            if item is None:item=Permission(name=name,module='hrms');n.db.add(item);n.db.flush()
            native.append(item)
        user.role.permissions=native
        policy.grants={'hrms':{'enabled':True,'permissions':names,'actions':['view','create','edit'],'scope':'own' if user is n.user else 'organization'}}
    n.db.commit()
    return n


def test_native_employee_read_list_detail_version_and_directory(employee_case):
    n=employee_case
    context=select_pack(n)
    headers={**n.headers,'X-Suite-Pack-Context':str(context.id)}
    for path in ('/api/v1/employees/','/api/v1/employees/directory','/api/v1/employees/filter-options','/api/v1/employees/reporting-managers','/api/v1/employees/custom-fields/definitions'):
        result=n.client.get(path,headers=headers)
        assert result.status_code==200,(path,result.text)
    detail=n.client.get(f'/api/v1/employees/{n.employee.id}',headers=headers)
    assert detail.status_code==200,detail.text
    assert len(detail.json()['profile_version'])==64


def test_native_employee_edit_uses_profile_version_and_retains_conflicting_draft(employee_case):
    n=employee_case
    detail=n.client.get(f'/api/v1/employees/{n.employee.id}',headers=n.headers)
    assert detail.status_code==200,detail.text
    headers={**n.headers,'If-Match':detail.json()['profile_version']}
    result=n.client.put(f'/api/v1/employees/{n.employee.id}',headers=headers,json={'first_name':'Updated canonical'})
    assert result.status_code==200,result.text
    stale=n.client.put(f'/api/v1/employees/{n.employee.id}',headers=headers,json={'first_name':'Stale draft'})
    assert stale.status_code==409,stale.text
    n.db.refresh(n.employee);assert n.employee.first_name=='Updated canonical'


@pytest.mark.parametrize('past_and_mail',[False,True])
def test_native_employee_create_with_configured_onboarding(employee_case,past_and_mail):
    from app.models.onboarding import OnboardingTemplate,OnboardingTemplateTask,EmployeeOnboarding,EmployeeOnboardingTask
    from app.business_packs.models import PackRecordOwnership
    n=employee_case
    template=OnboardingTemplate(organization_id=1,name='Native configured onboarding',applicable_for='all',is_active=True,created_by=n.admin.id)
    n.db.add(template);n.db.flush()
    task=OnboardingTemplateTask(template_id=template.id,task_name='Native welcome',category='HR',assigned_to_role='employee',due_day_offset=2)
    n.db.add(task);n.db.flush()
    from app.branches.models import BranchOwnership
    for row in (template,task):n.db.add(BranchOwnership(company_id=1,branch_id=n.branch.id,resource_table=row.__tablename__,resource_key=str(row.id),source='native-configured-onboarding'))
    n.db.commit()
    before=n.db.query(PackRecordOwnership).count()
    payload={'employee_id':uuid4().hex,'first_name':'New','last_name':'Canonical','date_of_joining':'2020-11-15' if past_and_mail else '2026-11-15',
        'branch_id':n.branch.id,'create_user_account':False}
    if past_and_mail:payload['work_email']='native-onboarding@example.com'
    result=n.client.post('/api/v1/employees/',headers={**n.admin_headers,'X-Suite-Pack-Context':'revoked-stale'},json=payload)
    assert result.status_code==201,result.text
    identity=result.json()['id']
    onboarding=n.db.query(EmployeeOnboarding).filter_by(employee_id=identity).one()
    assert onboarding.template_id==template.id
    actual=n.db.query(EmployeeOnboardingTask).filter_by(employee_onboarding_id=onboarding.id).all()
    assert len(actual)==1
    assert actual[0].task_name=='Native welcome'
    if past_and_mail:
        from app.models.email_outbox import EmailOutbox
        assert onboarding.status=='overdue'
        emails=n.db.query(EmailOutbox).filter_by(recipient='native-onboarding@example.com').all()
        assert emails and all(row.organization_id==1 and row.module=='hrms' and row.status=='queued' for row in emails)
    assert n.db.query(PackRecordOwnership).count()==before


def test_native_superuser_employee_login_keeps_canonical_identity(employee_case):
    from tests.test_settings_hub import actor
    from app.models.employee import Employee
    from app.models.user import User
    from app.common.models import CommonPerson,CommonProfile
    n=employee_case
    headers,user=actor(n.db,role='native_founder_'+uuid4().hex,superuser=True)
    headers.update({'X-Suite-Organization':'1','X-Suite-Branch':str(n.branch.id),'X-Suite-Pack-Context':'invalid-clinical-selector'})
    email=uuid4().hex+'@example.com'
    result=n.client.post('/api/v1/employees/',headers=headers,json={
        'employee_id':uuid4().hex,'first_name':'Native','last_name':'Account','date_of_joining':'2026-11-15','branch_id':n.branch.id,
        'create_user_account':True,'user_email':email,'user_password':'NativeEmployee!2026'})
    assert result.status_code==201,result.text
    employee=n.db.get(Employee,result.json()['id']);account=n.db.get(User,employee.user_id)
    assert account.email==email and not account.is_superuser
    assert account.role.name=='employee'
    person=n.db.query(CommonPerson).filter_by(user_id=account.id).one()
    assert person.source_record_id==employee.id and person.organization_id==1
    assert n.db.query(CommonProfile).filter_by(person_id=person.id).count()==1


@pytest.mark.parametrize('branch_input', ['omitted', 'null'])
def test_employee_creation_keeps_native_selected_branch_default(employee_case, branch_input):
    from app.models.employee import Employee
    n=employee_case
    select_pack(n, 'salon')
    payload={'employee_id':uuid4().hex,'first_name':'Native','last_name':'Default destination',
        'date_of_joining':'2026-11-15','employment_type':'Intern','create_user_account':False}
    if branch_input=='null':payload['branch_id']=None
    result=n.client.post('/api/v1/employees/',headers={**n.admin_headers,'X-Suite-Pack-Context':'invalid-selector'},json=payload)
    assert result.status_code==201,result.text
    employee=n.db.get(Employee,result.json()['id'])
    assert employee.branch_id==n.branch.id
    assert employee.employment_type=='Intern'
    from app.branches.models import BranchOwnership
    ownership=n.db.query(BranchOwnership).filter_by(resource_table='employees',resource_key=str(employee.id)).one()
    assert (ownership.company_id,ownership.branch_id)==(1,n.branch.id)


def test_employee_default_never_replaces_explicit_foreign_branch(employee_case):
    from app.models.company import Company,Branch
    from app.models.employee import Employee
    n=employee_case
    n.db.add(Company(id=77,name='Foreign employee company'));n.db.flush()
    foreign=Branch(company_id=77,name='Foreign employee destination');n.db.add(foreign);n.db.commit()
    before=n.db.query(Employee).count()
    response=n.client.post('/api/v1/employees/',headers=n.admin_headers,json={
        'employee_id':uuid4().hex,'first_name':'Must','last_name':'Remain denied','date_of_joining':'2026-11-15',
        'branch_id':foreign.id,'employment_type':'Intern','create_user_account':False})
    assert response.status_code==404,response.text
    assert n.db.query(Employee).count()==before


def test_employee_custom_fields_keep_false_and_exclude_foreign_entity_values(employee_case):
    from app.models.platform import CustomFieldDefinition,CustomFieldValue
    n=employee_case
    field=CustomFieldDefinition(module='employees',field_key='native_opt_in',label='Native consent',field_type='Checkbox',is_required=True,is_active=True)
    foreign=CustomFieldDefinition(module='crm',field_key='private_crm',label='Private CRM',field_type='Text',is_active=True)
    n.db.add_all([field,foreign]);n.db.flush()
    from app.models.security_boundary import SecurityResourceOwnership
    from app.branches.models import BranchOwnership
    for definition in (field,foreign):
        if n.db.get(SecurityResourceOwnership,(definition.__tablename__,definition.id)) is None:
            n.db.add(SecurityResourceOwnership(resource_table=definition.__tablename__,resource_id=definition.id,company_id=1))
        n.db.add(BranchOwnership(company_id=1,branch_id=n.branch.id,resource_table=definition.__tablename__,resource_key=str(definition.id),source='native-definition-fixture'))
    n.db.add(CustomFieldValue(definition_id=foreign.id,entity_type='crm_lead',entity_id=n.employee.id,value_text='private clinical campaign',updated_by=n.user.id));n.db.commit()
    before=n.client.get(f'/api/v1/employees/custom-fields/definitions?employee_id={n.employee.id}',headers=n.headers)
    assert before.status_code==200,before.text
    assert {item['id'] for item in before.json()['items']}=={field.id}
    result=n.client.put(f'/api/v1/employees/{n.employee.id}',headers=n.headers,json={'custom_fields':{'native_opt_in':False}})
    assert result.status_code==200,result.text
    stored=n.db.query(CustomFieldValue).filter_by(entity_type='employee',entity_id=n.employee.id,definition_id=field.id).one()
    assert stored.value_json is False
    values=n.client.get(f'/api/v1/employees/custom-fields/definitions?employee_id={n.employee.id}',headers=n.headers)
    assert values.json()['items'][0]['value'] is False
    rejected=n.client.put(f'/api/v1/employees/{n.employee.id}',headers=n.headers,json={'first_name':'Must roll back','custom_fields':{'private_crm':'spoof'}})
    assert rejected.status_code==422,rejected.text
    n.db.refresh(n.employee);assert n.employee.first_name=='Canonical'


def test_native_employee_company_admin_is_not_account_superuser(employee_case):
    n=employee_case
    result=n.client.post('/api/v1/employees/',headers=n.admin_headers,json={
        'employee_id':uuid4().hex,'first_name':'Forbidden','last_name':'Login','date_of_joining':'2026-11-15','branch_id':n.branch.id,
        'create_user_account':True,'user_email':uuid4().hex+'@example.com','user_password':'NativeEmployee!2026'})
    assert result.status_code==403,result.text


@pytest.mark.parametrize('enabled',[True,False])
def test_directory_keeps_original_native_view_auth_without_named_employee_permission(employee_case,enabled):
    from app.access.models import AccessPolicy
    n=employee_case
    n.user.role.permissions=[]
    policy=n.db.query(AccessPolicy).filter_by(user_id=n.user.id).one()
    policy.grants={'hrms':{'enabled':enabled,'permissions':[],'actions':['view'],'scope':'own'}};n.db.commit()
    response=n.client.get('/api/v1/employees/directory',headers={**n.headers,'X-Suite-Pack-Context':'invalid'})
    assert response.status_code==(200 if enabled else 403),response.text
    ordinary=n.client.get('/api/v1/employees/',headers=n.headers)
    assert ordinary.status_code==403,ordinary.text


def native_worker(n,scope='organization',permissions=('employee_view','employee_update')):
    from tests.test_settings_hub import actor
    from app.models.employee import Employee
    from app.branches.models import BranchGrant,BranchOwnership
    headers,user=actor(n.db,role='canonical_'+uuid4().hex,permissions=permissions,grants={
        'hrms':{'enabled':True,'permissions':list(permissions),'actions':['view','create','edit'],'scope':scope}})
    employee=Employee(employee_id=uuid4().hex,first_name='Native',last_name='Viewer',date_of_joining=date(2020,1,1),branch_id=n.branch.id,user_id=user.id,status='Active')
    n.db.add_all([employee,BranchGrant(company_id=1,user_id=user.id,branch_id=n.branch.id,can_write=True)]);n.db.flush()
    n.db.add(BranchOwnership(company_id=1,branch_id=n.branch.id,resource_table='employees',resource_key=str(employee.id),source='native-canonical-viewer'));n.db.commit()
    headers.update({'X-Suite-Organization':'1','X-Suite-Branch':str(n.branch.id)})
    return headers,user,employee


def test_masked_child_still_changes_profile_version_and_rejects_stale_edit(employee_case):
    from app.models.employee import EmployeeDocument
    from app.branches.models import BranchOwnership
    n=employee_case;headers,_,_=native_worker(n)
    doc=EmployeeDocument(employee_id=n.employee.id,document_type='Identity',document_number='private-native-id',file_url='/private/native-proof')
    n.db.add(doc);n.db.flush()
    n.db.add(BranchOwnership(company_id=1,branch_id=n.branch.id,resource_table=doc.__tablename__,resource_key=str(doc.id),source='native-profile-document'));n.db.commit()
    first=n.client.get(f'/api/v1/employees/{n.employee.id}',headers=headers)
    assert first.status_code==200,first.text
    assert first.json()['documents']==[] and 'private-native-id' not in first.text
    old=first.json()['profile_version'];doc.document_number='private-changed-native-id';n.db.commit()
    fresh=n.client.get(f'/api/v1/employees/{n.employee.id}',headers=headers)
    assert fresh.status_code==200 and fresh.json()['profile_version']!=old,fresh.text
    rejected=n.client.put(f'/api/v1/employees/{n.employee.id}',headers={**headers,'If-Match':old},json={'first_name':'Stale child draft'})
    assert rejected.status_code==409,rejected.text
    denied=n.client.put(f'/api/v1/employees/{n.employee.id}',headers=headers,json={'account_number':'123456789'})
    assert denied.status_code==403,denied.text
    n.db.refresh(n.employee);assert n.employee.first_name=='Canonical'


def test_core_marker_restored_on_success_failure_and_private_request(employee_case):
    n=employee_case
    context=select_pack(n)
    headers={**n.headers,'X-Suite-Pack-Context':str(context.id)}
    assert n.client.get(f'/api/v1/employees/{n.employee.id}',headers=headers).status_code==200
    assert 'business_pack_request_binding' not in n.db.info
    assert 'business_common_core_scope' not in n.db.info
    failed=n.client.put(f'/api/v1/employees/{n.employee.id}',headers=headers,json={'role_id':n.admin.role_id})
    assert failed.status_code==403,failed.text
    assert 'business_pack_request_binding' not in n.db.info
    control=n.client.get('/api/v1/access/me',headers={**headers,'X-Suite-Pack-Context':'invalid'})
    assert control.status_code==200,control.text
    private=n.client.get('/api/v1/srm/service-checkout/999999',headers={**headers,'X-Suite-Pack-Context':'invalid'})
    assert private.status_code==403,private.text
    assert 'business_pack_request_binding' not in n.db.info


@pytest.mark.parametrize('scope',['own','team','organization'])
def test_employee_native_scope_is_independent_of_pack_grants(employee_case,scope):
    from app.models.employee import Employee
    from app.branches.models import BranchOwnership
    from app.business_packs.models import PackUserGrant,PackRecordOwnership
    n=employee_case;headers,_,viewer=native_worker(n,scope)
    direct=Employee(employee_id=uuid4().hex,first_name='Direct',last_name='Report',date_of_joining=date(2020,1,1),branch_id=n.branch.id,reporting_manager_id=viewer.id,status='Active')
    n.db.add(direct);n.db.flush();n.db.add(BranchOwnership(company_id=1,branch_id=n.branch.id,resource_table='employees',resource_key=str(direct.id),source='native-direct-report'));n.db.commit()
    context=select_pack(n);n.db.query(PackUserGrant).delete();n.db.commit()
    result=n.client.get('/api/v1/employees/',headers={**headers,'X-Suite-Pack-Context':str(context.id)})
    assert result.status_code==200,result.text
    visible={row['id'] for row in result.json()['items']}
    assert viewer.id in visible
    assert (direct.id in visible)==(scope in {'team','organization'})
    assert (n.employee.id in visible)==(scope=='organization')
    assert n.db.query(PackRecordOwnership).count()==0


def employee_write_proof(n,monkeypatch,callback,purpose='hrms.employee_management'):
    from fastapi import Depends
    from app.core.deps import get_db,get_current_user
    from app.main import app
    from app.business_packs import common_core
    path='/api/v1/timesheets/employee-source-proof'
    operation=common_core.CoreOperation('edit','employee_update',frozenset({'custom_field_values'}),frozenset({'custom_field_values'}),purpose=purpose)
    monkeypatch.setattr(common_core,'OPERATIONS',MappingProxyType({**common_core.OPERATIONS,('POST',path):operation}))
    def endpoint(db=Depends(get_db),user=Depends(get_current_user)):
        callback(db,user)
        return {'saved':True}
    app.add_api_route(path,endpoint,methods=['POST']);route=app.routes[-1]
    try:return n.client.post(path,headers=n.headers)
    finally:app.routes.remove(route)


@pytest.mark.parametrize('invalid',['wrong_entity','missing_definition','forged_actor','wrong_employee','other_purpose'])
def test_injected_custom_value_requires_exact_installed_source_and_native_ownership(employee_case,monkeypatch,invalid):
    from app.models.platform import CustomFieldDefinition,CustomFieldValue
    from app.branches.models import BranchOwnership
    from app.models.employee import Employee
    n=employee_case
    definition=CustomFieldDefinition(module='employee',field_key='source_proof',label='Source proof',field_type='Text',is_active=True)
    n.db.add(definition);n.db.flush()
    n.db.add(BranchOwnership(company_id=1,branch_id=n.branch.id,resource_table=definition.__tablename__,resource_key=str(definition.id),source='native-definition'))
    other=Employee(employee_id=uuid4().hex,first_name='Unrelated',last_name='Employee',date_of_joining=date(2020,1,1),branch_id=n.branch.id,status='Active')
    n.db.add(other);n.db.flush();n.db.add(BranchOwnership(company_id=1,branch_id=n.branch.id,resource_table='employees',resource_key=str(other.id),source='native-source-negative'));n.db.commit()
    before=n.db.query(CustomFieldValue).count()
    def injected(db,user):
        value=CustomFieldValue(definition_id=999999 if invalid=='missing_definition' else definition.id,
            entity_type='crm_lead' if invalid=='wrong_entity' else 'employee',entity_id=other.id if invalid=='wrong_employee' else n.employee.id,
            updated_by=n.admin.id if invalid=='forged_actor' else user.id,value_text='must not persist')
        db.add(value);db.commit()
    result=employee_write_proof(n,monkeypatch,injected,'hrms.actual_time' if invalid=='other_purpose' else 'hrms.employee_management')
    assert result.status_code==403,result.text
    assert n.db.query(CustomFieldValue).count()==before
    assert 'business_pack_request_binding' not in n.db.info


def test_custom_value_binding_without_installed_core_scope_is_not_write_authority(employee_case):
    from app.business_packs.employee_core import native_value_write
    from app.business_packs.common_binding import CoreRequestBinding,bind_core_request
    from app.models.platform import CustomFieldValue
    n=employee_case
    binding=CoreRequestBinding(n.user.id,1,'PUT','/api/v1/employees/{employee_id}','hrms.employee_management')
    with bind_core_request(n.db,binding):
        assert native_value_write(n.db,n.user,1,CustomFieldValue(entity_type='employee',entity_id=n.employee.id,definition_id=1,updated_by=n.user.id)) is False


def test_employee_defaults_projection_does_not_read_private_other_modules(employee_case):
    from app.shared.models import ServicePolicy
    from sqlalchemy import event
    n=employee_case
    n.db.add(ServicePolicy(organization_id=1,module_key='*',scope_key='form-defaults:company:1',kind='form_defaults',updated_by=n.admin.id,
        values_json={'branch_id':n.branch.id,'department_id':n.department.id,'pipeline_id':98765,'stage_id':98765,'price_book_id':98765,'bank_account_id':98765,'payment_mode_id':98765}))
    n.db.commit()
    read_tables=[]
    def observe(execution):
        if execution.bind_mapper is not None:read_tables.append(execution.bind_mapper.local_table.name)
    event.listen(n.db,'do_orm_execute',observe)
    try:
        response=n.client.post('/api/v1/employees/',headers=n.admin_headers,json={
            'employee_id':uuid4().hex,'first_name':'Projected','last_name':'Defaults','date_of_joining':'2026-11-15','create_user_account':False})
    finally:event.remove(n.db,'do_orm_execute',observe)
    assert response.status_code==201,response.text
    assert response.json()['branch_id']==n.branch.id and response.json()['department_id']==n.department.id
    assert not any(name.startswith(('crm_','fam_')) for name in read_tables),read_tables


def test_native_self_department_edit_preserves_unchanged_own_realm(employee_case):
    n=employee_case
    response=n.client.put(f'/api/v1/employees/{n.employee.id}',headers=n.headers,json={'department_id':n.department.id,'designation_id':n.designation.id})
    assert response.status_code==200,response.text
    assert response.json()['department_id']==n.department.id
    again=n.client.get(f'/api/v1/employees/{n.employee.id}',headers=n.headers)
    assert again.status_code==200 and again.json()['department_id']==n.department.id,again.text


def test_employee_transition_does_not_recapture_unrelated_identity_changes(employee_case,monkeypatch):
    from app.business_packs import common_core
    from app.models.employee import Employee
    from sqlalchemy import update
    n=employee_case;headers,_,viewer=native_worker(n)
    original=common_core._native_authority;changed=False
    def raced(db,user,company,**kwargs):
        nonlocal changed
        if kwargs.get('employee_before') and not changed:
            changed=True
            db.connection().execute(update(Employee).where(Employee.id==viewer.id).values(department_id=n.department.id))
        return original(db,user,company,**kwargs)
    monkeypatch.setattr(common_core,'_native_authority',raced)
    response=n.client.put(f'/api/v1/employees/{n.employee.id}',headers=headers,json={'first_name':'Must not commit'})
    assert changed and response.status_code==403,response.text
    n.db.refresh(n.employee);n.db.refresh(viewer)
    assert n.employee.first_name=='Canonical' and viewer.department_id is None


def test_native_team_transfer_cannot_reuse_compiled_report_membership(employee_case):
    n=employee_case;headers,_,manager=native_worker(n,'team')
    _,_,report=native_worker(n,'own')
    report.reporting_manager_id=manager.id;n.db.commit()
    result=n.client.put(f'/api/v1/employees/{report.id}',headers=headers,json={'reporting_manager_id':None})
    assert result.status_code==403,result.text
    n.db.refresh(report);assert report.reporting_manager_id==manager.id


@pytest.mark.parametrize('with_session',[False,True])
def test_native_superuser_self_role_command_preserves_legacy_behavior(employee_case,monkeypatch,with_session):
    from tests.test_settings_hub import actor
    from app.business_packs import common_core
    n=employee_case
    headers,user=actor(n.db,role='native_self_role_'+uuid4().hex,superuser=True)
    headers.update({'X-Suite-Organization':'1','X-Suite-Branch':str(n.branch.id)})
    n.employee.user=user;n.db.commit()
    if with_session:
        from app.models.user import UserSession
        from datetime import datetime,timedelta,timezone
        from app.core.security import create_access_token
        session=UserSession(user_id=user.id,session_token_hash='native-session-proof',status='Active',last_seen_at=datetime.now(timezone.utc),expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
        n.db.add(session);n.db.commit()
        headers['Authorization']='Bearer '+create_access_token(user.id,session_id=session.id)
    old_role=user.role
    with monkeypatch.context() as legacy:
        legacy.setattr(common_core,'OPERATIONS',MappingProxyType(dict(common_core._TIME_OPERATIONS)))
        baseline=n.client.put(f'/api/v1/employees/{n.employee.id}',headers=headers,json={'role_id':n.admin.role_id})
        assert baseline.status_code==200,baseline.text
    user.role=old_role;n.db.commit()
    result=n.client.put(f'/api/v1/employees/{n.employee.id}',headers=headers,json={'role_id':n.admin.role_id})
    assert result.status_code==200,result.text
    n.db.refresh(user);assert user.is_superuser and user.role_id==n.admin.role_id


@pytest.mark.parametrize('shape',['mixed_late','count_late','eager','raw_alias'])
def test_actual_core_request_rejects_unregistered_secondary_sources(employee_case,monkeypatch,shape):
    from sqlalchemy import true,func
    from sqlalchemy.orm import registry,joinedload
    from app.models.attendance import Attendance
    from app.models.employee import Employee
    n=employee_case
    n.db.add(Attendance(employee_id=n.employee.id,attendance_date=date(2026,11,15),status='Present',remarks='private actual attendance'))
    n.db.commit()
    def injected(db,user):
        alternate=registry()
        class LateAttendance:pass
        alternate.map_imperatively(LateAttendance,Attendance.__table__)
        try:
            query=db.query(Employee,LateAttendance).join(LateAttendance,true())
            if shape=='mixed_late':query.all()
            elif shape=='count_late':query.count()
            elif shape=='eager':db.query(Employee).options(joinedload(Employee.attendances)).all()
            else:db.query(Employee).join(Attendance.__table__.alias('raw_private_actuals'),true()).all()
        finally:alternate.dispose()
    result=employee_write_proof(n,monkeypatch,injected)
    assert result.status_code==403,result.text


def self_role_case(n):
    from tests.test_settings_hub import actor
    headers,user=actor(n.db,role='native_role_proof_'+uuid4().hex,superuser=True)
    headers.update({'X-Suite-Organization':'1','X-Suite-Branch':str(n.branch.id)})
    n.employee.user=user;n.db.commit()
    return headers,user,user.role_id


@pytest.mark.parametrize('attack',['disable_su','principal_email','different_role','foreign_user','session_swap'])
def test_self_role_proof_cannot_authorize_any_other_principal_transition(employee_case,monkeypatch,attack):
    from app.business_packs import employee_core
    from app.models.user import User
    from sqlalchemy import update
    from dataclasses import replace
    n=employee_case;headers,user,old=self_role_case(n)
    original=employee_core.role_change_proof
    def injected(db,actor,employee,role_id):
        original(db,actor,employee,role_id)
        proof=db.info['_native_employee_role_change']
        if attack=='disable_su':db.connection().execute(update(User).where(User.id==actor.id).values(is_superuser=False))
        elif attack=='principal_email':db.connection().execute(update(User).where(User.id==actor.id).values(email='wrong-principal@example.com'))
        elif attack=='different_role':db.info['_native_employee_role_change']=replace(proof,new_role_id=n.user.role_id)
        elif attack=='foreign_user':db.info['_native_employee_role_change']=replace(proof,user=n.user)
        else:actor._suite_session_id=123456789
    monkeypatch.setattr(employee_core,'role_change_proof',injected)
    response=n.client.put(f'/api/v1/employees/{n.employee.id}',headers=headers,json={'role_id':n.admin.role_id})
    assert response.status_code==403,response.text
    actual=n.db.query(User).filter_by(id=user.id).populate_existing().one()
    assert actual.is_superuser and actual.role_id==old and actual.email!='wrong-principal@example.com'
    assert '_native_employee_update' not in n.db.info and '_native_employee_role_change' not in n.db.info


@pytest.mark.parametrize('attack',['fake_source','unrelated_source','detached_source','foreign_recipient','body','row_retarget','mailbox_read','id_probe_read','wrong_purpose','forged_event','late_principal','late_employee'])
def test_native_employee_mail_requires_exact_live_source_and_never_grants_mailbox_access(employee_case,monkeypatch,attack):
    from app.services import email_events,email_dispatch
    from app.business_packs import employee_email
    from app.business_packs.common_binding import CoreRequestBinding
    from app.models.email_outbox import EmailOutbox
    from app.models.user import User
    from app.models.employee import Employee
    from sqlalchemy import update
    from dataclasses import replace
    from types import SimpleNamespace
    n=employee_case;headers,user,old=self_role_case(n)
    before=n.db.query(EmailOutbox).count()
    real_queue=email_dispatch.queue_email
    real_duplicate=employee_email.duplicate_exists
    if attack=='forged_event':
        def forged(db,event):
            fields=list(event.fields);fields[6]+=' forged private payload'
            return real_duplicate(db,replace(event,fields=tuple(fields)))
        monkeypatch.setattr(employee_email,'duplicate_exists',forged)
    def injected(db,**kwargs):
        if attack=='fake_source':kwargs['source_record']=SimpleNamespace(id=user.id,__tablename__='users')
        elif attack=='unrelated_source':kwargs['source_record']=n.user
        elif attack=='detached_source':db.expunge(kwargs['source_record'])
        elif attack=='foreign_recipient':kwargs['recipient']='unrelated@example.com'
        elif attack=='body':kwargs['body']+=' must not be delivered'
        elif attack=='mailbox_read':db.query(EmailOutbox).all()
        elif attack=='id_probe_read':db.query(EmailOutbox.id).filter(EmailOutbox.event_key=='not-authorized').first()
        elif attack=='wrong_purpose':db.info['business_pack_request_binding']=CoreRequestBinding(user.id,1,'GET','/api/v1/timesheets/projects')
        elif attack=='late_principal':db.connection().execute(update(User).where(User.id==user.id).values(email='late-principal@example.com'))
        elif attack=='late_employee':db.connection().execute(update(Employee).where(Employee.id==n.employee.id).values(department_id=n.department.id))
        row=real_queue(db,**kwargs)
        if attack=='row_retarget':row.recipient='retargeted@example.com'
        return row
    monkeypatch.setattr(email_events,'queue_email',injected)
    response=n.client.put(f'/api/v1/employees/{n.employee.id}',headers=headers,json={'role_id':n.admin.role_id})
    assert response.status_code==403,response.text
    assert n.db.query(EmailOutbox).count()==before
    assert n.db.query(User.role_id).filter(User.id==user.id).scalar()==old
    assert 'business_pack_request_binding' not in n.db.info
