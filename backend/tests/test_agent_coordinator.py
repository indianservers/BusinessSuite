from uuid import uuid4
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,approve,tick
from tests.test_saved_agents import profile
from tests.test_agent_workflows import start,process,state
from ai_test_utils import auth_headers
from app.ai_operator.suite_models import SuiteRun
from app.apps.crm.models import CRMTask

ROOT='/api/v1/ai-operator/suite/agents/coordinator'
FLOWS='/api/v1/ai-operator/suite/agents/workflows'


def propose(client,h,text,**extra):
    body={'request_key':str(uuid4()),'text':text,'provider':'local',**extra}
    r=client.post(ROOT+'/messages',headers=h,json=body);assert r.status_code==200,r.text
    return r.json(),body


def test_coordinator_followups_review_idempotency_and_existing_workflow(client,db):
    h,_,_,_=setup_suite(client,db);agent=profile(client,h,name='CRM Specialist')
    draft,body=propose(client,h,'CRM Specialist: Create CRM task called Coordinated followup')
    assert draft['draft']['nodes'][0]['agent_id']==agent['id'] and draft['workflow_id'] is None
    assert db.query(SuiteRun).count()==0 and db.query(CRMTask).count()==0
    assert client.post(ROOT+'/messages',headers=h,json=body).json()['context_id']==draft['context_id']
    changed,_=propose(client,h,'Call it Customer recovery',context_id=draft['context_id'],revision=1)
    assert changed['revision']==2 and changed['draft']['name']=='Customer recovery'
    url=ROOT+f'/{draft["context_id"]}/apply'
    assert client.post(url,headers=h,json={'preview_hash':draft['preview_hash']}).status_code==409
    r=client.post(url,headers=h,json={'preview_hash':changed['preview_hash']});assert r.status_code==200,r.text
    flow=r.json()['workflow_preview'];assert flow['status']=='preview' and db.query(SuiteRun).count()==1
    assert client.post(url,headers=h,json={'preview_hash':changed['preview_hash']}).json()['workflow_id']==flow['id']
    start(client,h,flow);process(client,db)
    node=state(client,h,flow)['nodes'][0]
    result=client.get(FLOWS+f'/{flow["id"]}/results',headers=h).json()
    assert result['complete'] is False and result['items'][0]['status']=='awaiting_approval' and result['items'][0]['receipts']==[]
    child=client.get('/api/v1/ai-operator/suite/runs/'+str(node['run_id']),headers=h).json();approve(client,h,child);tick(client,db);process(client,db)
    result=client.get(FLOWS+f'/{flow["id"]}/results',headers=h).json()
    assert result['complete'] and result['items'][0]['status']=='succeeded'
    assert result['items'][0]['receipts'][0]['record_id']==db.query(CRMTask).one().id


def test_coordinator_is_private_and_agent_revision_is_pinned(client,db):
    h,_,_,_=setup_suite(client,db);agent=profile(client,h,name='Delivery specialist')
    draft,_=propose(client,h,'Delivery specialist: Create CRM task called Delivery recovery')
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    assert client.get(ROOT+f'/{draft["context_id"]}',headers=other).status_code==404
    body={k:agent[k] for k in ('name','instructions','modules','tools','memory','workspace_id','project_id','provider','skill_ids','connection_ids','environment','mcp_ids')}
    body.update(revision=1,instructions='New instructions must be reviewed')
    assert client.put('/api/v1/ai-operator/suite/agents/'+str(agent['id']),headers=h,json=body).status_code==200
    assert client.post(ROOT+f'/{draft["context_id"]}/apply',headers=h,json={'preview_hash':draft['preview_hash']}).status_code==409
    assert db.query(SuiteRun).count()==0


def test_local_named_composition_respects_independent_and_ordered_steps(client,db):
    h,_,_,_=setup_suite(client,db)
    for name in ('Customer reviewer','Delivery reviewer','Report writer'):profile(client,h,name=name)
    draft,_=propose(client,h,'Customer reviewer: review overdue tasks; Delivery reviewer: review delivery risks then Report writer: summarize findings')
    assert [n['depends_on'] for n in draft['draft']['nodes']]==[[],[],[2]]
    unclear,_=propose(client,h,'Review all customer projects and fix staffing')
    assert unclear['draft']['question'] and unclear['draft']['nodes']==[]
    assert client.post(ROOT+f'/{unclear["context_id"]}/apply',headers=h,json={'preview_hash':unclear['preview_hash']}).status_code==409


