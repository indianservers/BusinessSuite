from uuid import uuid4
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit,mock_provider
from tests.test_suite_operator import setup_suite
from ai_test_utils import auth_headers
from app.ai_operator.assistant_models import AssistantConversation
from app.apps.automation.models import AutomationScheduledJob as Job
from app.ai_operator.suite_models import SuiteRun

ROOT='/api/v1/ai-operator/suite/agents/builder'


def send(client,h,text,prior=None,**extra):
    body={'request_key':str(uuid4()),'text':text,'provider':'local',**extra}
    if prior:body.update(context_id=prior['context_id'],revision=prior['revision'])
    response=client.post(ROOT+'/messages',headers=h,json=body)
    assert response.status_code==200,response.text
    return response.json(),body


def profiles(db):return db.query(AssistantConversation).filter(AssistantConversation.references['saved_agent'].as_boolean()==True).count()


def test_builder_followups_review_and_compound_save_are_idempotent(client,db):
    h,_,_,_=setup_suite(client,db)
    first,body=send(client,h,'Create a delivery coordinator that checks delayed projects every morning')
    assert not first['question'] and first['schedule']['frequency']=='daily'
    assert profiles(db)==0 and db.query(Job).count()==0
    assert client.post(ROOT+'/messages',headers=h,json=body).json()['context_id']==first['context_id']
    renamed,_=send(client,h,'Call it Recovery Captain',first)
    assert renamed['config']['name']=='Recovery Captain'
    assert renamed['draft']['run_prompt']==first['draft']['run_prompt']
    assert client.post(ROOT+f'/{first["context_id"]}/apply',headers=h,json={'preview_hash':first['preview_hash']}).status_code==409
    final,_=send(client,h,'At 10:30 am',renamed)
    assert final['draft']['schedule']['at']=='10:30'
    response=client.post(ROOT+f'/{final["context_id"]}/apply',headers=h,json={'preview_hash':final['preview_hash']})
    assert response.status_code==200,response.text
    result=response.json();assert result['agent']['name']=='Recovery Captain'
    assert result['schedule_preview']['status']=='preview'
    assert result['schedule_preview']['spec']['prompt']==first['draft']['run_prompt']
    assert profiles(db)==1 and db.query(SuiteRun).count()==0
    again=client.post(ROOT+f'/{final["context_id"]}/apply',headers=h,json={'preview_hash':final['preview_hash']})
    assert again.status_code==200,again.text
    assert again.json()['agent_id']==result['agent_id'] and db.query(Job).count()==1 and profiles(db)==1


def test_builder_asks_for_work_and_retains_permissions_and_provider_corrections(client,db):
    h,_,_,_=setup_suite(client,db)
    draft,_=send(client,h,'Create a CRM sales assistant every morning')
    assert draft['question']
    complete,_=send(client,h,'Show my overdue tasks',draft)
    assert not complete['question'] and complete['draft']['run_prompt']=='Show my overdue tasks'
    local,_=send(client,h,'Use local intelligence',complete)
    narrowed,_=send(client,h,'Only CRM and read only',local)
    assert narrowed['config']['provider']=='local'
    assert narrowed['config']['modules']==['CRM']
    from app.ai_operator.suite_tools import TOOLS
    assert all(TOOLS[t].method=='GET' for t in narrowed['config']['tools'])
    assert narrowed['schedule']['frequency']=='daily'
    assert narrowed['draft']['run_prompt']==complete['draft']['run_prompt']


def test_builder_is_private_persistent_and_rejects_stale_followups(client,db):
    h,_,_,_=setup_suite(client,db);draft,_=send(client,h,'Create an HR assistant')
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    assert client.get(ROOT+f'/{draft["context_id"]}',headers=other).status_code==404
    assert client.get(ROOT,headers=other).json()['items']==[]
    changed,_=send(client,h,'Call it HR help',draft)
    response=client.post(ROOT+'/messages',headers=h,json={'request_key':str(uuid4()),'text':'Call it stale','provider':'local','context_id':draft['context_id'],'revision':draft['revision']})
    assert response.status_code==409,response.text
    restored=client.get(ROOT+f'/{draft["context_id"]}',headers=h).json()
    assert restored['revision']==changed['revision'] and len(restored['messages'])==2


