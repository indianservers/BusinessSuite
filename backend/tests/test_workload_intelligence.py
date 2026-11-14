import json
from datetime import date
from uuid import uuid4
import pytest
from app.apps.project_management.models import PMSProject,PMSTask,PMSUserCapacity
from tests.test_suite_operator import setup_suite,ROOT,approve,tick
from tests.test_suite_workspace import say
from tests.test_ai_operator import mock_provider,isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context


def task(client,h,pid,uid,title,hours,status='To Do'):
    value=client.post(f'/api/v1/project-management/projects/{pid}/tasks',headers=h,json={
        'title':title,'task_key':'WL-'+uuid4().hex[:8],'assignee_user_id':uid,'start_date':'2026-05-04',
        'due_date':'2026-05-08','estimated_hours':hours,'status':status})
    assert value.status_code==200,value.text
    return value.json()['id']


def setup_load(client,db):
    h,user,pid,base=setup_suite(client,db);project=db.get(PMSProject,pid)
    open_id=task(client,h,pid,user.id,'Synthetic open work',30)
    closed=task(client,h,pid,user.id,'Synthetic completed work',100)
    db.get(PMSTask,closed).status='Done'
    db.add(PMSUserCapacity(organization_id=project.organization_id,user_id=user.id,week_start_date=date(2026,5,4),capacity_hours=20))
    db.commit()
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Synthetic workload','workspace_id':project.workspace_id}).json()['id']
    return h,user,pid,project.workspace_id,chat,open_id


def test_native_workload_excludes_closed_work_and_uses_full_final_week(client,db):
    h,user,pid,workspace,chat,open_id=setup_load(client,db)
    response=client.get(ROOT+f'/pms/workload/{pid}',headers=h,params={'start':'2026-05-04','weeks':2})
    assert response.status_code==200,response.text
    value=response.json();person=next(row for row in value['rows'] if row['user_id']==user.id)
    assert person['planned_hours']==30 and person['capacity_hours']==60
    assert person['weeks'][0]['status']=='over' and person['weeks'][0]['capacity_hours']==20
    assert person['weeks'][1]['capacity_hours']==40
    assert value['end']=='2026-05-17' and value['scope']=='selected_project_only'
    assert 'email' not in response.text and 'Synthetic open work' not in response.text
    assert response.headers['cache-control']=='private, no-store'
    native=client.get('/api/v1/project-management/workload',headers=h,params={'projectId':pid,'from':'2026-05-04','to':'2026-05-11','basis':'hours'})
    assert native.status_code==200,native.text
    original=next(row for row in native.json()['rows'] if row['user_id']==user.id)
    assert original['cells'][1]['capacity_hours']==40 and original['cells'][0]['planned_hours']==30


