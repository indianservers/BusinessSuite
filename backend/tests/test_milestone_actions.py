"""Reviewed milestone edits use native PMS permissions and concurrency."""
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,prepare,approve,tick,ROOT
from tests.test_suite_conversations import create,say
from app.apps.project_management.models import PMSMilestone
from uuid import uuid4
import pytest


def setup(client,db):
    headers,user,project,_=setup_suite(client,db)
    response=client.post(f'/api/v1/project-management/projects/{project}/milestones',headers=headers,json={'name':'Release review','start_date':'2027-03-01','due_date':'2027-03-20'})
    assert response.status_code==200,response.text
    return headers,user,project,response.json()['id']


def read(client,h,ident):
    response=client.get(f'/api/v1/project-management/milestones/{ident}',headers=h)
    assert response.status_code==200,response.text
    return response.json()


def test_local_milestone_followups_review_correction_cancel_and_execution(client,db):
    h,user,project,ident=setup(client,db);chat=create(client,h)
    first=say(client,h,chat,'PMS: update milestone',project_id=project)
    assert first['status']=='needs_clarification',first
    ack=say(client,h,chat,'yes');assert ack['status']=='needs_clarification' and not ack['plan']['steps']
    selected=say(client,h,chat,f'milestone #{ident}');assert selected['status']=='needs_clarification',selected
    draft=say(client,h,chat,'due date: 2027-03-25, name: Release acceptance')
    assert draft['status']=='awaiting_approval',draft
    assert draft['plan']['steps'][0]['tool']=='pms.update_milestone'
    assert draft['result']['milestone_changes']['1']['record_id']==ident
    assert db.get(PMSMilestone,ident).due_date.isoformat()=='2027-03-20'
    corrected=say(client,h,chat,'due date: 2027-03-28')
    assert corrected['status']=='awaiting_approval',corrected
    approve(client,h,corrected);assert tick(client,db)==1
    row=read(client,h,ident);assert row['due_date']=='2027-03-28' and row['name']=='Release acceptance'
    assert tick(client,db)==0


def test_native_stale_revision_and_invalid_date_range_do_not_write(client,db):
    h,user,project,ident=setup(client,db);record=read(client,h,ident)
    url=f'/api/v1/project-management/milestones/{ident}'
    response=client.patch(url,headers=h,json={'expected_revision':record['revision'],'due_date':'2027-02-20'})
    assert response.status_code==422,response.text
    response=client.patch(url,headers=h,json={'expected_revision':record['revision'],'name':'Updated'})
    assert response.status_code==200,response.text
    response=client.patch(url,headers=h,json={'expected_revision':record['revision'],'name':'Stale'})
    assert response.status_code==409,response.text
    assert read(client,h,ident)['name']=='Updated'


def test_reviewed_completion_exposes_progress_and_preserves_client_approval(client,db):
    h,user,project,ident=setup(client,db)
    record=read(client,h,ident)
    run=prepare(client,h,[{'tool':'pms.update_milestone','record_id':ident,'payload':{'expected_revision':record['revision'],'status':'Completed'}}],project_id=project)
    changes=run['result']['milestone_changes']['1']['changes']
    assert any(item['field']=='progress_percent' and item['after']==100 for item in changes)
    approve(client,h,run);tick(client,db)
    row=read(client,h,ident)
    assert row['status']=='Completed' and row['progress_percent']==100 and row['completed_at']
    assert row['client_approval_status']=='Not Required'


@pytest.mark.parametrize('field,value',[('client_approval_status','Approved'),('project_id',999),('progress_percent',101),('name',' '),('status','Approved')])
def test_native_milestone_rejects_invalid_or_approval_bypass_fields(client,db,field,value):
    h,user,project,ident=setup(client,db);record=read(client,h,ident)
    response=client.patch(f'/api/v1/project-management/milestones/{ident}',headers=h,json={'expected_revision':record['revision'],field:value})
    assert response.status_code==422,response.text


