import base64
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from tests.test_ai_operator import isolate_generic_http_audit, mock_provider
from tests.test_suite_operator import setup_suite, approve, tick
from app.ai_operator.commitments import reconcile
from app.apps.automation.models import AutomationScheduledJob as Job
from app.apps.crm.models import CRMTask

ROOT = '/api/v1/ai-operator/suite'


def extract(client, headers, **extra):
    body = {'request_key': str(uuid4()), 'module': 'CRM', 'text': 'Alice: I will send the proposal by 2030-01-10.', 'author': 'Meeting notes', **extra}
    response = client.post(ROOT + '/commitments/extract', headers=headers, json=body)
    assert response.status_code == 200, response.text
    return response.json(), body


def test_commitment_evidence_confirmation_reviewed_task_and_followthrough(client, db):
    headers, user, _, _ = setup_suite(client, db)
    batch, body = extract(client, headers)
    assert batch['candidates'][0]['quote'] in body['text'] and batch['source']['verified'] is False
    assert batch['candidates'][0]['ambiguities'] == ['owner']
    assert client.post(ROOT + '/commitments/extract', headers=headers, json=body).json()['id'] == batch['id']
    assert client.get(ROOT + f'/commitments/{batch["id"]}/candidates/1/task-draft', headers=headers).status_code == 409
    confirmed = client.post(ROOT + f'/commitments/{batch["id"]}/candidates/1/confirm', headers=headers,
        json={'revision': batch['revision'], 'title': 'Send the proposal', 'owner_user_id': user.id, 'due_date': '2030-01-10'})
    assert confirmed.status_code == 200, confirmed.text
    plan = client.get(ROOT + f'/commitments/{batch["id"]}/candidates/1/task-draft', headers=headers).json()
    command = client.post(ROOT + '/commands', headers=headers, json={'request_key': str(uuid4()), 'text': plan['summary'],
        'provider': 'local', 'module': plan['module'], 'commitment_id': batch['id'], 'candidate_id': 1,
        'local_plan': {'summary': plan['summary'], 'steps': plan['steps']}})
    assert command.status_code == 200 and command.json()['status'] == 'awaiting_approval', command.text
    assert db.query(CRMTask).count() == 0
    approve(client, headers, command.json()); tick(client, db)
    assert db.query(CRMTask).one().title == 'Send the proposal'
    reconcile(db)
    state = client.get(ROOT + '/commitments', headers=headers).json()['items'][0]
    assert state['candidates'][0]['status'] == 'task_created', state
    stored = db.get(Job, batch['id'])
    assert 'Alice: I will' not in stored.payload_json['encrypted_source']
    client.delete(ROOT + f'/commitments/{batch["id"]}', headers=headers)
    db.expire_all()
    assert 'encrypted_source' not in db.get(Job, batch['id']).payload_json
    assert db.get(Job, batch['id']).payload_json['candidates'] == []


def test_cloud_extraction_rejects_invented_quotes(client, db, monkeypatch):
    headers, _, _, _ = setup_suite(client, db)
    mock_provider(monkeypatch, {'commitments': [{'title': 'Fake', 'quote': 'This never appeared', 'due_date': None, 'owner_name': None}]})
    response = client.post(ROOT + '/commitments/extract', headers=headers, json={'request_key': str(uuid4()), 'text': 'We will review tomorrow.', 'provider': 'gemini'})
    assert response.status_code == 422
    assert db.query(CRMTask).count() == 0


def configured_connection(client, headers, db, user, connector):
    from app.apps.power_apps.models import PowerEnvironment
    from app.apps.power_apps.integrations.models import Credential, Connection
    from app.apps.power_apps.integrations.vault import CredentialVault
    if not db.query(PowerEnvironment).filter_by(organization_id=1, key='development').first():
        db.add(PowerEnvironment(organization_id=1, key='development', enabled=True))
    db.commit()
    response = client.post('/api/v1/power-apps/integrations/connections', headers=headers, json={
        'connector_id': connector, 'name': 'Private fixture account', 'auth_type': 'bearer',
        'secrets': {'access_token': 'fixture-not-live'}, 'writes_enabled': False,
        'scopes': {'gmail': ['https://www.googleapis.com/auth/gmail.readonly'], 'outlook': ['Mail.Read', 'Mail.ReadBasic'],
                   'google_calendar': ['https://www.googleapis.com/auth/calendar.events.readonly'], 'microsoft_calendar': ['Calendars.Read']}[connector]})
    assert response.status_code == 201, response.text
    return db.get(Connection, response.json()['id'])