def test_native_workspace_workload_combines_projects_without_duplicating_capacity(client,db,monkeypatch):
    from app.apps.project_management.models import PMSWorkspace,PMSWorkspaceMember
    h,user,pid,workspace,chat,open_id=setup_load(client,db)
    project=db.get(PMSProject,pid)
    selected=PMSWorkspace(name='Selected workload workspace',organization_id=project.organization_id)
    db.add(selected);db.flush();workspace=selected.id
    project.workspace_id=workspace
    db.add(PMSWorkspaceMember(workspace_id=workspace,user_id=user.id,role='Owner'))
    second=PMSProject(name='Second authorized project',project_key=uuid4().hex[:12],
        organization_id=project.organization_id,workspace_id=workspace)
    elsewhere=PMSWorkspace(name='Different workspace',organization_id=project.organization_id)
    db.add_all([second,elsewhere]);db.flush()
    db.add(PMSWorkspaceMember(workspace_id=elsewhere.id,user_id=user.id,role='Owner'))
    outside=PMSProject(name='Outside selected workspace',project_key=uuid4().hex[:12],
        organization_id=project.organization_id,workspace_id=elsewhere.id)
    db.add(outside);db.commit()
    task(client,h,second.id,user.id,'Second project effort',15)
    task(client,h,outside.id,user.id,'Other workspace effort',80)
    endpoint='/api/v1/project-management/workload'
    params={'workspace_id':workspace,'from':'2026-05-04','to':'2026-05-04','basis':'hours'}
    response=client.get(endpoint,headers=h,params=params)
    assert response.status_code==200,response.text
    value=response.json();person=next(row for row in value['rows'] if row['user_id']==user.id)
    assert person['totals']['planned_hours']==45
    assert person['totals']['capacity_hours']==20
    assert {row['id'] for row in value['projects']}=={pid,second.id}
    narrowed=client.get(endpoint,headers=h,params={**params,'projectId':outside.id})
    assert narrowed.status_code==200 and narrowed.json()['rows']==[]
    assert client.get(endpoint,headers=h,params={**params,'workspace_id':0}).status_code==422
    snapshot=client.get(ROOT+f'/pms/workload/{pid}',headers=h,params={'start':'2026-05-04','scope':'workspace'})
    assert snapshot.status_code==200,snapshot.text
    source=snapshot.json();person=next(row for row in source['rows'] if row['user_id']==user.id)
    assert source['scope']=='authorized_workspace_projects' and source['project_count']==2
    assert person['planned_hours']==45 and person['capacity_hours']==20
    assert person['scope_headroom_hours']==-25 and 'project_headroom_hours' not in person
    assert 'Other workspace effort' not in snapshot.text and 'Second project effort' not in snapshot.text
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Synthetic workspace workload','workspace_id':workspace}).json()['id']
    initial=say(client,h,chat,f'Show workspace workload: project={pid}; start=2026-05-04',module='PMS',workspace_id=workspace)
    assert initial['status']=='answered',initial.get('error_code')
    assert '45 planned hours / 20 capacity hours' in initial['plan']['summary']
    assert 'authorized workspace projects only' in initial['plan']['summary']
    assert initial['result']['citations'][0]['href']==f'/pms/workload?workspace_id={workspace}&from=2026-05-04&to=2026-05-10&basis=hours'
    following=say(client,h,chat,'start=2026-05-11; weeks=1',module='PMS',workspace_id=workspace)
    assert following['status']=='answered',following.get('error_code')
    assert following['result']['workload_request']['scope']=='workspace'
    assert '0 planned hours / 40 capacity hours' in following['plan']['summary']
    assert not following['receipts']
    from ai_test_utils import auth_headers
    member,actor=auth_headers(client,db,email=f'workload-member-{uuid4()}@example.com',permissions=['ai_assistant','pms_view'])
    db.add(PMSWorkspaceMember(workspace_id=workspace,user_id=actor.id,role='Member'));db.commit()
    scoped=client.get(ROOT+f'/pms/workload/{pid}',headers=member,params={'start':'2026-05-04','scope':'workspace'})
    assert scoped.status_code==200,scoped.text
    assert scoped.json()['project_count']==2
    assert next(row for row in scoped.json()['rows'] if row['user_id']==user.id)['planned_hours']==45
    assert client.get(ROOT+f'/pms/workload/{outside.id}',headers=member,params={'start':'2026-05-04','scope':'workspace'}).status_code in {403,404}
    configured=client.put(f'/api/v1/ai-operator/providers/gemini?workspace_id={workspace}',headers=h,json={
        'model':'test-model','api_key':'unit-test-secret-key','enabled':True,'data_sharing_allowed':True})
    assert configured.status_code==200,configured.text
    calls=mock_provider(monkeypatch,{'summary':'Authorized workspace planning snapshot','steps':[],'source_ids':[f's1:{pid}']})
    result=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'PMS','workspace_id':workspace,
        'text':'Inspect cross-project workload evidence','context':[{'tool':'pms.workload','record_id':pid,'payload':{'start':'2026-05-04','scope':'workspace'}}]})
    assert result.status_code==200,result.text
    outbound=json.loads(json.loads(calls[0].content)['contents'][0]['parts'][0]['text'])
    packet=next(row['records'] for row in outbound['authorized_context'] if row['tool']=='pms.workload')
    assert packet['scope']=='authorized_workspace_projects' and packet['project_count']==2
    assert next(row for row in packet['rows'] if row['user_id']==user.id)['planned_hours']==45


