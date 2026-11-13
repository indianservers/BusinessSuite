"""Core policy provenance reuses private runs, API logs and existing audit storage."""
import json
from types import MappingProxyType
from uuid import uuid4
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit,mock_provider
from tests.test_ai_operations import setup
from tests.test_task_routing_api import command,rate
from tests.test_provider_fallback_api import setup as fallback_setup,body
from ai_test_utils import auth_headers
from app.ai_operator import prompt_registry as registry
from app.ai_operator.suite_models import SuiteRun
from app.ai_operator.models import OperatorApiLog
from app.ai_agents.models import AiAuditLog
ROOT='/api/v1/ai-operator'


def test_success_and_failed_attempts_record_no_business_text_in_version_metadata(client,db,monkeypatch):
    h,alternate,calls=fallback_setup(client,db,monkeypatch)
    private='Synthetic private business context marker'
    response=client.post(ROOT+'/suite/commands',headers=h,json=body(text='Create a CRM task: '+private))
    assert response.status_code==200,response.text
    run=response.json();traces=run['result']['prompt_versions']
    assert len(traces)==2 and [p['status'] for p in traces]==['failed','success']
    assert [p['provider'] for p in traces]==['gemini','openai']
    assert all(p['request_attempted'] and p['version']==1 for p in traces)
    assert len({p['instruction_sha256'] for p in traces})==1
    assert len({p['request_fingerprint']['value'] for p in traces})==2
    assert all(p['request_fingerprint']['algorithm']=='HMAC-SHA256' for p in traces)
    assert private not in json.dumps(traces) and 'unit-test-secret-key' not in json.dumps(traces)
    logs=db.query(OperatorApiLog).filter_by(suite_run_id=run['id']).all()
    assert {p['api_log_id'] for p in traces}=={log.id for log in logs}
    audits=db.query(AiAuditLog).filter_by(action='llm.prompt.version').all()
    assert len(audits)==2 and private not in json.dumps([a.input_json for a in audits])
    usage=client.get(ROOT+'/analytics',headers=h);assert usage.status_code==200,usage.text
    selected=[r for r in usage.json()['logs'] if r['suite_run_id']==run['id']]
    assert len(selected)==2 and all(r['core_prompt']['version']==1 for r in selected)
    catalog=client.get(ROOT+'/prompt-versions',headers=h);assert catalog.status_code==200,catalog.text
    assert len(catalog.json()['items'])==5
    low,_=auth_headers(client,db,email='prompt-reader-'+uuid4().hex+'@example.com',permissions=['ai_assistant'])
    assert client.get(ROOT+'/prompt-versions',headers=low).status_code==403
    assert client.get(ROOT+f'/suite/runs/{run["id"]}',headers=low).status_code in (403,404)


def test_new_core_revision_requires_new_reviews_and_server_rollback_restores_exact_v1(client,db,monkeypatch):
    h,user,project,task,workspace=setup(client,db)
    calls=mock_provider(monkeypatch,{'summary':'Visible lead summary','steps':[]})
    for _ in range(3):
        r=command(client,h,workspace,project,'Show leads');assert r.status_code==200,r.text
        assert r.json()['result']['prompt_versions'][0]['version']==1;rate(client,h,r.json())
    r=command(client,h,workspace,project,'List leads',provider='auto');assert r.status_code==200,r.text
    assert r.json()['result']['routing']['measurement']['core_prompt']['version']==1
    original=registry.TEMPLATES['authorized-json'][1]
    with monkeypatch.context() as change:
        templates={**registry.TEMPLATES,'authorized-json':MappingProxyType({1:original,2:original+' Core policy revision two.'})}
        change.setattr(registry,'TEMPLATES',MappingProxyType(templates))
        change.setattr(registry,'ACTIVE',MappingProxyType({**registry.ACTIVE,'authorized-json':2}))
        before=len(calls)
        rejected=command(client,h,workspace,project,'Show leads',provider='auto')
        assert rejected.status_code==409,rejected.text
        assert len(calls)==before
        assert registry.render('suite_plan',{},version=1)[1]['version']==1
    restored=command(client,h,workspace,project,'List leads',provider='auto')
    assert restored.status_code==200,restored.text
    assert restored.json()['result']['routing']['measurement']['core_prompt']['version']==1
