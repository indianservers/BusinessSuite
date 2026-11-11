import json
from uuid import uuid4
import httpx
import pytest
from tests.test_suite_operator import setup_suite, ROOT
from tests.test_ai_operator import mock_provider, isolate_generic_http_audit
from app.ai_operator import providers
from app.ai_operator.models import OperatorApiLog, OperatorProvider
from app.apps.crm.models import CRMTask


def test_transient_retries_and_retry_after_budget(monkeypatch):
    real = httpx.Client
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(503 if len(calls)<3 else 200)
    monkeypatch.setattr(providers.httpx,'Client',lambda **kw: real(transport=httpx.MockTransport(handler),**kw))
    monkeypatch.setattr(providers.time,'sleep',lambda _:None)
    assert providers.request_json('https://example.com',{}, {},45).status_code==200
    assert len(calls)==3
    calls.clear()
    def limited(request):
        calls.append(request)
        return httpx.Response(429,headers={'Retry-After':'3600'})
    monkeypatch.setattr(providers.httpx,'Client',lambda **kw: real(transport=httpx.MockTransport(limited),**kw))
    assert providers.request_json('https://example.com',{}, {},1).status_code==429
    assert len(calls)==1


@pytest.mark.parametrize('status',[400,401,403])
def test_permanent_errors_are_not_retried(monkeypatch,status):
    real=httpx.Client
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(status)
    monkeypatch.setattr(providers.httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    assert providers.request_json('https://example.com',{}, {},45).status_code==status
    assert len(calls)==1


def test_default_prefers_scoped_gemini_and_preferences_are_private(client,db,monkeypatch):
    h,user,_,_=setup_suite(client,db)
    health=client.get(ROOT+'/intelligence',headers=h)
    assert health.status_code==200,health.text
    assert health.json()['selected_provider']=='gemini'
    assert 'encrypted_key' not in health.text and 'unit-test-secret-key' not in health.text
    mock_provider(monkeypatch,{'summary':'Draft','steps':[{'tool':'crm.create_task','payload':{'title':'Review'}}]})
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'preferred','text':'Create a followup'})
    assert response.status_code==200,response.text
    run=response.json()
    assert run['status']=='awaiting_approval',run
    assert run['result']['request']['provider']=='gemini'
    assert run['result']['intelligence']=={'provider':'gemini','model':'test-model','engine':'provider'}
    assert db.query(CRMTask).count()==0
    changed=client.put(ROOT+'/intelligence',headers=h,json={'provider':'local','module':'CRM'})
    assert changed.status_code==200,changed.text
    assert client.get(ROOT+'/intelligence?module=CRM',headers=h).json()['selected_provider']=='local'
    assert client.get(ROOT+'/intelligence?module=PMS',headers=h).json()['selected_provider']=='gemini'
    from ai_test_utils import auth_headers
    h2,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    assert client.get(ROOT+'/intelligence?module=CRM',headers=h2).json()['preference']=='preferred'