@pytest.mark.parametrize('connector', ['gmail', 'outlook'])
def test_both_mail_connectors_use_owner_vault_and_purge_revoked_sources(client, db, monkeypatch, connector):
    from app.apps.power_apps.integrations import adapters
    from app.apps.power_apps.integrations.transport import Response
    from app.apps.power_apps.integrations.models import Credential, Operation
    headers, user, _, _ = setup_suite(client, db)
    conn = configured_connection(client, headers, db, user, connector)
    calls = []
    text = 'Alice: I will deliver the release by 2030-01-10.'
    class Provider:
        def __init__(self, *args, **kwargs): pass
        def request(self, method, url, headers=None, body=None, **kwargs):
            calls.append((method, url))
            assert method == 'GET'
            value = {'id': 'm1', 'payload': {'mimeType': 'text/plain', 'headers': [{'name': 'From', 'value': 'alice@example.test'}, {'name': 'Subject', 'value': 'Release commitment'}],
                'body': {'data': base64.urlsafe_b64encode(text.encode()).decode()}}} if connector == 'gmail' else {'id': 'm1', 'subject': 'Release commitment', 'from': {'emailAddress': {'address': 'alice@example.test'}}, 'body': {'contentType': 'text', 'content': text}}
            return Response(200, {}, json.dumps(value).encode(), 1)
    monkeypatch.setattr(adapters, 'HTTP_FACTORY', Provider)
    batch, _ = extract(client, headers, source_type='connected', text='', connection_id=conn.id, source_id='m1')
    assert batch['source']['verified'] is True and batch['source']['author'] == 'alice@example.test', batch
    assert len(batch['candidates']) == 1 and calls
    assert all(operation.output == {'source_read': True, 'retained': False} for operation in db.query(Operation))
    db.get(Credential, conn.credential_id).revoked_at = datetime.now(timezone.utc); db.commit()
    response = client.get(ROOT + '/commitments', headers=headers)
    assert response.status_code == 200, response.text
    revoked = response.json()['items'][0]
    assert revoked['status'] == 'revoked' and revoked['candidates'] == [], revoked
    assert 'encrypted_source' not in db.get(Job, batch['id']).payload_json
    assert client.get(ROOT + f'/commitments/{batch["id"]}/candidates/1/task-draft', headers=headers).status_code == 409


def test_connected_source_404_clears_derived_quotes(client, db, monkeypatch):
    from app.ai_operator import commitments
    from fastapi import HTTPException
    headers, user, _, _ = setup_suite(client, db)
    conn = configured_connection(client, headers, db, user, 'gmail')
    text = 'We will send the quote by 2030-01-10.'
    source = {'kind': 'gmail', 'id': 'm1', 'connection_revision': conn.revision, 'content_hash': 'original', 'verified': True}
    monkeypatch.setattr(commitments, 'load_source', lambda *args: (text, source))
    batch, _ = extract(client, headers, source_type='connected', text='', connection_id=conn.id, source_id='m1')
    def deleted(*args): raise HTTPException(404, 'Gone')
    monkeypatch.setattr(commitments, 'load_source', deleted)
    refreshed = client.post(ROOT + f'/commitments/{batch["id"]}/refresh-source', headers=headers)
    assert refreshed.status_code == 200 and refreshed.json()['status'] == 'deleted', refreshed.text
    assert refreshed.json()['candidates'] == []


@pytest.mark.parametrize('connector', ['google_calendar', 'microsoft_calendar'])
def test_both_calendar_connectors_read_selected_event_using_current_user(client, db, monkeypatch, connector):
    from app.apps.power_apps.integrations import adapters
    from app.apps.power_apps.integrations.transport import Response
    headers, user, _, _ = setup_suite(client, db)
    conn = configured_connection(client, headers, db, user, connector)
    calls = []
    class Provider:
        def __init__(self, *args, **kwargs): pass
        def request(self, method, url, **kwargs):
            calls.append(url)
            value = {'id': 'e1', 'summary': 'Delivery meeting', 'description': 'We will ship by 2030-01-10.', 'organizer': {'email': 'owner@example.test'}} if connector == 'google_calendar' else {'id': 'e1', 'subject': 'Delivery meeting', 'body': {'contentType': 'text', 'content': 'We will ship by 2030-01-10.'}, 'organizer': {'emailAddress': {'address': 'owner@example.test'}}}
            return Response(200, {}, json.dumps(value).encode(), 1)
    monkeypatch.setattr(adapters, 'HTTP_FACTORY', Provider)
    batch, _ = extract(client, headers, source_type='connected', text='', connection_id=conn.id, source_id='e1')
    assert batch['source']['verified'] is True and batch['source']['kind'] == connector
    assert len(batch['candidates']) == 1
    assert ('/me/events/e1' if connector == 'microsoft_calendar' else '/calendars/primary/events/e1') in calls[0]