def test_capacity_snapshot_reuses_holiday_adjustments_without_exposing_reasons(client,db):
    from app.models.attendance import Holiday
    h,user,pid,workspace,chat,open_id=setup_load(client,db)
    db.add(Holiday(name='Synthetic private holiday name',description='Private annotation',holiday_date=date(2026,5,5),is_active=True));db.commit()
    response=client.get(ROOT+f'/pms/workload/{pid}',headers=h,params={'start':'2026-05-04'})
    assert response.status_code==200,response.text
    person=next(row for row in response.json()['rows'] if row['user_id']==user.id)
    assert person['capacity_hours']==16
    assert 'private holiday' not in response.text and 'Private annotation' not in response.text


def test_local_conversation_clarifies_project_and_returns_cited_native_workload(client,db):
    h,user,pid,workspace,chat,open_id=setup_load(client,db)
    pending=say(client,h,chat,'PMS: Show workload',module='PMS',workspace_id=workspace)
    assert pending['status']=='needs_clarification'
    result=say(client,h,chat,f'project={pid}; start=2026-05-04; weeks=2',module='PMS',workspace_id=workspace)
    assert result['status']=='answered',result.get('error_code')
    assert '30 planned hours / 60 capacity hours' in result['plan']['summary']
    assert result['plan']['source_ids'] and not result['receipts']
    assert result['result']['citations'][0]['href']==f'/pms/workload?projectId={pid}&from=2026-05-04&to=2026-05-17&basis=hours'
    following=say(client,h,chat,'start=2026-05-11; weeks=1',module='PMS',workspace_id=workspace)
    assert following['status']=='answered',following.get('error_code')
    assert '0 planned hours / 40 capacity hours' in following['plan']['summary']


@pytest.mark.parametrize('params',[{'start':'2026-05-05'},{'start':'2026-05-04','weeks':5},
    {'start':'2026-05-04','weeks':0},{'start':'2026-05-04','after_user_id':1,'assignee_user_id':1}])
def test_bounded_workload_read_rejects_invalid_ranges_and_selectors(client,db,params):
    h,user,pid,workspace,chat,open_id=setup_load(client,db)
    assert client.get(ROOT+f'/pms/workload/{pid}',headers=h,params=params).status_code==422


def test_cloud_context_preserves_capacity_and_supports_reviewed_task_creation(client,db,monkeypatch):
    h,user,pid,workspace,chat,open_id=setup_load(client,db)
    plan={'summary':'Review an additional project task after checking workload','source_ids':[f's1:{pid}'],
        'steps':[{'tool':'pms.create_task','record_id':pid,'payload':{'title':'Synthetic reviewed workload followup','task_key':'WL-FOLLOWUP','assignee_user_id':user.id}}]}
    calls=mock_provider(monkeypatch,plan)
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'PMS',
        'workspace_id':workspace,'text':'Review project workload, then prepare a separately reviewed follow-up task',
        'context':[{'tool':'pms.workload','record_id':pid,'payload':{'start':'2026-05-04','weeks':2}}]})
    assert response.status_code==200,response.text
    draft=response.json();assert draft['status']=='awaiting_approval',draft.get('error_code')
    outbound=json.loads(json.loads(calls[0].content)['contents'][0]['parts'][0]['text'])
    source=next(row['records'] for row in outbound['authorized_context'] if row['tool']=='pms.workload')
    person=next(row for row in source['rows'] if row['user_id']==user.id)
    assert person['capacity_hours']==60 and person['weeks'][0]['planned_hours']==30
    assert source['scope']=='selected_project_only' and 'limitations' in source
    assert not db.query(PMSTask).filter_by(task_key='WL-FOLLOWUP').first()
    approve(client,h,draft);tick(client,db)
    completed=client.get(ROOT+f'/runs/{draft["id"]}',headers=h).json()
    assert completed['status']=='succeeded',completed.get('error_code')
    assert db.query(PMSTask).filter_by(task_key='WL-FOLLOWUP').count()==1


