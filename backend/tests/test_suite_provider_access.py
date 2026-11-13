"""Cross-module consumers can use a scoped provider without credential access."""
from tests.rich_text_test_utils import organization_context
from uuid import uuid4
import pytest
from tests.test_suite_module_scope import managed
from tests.test_ai_operator import mock_provider,isolate_generic_http_audit
from tests.test_suite_conversations import ROOT


def test_hrms_ai_consumer_can_use_company_gemini_without_pms_access(client,db,monkeypatch):
    _,_,headers,user=managed(client,db)
    calls=mock_provider(monkeypatch,{'summary':'No business action requested.','steps':[]})
    response=client.post(ROOT+'/commands',headers=headers,json={'request_key':str(uuid4()),'text':'Explain what an action review is.','provider':'gemini','mode':'auto'})
    assert response.status_code==200,response.text
    assert response.json()['status']=='answered',response.json()
    assert len(calls)==1
    assert client.get('/api/v1/project-management/projects',headers=headers).status_code==403


def test_cross_module_provider_catalog_is_public_metadata_not_credentials(client,db):
    _,_,headers,user=managed(client,db)
    response=client.get(ROOT+'/providers',headers=headers)
    assert response.status_code==200,response.text
    assert response.json()['items'][0]['provider']=='gemini'
    assert response.json()['items'][0]['has_key'] is True
    assert 'encrypted_key' not in response.text and 'unit-test-secret-key' not in response.text
    assert client.put('/api/v1/ai-operator/providers/gemini',headers=headers,json={'model':'unauthorized-change'}).status_code==403
    assert client.post('/api/v1/ai-operator/providers/gemini/test',headers=headers).status_code==403


def test_consumers_do_not_inherit_another_company_configuration(client,db):
    _,_,headers,user=managed(client,db)
    from ai_test_utils import auth_headers
    from app.access.models import AccessPolicy
    other_headers,other=auth_headers(client,db,email=f'{uuid4()}@example.com',company_id=2,permissions=['ai_assistant'])
    db.add(AccessPolicy(company_id=2,user_id=other.id,status='active',grants={'ai':{'enabled':True,'role':'Employee','scope':'own','permissions':['ai_assistant'],'actions':['view','create']}}));db.commit()
    response=client.get(ROOT+'/providers',headers=other_headers)
    assert response.status_code==200,response.text
    assert response.json()=={'items':[]}
    response=client.post(ROOT+'/commands',headers=other_headers,json={'request_key':str(uuid4()),'text':'Explain an action review','provider':'gemini','mode':'auto'})
    assert response.status_code==409,response.text


@pytest.mark.parametrize('flag',['enabled','data_sharing_allowed'])
def test_disabled_company_provider_cannot_be_consumed(client,db,monkeypatch,flag):
    _,_,headers,user=managed(client,db)
    from app.ai_operator.models import OperatorProvider
    row=db.query(OperatorProvider).filter_by(provider='gemini').one();setattr(row,flag,False);db.commit()
    calls=mock_provider(monkeypatch,{'summary':'Must not call cloud','steps':[]})
    response=client.post(ROOT+'/commands',headers=headers,json={'request_key':str(uuid4()),'text':'Explain an action review','provider':'gemini','mode':'auto'})
    assert response.status_code==409,response.text
    assert not calls


def test_ai_only_consumer_circuit_breaker_reads_own_sanitized_usage(client,db,monkeypatch):
    _,_,headers,user=managed(client,db)
    from app.ai_operator.models import OperatorApiLog
    for _ in range(3):
        db.add(OperatorApiLog(scope_key='company:1',module='CROSS',user_id=user.id,provider='gemini',model='test-model',purpose='suite_plan',status='failed',http_status=503,duration_ms=1))
    db.commit()
    calls=mock_provider(monkeypatch,{'summary':'Circuit must block outbound request','steps':[]})
    response=client.post(ROOT+'/commands',headers=headers,json={'request_key':str(uuid4()),'text':'Explain an action review','provider':'gemini','mode':'auto'})
    assert response.status_code==200,response.text
    assert response.json()['status']=='failed',response.json()
    assert response.json()['error_code']=='AI_POLICY_HTTP_503'
    log=db.query(OperatorApiLog).filter_by(user_id=user.id).order_by(OperatorApiLog.id.desc()).first()
    assert log.error_code=='PROVIDER_CIRCUIT_OPEN'
    assert not calls


def test_another_users_provider_failures_do_not_block_consumer(client,db,monkeypatch):
    _,owner,headers,user=managed(client,db)
    from app.ai_operator.models import OperatorApiLog
    for _ in range(3):
        db.add(OperatorApiLog(scope_key='company:1',module='CROSS',user_id=owner.id,provider='gemini',model='test-model',purpose='suite_plan',status='failed',http_status=503,duration_ms=1))
    db.commit()
    calls=mock_provider(monkeypatch,{'summary':'No business action requested.','steps':[]})
    response=client.post(ROOT+'/commands',headers=headers,json={'request_key':str(uuid4()),'text':'Explain an action review','provider':'gemini','mode':'auto'})
    assert response.status_code==200,response.text
    assert response.json()['status']=='answered',response.json()
    assert len(calls)==1
