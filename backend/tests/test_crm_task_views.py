from uuid import uuid4
import pytest
from tests.test_suite_operator import setup_suite,approve,tick,ROOT
from tests.test_suite_workspace import chat,say
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context
from app.shared.models import ServicePolicy
from app.ai_operator import suite
from ai_test_utils import auth_headers

V='/api/v1/crm/task-views'


def test_native_views_are_server_private_versioned_and_not_business_writes(client,db):
    h,user,_,_=setup_suite(client,db)
    first=client.post(V,headers=h,json={'name':'Overdue mine','filters':{'queue':'overdue','mine':True,'priority':'High'}})
    assert first.status_code==201,first.text
    value=first.json();view=value['items'][0]
    row=db.query(ServicePolicy).filter_by(kind='pipeline_ui').one()
    assert row.scope_key.endswith(f':{user.id}') and row.values_json['views'][0]['shared'] is False
    other,_=auth_headers(client,db,email=f'view-{uuid4()}@example.com',permissions=['crm_activities_view'])
    response=client.get(V,headers=other);assert response.status_code==200,response.text
    assert response.json()['items']==[]
    assert client.put(V+'/'+view['id'],headers=other,json={'name':'Stolen','filters':{},'revision':value['revision']}).status_code==404
    edited=client.put(V+'/'+view['id'],headers=h,json={'name':'Followups','filters':{'queue':'today'},'revision':value['revision']})
    assert edited.status_code==200
    assert client.delete(V+'/'+view['id'],headers=h,params={'revision':value['revision']}).status_code==409
    assert client.delete(V+'/'+view['id'],headers=h,params={'revision':edited.json()['revision']}).status_code==200
    assert client.get(V,headers=h).json()['items']==[]
    limited,_=auth_headers(client,db,email=f'deal-view-{uuid4()}@example.com',permissions=['crm_deals_view'])
    assert client.get(V,headers=limited).status_code==403
    wrong={**h,'X-Task-View-User':str(user.id+1000),'X-Task-View-Company':'1'}
    assert client.post(V,headers=wrong,json={'name':'Wrong account','filters':{}}).status_code==409
    assert client.get(V,headers=h).headers['cache-control']=='private, no-store'


def test_browser_import_is_atomic_idempotent_and_never_overwrites_conflicts(client,db):
    h,user,_,_=setup_suite(client,db)
    legacy={'views':[{'name':'My overdue','filters':{'queue':'overdue'}},{'name':'Today','filters':{'queue':'today'}}]}
    response=client.post(V+'/import-browser',headers=h,json=legacy);assert response.status_code==200,response.text
    assert response.json()['imported']==2
    retry=client.post(V+'/import-browser',headers=h,json=legacy)
    assert retry.status_code==200 and retry.json()['imported']==0 and retry.json()['retained']==2
    conflict={'views':[{'name':'Should rollback','filters':{}},{'name':'My overdue','filters':{'queue':'completed'}}]}
    assert client.post(V+'/import-browser',headers=h,json=conflict).status_code==409
    assert [v['name'] for v in client.get(V,headers=h).json()['items']]==['My overdue','Today']
    assert client.post(V,headers=h,json={'name':'No sharing','filters':{},'shared':True}).status_code==422


def test_bot_crm_view_followups_inline_edit_review_and_native_result(client,db):
    h,user,_,_=setup_suite(client,db);ident=chat(client,h)
    draft=say(client,h,ident,'CRM: Save task view called Delivery: queue=overdue; mine=true',module='CRM')
    assert draft['status']=='awaiting_approval',draft.get('error_code')
    assert draft['plan']['steps'][0]['tool']=='crm.create_saved_view'
    assert client.get(V,headers=h).json()['items']==[]
    corrected=say(client,h,ident,'priority=High; search=delivery',module='CRM')
    assert corrected['status']=='awaiting_approval'
    payload=corrected['plan']['steps'][0]['payload']
    assert payload['filters']['queue']=='overdue' and payload['filters']['mine'] is True
    assert client.post(ROOT+'/crm/views/create-approved',headers=h,json={**payload,'suite_run_id':corrected['id'],'suite_step':1}).status_code==403
    revised=client.post(ROOT+f'/runs/{corrected["id"]}/revise',headers=h,json={'request_key':str(uuid4()),'plan_hash':corrected['plan_hash'],
        'changes':[{'step':1,'field':'name','value':'Delivery focus'}]})
    assert revised.status_code==200,revised.text
    final_draft=say(client,h,ident,'queue=today',module='CRM');assert final_draft['status']=='awaiting_approval'
    assert final_draft['plan']['steps'][0]['payload']['name']=='Delivery focus'
    approve(client,h,final_draft);tick(client,db)
    finished=client.get(ROOT+f'/runs/{final_draft["id"]}',headers=h).json();assert finished['status']=='succeeded',finished.get('error_code')
    views=client.get(V,headers=h).json()['items'];assert len(views)==1 and views[0]['filters']['queue']=='today'
    assert finished['result_cards'][0]['href']==f'/crm/tasks?view={views[0]["id"]}'
    approve(client,h,finished);tick(client,db);assert len(client.get(V,headers=h).json()['items'])==1


def test_crm_view_recovers_lost_outer_receipt_without_duplicate(client,db,monkeypatch):
    h,user,_,_=setup_suite(client,db);ident=chat(client,h)
    draft=say(client,h,ident,'Save task view called Recovery: queue=overdue',module='CRM');approve(client,h,draft)
    original=suite.finish_step
    def lost(*args,**kwargs):raise RuntimeError('Synthetic lost CRM view receipt')
    monkeypatch.setattr(suite,'finish_step',lost);tick(client,db);monkeypatch.setattr(suite,'finish_step',original)
    stopped=client.get(ROOT+f'/runs/{draft["id"]}',headers=h).json()
    assert stopped['status']=='needs_reconciliation' and stopped['can_resume']
    resumed=client.post(ROOT+f'/runs/{draft["id"]}/resume',headers=h,json={'plan_hash':draft['plan_hash']})
    assert resumed.status_code==200 and resumed.json()['status']=='succeeded',resumed.text
    assert len(client.get(V,headers=h).json()['items'])==1


@pytest.mark.parametrize('operation',['change','remove'])
def test_crm_view_changed_after_commit_cannot_be_recreated_or_claimed_unchanged(client,db,monkeypatch,operation):
    h,user,_,_=setup_suite(client,db);ident=chat(client,h)
    draft=say(client,h,ident,'Save task view called Stale: queue=overdue',module='CRM');approve(client,h,draft)
    original=suite.finish_step
    def lost(*args,**kwargs):raise RuntimeError('Synthetic lost outer receipt')
    monkeypatch.setattr(suite,'finish_step',lost);tick(client,db);monkeypatch.setattr(suite,'finish_step',original)
    current=client.get(V,headers=h).json();view=current['items'][0]
    if operation=='change':response=client.put(V+'/'+view['id'],headers=h,json={'name':view['name'],'filters':{'queue':'completed'},'revision':current['revision']})
    else:response=client.delete(V+'/'+view['id'],headers=h,params={'revision':current['revision']})
    assert response.status_code==200
    resumed=client.post(ROOT+f'/runs/{draft["id"]}/resume',headers=h,json={'plan_hash':draft['plan_hash']})
    assert resumed.status_code==409
    assert len(client.get(V,headers=h).json()['items'])==(1 if operation=='change' else 0)
