import json
import pytest
from app.ai_operator import suite
from app.apps.project_management.models import PMSSavedFilter
from tests.test_saved_view_actions import setup
from tests.test_suite_operator import ROOT, approve, tick, prepare
from tests.test_suite_workspace import say
from tests.test_ai_operator import isolate_generic_http_audit


def native(client,h,project,name='PMS focus'):
    response=client.post('/api/v1/project-management/saved-views',headers=h,json={
        'name':name,'project_id':project,'view_type':'task_list','entity_type':'task','visibility':'private',
        'filters':{'projectId':str(project),'priority':'High'},'sort':{'field':'due_date'},'columns':{'name':True}})
    assert response.status_code==201,response.text
    return response.json()


def done(client,h,draft):return client.get(ROOT+f'/runs/{draft["id"]}',headers=h).json()


def test_pms_view_update_followups_inline_and_remove_reuse_native_storage(client,db):
    h,user,project,workspace,chat=setup(client,db);row=native(client,h,project)
    draft=say(client,h,chat,'PMS: Update saved view called PMS focus: priority=Low',module='PMS',workspace_id=workspace,project_id=project)
    assert draft['status']=='awaiting_approval',draft.get('error_code')
    revised=client.post(ROOT+f'/runs/{draft["id"]}/revise',headers=h,json={'request_key':'pms-view-inline-unique','plan_hash':draft['plan_hash'],'changes':[{'step':1,'field':'name','value':'Inline renamed'}]})
    assert revised.status_code==200,revised.text
    draft=say(client,h,chat,'Make it Medium',module='PMS',workspace_id=workspace,project_id=project)
    assert draft['plan']['steps'][0]['payload']['name']=='Inline renamed'
    assert draft['result']['view_changes']['1']['changes']
    assert client.post(ROOT+'/pms/views/update-approved',headers=h,json={**draft['plan']['steps'][0]['payload'],'suite_run_id':draft['id'],'suite_step':1}).status_code==403
    approve(client,h,draft);tick(client,db);result=done(client,h,draft)
    assert result['status']=='succeeded',result.get('error_code')
    db.expire_all();stored=db.get(PMSSavedFilter,row['id'])
    assert stored.name=='Inline renamed' and json.loads(stored.filters_json)['priority']=='Medium'
    assert json.loads(stored.sort_json)=={'field':'due_date'} and json.loads(stored.columns_json)=={'name':True}
    assert not stored.is_shared and stored.visibility=='private'
    assert result['result_cards'][0]['href']==f'/pms/tasks/advanced?view={row["id"]}'
    before=stored.updated_at;approve(client,h,result);tick(client,db);db.refresh(stored);assert stored.updated_at==before
    removal=say(client,h,chat,'Remove that view',module='PMS',workspace_id=workspace)
    assert removal['status']=='awaiting_approval',removal.get('error_code')
    approve(client,h,removal);tick(client,db);removed=done(client,h,removal)
    assert removed['status']=='succeeded',removed.get('error_code')
    assert removed['result_cards'][0]['href']=='/pms/tasks/advanced'
    assert db.get(PMSSavedFilter,row['id']) is None
    assert client.get(ROOT+f'/conversations/{chat}',headers=h).status_code==200


@pytest.mark.parametrize('action',['update','remove'])
def test_pms_view_committed_receipt_recovery(client,db,monkeypatch,action):
    h,user,project,workspace,chat=setup(client,db);row=native(client,h,project)
    text=f'{action} view called PMS focus'+(': priority=Low' if action=='update' else '')
    draft=say(client,h,chat,text,module='PMS',workspace_id=workspace,project_id=project)
    assert draft['status']=='awaiting_approval',draft.get('error_code')
    approve(client,h,draft);original=suite.finish_step
    def lost(*args,**kwargs):raise RuntimeError('Synthetic lost receipt')
    monkeypatch.setattr(suite,'finish_step',lost);tick(client,db);stopped=done(client,h,draft)
    assert stopped['status']=='needs_reconciliation' and stopped['can_resume']
    monkeypatch.setattr(suite,'finish_step',original)
    response=client.post(ROOT+f'/runs/{draft["id"]}/resume',headers=h,json={'plan_hash':draft['plan_hash']})
    assert response.status_code==200,response.text
    assert response.json()['status']=='succeeded'
    assert db.query(PMSSavedFilter).count()==(1 if action=='update' else 0)


@pytest.mark.parametrize('field',['name','query','sort_json','is_shared'])
def test_pms_view_native_changes_reject_stale_approval(client,db,field):
    h,user,project,workspace,chat=setup(client,db);row=native(client,h,project)
    draft=say(client,h,chat,'Update view called PMS focus: priority=Low',module='PMS',workspace_id=workspace,project_id=project)
    assert draft['status']=='awaiting_approval',draft.get('error_code')
    stored=db.get(PMSSavedFilter,row['id']);setattr(stored,field,True if field=='is_shared' else 'changed');db.commit()
    assert client.post(ROOT+f'/runs/{draft["id"]}/approve',headers=h,json={'plan_hash':draft['plan_hash']}).status_code in {403,404,409}


