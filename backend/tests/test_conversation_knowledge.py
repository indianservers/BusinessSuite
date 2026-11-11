import json
from uuid import uuid4
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite
from tests.test_knowledge_search import chat
from tests.test_saved_agents import profile
from app.ai_operator import local_embeddings

ROOT='/api/v1/ai-operator/suite'


@pytest.fixture(autouse=True)
def lexical_fixture(monkeypatch):
    def offline(_):raise ValueError('No external or ML dependency in API contract tests')
    monkeypatch.setattr(local_embeddings,'encode',offline)


def upload(client,h,conversation):
    r=client.post(ROOT+f'/conversations/{conversation}/attachments',headers=h,files={'file':('delivery-policy.txt',b'Escalation owners review stalled commitments before creating recovery tasks.','text/plain')})
    assert r.status_code==201,r.text
    return r.json()['id']


def command(client,h,conversation,**extra):
    body={'request_key':str(uuid4()),'text':'Search knowledge for: Escalation owners','module':'CRM','provider':'local','conversation_id':conversation,**extra}
    r=client.post(ROOT+'/commands',headers=h,json=body)
    assert r.status_code==200,r.text
    return r.json(),body


def test_local_conversation_retrieves_cited_excerpts_and_replays_one_run(client,db):
    h,_,_,_=setup_suite(client,db);conversation=chat(client,h);ident=upload(client,h,conversation)
    run,body=command(client,h,conversation)
    assert run['status']=='answered',run
    assert 'Escalation owners' in run['plan']['summary']
    assert run['result']['citations'][0]['id']==f'upload:{ident}:0'
    assert run['result']['citations'][0]['href']==f'#bot-attachment-{ident}'
    assert run['result']['knowledge']['read_budget_used']==3
    assert run['approval_id'] is None and run['receipts']==[]
    assert client.post(ROOT+'/commands',headers=h,json=body).json()['id']==run['id']
    follow,_=command(client,h,conversation,text='What about stalled commitments?')
    assert follow['status']=='answered' and follow['result']['citations'][0]['file_id']==ident
    r=client.post(ROOT+f'/conversations/{conversation}/attachments',headers=h,files={'file':('leave-policy.txt',b'Annual leave requests require reporting manager approval.','text/plain')})
    assert r.status_code==201
    annual_id=r.json()['id']
    follow,_=command(client,h,conversation,text='What about annual leave requests?')
    assert follow['status']=='answered' and follow['result']['request']['module']=='CRM',follow
    assert follow['result']['citations'][0]['file_id']==annual_id
    assert client.delete(ROOT+f'/conversations/{conversation}/attachments/{ident}',headers=h).status_code==200
    follow,_=command(client,h,conversation)
    assert follow['status']=='answered' and follow['result']['citations']==[]
    assert 'No matching excerpts' in follow['plan']['summary']


def test_provider_can_request_search_and_only_use_server_issued_citations(client,db,monkeypatch):
    from app.ai_operator import suite
    h,_,_,_=setup_suite(client,db);conversation=chat(client,h);ident=upload(client,h,conversation);calls=[]
    def propose(*args,**kwargs):
        packet=json.loads(kwargs['prompt']);calls.append(packet)
        if len(calls)==1:return {'summary':'Retrieve supporting policy evidence.','context_requests':[{'tool':'crm.search_knowledge','payload':{'query':'Escalation owners','mode':'lexical','include_records':False}}],'steps':[]}
        assert 'Escalation owners' in json.dumps(packet['authorized_context'])
        return {'summary':'The uploaded policy says escalation owners review stalled commitments.','steps':[],'source_ids':[f'upload:{ident}:0']}
    monkeypatch.setattr(suite,'generate_json',propose)
    run,_=command(client,h,conversation,provider='gemini',text='What does our uploaded policy say about escalation owners?')
    assert run['status']=='answered',run
    assert len(calls)==2 and run['result']['planning_reads']==5
    assert run['result']['citations'][0]['file_id']==ident
    assert run['approval_id'] is None


def test_agent_search_keeps_native_tool_allowlist_and_requires_search_capability(client,db):
    h,_,_,_=setup_suite(client,db);conversation=chat(client,h);upload(client,h,conversation)
    agent=profile(client,h,tools=['crm.search_knowledge'])
    run,_=command(client,h,conversation,agent_id=agent['id'])
    assert run['status']=='answered',run
    assert run['result']['knowledge']['read_budget_used']==1
    denied=profile(client,h,tools=['crm.tasks'])
    run,_=command(client,h,conversation,agent_id=denied['id'])
    assert run['status']=='failed' and not run['result'].get('citations') and run['approval_id'] is None


def test_nested_search_calls_cannot_exceed_planning_budget(client,db):
    h,_,_,_=setup_suite(client,db);conversation=chat(client,h)
    run,_=command(client,h,conversation,text='Read selected knowledge sources',local_plan={'summary':'Read only','steps':[]},
        context=[{'tool':'crm.search_knowledge','payload':{'query':'one','mode':'lexical'}},
            {'tool':'crm.search_knowledge','payload':{'query':'two','mode':'lexical'}},
            {'tool':'crm.search_knowledge','payload':{'query':'three','mode':'lexical'}}])
    assert run['status']=='failed' and '422' in run['error_code'] and run['approval_id'] is None


def test_search_command_preserves_pending_action(client,db):
    from app.ai_operator.suite_models import SuiteRun
    h,_,_,_=setup_suite(client,db);conversation=chat(client,h)
    run,_=command(client,h,conversation,text='Create CRM task called Delivery followup')
    assert run['status']=='awaiting_approval'
    r=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'CRM','conversation_id':conversation,'text':'Search knowledge for: delivery'})
    assert r.status_code==409
    db.refresh(db.get(SuiteRun,run['id']));assert db.get(SuiteRun,run['id']).status=='awaiting_approval'


def test_model_cannot_cite_unissued_search_source(client,db,monkeypatch):
    from app.ai_operator import suite
    h,_,_,_=setup_suite(client,db);conversation=chat(client,h);upload(client,h,conversation)
    monkeypatch.setattr(suite,'generate_json',lambda *a,**k:{'summary':'Unsupported claim','steps':[],'source_ids':['upload:999999:0']})
    run,_=command(client,h,conversation,provider='gemini')
    assert run['status']=='failed' and '422' in run['error_code'] and run['approval_id'] is None
