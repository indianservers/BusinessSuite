"""Fingerprints match actual fixed-host payloads without retaining private input."""
import json
import time
import pytest
from fastapi import HTTPException
from tests.test_ai_operator import isolate_generic_http_audit, setup_operator, mock_provider, plan_for, preview
from app.ai_operator import providers, prompt_provenance, request_fingerprints
from app.ai_operator.models import OperatorProvider, OperatorApiLog
from app.ai_operator.schemas import TaskPlan
from app.ai_agents.models import AiAuditLog
from app.apps.project_management.models import PMSTask


@pytest.mark.parametrize('provider', ['openai', 'gemini', 'claude'])
def test_recorded_fingerprint_matches_actual_authorized_provider_body(client, db, monkeypatch, provider):
    headers, user, project, task = setup_operator(client, db, provider)
    calls = mock_provider(monkeypatch, plan_for(task))
    response = preview(client, headers, project, task, provider)
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'awaiting_approval'
    log = db.query(OperatorApiLog).filter_by(run_id=response.json()['id']).one()
    trace = prompt_provenance.lookup(db, [log])[log.id]
    assert trace['request_attempted'] and len(calls) == 1
    actual = calls[0]
    payload = json.loads(actual.content)
    expected = request_fingerprints.fingerprint(provider=provider, model=log.model,
        purpose=log.purpose, scope_key=log.scope_key, user_id=user.id,
        endpoint=str(actual.url), body=payload)
    assert trace['request_fingerprint'] == expected
    assert 'unit-test-secret-key' not in json.dumps(trace)
    assert 'Set priority High' not in json.dumps(trace)
    assert db.get(PMSTask, task).priority != 'High'
    audits = db.query(AiAuditLog).filter_by(action='llm.prompt.version').all()
    assert all('Set priority High' not in json.dumps(row.input_json) for row in audits)
    analytics = client.get('/api/v1/ai-operator/analytics', headers=headers)
    assert analytics.status_code == 200, analytics.text
    entry = next(item for item in analytics.json()['logs'] if item['id'] == log.id)
    assert entry['core_prompt']['request_fingerprint'] == expected


@pytest.mark.parametrize('reason', ['sharing_disabled', 'deadline_expired'])
def test_unsent_attempt_does_not_claim_a_complete_request_fingerprint(client, db, monkeypatch, reason):
    _, user, _, task = setup_operator(client, db, 'gemini')
    calls = mock_provider(monkeypatch, plan_for(task))
    config = db.query(OperatorProvider).filter_by(provider='gemini').one()
    if reason == 'sharing_disabled':
        config.data_sharing_allowed = False
    with providers.planning_deadline(time.monotonic() - 1 if reason == 'deadline_expired' else time.monotonic() + 30):
        with pytest.raises(HTTPException) as error:
            providers.generate_json(db, user, config, prompt='Synthetic private context',
                schema=TaskPlan.model_json_schema())
    assert error.value.status_code == (504 if reason == 'deadline_expired' else 409)
    db.commit()
    log = db.query(OperatorApiLog).one()
    trace = prompt_provenance.lookup(db, [log])[log.id]
    assert not calls and not trace['request_attempted'] and 'request_fingerprint' not in trace
    assert 'Synthetic private context' not in json.dumps(trace)