def test_pms_view_read_limits_ownership_scope_and_repeated_target(client,db):
    h,user,project,workspace,chat=setup(client,db);row=native(client,h,project)
    listed=client.get(ROOT+f'/pms/views/records/{project}',headers=h)
    assert listed.status_code==200,listed.text
    value=listed.json()['items'][0]
    assert value['filters']['priority']=='High' and len(value['source_sha256'])==64
    assert listed.headers['cache-control']=='private, no-store'
    from app.ai_operator.suite_tools import minimize_source
    assert minimize_source('pms.saved_views',listed.json())==listed.json()
    payload={key:value[key] for key in ('project_id','source_sha256','name','filters')};payload.update(view_id=value['id'],name='Changed')
    repeated=prepare(client,h,[{'tool':'pms.update_saved_view','payload':payload},{'tool':'pms.remove_saved_view','payload':{key:payload[key] for key in ('project_id','view_id','source_sha256')},'depends_on':[1]}],module='PMS',workspace_id=workspace,provider='local')
    assert repeated['status']!='awaiting_approval'
    stored=db.get(PMSSavedFilter,row['id']);stored.user_id=None;db.commit()
    assert client.get(ROOT+f'/pms/views/records/{project}',headers=h).json()['items']==[]


def test_pms_view_post_commit_changes_are_not_claimed_unchanged(client,db,monkeypatch):
    h,user,project,workspace,chat=setup(client,db);row=native(client,h,project)
    draft=say(client,h,chat,'Update view called PMS focus: priority=Low',module='PMS',workspace_id=workspace,project_id=project)
    approve(client,h,draft);original=suite.finish_step
    def lost(*args,**kwargs):raise RuntimeError('Synthetic lost receipt')
    monkeypatch.setattr(suite,'finish_step',lost);tick(client,db);monkeypatch.setattr(suite,'finish_step',original)
    assert done(client,h,draft)['status']=='needs_reconciliation'
    db.expire_all();stored=db.get(PMSSavedFilter,row['id']);stored.columns_json=json.dumps({'changed':True});db.commit()
    assert client.post(ROOT+f'/runs/{draft["id"]}/resume',headers=h,json={'plan_hash':draft['plan_hash']}).status_code==409
    db.refresh(stored);assert json.loads(stored.columns_json)=={'changed':True}


def test_pms_view_clarification_keeps_filters_and_rejects_other_workspace(client,db):
    h,user,project,workspace,chat=setup(client,db);row=native(client,h,project)
    pending=say(client,h,chat,'Update view: priority=Low',module='PMS',workspace_id=workspace)
    assert pending['status']=='needs_clarification'
    selected=say(client,h,chat,f'project={project}; view={row["id"]}',module='PMS',workspace_id=workspace)
    assert selected['status']=='awaiting_approval',selected.get('error_code')
    assert selected['plan']['steps'][0]['payload']['filters']['priority']=='Low'
    other=client.post('/api/v1/project-management/workspaces',headers=h,json={'name':'Other view workspace'}).json()['id']
    invalid=prepare(client,h,selected['plan']['steps'],module='PMS',workspace_id=other,provider='local')
    assert invalid['status']!='awaiting_approval'


def test_pms_view_distinct_targets_can_execute_with_dependencies(client,db):
    h,user,project,workspace,chat=setup(client,db);one=native(client,h,project);two=native(client,h,project,'Second focus')
    items=client.get(ROOT+f'/pms/views/records/{project}',headers=h).json()['items']
    steps=[]
    for index,item in enumerate(items):
        steps.append({'tool':'pms.update_saved_view','payload':{'project_id':project,'view_id':item['id'],
            'source_sha256':item['source_sha256'],'name':item['name'],'filters':{**item['filters'],'priority':'Low'}},'depends_on':[1] if index else []})
    draft=prepare(client,h,steps,module='PMS',workspace_id=workspace,provider='local')
    assert draft['status']=='awaiting_approval',draft.get('error_code')
    approve(client,h,draft);tick(client,db);result=done(client,h,draft)
    assert result['status']=='succeeded' and len(result['receipts'])==2,result.get('error_code')
    db.expire_all();assert all(json.loads(db.get(PMSSavedFilter,item['id']).filters_json)['priority']=='Low' for item in items)


def test_pms_view_opaque_queries_are_not_offered_for_replacement(client,db):
    h,user,project,workspace,chat=setup(client,db);row=native(client,h,project)
    stored=db.get(PMSSavedFilter,row['id']);stored.query='native expression';db.commit()
    value=client.get(ROOT+f'/pms/views/records/{project}',headers=h).json()
    assert value['items']==[] and value['unsupported_views']==1


def test_pms_view_noop_clarifies_and_defaults_are_preserved(client,db):
    h,user,project,workspace,chat=setup(client,db);row=native(client,h,project)
    stored=db.get(PMSSavedFilter,row['id']);stored.is_default=True;db.commit()
    unchanged=say(client,h,chat,'Update view called PMS focus',module='PMS',workspace_id=workspace,project_id=project)
    assert unchanged['status']=='needs_clarification'
    changed=say(client,h,chat,'Rename that view to Renamed default',module='PMS',workspace_id=workspace,project_id=project)
    assert changed['status']=='awaiting_approval',changed.get('error_code')
    approve(client,h,changed);tick(client,db);assert done(client,h,changed)['status']=='succeeded'
    db.refresh(stored);assert stored.is_default and stored.name=='Renamed default'
