"""Reviewed changes retain canonical ownership, versions and committed receipts."""
from uuid import uuid4
import pytest
from tests.test_suite_operator import setup_suite,approve,tick,ROOT
from tests.test_suite_workspace import chat,say
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context
from app.ai_operator import suite
from ai_test_utils import auth_headers


@pytest.fixture(params=['CRM','HRMS'])
def view_case(request,client,db):
    h,user,_,_=setup_suite(client,db);module=request.param
    path='/api/v1/crm/task-views' if module=='CRM' else '/api/v1/helpdesk/ticket-views'
    filters={'queue':'overdue','priority':'High'} if module=='CRM' else {'status':'Pending','priority':'High'}
    response=client.post(path,headers=h,json={'name':'Focus','filters':filters});assert response.status_code==201,response.text
    return h,module,path,response.json()['items'][0],chat(client,h)


def get(client,h,run):return client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()


def test_conversational_change_preview_inline_correction_removal_and_replay(client,db,view_case):
    h,module,path,view,ident=view_case
    draft=say(client,h,ident,'Update saved view called Focus: priority=Low',module=module)
    assert draft['status']=='awaiting_approval',draft.get('error_code')
    assert draft['plan']['steps'][0]['tool']==module.lower()+'.update_saved_view'
    assert client.get(path,headers=h).json()['items'][0]['filters']['priority']=='High'
    assert draft['result']['view_changes']['1']['changes']==[{'field':'priority','before':'High','after':'Low'}]
    revised=client.post(ROOT+f'/runs/{draft["id"]}/revise',headers=h,json={'request_key':str(uuid4()),'plan_hash':draft['plan_hash'],'changes':[{'step':1,'field':'name','value':'Reviewed focus'}]})
    assert revised.status_code==200,revised.text
    corrected=say(client,h,ident,'priority=Medium',module=module)
    assert corrected['plan']['steps'][0]['payload']['name']=='Reviewed focus'
    payload=corrected['plan']['steps'][0]['payload']
    assert client.post(ROOT+f'/{module.lower()}/views/update-approved',headers=h,json={**payload,'suite_run_id':corrected['id'],'suite_step':1}).status_code==403
    approve(client,h,corrected);tick(client,db);done=get(client,h,corrected)
    assert done['status']=='succeeded',done.get('error_code')
    assert done['result_cards'][0]['href'].endswith('?view='+view['id'])
    values=client.get(path,headers=h).json();assert values['items'][0]['name']=='Reviewed focus' and values['items'][0]['filters']['priority']=='Medium'
    approve(client,h,done);tick(client,db);assert client.get(path,headers=h).json()['revision']==values['revision']
    removal=say(client,h,ident,'Remove that view',module=module)
    assert removal['status']=='awaiting_approval' and removal['plan']['steps'][0]['tool']==module.lower()+'.remove_saved_view'
    assert client.get(path,headers=h).json()['items']
    approve(client,h,removal);tick(client,db);removed=get(client,h,removal)
    assert removed['status']=='succeeded' and client.get(path,headers=h).json()['items']==[]
    assert '?view=' not in removed['result_cards'][0]['href']
    approve(client,h,removed);tick(client,db);assert client.get(path,headers=h).json()['items']==[]
    assert client.get(ROOT+f'/conversations/{ident}',headers=h).status_code==200


def test_missing_target_followups_noop_and_switch_do_not_transfer_old_draft(client,db,view_case):
    h,module,path,view,ident=view_case
    pending=say(client,h,ident,'Update saved view: priority=Low',module=module)
    assert pending['status']=='needs_clarification'
    selected=say(client,h,ident,'view=Focus',module=module)
    assert selected['status']=='awaiting_approval' and selected['plan']['steps'][0]['payload']['filters']['priority']=='Low'
    other=client.post(path,headers=h,json={'name':'Other','filters':{'priority':'Medium'}}).json()['items'][-1]
    switched=say(client,h,ident,'view=Other; name=Other reviewed',module=module)
    payload=switched['plan']['steps'][0]['payload']
    assert payload['view_id']==other['id'] and payload['name']=='Other reviewed' and payload['filters']['priority']=='Medium'
    cancelled=say(client,h,ident,'Cancel',module=module);assert cancelled['status']=='answered'
    assert client.get(path,headers=h).json()['items'][0]['filters']['priority']=='High'
    noop=say(client,h,ident,'Update saved view called Focus',module=module)
    assert noop['status']=='needs_clarification'


def test_native_change_after_preview_rejects_stale_approval(client,db,view_case):
    h,module,path,view,ident=view_case
    draft=say(client,h,ident,'Update saved view called Focus: priority=Low',module=module)
    current=client.get(path,headers=h).json()
    response=client.put(path+'/'+view['id'],headers=h,json={'name':'Concurrent edit','filters':view['filters'],'revision':current['revision']});assert response.status_code==200
    response=client.post(ROOT+f'/runs/{draft["id"]}/approve',headers=h,json={'plan_hash':draft['plan_hash']})
    assert response.status_code==409
    assert client.get(path,headers=h).json()['items'][0]['name']=='Concurrent edit'


