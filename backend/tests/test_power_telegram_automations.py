import json
from urllib.parse import unquote
import pytest
from app.apps.power_apps.telegram import conversation, poll_tick
from app.apps.power_apps.integrations import adapters
from app.apps.power_apps.integrations.transport import Response
from app.apps.power_apps.integrations.models import Credential
from app.apps.power_apps.runtime_models import AutomationTrigger as Trigger, AutomationEvent as Event
from app.apps.power_apps.models import PowerExecution
from app.apps.power_apps.runtime import claim, process
from tests.test_power_runtime import db
from tests.test_power_apps import actors

ROOT = '/api/v1/power-apps/automations/telegram'


def test_conversation_preserves_separate_topics_and_cancel():
    state, _ = conversation('Sales')
    state, _ = conversation('Alex', state)
    state, reply = conversation('Need a quotation', state)
    assert state == {'stage': 'complete', 'topic': 'Sales', 'name': 'Alex', 'requirement': 'Need a quotation'}
    assert 'received your enquiry' in reply
    assert conversation('/cancel', state)[0] == {'stage': 'menu'}
    assert conversation('Support')[0]['topic'] == 'Support'
    assert 'order number' in conversation('Sam', conversation('Order status')[0])[1]


def test_setup_poll_deduplicate_reply_logs_pause_and_scope(client, db, actors, monkeypatch):
    updates = []
    sent = []
    token = '123456789:fixture_telegram_token'
    class Transport:
        def __init__(self, policy):
            assert policy.allowed_hosts == {'api.telegram.org'}
        def request(self, method, url, **kwargs):
            url = unquote(url)
            if url.endswith('/getMe'):
                result = {'id': 123456789, 'username': 'enquiry_fixture_bot', 'is_bot': True}
            elif url.endswith('/getWebhookInfo'):
                result = {'url': ''}
            elif url.endswith('/getUpdates'):
                result = updates
            else:
                assert url.endswith('/sendMessage')
                sent.append(json.loads(kwargs['body']))
                result = {'message_id': len(sent)}
            return Response(200, {}, json.dumps({'ok': True, 'result': result}).encode(), 1)
    monkeypatch.setattr(adapters, 'HTTP_FACTORY', Transport)
    response = client.post(ROOT + '/setup', headers=actors[0], json={'token': token})
    assert response.status_code == 201, response.text
    resource_id = response.json()['resource_id']
    assert token not in response.text
    assert all(token not in row.encrypted_value for row in db.query(Credential).all())
    trigger = db.query(Trigger).filter_by(resource_id=resource_id, kind='telegram').one()
    for update_id, text in enumerate(['/start', 'Sales', 'Alex', 'Need 10 units'], 1):
        updates[:] = [{'update_id': update_id, 'message': {'date': trigger.config['started_at'] + 1, 'chat': {'id': 42, 'type': 'private'}, 'from': {'first_name': 'Alex', 'is_bot': False}, 'text': text}}]
        trigger.next_at = None
        db.commit()
        poll_tick(db)
        for _ in range(10):
            job = claim(db, 'telegram-test')
            if not job:
                break
            from app.access.service import background_scope
            from app.apps.power_apps.runtime_triggers import trigger_identity
            actor = trigger_identity(db, trigger)
            with background_scope(db, actor, 'power_apps', 'create', branch_id=trigger.config.get('branch_id')):
                process(db, *job)
    assert len(sent) == 4
    assert all(item['chat_id'] == '42' for item in sent)
    assert 'received your enquiry' in sent[-1]['text']
    assert db.query(PowerExecution).filter_by(resource_id=resource_id).count() == 4
    trigger = db.get(Trigger, trigger.id)
    trigger.next_at = None
    db.commit()
    poll_tick(db)
    assert db.query(PowerExecution).filter_by(resource_id=resource_id).count() == 4
    listing = client.get(ROOT + '/bots', headers=actors[0])
    assert listing.status_code == 200, listing.text
    assert listing.json()['items'] and listing.json()['items'][0]['messages'], (listing.json(), [(e.resource_id, e.kind, e.details) for e in db.query(Event).all() if e.kind == 'telegram_message'])
    assert listing.json()['items'][0]['messages'][0]['enquiry_completed'] is True
    assert token not in listing.text
    other = client.get(ROOT + '/bots', headers=actors[2])
    assert other.status_code == 200 and other.json()['items'] == []
    paused = client.put(f'{ROOT}/{resource_id}', headers=actors[0], json={'enabled': False})
    assert paused.status_code == 200, paused.text
    assert not db.get(Trigger, trigger.id).enabled
    assert client.get(ROOT + '/bots').status_code in {401, 403}


def test_preview_is_offline_and_validated(client, actors):
    response = client.post(ROOT + '/simulate', headers=actors[0], json={'messages': ['/start', 'Support', 'Alex', 'Login problem']})
    assert response.status_code == 200, response.text
    assert response.json()['sent'] is False
    assert response.json()['enquiry']['requirement'] == 'Login problem'
    assert client.post(ROOT + '/simulate', headers=actors[0], json={'messages': ['x' * 4097]}).status_code == 422
