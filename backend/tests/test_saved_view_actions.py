import json
import pytest
from uuid import uuid4
from app.ai_operator import suite
from app.apps.project_management.models import PMSProject,PMSSavedFilter
from tests.test_suite_operator import setup_suite,prepare,approve,tick,ROOT
from tests.test_suite_workspace import say
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context


def setup(client,db):
    h,user,project,_=setup_suite(client,db);workspace=db.get(PMSProject,project).workspace_id
    response=client.post(ROOT+'/conversations',headers=h,json={'title':'Saved view followups','workspace_id':workspace})
    assert response.status_code==201
    return h,user,project,workspace,response.json()['id']


def test_saved_view_followups_create_native_private_filter_and_result_link(client,db):
    h,user,project,workspace,chat=setup(client,db)
    first=say(client,h,chat,'Save task view called Delivery focus: priority=High',module='PMS',workspace_id=workspace)
    assert first['status']=='needs_clarification' and db.query(PMSSavedFilter).count()==0
    draft=say(client,h,chat,f'project={project}; status=In Progress',module='PMS',workspace_id=workspace)
    assert draft['status']=='awaiting_approval' and draft['plan']['steps'][0]['tool']=='pms.create_saved_view'
    corrected=say(client,h,chat,'name=Urgent delivery; priority=Urgent',module='PMS',workspace_id=workspace)
    assert corrected['status']=='awaiting_approval'
    payload=corrected['plan']['steps'][0]['payload']
    assert payload['name']=='Urgent delivery' and payload['filters']['status']=='In Progress'
    direct=client.post(ROOT+'/pms/views/create-approved',headers=h,json={**payload,'suite_run_id':corrected['id'],'suite_step':1})
    assert direct.status_code==403 and db.query(PMSSavedFilter).count()==0
    approve(client,h,corrected);tick(client,db)
    final=client.get(ROOT+f'/runs/{corrected["id"]}',headers=h).json()
    assert final['status']=='succeeded',final.get('error_code')
    row=db.query(PMSSavedFilter).one()
    assert row.user_id==user.id and row.project_id==project and row.visibility=='private' and not row.is_shared and not row.is_default
    assert json.loads(row.filters_json)['projectId']==str(project)
    assert json.loads(row.filters_json)['priority']=='Urgent'
    assert final['result_cards'][0]['href']==f'/pms/tasks/advanced?view={row.id}'
    approve(client,h,final);tick(client,db);assert db.query(PMSSavedFilter).count()==1


def test_saved_view_recovery_after_lost_outer_receipt_is_not_duplicated(client,db,monkeypatch):
    h,user,project,workspace,chat=setup(client,db)
    draft=say(client,h,chat,f'Save view called Recovery: project={project}; status=Blocked',module='PMS',workspace_id=workspace)
    approve(client,h,draft);original=suite.finish_step
    def lost(*args,**kwargs):raise RuntimeError('Synthetic lost saved-view receipt')
    monkeypatch.setattr(suite,'finish_step',lost);tick(client,db)
    stopped=client.get(ROOT+f'/runs/{draft["id"]}',headers=h).json()
    assert stopped['status']=='needs_reconciliation' and stopped['can_resume'] and db.query(PMSSavedFilter).count()==1
    monkeypatch.setattr(suite,'finish_step',original)
    response=client.post(ROOT+f'/runs/{draft["id"]}/resume',headers=h,json={'plan_hash':draft['plan_hash']})
    assert response.status_code==200 and response.json()['status']=='succeeded'
    assert db.query(PMSSavedFilter).count()==1


@pytest.mark.parametrize('field',['filters_json','query','sort_json'])
def test_saved_view_changed_after_commit_blocks_resume(client,db,monkeypatch,field):
    h,user,project,workspace,chat=setup(client,db)
    draft=say(client,h,chat,f'Save view called Stale receipt: project={project}',module='PMS',workspace_id=workspace)
    approve(client,h,draft);original=suite.finish_step
    def lost(*args,**kwargs):raise RuntimeError('Synthetic lost receipt')
    monkeypatch.setattr(suite,'finish_step',lost);tick(client,db);monkeypatch.setattr(suite,'finish_step',original)
    row=db.query(PMSSavedFilter).one();setattr(row,field,'changed non-JSON native query' if field=='query' else json.dumps({'status':'Done'}));db.commit()
    denied=client.post(ROOT+f'/runs/{draft["id"]}/resume',headers=h,json={'plan_hash':draft['plan_hash']})
    assert denied.status_code==409 and db.query(PMSSavedFilter).count()==1


def test_saved_view_rejects_other_workspace_and_sharing_payload(client,db):
    h,user,project,workspace,chat=setup(client,db)
    other=client.post('/api/v1/project-management/workspaces',headers=h,json={'name':'Other workspace'}).json()['id']
    draft=prepare(client,h,[{'tool':'pms.create_saved_view','payload':{'name':'Wrong scope','project_id':project}}],module='PMS',workspace_id=other,provider='local')
    assert draft['status']!='awaiting_approval' and db.query(PMSSavedFilter).count()==0
    draft=prepare(client,h,[{'tool':'pms.create_saved_view','payload':{'name':'No publishing','project_id':project,'visibility':'workspace'}}],module='PMS',workspace_id=workspace,provider='local')
    assert draft['status']!='awaiting_approval' and db.query(PMSSavedFilter).count()==0


def test_saved_view_project_scope_is_rechecked_at_approval(client,db):
    h,user,project,workspace,chat=setup(client,db)
    draft=say(client,h,chat,f'Please create a saved task view called Scoped: project={project}',module='PMS',workspace_id=workspace)
    assert draft['status']=='awaiting_approval'
    other=client.post('/api/v1/project-management/workspaces',headers=h,json={'name':'Changed project workspace'}).json()['id']
    row=db.get(PMSProject,project);row.workspace_id=other;db.commit()
    denied=client.post(ROOT+f'/runs/{draft["id"]}/approve',headers=h,json={'plan_hash':draft['plan_hash']})
    assert denied.status_code==403 and db.query(PMSSavedFilter).count()==0


def test_saved_view_inline_name_revision_retains_conversational_filters(client,db):
    h,user,project,workspace,chat=setup(client,db)
    draft=say(client,h,chat,f'Save view called Original name: project={project}; priority=High',module='PMS',workspace_id=workspace)
    response=client.post(ROOT+f'/runs/{draft["id"]}/revise',headers=h,json={'request_key':str(uuid4()),'plan_hash':draft['plan_hash'],
        'changes':[{'step':1,'field':'name','value':'Edited name'}]})
    assert response.status_code==200
    followup=say(client,h,chat,'status=Blocked',module='PMS',workspace_id=workspace)
    assert followup['status']=='awaiting_approval'
    payload=followup['plan']['steps'][0]['payload']
    assert payload['name']=='Edited name' and payload['filters']['priority']=='High' and payload['filters']['status']=='Blocked'