def test_native_pending_client_approval_requires_native_lifecycle(client,db):
    h,user,project,ident=setup(client,db)
    row=db.get(PMSMilestone,ident);row.client_approval_status='Pending';db.commit()
    record=read(client,h,ident)
    response=client.patch(f'/api/v1/project-management/milestones/{ident}',headers=h,json={'expected_revision':record['revision'],'due_date':'2027-03-30'})
    assert response.status_code==409,response.text


def test_stale_between_approval_and_execution_preserves_concurrent_change(client,db):
    h,user,project,ident=setup(client,db);record=read(client,h,ident)
    run=prepare(client,h,[{'tool':'pms.update_milestone','record_id':ident,'payload':{'expected_revision':record['revision'],'due_date':'2027-03-28'}}],project_id=project)
    approve(client,h,run)
    response=client.patch(f'/api/v1/project-management/milestones/{ident}',headers=h,json={'expected_revision':record['revision'],'name':'Concurrent update'})
    assert response.status_code==200,response.text
    tick(client,db)
    response=client.get(ROOT+f'/runs/{run["id"]}',headers=h)
    assert response.status_code==200,response.text
    assert response.json()['status']=='paused'
    assert tick(client,db)==0
    assert read(client,h,ident)['name']=='Concurrent update'
    assert read(client,h,ident)['due_date']=='2027-03-20'


def test_same_milestone_multiple_writes_require_combined_review(client,db):
    h,user,project,ident=setup(client,db);record=read(client,h,ident)
    run=prepare(client,h,[{'tool':'pms.update_milestone','record_id':ident,'payload':{'expected_revision':record['revision'],'name':'First'}},{'tool':'pms.update_milestone','record_id':ident,'payload':{'expected_revision':record['revision'],'due_date':'2027-03-28'}}],project_id=project)
    assert run['status']=='failed' and not run['receipts'],run
    assert read(client,h,ident)['name']=='Release review'


def test_milestone_edit_requires_native_project_write_permission(client,db):
    h,user,project,ident=setup(client,db);record=read(client,h,ident)
    from ai_test_utils import auth_headers
    from app.apps.project_management.models import PMSProjectMember
    viewer,actor=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','pms_view'])
    db.add(PMSProjectMember(project_id=project,user_id=actor.id,role='Viewer'));db.commit()
    response=client.patch(f'/api/v1/project-management/milestones/{ident}',headers=viewer,json={'expected_revision':record['revision'],'name':'Not allowed'})
    assert response.status_code in {403,404},response.text
    assert read(client,h,ident)['name']=='Release review'


def test_cloud_milestone_plan_reads_exact_native_revision_before_review(client,db,monkeypatch):
    import json
    from tests.test_ai_operator import mock_provider
    h,user,project,ident=setup(client,db);record=read(client,h,ident)
    calls=mock_provider(monkeypatch,{'summary':'Review milestone deadline','steps':[{'tool':'pms.update_milestone','record_id':ident,'payload':{'expected_revision':record['revision'],'due_date':'2027-03-28'}}]})
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'PMS','project_id':project,'text':f'PMS: reschedule milestone #{ident} to 2027-03-28'})
    assert response.status_code==200,response.text
    assert response.json()['status']=='awaiting_approval',response.json()
    packet=json.loads(json.loads(calls[0].content)['contents'][0]['parts'][0]['text'])
    exact=next(item for item in packet['authorized_context'] if item['tool']=='pms.milestone')
    assert exact['records']['revision']==record['revision']
    assert packet['milestone_planning_policy']['version']==1
    assert read(client,h,ident)['due_date']=='2027-03-20'


def test_milestone_project_selection_is_not_confused_with_milestone_record_id(client,db):
    h,user,project,ident=setup(client,db);record=read(client,h,ident)
    response=client.post('/api/v1/project-management/projects',headers=h,json={'name':'Other selected project','project_key':'OTHER'})
    assert response.status_code==200,response.text
    other=response.json()['id']
    run=prepare(client,h,[{'tool':'pms.update_milestone','record_id':ident,'payload':{'expected_revision':record['revision'],'name':'Wrong project edit'}}],project_id=other)
    assert run['status']=='failed' and not run['receipts'],run
    assert read(client,h,ident)['name']=='Release review'


