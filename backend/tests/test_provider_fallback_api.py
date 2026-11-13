"""Real suite/API integration with synthetic provider responses and no network."""
import json
from uuid import uuid4
import httpx
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,approve,tick
from app.ai_operator.models import OperatorProvider,OperatorApiLog
from app.apps.crm.models import CRMTask
from app.ai_operator import providers
ROOT='/api/v1/ai-operator/suite'


def setup(client,db,monkeypatch,*,status=503,change=None,alternate_status=200,question=False):
    h,user,project,task=setup_suite(client,db)
    primary=db.query(OperatorProvider).filter_by(provider='gemini').one()
    alternate=OperatorProvider(scope_key=primary.scope_key,provider='openai',model='synthetic-alternate',
        encrypted_key=primary.encrypted_key,enabled=True,data_sharing_allowed=True,updated_by=user.id)
    db.add(alternate);db.commit();calls=[]
    plan={'summary':'Review follow-up work','steps':[],'question':'What should the task be called?'} if question else {
        'summary':'Review one CRM task','steps':[{'tool':'crm.create_task','payload':{'title':'Check delivery date'}}]}
    def respond(url,headers,body,seconds):
        calls.append({'provider':'gemini' if 'googleapis' in url else 'openai','seconds':seconds,
                      'retry_budget':providers._request_attempts.get()})
        if 'googleapis' in url:
            if change:
                setattr(alternate,*change);db.commit()
            code=status;value={'error':'Synthetic private provider body must not appear in trace'}
        else:
            code=alternate_status
            value={'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(plan)}]}],
                   'usage':{'input_tokens':20,'output_tokens':10}}
        return httpx.Response(code,json=value,request=httpx.Request('POST',url))
    monkeypatch.setattr(providers,'request_json',respond)
    return h,alternate,calls


def body(**extra):
    return {'request_key':str(uuid4()),'text':'Create a CRM task to check the delivery date','provider':'gemini',
            'fallback_provider':'openai','module':'CRM',**extra}


def test_transient_fallback_preserves_exact_review_idempotency_and_execution(client,db,monkeypatch):
    h,alternate,calls=setup(client,db,monkeypatch)
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Synthetic reviewed fallback action'}).json()['id']
    before=db.query(CRMTask).count();request=body(conversation_id=chat)
    r=client.post(ROOT+'/commands',headers=h,json=request);assert r.status_code==200,r.text
    run=r.json();assert run['status']=='awaiting_approval' and not run['receipts'],run
    trace=run['result']['provider_routing']
    assert trace['fallback_used'] and [a['provider'] for a in trace['attempts']]==['gemini','openai']
    assert run['result']['intelligence']['provider']=='openai'
    assert db.query(CRMTask).count()==before
    assert [c['provider'] for c in calls]==['gemini','openai'] and all(c['retry_budget']==1 for c in calls)
    assert db.query(OperatorApiLog).filter_by(suite_run_id=run['id']).count()==2
    assert client.post(ROOT+'/commands',headers=h,json=request).json()['id']==run['id'] and len(calls)==2
    changed={**request,'fallback_provider':None}
    assert client.post(ROOT+'/commands',headers=h,json=changed).status_code==409
    edited=client.post(ROOT+f'/runs/{run["id"]}/revise',headers=h,json={'request_key':str(uuid4()),
        'plan_hash':run['plan_hash'],'changes':[{'step':1,'field':'title','value':'Confirm revised delivery date'}]})
    assert edited.status_code==200,edited.text
    run=edited.json();assert run['status']=='awaiting_approval' and len(calls)==2
    assert run['plan']['steps'][0]['payload']['title']=='Confirm revised delivery date'
    assert 'fallback_provider' not in run['result']['request'] and not run['receipts']
    approve(client,h,run);tick(client,db)
    final=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert final['status']=='succeeded' and len(final['receipts'])==1,final
    assert db.query(CRMTask).count()==before+1


@pytest.mark.parametrize('status',[401,403])
def test_permanent_provider_error_never_calls_fallback(client,db,monkeypatch,status):
    h,alternate,calls=setup(client,db,monkeypatch,status=status)
    before=db.query(CRMTask).count()
    r=client.post(ROOT+'/commands',headers=h,json=body());assert r.status_code==200,r.text
    run=r.json();assert run['status']=='failed' and not run['receipts']
    assert [c['provider'] for c in calls]==['gemini']
    assert not run['result']['provider_routing']['fallback_used'] and db.query(CRMTask).count()==before
    assert 'Synthetic private' not in json.dumps(run['result']['provider_routing'])


def test_revoked_sharing_blocks_fallback_before_private_context_is_sent(client,db,monkeypatch):
    h,alternate,calls=setup(client,db,monkeypatch,change=('data_sharing_allowed',False))
    r=client.post(ROOT+'/commands',headers=h,json=body());assert r.status_code==200,r.text
    assert r.json()['status']=='failed' and [c['provider'] for c in calls]==['gemini']
    assert not r.json()['result']['provider_routing']['fallback_used']


def test_fallback_must_be_connected_and_distinct_before_any_call(client,db,monkeypatch):
    h,alternate,calls=setup(client,db,monkeypatch)
    assert client.post(ROOT+'/commands',headers=h,json=body(fallback_provider='gemini')).status_code==422
    alternate.enabled=False;db.commit()
    assert client.post(ROOT+'/commands',headers=h,json=body()).status_code==409
    assert client.post(ROOT+'/commands',headers=h,json=body(provider='local')).status_code==422
    assert calls==[]


def test_pending_followup_retains_fallback_choice(client,db,monkeypatch):
    h,alternate,calls=setup(client,db,monkeypatch,question=True)
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Synthetic fallback clarification'}).json()['id']
    first=client.post(ROOT+'/commands',headers=h,json=body(conversation_id=chat)).json()
    assert first['status']=='needs_clarification',first
    rejected=client.post(ROOT+'/commands',headers=h,json=body(conversation_id=chat,parent_run_id=first['id'],fallback_provider=None))
    assert rejected.status_code==409
    follow=body(conversation_id=chat,parent_run_id=first['id'],text='Confirm delivery date');follow.pop('fallback_provider')
    second=client.post(ROOT+'/commands',headers=h,json=follow);assert second.status_code==200,second.text
    assert second.json()['result']['request']['fallback_provider']=='openai'
    assert second.json()['status']=='needs_clarification'


def test_failed_planning_can_retry_locally_without_inheriting_cloud_fallback(client,db,monkeypatch):
    h,alternate,calls=setup(client,db,monkeypatch,alternate_status=503)
    first=client.post(ROOT+'/commands',headers=h,json=body()).json()
    assert first['status']=='failed' and first['result']['can_retry_planning'],first
    response=client.post(ROOT+f'/runs/{first["id"]}/retry-planning',headers=h,
        json={'request_key':str(uuid4()),'provider':'local'})
    assert response.status_code==200,response.text
    assert response.json()['status'] in {'needs_clarification','awaiting_approval'}
    assert 'fallback_provider' not in response.json()['result']['request']
    assert len(calls)==2 and not response.json()['receipts']
