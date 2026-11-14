from datetime import date
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from app.access.models import AccessMembership, AccessPolicy
from app.models.company import Company, Branch
from app.models.employee import Employee
from app.apps.crm.models import CRMCompany
from app.apps.project_management.models import PMSWorkspace, PMSProject, PMSNote
from app.apps.srm.models import SRMSalesOrder
from app.apps.fam.models import FAMLedgerGroup, FAMLedger
from tests.test_pms_task_studio import studio
from tests.test_pms_workspaces import middleware_database
from tests.rich_text_test_utils import organization_context
from app.models.user import User, UserSession
from app.core.security import create_access_token
from tests.tenant_test_utils import assign_company


@pytest.fixture
def admin_data(db, studio):
    root, admin, regular, root_headers, admin_headers, regular_headers, *_ = studio
    admin.employee.employment_type = 'Full-time'
    membership = db.query(AccessMembership).filter_by(user_id=admin.id, company_id=1).first()
    if membership is None:
        membership = AccessMembership(user_id=admin.id, company_id=1, active=True)
        db.add(membership)
    membership.is_admin = True
    disabled = {key:{'enabled':False,'role':'viewer','permissions':[],'actions':[],'scope':'own'}
                for key in ['hrms','crm','project_management','srm','fam','analytics','communication','power_apps']}
    policy = AccessPolicy(user_id=admin.id, company_id=1, status='active', grants=disabled)
    db.add(policy)
    other = Company(name='Foreign read company', is_active=True)
    db.add(other); db.flush()
    foreign_owner = User(email='foreign-admin-read-owner@test.com', hashed_password='unused', is_active=True)
    db.add(foreign_owner); db.flush(); assign_company(db, foreign_owner, other.id)
    second = Branch(company_id=1, name='Second owned branch', is_active=True)
    foreign = Branch(company_id=other.id, name='Foreign read branch', is_active=True)
    db.add_all([second, foreign]); db.flush()
    rows = {}
    for company, branch, suffix in [(1, second.id, 'LOCAL'), (other.id, foreign.id, 'FOREIGN')]:
        employee = Employee(employee_id='ADMIN-READ-'+suffix, first_name=suffix, last_name='Employee', employment_type='Intern', branch_id=branch, date_of_joining=date.today())
        customer = CRMCompany(organization_id=company, branch_id=branch, name=suffix+' customer', owner_user_id=root.id)
        workspace = PMSWorkspace(organization_id=company, name=suffix+' workspace')
        group = FAMLedgerGroup(company_id=company, group_name=suffix+' group', group_code='ADMIN-READ', nature='asset')
        db.add_all([employee, customer, workspace, group]); db.flush()
        project = PMSProject(organization_id=company, workspace_id=workspace.id, branch_id=branch, project_key='ADMIN-READ-'+suffix, name=suffix+' project', owner_user_id=root.id)
        order = SRMSalesOrder(organization_id=company, title=suffix+' order', order_number='ADMIN-READ-'+suffix, created_by=root.id)
        ledger = FAMLedger(company_id=company, ledger_code='ADMIN-READ', ledger_name=suffix+' ledger', ledger_group_id=group.id, nature='asset')
        from app.apps.communication.models import CommunicationCampaign
        from app.apps.automation.models import AutomationWorkflow
        from app.apps.analytics.models import AnalyticsReport
        from app.ai_agents.models import AiConversation, AiMessage, AiHandoffNote
        from app.ai_operator.assistant_models import AssistantConversation
        campaign = CommunicationCampaign(organization_id=company, name=suffix+' campaign', created_by=root.id)
        workflow = AutomationWorkflow(organization_id=company, name=suffix+' workflow', module_name='crm', record_type='lead', trigger_type='manual', created_by=root.id)
        report = AnalyticsReport(name=suffix+' report', module_name='CRM', owner_id=root.id if company==1 else foreign_owner.id)
        conversation = AiConversation(organization_id=company, user_id=root.id if company==1 else foreign_owner.id, module='CRM', title=suffix+' conversation')
        suite_chat = AssistantConversation(organization_id=company, user_id=root.id if company==1 else foreign_owner.id, title=suffix+' suite conversation', references={'suite_conversation':True,'scope_key':f'company:{company}'})
        db.add_all([project, order, ledger, campaign, workflow, report, conversation, suite_chat]); db.flush()
        db.add(AiMessage(conversation_id=conversation.id, role='user', content=suffix+' memo'))
        note = PMSNote(owner_id=root.id if company==1 else foreign_owner.id, title=suffix+' private note', content=suffix+' content', tags=[])
        db.add(note); db.flush()
        handoff = AiHandoffNote(organization_id=company,module='CRM',summary=suffix+' handoff',created_by=root.id if company==1 else foreign_owner.id)
        db.add(handoff);db.flush()
        rows[suffix] = {'employee':employee.id, 'customer':customer.id, 'workspace':str(workspace.id), 'project':project.id, 'order':order.id, 'ledger':ledger.id,
                       'handoff':handoff.id,'note':note.id,'campaign':campaign.id,'workflow':workflow.id,'report':report.id,'conversation':conversation.id,'suite_chat':suite_chat.id}
    sessions = {}
    for key,user in [('root',root),('admin',admin)]:
        session = UserSession(user_id=user.id, session_token_hash=uuid4().hex, status='Active', expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
        db.add(session); db.flush()
        sessions[key] = {'Authorization':'Bearer '+create_access_token(user.id, session_id=session.id),'X-Suite-Organization':'1','X-Suite-Branch':'all'}
    db.commit()
    return {'root':root_headers, 'admin':admin_headers, 'regular':regular_headers, 'user':admin,
            'foreign_company':other.id, 'rows':rows, 'policy':policy, 'sessions':sessions}


def entries(response):
    assert response.status_code == 200, response.text
    value = response.json()
    if isinstance(value, list):
        return value
    return value.get('items', value.get('rows', value.get('data', [])))


@pytest.mark.parametrize('role', ['root','admin'])
@pytest.mark.parametrize('path,record', [('/employees/','employee'),('/crm/companies','customer'),
    ('/project-management/workspaces','workspace'),('/project-management/projects','project'),
    ('/srm/sales-orders','order'),('/fam/ledgers','ledger')])
def test_administrators_read_other_users_records_across_all_company_branches(client, admin_data, role, path, record):
    headers = {k:v for k,v in admin_data[role].items() if k != 'X-Suite-Branch'}
    result = entries(client.get('/api/v1'+path, headers=headers))
    ids = {str(row['id']) for row in result}
    assert str(admin_data['rows']['LOCAL'][record]) in ids
    assert str(admin_data['rows']['FOREIGN'][record]) not in ids
    assert not getattr(admin_data['user'], '_suite_admin_read', False)


@pytest.mark.parametrize('path,record', [('/employees/','employee'),('/crm/companies','customer'),
    ('/project-management/workspaces','workspace'),('/project-management/projects','project'),
    ('/srm/sales-orders','order'),('/fam/ledgers','ledger')])
def test_platform_administrator_reads_the_selected_company_not_their_home_company(client, admin_data, path, record):
    headers = {**admin_data['root'], 'X-Suite-Organization':str(admin_data['foreign_company']), 'X-Suite-Branch':'all'}
    ids = {str(row['id']) for row in entries(client.get('/api/v1'+path, headers=headers))}
    assert str(admin_data['rows']['FOREIGN'][record]) in ids
    assert str(admin_data['rows']['LOCAL'][record]) not in ids


def test_company_admin_cannot_read_another_company_or_gain_mutation_permissions(client, db, admin_data):
    foreign = {**admin_data['admin'], 'X-Suite-Organization':str(admin_data['foreign_company']), 'X-Suite-Branch':'all'}
    assert client.get('/api/v1/crm/companies', headers=foreign).status_code == 403
    assert client.post('/api/v1/crm/companies', json={'name':'Unauthorized write'}, headers=admin_data['admin']).status_code == 403
    admin_data['policy'].status = 'suspended'
    db.commit()
    assert client.get('/api/v1/crm/companies', headers=admin_data['admin']).status_code == 403


def test_admin_can_inspect_existing_data_in_disabled_modules_without_enabling_writes(client, db, admin_data):
    from app.apps.business_os.models import BOSEnabledModule
    row = db.query(BOSEnabledModule).filter_by(company_id=1, module_key='analytics').first()
    if row is None:
        row = BOSEnabledModule(company_id=1, module_key='analytics', display_name='Analytics')
        db.add(row)
    row.enabled = False
    db.commit()
    assert client.get('/api/v1/analytics/reports', headers=admin_data['admin']).status_code == 200
    assert client.get('/api/v1/analytics/reports', headers=admin_data['regular']).status_code == 403
    assert client.post('/api/v1/analytics/reports', json={}, headers=admin_data['admin']).status_code == 403
    access = client.get('/api/v1/access/me', headers=admin_data['admin']).json()
    assert 'analytics' not in access['companyDisabledModules']
    assert 'analytics' in access['readOnlyModules']
    assert set(access['grants']['analytics']['actions']) == {'view','export'}


def test_administrators_default_to_all_branches_but_keep_a_concrete_write_destination(client, admin_data):
    headers = {k:v for k,v in admin_data['admin'].items() if k != 'X-Suite-Branch'}
    response = client.get('/api/v1/branches/context', headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['selected'] is None
    assert response.json()['all_branches']
    assert response.json()['default_branch_id'] is not None


@pytest.mark.parametrize('role', ['root','admin'])
@pytest.mark.parametrize('path,record', [('/communication/campaigns','campaign'),('/automation/workflows','workflow'),('/analytics/reports','report'),('/interns-hub/admin/interns','employee'),('/ai-agents/handoff-notes','handoff'),('/ai-agents/conversations','conversation'),('/ai-operator/suite/conversations','suite_chat')])
def test_addon_modules_allow_company_wide_administrative_reads(client, admin_data, role, path, record):
    ids = {str(row['id']) for row in entries(client.get('/api/v1'+path, headers=admin_data['sessions'][role]))}
    assert str(admin_data['rows']['LOCAL'][record]) in ids
    assert str(admin_data['rows']['FOREIGN'][record]) not in ids


def test_ai_admin_history_is_read_only_and_company_bound(client, admin_data):
    own = admin_data['rows']['LOCAL']['conversation']
    foreign = admin_data['rows']['FOREIGN']['conversation']
    headers = admin_data['sessions']['admin']
    messages = entries(client.get(f'/api/v1/ai-agents/conversations/{own}/messages', headers=headers))
    assert [m['content'] for m in messages] == ['LOCAL memo']
    assert client.get(f'/api/v1/ai-agents/conversations/{foreign}', headers=headers).status_code == 404
    assert client.post(f'/api/v1/ai-agents/conversations/{own}/messages', json={'content':'Not authorized'}, headers=headers).status_code == 403


@pytest.mark.parametrize('role', ['root','admin'])
def test_admin_project_detail_is_company_bound(client, admin_data, role):
    headers = {**admin_data[role], 'X-Suite-Branch':'all'}
    for suffix, status in [('LOCAL',200),('FOREIGN',404)]:
        project = admin_data['rows'][suffix]['project']
        response = client.get(f'/api/v1/project-management/projects/{project}', headers=headers)
        assert response.status_code == status, response.text


@pytest.mark.parametrize('role', ['root','admin'])
def test_admin_notes_are_company_bound_and_read_only(client, admin_data, role):
    headers = {**admin_data[role], 'X-Suite-Branch':'all'}
    local = admin_data['rows']['LOCAL']['note']
    foreign = admin_data['rows']['FOREIGN']['note']
    rows = entries(client.get('/api/v1/project-management/notes', headers=headers))
    assert local in {row['id'] for row in rows}
    assert foreign not in {row['id'] for row in rows}
    assert client.get(f'/api/v1/project-management/notes/{local}', headers=headers).status_code == 200
    assert client.get(f'/api/v1/project-management/notes/{foreign}', headers=headers).status_code == 404


def test_company_admin_read_crosses_business_os_middleware_gate_without_enabling_writes(client, db, admin_data):
    from app.apps.business_os.models import BOSEnabledModule
    row = db.query(BOSEnabledModule).filter_by(company_id=1, module_key='communication').first()
    if row is None:
        row = BOSEnabledModule(company_id=1, module_key='communication', display_name='Communication')
        db.add(row)
    row.enabled = False
    db.commit()
    for key in ['root','admin']:
        assert client.get('/api/v1/communication/campaigns', headers={**admin_data[key], 'X-Suite-Branch':'all'}).status_code == 200
    assert client.get('/api/v1/communication/campaigns', headers=admin_data['regular']).status_code == 403
    assert client.post('/api/v1/communication/campaigns', headers=admin_data['admin'], json={}).status_code == 403


@pytest.mark.parametrize('role', ['root','admin'])
def test_admin_ai_catalog_all_branches_is_read_only(client, admin_data, role):
    assert client.get('/api/v1/ai-agents', headers=admin_data['sessions'][role]).status_code == 200


def test_batched_intern_summaries_preserve_execution_metrics(db, admin_data):
    from app.apps.interns_hub.pms_adapter import summary, summaries
    from app.apps.project_management.models import PMSTask, PMSTaskAssignee
    from app.models.attendance import Attendance
    user = admin_data['user']
    project = admin_data['rows']['LOCAL']['project']
    for index,status in enumerate(['Done','In Progress','Rejected']):
        task = PMSTask(project_id=project,title=f'Summary task {index}',task_key=f'SUM-{index}')
        db.add(task);db.flush()
        db.add(PMSTaskAssignee(task_id=task.id,user_id=user.id,execution_status=status,due_date=date.today()-timedelta(days=1)))
    db.add(Attendance(employee_id=user.employee.id,attendance_date=date.today(),status='Present'))
    db.commit()
    expected = summary(db,user.employee,date.today())
    assert expected['total_tasks'] == 3
    assert expected['completed'] == 1
    assert expected['overdue'] == 1
    assert summaries(db,[user.employee],date.today(),1)[user.employee.id] == expected


@pytest.mark.parametrize('role', ['root','admin'])
@pytest.mark.parametrize('path', ['/logs/audit','/logs/requests','/files-storage/files','/power-apps/integrations/connections','/power-apps/approvals/requests'])
def test_admin_can_inspect_company_audit_storage_and_disabled_environments(client, admin_data, role, path):
    response = client.get('/api/v1'+path,headers=admin_data['sessions'][role])
    assert response.status_code == 200, response.text