def test_milestone_owner_must_be_active_and_project_eligible(client,db):
    h,user,project,ident=setup(client,db);record=read(client,h,ident)
    from ai_test_utils import auth_headers
    _,outsider=auth_headers(client,db,email=f'{uuid4()}@example.com',company_id=2,permissions=['pms_view'])
    response=client.patch(f'/api/v1/project-management/milestones/{ident}',headers=h,json={'expected_revision':record['revision'],'owner_user_id':outsider.id})
    assert response.status_code==422,response.text
    assert read(client,h,ident)['owner_user_id'] is None


def test_milestone_list_pagination_is_bounded(client,db):
    h,user,project,ident=setup(client,db)
    response=client.get(f'/api/v1/project-management/projects/{project}/milestones',headers=h,params={'limit':101})
    assert response.status_code==422,response.text


def test_native_owner_assignment_completion_reopen_and_clear(client,db):
    h,user,project,ident=setup(client,db)
    url=f'/api/v1/project-management/milestones/{ident}'
    record=read(client,h,ident)
    response=client.patch(url,headers=h,json={'expected_revision':record['revision'],'owner_user_id':user.id,'status':'In Progress','progress_percent':25})
    assert response.status_code==200,response.text
    record=response.json();assert record['owner_user_id']==user.id and record['progress_percent']==25
    response=client.patch(url,headers=h,json={'expected_revision':record['revision'],'status':'Completed'})
    assert response.status_code==200,response.text
    record=response.json();assert record['progress_percent']==100 and record['completed_at']
    response=client.patch(url,headers=h,json={'expected_revision':record['revision'],'status':'In Progress','owner_user_id':None})
    assert response.status_code==200,response.text
    assert response.json()['progress_percent']==0 and response.json()['completed_at'] is None
    assert response.json()['owner_user_id'] is None


def test_milestone_identity_and_result_link_use_its_actual_parent_project(client,db):
    h,user,project,first=setup(client,db)
    response=client.post(f'/api/v1/project-management/projects/{project}/milestones',headers=h,json={'name':'Second milestone'})
    assert response.status_code==200,response.text
    ident=response.json()['id']
    if ident==project:
        response=client.post(f'/api/v1/project-management/projects/{project}/milestones',headers=h,json={'name':'Different milestone identity'})
        assert response.status_code==200,response.text
        ident=response.json()['id']
    assert ident!=project
    record=read(client,h,ident)
    run=prepare(client,h,[{'tool':'pms.update_milestone','record_id':ident,'payload':{'expected_revision':record['revision'],'name':'Reviewed second milestone'}}],project_id=project)
    approve(client,h,run);tick(client,db)
    response=client.get(ROOT+f'/runs/{run["id"]}',headers=h)
    assert response.status_code==200,response.text
    final=response.json();assert final['status']=='succeeded',final
    assert final['receipts'][0]['project_id']==project
    assert final['result_cards'][0]['href']==f'/pms/projects/{project}/milestones'


def test_reviewed_milestone_owner_assignment_retains_execution_receipt(client,db):
    h,user,project,ident=setup(client,db);record=read(client,h,ident)
    run=prepare(client,h,[{'tool':'pms.update_milestone','record_id':ident,'payload':{'expected_revision':record['revision'],'owner_user_id':user.id}}],project_id=project)
    approve(client,h,run);tick(client,db)
    response=client.get(ROOT+f'/runs/{run["id"]}',headers=h)
    assert response.status_code==200,response.text
    assert response.json()['status']=='succeeded',response.json()
    assert response.json()['receipts'][0]['status']=='succeeded'
    assert read(client,h,ident)['owner_user_id']==user.id