def test_read_followup_cannot_switch_project_or_replace_sources_with_other_tools(client,db):
    h,user,pid,workspace,chat,open_id=setup_load(client,db)
    initial=say(client,h,chat,f'Show workload: start=2026-05-04; project={pid}',module='PMS',workspace_id=workspace)
    assert initial['status']=='answered',initial.get('error_code')
    for extra in ({'text':f'project={pid+1000}'},{'text':'weeks=2','context':[{'tool':'crm.tasks'}]}):
        response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'PMS',
            'workspace_id':workspace,'conversation_id':chat,**extra})
        assert response.status_code==409,response.text


def test_pending_business_action_is_not_replaced_by_a_workload_read(client,db):
    h,user,pid,workspace,chat,open_id=setup_load(client,db)
    pending=say(client,h,chat,'CRM: Create a task called Synthetic pending approval',module='CRM',workspace_id=workspace)
    assert pending['status']=='awaiting_approval',pending.get('error_code')
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'PMS',
        'workspace_id':workspace,'conversation_id':chat,'project_id':pid,'text':'PMS: Show workload'})
    assert response.status_code==409,response.text
    assert client.get(ROOT+f'/runs/{pending["id"]}',headers=h).json()['status']=='awaiting_approval'


def test_native_secondary_only_assignment_is_counted_in_workload(client,db):
    h,user,pid,workspace,chat,open_id=setup_load(client,db)
    task_row=db.get(PMSTask,open_id);task_row.assignee_user_ids=[user.id];task_row.assignee_user_id=None;db.commit()
    value=client.get(ROOT+f'/pms/workload/{pid}',headers=h,params={'start':'2026-05-04'}).json()
    person=next(row for row in value['rows'] if row['user_id']==user.id)
    assert person['planned_hours']==30 and person['weeks'][0]['task_count']==1


def test_workload_scope_and_read_argument_authority_are_enforced(client,db):
    from ai_test_utils import auth_headers
    from app.ai_operator.suite_tools import validate_payload,TOOLS
    from fastapi import HTTPException
    h,user,pid,workspace,chat,open_id=setup_load(client,db)
    other,_=auth_headers(client,db,email=f'workload-outsider-{uuid4()}@example.com',permissions=['ai_assistant'])
    assert client.get(ROOT+f'/pms/workload/{pid}',headers=other,params={'start':'2026-05-04'}).status_code in {403,404}
    assert client.get(ROOT+f'/pms/workload/{pid}',headers=other,params={'start':'2026-05-04','scope':'workspace'}).status_code in {403,404}
    for arguments in ({'start':'2026-05-04','user_id':user.id},{'start':'2026-05-04','weeks':True},
                      {'start':'2026-05-04','scope':'organization'},{'start':'2026-05-04','workspace_id':999}):
        with pytest.raises(HTTPException):validate_payload(TOOLS['pms.workload'],arguments)


def test_workspace_workload_never_falls_back_to_all_projects_for_legacy_project(client,db):
    h,user,pid,workspace,chat,open_id=setup_load(client,db)
    assert workspace is None
    response=client.get(ROOT+f'/pms/workload/{pid}',headers=h,params={'start':'2026-05-04','scope':'workspace'})
    assert response.status_code==422,response.text