@pytest.mark.parametrize('bad',['unknown_agent','cycle'])
def test_provider_cannot_invent_agents_or_cyclic_dependencies(client,db,monkeypatch,bad):
    from app.ai_operator import providers
    h,_,_,_=setup_suite(client,db);agent=profile(client,h)
    monkeypatch.setattr(providers,'generate_json',lambda *a,**k:{'name':'Invalid graph','nodes':[{'agent_id':999999 if bad=='unknown_agent' else agent['id'],'instructions':'Review authorized tasks','depends_on':[] if bad=='unknown_agent' else [1]}]})
    r=client.post(ROOT+'/messages',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','text':'Plan a coordinated review'})
    assert r.status_code==422,r.text
    assert db.query(SuiteRun).count()==0


def test_provider_plan_is_validated_and_new_messages_use_server_draft(client,db,monkeypatch):
    from app.ai_operator import providers
    h,_,_,_=setup_suite(client,db);agent=profile(client,h);prompts=[]
    def generate(*a,**k):
        import json
        prompts.append(json.loads(k['prompt']))
        return {'name':'Recovery review','nodes':[{'agent_id':agent['id'],'instructions':'Review overdue CRM tasks; ask for missing scope.','depends_on':[]}]}
    monkeypatch.setattr(providers,'generate_json',generate)
    draft,_=propose(client,h,'Review customer recovery',provider='gemini')
    changed,_=propose(client,h,'Keep the review focused on overdue work',provider='gemini',context_id=draft['context_id'],revision=1)
    assert prompts[1]['previous_draft']==draft['draft'] and changed['revision']==2
    assert client.get(ROOT+f'/{draft["context_id"]}',headers=h).json()['messages'][0]['text']=='Review customer recovery'
    assert db.query(SuiteRun).count()==0


def test_apply_recovers_committed_preview_without_duplicate_workflow(client,db,monkeypatch):
    from fastapi import HTTPException
    from app.ai_operator import agent_workflows
    h,_,_,_=setup_suite(client,db);profile(client,h,name='Recovery specialist')
    draft,_=propose(client,h,'Recovery specialist: Create CRM task called Recovery check')
    original=agent_workflows.preview;attempts=[]
    def lost_response(*a,**k):
        result=original(*a,**k);attempts.append(result['id'])
        if len(attempts)==1:raise HTTPException(503,'Synthetic response loss after commit')
        return result
    monkeypatch.setattr(agent_workflows,'preview',lost_response)
    url=ROOT+f'/{draft["context_id"]}/apply';body={'preview_hash':draft['preview_hash']}
    assert client.post(url,headers=h,json=body).status_code==503
    recovered=client.post(url,headers=h,json=body)
    assert recovered.status_code==200,recovered.text
    assert recovered.json()['workflow_id']==attempts[0] and len(set(attempts))==1
    assert db.query(SuiteRun).count()==1 and db.query(CRMTask).count()==0


def test_slow_provider_cannot_overwrite_a_newer_design_revision(client,db,monkeypatch):
    from app.ai_operator import providers
    from app.ai_operator.assistant_models import AssistantConversation
    h,_,_,_=setup_suite(client,db);agent=profile(client,h,name='Revision specialist')
    draft,_=propose(client,h,'Revision specialist: review tasks')
    def another_writer(*a,**k):
        # Simulate a committed competing revision while inference is in flight.
        row=db.get(AssistantConversation,draft['context_id'])
        row.references={**row.references,'revision':2};db.commit()
        return {'name':'Stale inference','nodes':[{'agent_id':agent['id'],'instructions':'Review old work','depends_on':[]}]}
    monkeypatch.setattr(providers,'generate_json',another_writer)
    r=client.post(ROOT+'/messages',headers=h,json={'request_key':str(uuid4()),'text':'Review overdue work','context_id':draft['context_id'],'revision':1,'provider':'gemini'})
    assert r.status_code==409,r.text
    db.expire_all();row=db.get(AssistantConversation,draft['context_id'])
    assert row.references['revision']==2 and row.references['draft']['name']!='Stale inference'