def test_milestone_project_move_still_invalidates_authorization_context(client,db):
    from app.ai_agents.security import fingerprint
    h,user,project,ident=setup(client,db)
    response=client.post('/api/v1/project-management/projects',headers=h,json={'name':'New milestone parent','project_key':'PARENT'})
    assert response.status_code==200,response.text
    other=response.json()['id']
    before=fingerprint(db,user,1)
    # Simulate the authenticated origin a canonical project-move service supplies.
    previous=db.info.get('ai_request_context')
    db.info['ai_request_context']={'user_id':user.id,'company_id':1,'session_id':None}
    try:
        row=db.get(PMSMilestone,ident);row.project_id=other;db.commit()
        assert fingerprint(db,user,1)!=before
    finally:
        if previous is None:db.info.pop('ai_request_context',None)
        else:db.info['ai_request_context']=previous


def test_completion_draft_can_be_corrected_without_retaining_derived_progress(client,db):
    h,user,project,ident=setup(client,db);chat=create(client,h)
    complete=say(client,h,chat,f'PMS: complete milestone #{ident}',project_id=project)
    assert complete['status']=='awaiting_approval',complete
    assert complete['plan']['steps'][0]['payload']['progress_percent']==100
    corrected=say(client,h,chat,'status: In Progress')
    assert corrected['status']=='awaiting_approval',corrected
    approve(client,h,corrected);tick(client,db)
    record=read(client,h,ident)
    assert record['status']=='In Progress' and record['progress_percent']==0 and record['completed_at'] is None


@pytest.mark.parametrize('separator',['and','then'])
def test_compound_and_natural_followup_keep_one_record_and_review_all_changes(client,db,separator):
    h,user,project,ident=setup(client,db);chat=create(client,h)
    draft=say(client,h,chat,f'PMS: rename milestone #{ident} to "Client sign-off" {separator} move it to 2027-03-28',project_id=project)
    assert draft['status']=='awaiting_approval',draft
    assert len(draft['plan']['steps'])==1
    corrected=say(client,h,chat,'Rename it to "Final sign-off"')
    assert corrected['status']=='awaiting_approval',corrected
    payload=corrected['plan']['steps'][0]['payload']
    assert payload['name']=='Final sign-off' and payload['due_date']=='2027-03-28'
    approve(client,h,corrected);tick(client,db)
    row=read(client,h,ident)
    assert row['name']=='Final sign-off' and row['due_date']=='2027-03-28'


@pytest.mark.parametrize('correction',['Rename it to "Final acceptance"','name: Final acceptance'])
def test_compound_without_record_collects_id_before_preparing_any_action(client,db,correction):
    h,user,project,ident=setup(client,db);chat=create(client,h)
    pending=say(client,h,chat,'PMS: rename milestone to "Release acceptance" then move it to 2027-03-28',project_id=project)
    assert pending['status']=='needs_clarification' and not pending['plan']['steps'],pending
    revised=say(client,h,chat,correction)
    assert revised['status']=='needs_clarification' and not revised['plan']['steps'],revised
    draft=say(client,h,chat,f'milestone #{ident}')
    assert draft['status']=='awaiting_approval',draft
    payload=draft['plan']['steps'][0]['payload']
    assert payload['name']=='Final acceptance' and payload['due_date']=='2027-03-28'
    cancelled=say(client,h,chat,'cancel');assert cancelled['status']=='answered'
    assert read(client,h,ident)['name']=='Release review'


def test_conflicting_deadlines_require_followup_before_review_or_execution(client,db):
    h,user,project,ident=setup(client,db);chat=create(client,h)
    pending=say(client,h,chat,f'PMS: update milestone #{ident} due date: 2027-03-28, due date: 2027-04-01',project_id=project)
    assert pending['status']=='needs_clarification' and not pending['plan']['steps'],pending
    corrected=say(client,h,chat,'due date: 2027-04-01')
    assert corrected['status']=='awaiting_approval',corrected
    approve(client,h,corrected);tick(client,db)
    assert read(client,h,ident)['due_date']=='2027-04-01'