@pytest.mark.parametrize('half,expected',[(False,16),(True,18)])
def test_approved_hrms_leave_reduces_capacity_but_private_leave_fields_do_not_escape(client,db,half,expected):
    from app.models.employee import Employee
    from app.models.leave import LeaveRequest,LeaveType
    h,user,pid,workspace,chat,open_id=setup_load(client,db)
    employee=Employee(employee_id='WL-'+uuid4().hex[:8],user_id=user.id,first_name='Workload',last_name='User',date_of_joining=date(2020,1,1))
    leave_type=LeaveType(name='Synthetic confidential type',code=uuid4().hex[:12],days_allowed=20)
    db.add_all([employee,leave_type]);db.flush()
    for day,status in [(5,'Approved'),(6,'Pending')]:
        db.add(LeaveRequest(company_id=1,employee_id=employee.id,leave_type_id=leave_type.id,
            from_date=date(2026,5,day),to_date=date(2026,5,day),days_count=1,is_half_day=half,
            reason='Synthetic sensitive leave purpose',status=status))
    db.commit();db.expire(user,['employee'])
    response=client.get(ROOT+f'/pms/workload/{pid}',headers=h,params={'start':'2026-05-04'})
    assert response.status_code==200,response.text
    person=next(row for row in response.json()['rows'] if row['user_id']==user.id)
    assert person['capacity_hours']==expected
    assert 'confidential type' not in response.text and 'sensitive leave purpose' not in response.text


def test_workload_person_pages_and_direct_lookup_keep_scope_and_context_limits(client,db,monkeypatch):
    from ai_test_utils import auth_headers
    h,user,pid,workspace,chat,open_id=setup_load(client,db);ids=[user.id]
    for index in range(11):
        _,person=auth_headers(client,db,email=f'capacity-page-{uuid4()}@example.com',permissions=[])
        response=client.post(f'/api/v1/project-management/projects/{pid}/members',headers=h,json={'user_id':person.id,'role':'Member'})
        assert response.status_code==201,response.text
        ids.append(person.id)
    path=ROOT+f'/pms/workload/{pid}';first=client.get(path,headers=h,params={'start':'2026-05-04'}).json()
    assert first['has_more'] and len(first['rows'])==10
    last=client.get(path,headers=h,params={'start':'2026-05-04','after_user_id':first['next_after_user_id']}).json()
    assert not last['has_more']
    assert [row['user_id'] for row in first['rows']+last['rows']]==sorted(ids)
    direct=client.get(path,headers=h,params={'start':'2026-05-04','assignee_user_id':ids[-1]}).json()
    assert [row['user_id'] for row in direct['rows']]==[ids[-1]]
    calls=mock_provider(monkeypatch,{'summary':'Which person should be selected?','question':'Choose an assignee ID.','steps':[]})
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'PMS','workspace_id':workspace,
        'text':'Inspect the project workload source page','context':[{'tool':'pms.workload','record_id':pid,'payload':{'start':'2026-05-04'}}]})
    assert response.status_code==200,response.text
    outbound=json.loads(json.loads(calls[0].content)['contents'][0]['parts'][0]['text'])
    source=next(row for row in outbound['authorized_context'] if row['tool']=='pms.workload')
    assert not source['complete'] and len(source['records']['rows'])==10


def test_native_workload_bounds_and_local_truncation_are_explicit(client,db):
    h,user,pid,workspace,chat,open_id=setup_load(client,db)
    response=client.get('/api/v1/project-management/workload',headers=h,params={'projectId':pid,'from':'2026-01-05','to':'2027-01-04'})
    assert response.status_code==422
    from app.ai_operator.workload_intelligence import local_answer
    value=local_answer([{'tool':'pms.workload','records':{'truncated':True}}],[])
    assert value['question'] and not value['steps'] and not value['source_ids']


def test_specialist_templates_offer_workload_as_a_reviewable_capability():
    from app.ai_operator.agent_templates import templates
    versions={'project':4,'delivery':3,'performance':3}
    for value in templates():
        if value['id'] not in versions:continue
        assert value['version']==versions[value['id']]
        assert 'pms.workload' in value['tools'] and 'PMS' in value['modules']
        assert 'do not infer availability or employee performance' in value['instructions']