def test_cloud_builder_uses_registered_tools_and_never_saves_without_review(client,db,monkeypatch):
    h,_,_,_=setup_suite(client,db)
    mock_provider(monkeypatch,{'name':'Sales coordinator','instructions':'Prepare reviewed follow-up tasks.','tools':['crm.tasks','crm.create_task'],'memory':[],'run_prompt':'Show overdue tasks','schedule':None,'question':None})
    draft,_=send(client,h,'Create a sales coordinator',provider='gemini')
    assert draft['provider']=='gemini' and profiles(db)==0 and db.query(SuiteRun).count()==0
    assert draft['knowledge'][0]['tool']=='crm.tasks'


def test_specialist_catalog_covers_all_requested_roles_and_finance_uses_cloud(client,db):
    from app.ai_operator.saved_agents import Config
    h,_,_,_=setup_suite(client,db)
    r=client.get('/api/v1/ai-operator/suite/agents/catalog/templates',headers=h)
    assert r.status_code==200,r.text
    assert len(r.json()['items'])==14
    for item in r.json()['items']:
        Config(name=item['name'],instructions=item['instructions'],modules=item['modules'],tools=item['tools'])
    draft,_=send(client,h,'Create a finance assistant')
    assert draft['config']['modules']==['FAM']
    assert draft['config']['provider']=='preferred'
    with pytest.raises(ValueError):Config(name='Finance',instructions='Review vouchers',modules=['FAM'],tools=['fam.vouchers'],provider='local')


def test_trained_role_recommendation_still_uses_typed_config_and_review(client,db,monkeypatch):
    from app.ai_operator import builder_tensorflow
    monkeypatch.setattr(builder_tensorflow,'predict',lambda text:{'label':'lead-qualification','score':.97,'margin':.85,'engine':'tensorflow-agent-builder-v1'})
    h,_,_,_=setup_suite(client,db)
    draft,_=send(client,h,'Build a helper to screen fresh prospects')
    assert draft['config']['name']=='Lead Qualification Agent'
    assert draft['local_prediction']['used']
    assert profiles(db)==0 and db.query(SuiteRun).count()==0


def test_builder_rejects_credentials_and_archives_private_designs(client,db):
    h,_,_,_=setup_suite(client,db)
    response=client.post(ROOT+'/messages',headers=h,json={'request_key':str(uuid4()),'text':'Create an agent with AQ.'+'A'*32,'provider':'local'})
    assert response.status_code==422,response.text
    draft,_=send(client,h,'Create a CRM sales assistant')
    assert client.delete(ROOT+f'/{draft["context_id"]}',headers=h).status_code==200
    assert client.get(ROOT+f'/{draft["context_id"]}',headers=h).status_code==404


def test_cloud_followup_cannot_silently_broaden_read_only_tools(client,db,monkeypatch):
    import httpx
    h,_,_,_=setup_suite(client,db);real_client=httpx.Client
    answer={'name':'Sales reader','instructions':'Review authorized tasks.','tools':['crm.tasks','crm.create_task'],'memory':[],'run_prompt':'Show tasks','schedule':None,'question':None}
    mock_provider(monkeypatch,answer)
    first,_=send(client,h,'Create a CRM assistant, read only',provider='gemini')
    assert first['config']['tools']==['crm.tasks']
    monkeypatch.setattr('app.ai_operator.providers.httpx.Client',real_client)
    mock_provider(monkeypatch,{**answer,'name':'Renamed reader'})
    changed,_=send(client,h,'Call it Renamed reader',first,provider='gemini')
    assert changed['config']['tools']==['crm.tasks'] and changed['constraints']['read_only']