def test_failed_planning_recovers_without_business_writes_and_keeps_health_separate(client,db,monkeypatch):
    h,user,_,_=setup_suite(client,db)
    monkeypatch.setattr(providers.time,'sleep',lambda _:None)
    real_client=httpx.Client
    calls=mock_provider(monkeypatch,{},status=503)
    failed=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','text':'Create CRM task Review'}).json()
    assert failed['status']=='failed' and failed['result']['can_retry_planning']
    assert len(calls)==3
    monkeypatch.setattr(providers.httpx,'Client',real_client)
    mock_provider(monkeypatch,{'summary':'Connection verified','clarification':None,'steps':[]})
    tested=client.post('/api/v1/ai-operator/providers/gemini/test',headers=h)
    assert tested.status_code==200,tested.text
    health=client.get(ROOT+'/intelligence',headers=h).json()['items'][0]
    assert health['connectivity']['status']=='success', json.dumps({'health':health,'scope':failed['scope_key'],'logs':[(r.user_id,r.scope_key,r.model,r.purpose,r.status) for r in db.query(OperatorApiLog).all()],'uid':user.id})
    assert health['planning']['error_code']=='PROVIDER_HTTP_503'
    monkeypatch.setattr(providers.httpx,'Client',real_client)
    mock_provider(monkeypatch,{'summary':'Recovered draft','steps':[{'tool':'crm.create_task','payload':{'title':'Review'}}]})
    key=str(uuid4())
    url=ROOT+f'/runs/{failed["id"]}/retry-planning'
    recovered=client.post(url,headers=h,json={'request_key':key})
    assert recovered.status_code==200,recovered.text
    assert recovered.json()['status']=='awaiting_approval',recovered.text
    assert recovered.json()['command']==failed['command']
    again=client.post(url,headers=h,json={'request_key':key})
    assert again.json()['id']==recovered.json()['id']
    assert db.query(CRMTask).count()==0
    denied=client.post(ROOT+f'/runs/{recovered.json()["id"]}/retry-planning',headers=h,json={'request_key':str(uuid4())})
    assert denied.status_code==409


def test_connectivity_success_does_not_reset_planning_circuit(client,db):
    _,user,_,_=setup_suite(client,db)
    config=db.query(OperatorProvider).filter_by(provider='gemini').first()
    for _ in range(3):
        db.add(OperatorApiLog(user_id=user.id,scope_key=config.scope_key,provider='gemini',model=config.model,purpose='suite_plan',status='failed',http_status=503,duration_ms=1))
    db.flush()
    db.add(OperatorApiLog(user_id=user.id,scope_key=config.scope_key,provider='gemini',model=config.model,purpose='test',status='success',duration_ms=1))
    db.flush()
    assert providers.circuit_open(db,user,config,config.scope_key)


def test_explicit_preference_does_not_silently_fallback_when_disabled(client,db):
    h,_,_,_=setup_suite(client,db)
    selected=client.put(ROOT+'/intelligence',headers=h,json={'provider':'gemini','module':'CRM'})
    assert selected.status_code==200
    disabled=client.put('/api/v1/ai-operator/providers/gemini',headers=h,json={'model':'test-model','enabled':False,'data_sharing_allowed':True})
    assert disabled.status_code==200,disabled.text
    state=client.get(ROOT+'/intelligence?module=CRM',headers=h).json()
    assert state['selected_provider'] is None
    rejected=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'text':'Prepare a followup','module':'CRM','provider':'preferred'})
    assert rejected.status_code==409
    assert db.query(CRMTask).count()==0


def test_transport_retry_is_bounded(monkeypatch):
    real=httpx.Client
    attempts=[]
    def handler(request):
        attempts.append(request)
        raise httpx.ReadTimeout('private provider details')
    monkeypatch.setattr(providers.httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    monkeypatch.setattr(providers.time,'sleep',lambda _:None)
    with pytest.raises(httpx.ReadTimeout):
        providers.request_json('https://example.com',{}, {},45)
    assert len(attempts)==3


def test_pending_conversation_pins_provider_when_default_changes(client,db,monkeypatch):
    h,_,_,_=setup_suite(client,db)
    calls=mock_provider(monkeypatch,{'summary':'Need a title','question':'Which title?','steps':[]})
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Pinned provider'}).json()
    first=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'conversation_id':chat['id'],'provider':'preferred','module':'CRM','text':'Create task'}).json()
    assert first['status']=='needs_clarification',first
    assert client.put(ROOT+'/intelligence',headers=h,json={'provider':'local','module':'CRM'}).status_code==200
    follow=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'conversation_id':chat['id'],'parent_run_id':first['id'],'provider':'preferred','module':'CRM','text':'Contract review'})
    assert follow.status_code==200,follow.text
    assert follow.json()['result']['request']['provider']=='gemini'
    assert len(calls)==2
    assert db.query(CRMTask).count()==0