@pytest.mark.parametrize('action',['update','remove'])
def test_committed_change_recovers_lost_receipt_without_second_mutation(client,db,monkeypatch,view_case,action):
    h,module,path,view,ident=view_case
    text='Update saved view called Focus: priority=Low' if action=='update' else 'Remove saved view called Focus'
    draft=say(client,h,ident,text,module=module);assert draft['status']=='awaiting_approval';approve(client,h,draft)
    original=suite.finish_step
    def lost(*args,**kwargs):raise RuntimeError('Synthetic lost saved-view receipt')
    monkeypatch.setattr(suite,'finish_step',lost);tick(client,db);monkeypatch.setattr(suite,'finish_step',original)
    stopped=get(client,h,draft);assert stopped['status']=='needs_reconciliation' and stopped['can_resume'],stopped.get('error_code')
    revision=client.get(path,headers=h).json()['revision']
    response=client.post(ROOT+f'/runs/{draft["id"]}/resume',headers=h,json={'plan_hash':draft['plan_hash']})
    assert response.status_code==200 and response.json()['status']=='succeeded',response.text
    assert client.get(path,headers=h).json()['revision']==revision


def test_changed_committed_update_is_not_claimed_unchanged(client,db,monkeypatch,view_case):
    h,module,path,view,ident=view_case
    draft=say(client,h,ident,'Update saved view called Focus: priority=Low',module=module);approve(client,h,draft)
    original=suite.finish_step
    def lost(*args,**kwargs):raise RuntimeError('Synthetic lost receipt')
    monkeypatch.setattr(suite,'finish_step',lost);tick(client,db);monkeypatch.setattr(suite,'finish_step',original)
    current=client.get(path,headers=h).json()
    assert client.put(path+'/'+view['id'],headers=h,json={'name':'Edited later','filters':view['filters'],'revision':current['revision']}).status_code==200
    response=client.post(ROOT+f'/runs/{draft["id"]}/resume',headers=h,json={'plan_hash':draft['plan_hash']})
    assert response.status_code==409
    assert client.get(path,headers=h).json()['items'][0]['name']=='Edited later'


def test_private_view_reads_and_actions_do_not_cross_owners(client,db,view_case):
    h,module,path,view,ident=view_case
    other,_=auth_headers(client,db,email=f'view-owner-{uuid4()}@example.com',permissions=['ai_assistant','crm_activities_view'])
    assert client.get(path,headers=other).json()['items']==[]
    assert client.put(path+'/'+view['id'],headers=other,json={'name':'Unauthorized','filters':{},'revision':1}).status_code==404
    tools=client.get(ROOT+'/tools',headers=h).json()
    assert module.lower()+'.saved_views' in str(tools)


def test_cross_module_view_changes_use_dependencies_and_independent_native_revisions(client,db):
    from tests.test_suite_operator import prepare
    h,user,_,_=setup_suite(client,db);steps=[]
    for module,path in [('crm','/api/v1/crm/task-views'),('hrms','/api/v1/helpdesk/ticket-views')]:
        value=client.post(path,headers=h,json={'name':'Cross-module focus','filters':{'priority':'High'}}).json()
        view=value['items'][0]
        steps.append({'tool':module+'.update_saved_view','payload':{'view_id':view['id'],'revision':value['revision'],'name':'Reviewed '+module,'filters':{**view['filters'],'priority':'Low'}},'depends_on':[1] if module=='hrms' else []})
    draft=prepare(client,h,steps);assert draft['status']=='awaiting_approval'
    assert set(draft['result']['view_changes'])=={'1','2'}
    approve(client,h,draft);tick(client,db);done=get(client,h,draft)
    assert done['status']=='succeeded' and len(done['receipts'])==2,done.get('error_code')
    for path in ['/api/v1/crm/task-views','/api/v1/helpdesk/ticket-views']:
        assert client.get(path,headers=h).json()['items'][0]['filters']['priority']=='Low'


def test_same_collection_revision_chain_projects_and_executes_once(client,db,view_case):
    h,module,path,view,ident=view_case;revision=client.get(path,headers=h).json()['revision']
    payload={'view_id':view['id'],'revision':revision,'name':'Revised focus','filters':{**view['filters'],'priority':'Low'}}
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':module,'text':'Synthetic reviewed same-policy chain',
        'local_plan':{'summary':'Review both changes','steps':[{'tool':module.lower()+'.update_saved_view','payload':payload},{'tool':module.lower()+'.remove_saved_view','payload':{'view_id':view['id'],'revision':revision},'depends_on':[1]}]}})
    assert response.status_code==200,response.text
    draft=response.json();assert draft['status']=='awaiting_approval' and not draft['receipts']
    assert draft['result']['view_changes']['2']['record_name']=='Revised focus'
    assert client.get(path,headers=h).json()['revision']==revision
    approve(client,h,draft);tick(client,db);done=get(client,h,draft)
    assert done['status']=='succeeded' and [r['view_revision'] for r in done['receipts']]==[revision+1,revision+2],done.get('error_code')
    assert client.get(path,headers=h).json()['items']==[]
