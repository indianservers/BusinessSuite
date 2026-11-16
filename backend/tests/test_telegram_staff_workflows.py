from datetime import timedelta

from app.apps.crm.models import CRMTask
from app.apps.power_apps.models import TelegramConversation
from app.apps.power_apps.runtime_models import AutomationEvent as Event
from tests.test_power_runtime import db
from tests.test_power_apps import actors
from tests.test_telegram_operations import bot, ROOT
from tests.test_telegram_experience import publish, fact, deliver
from tests.test_telegram_ai import ai_permission


def test_grounded_staff_draft_requires_explicit_send_and_rejects_stale_sources(client, db, actors, bot):
    resource, trigger, owner, _, receive = bot
    ai_permission(db, owner)
    publish(client, actors, resource, knowledge=[fact()])
    receive('/human')
    receive('What are the showroom opening hours?')
    thread = db.query(TelegramConversation).one()
    route = f'{ROOT}/{resource.id}/conversations/{thread.id}'
    assert client.put(route, headers=actors[0], json={'action': 'claim'}).status_code == 200
    from app.apps.power_apps.models import TelegramMessage
    outgoing_before = db.query(TelegramMessage).filter_by(direction='outgoing').count()
    result = client.post(route + '/draft', headers=actors[0], json={})
    assert result.status_code == 200, result.text
    value = result.json()
    assert value['sent'] is False and value['sources'][0]['id'] == 'opening-hours'
    assert '9 AM' in value['text']
    assert db.query(TelegramMessage).filter_by(direction='outgoing').count() == outgoing_before
    receive('Actually, is that also true on Sunday?')
    stale = client.post(route + '/reply', headers=actors[0], json={'text': value['text'], 'draft_id': value['id'], 'client_key': 'draft-stale-test-key'})
    assert stale.status_code == 409
    fresh = client.post(route + '/draft', headers=actors[0], json={}).json()
    reply = client.post(route + '/reply', headers=actors[0], json={'text': fresh['text'], 'draft_id': fresh['id'], 'client_key': 'draft-reviewed-test-key'})
    assert reply.status_code == 202, reply.text
    assert db.get(Event, fresh['id']).details['status'] == 'used'


def test_industry_stage_approval_gates_crm_creation_and_tracks_transitions(client, db, actors, bot):
    resource, _, owner, _, _ = bot
    from app.apps.power_apps.telegram_experience import IndustryWorkflow, IntakeQuestion, ServiceStage
    flow = IndustryWorkflow(id='service-review', name='Reviewed service', industry='Consulting', result='task', questions=[IntakeQuestion(key='full_name', label='Your name')],
        approval_user_ids=[owner.id], stages=[ServiceStage(key='received', label='Received', requires_approval=True, next_stages=['completed']), ServiceStage(key='completed', label='Completed')])
    publish(client, actors, resource, workflows=[flow])
    deliver(db, bot, 1, callback='wf:service-review')
    deliver(db, bot, 2, text='Verified visitor')
    thread = db.query(TelegramConversation).one()
    assert db.query(CRMTask).count() == 0 and thread.context['stage_approved'] is False
    review = db.query(Event).filter_by(kind='telegram_stage_review').one()
    assert client.post(f'{ROOT}/{resource.id}/stage-reviews/{review.id}', headers=actors[1], json={'approved': True}).status_code == 404
    result = client.post(f'{ROOT}/{resource.id}/stage-reviews/{review.id}', headers=actors[0], json={'approved': True})
    assert result.status_code == 200, result.text
    assert db.query(CRMTask).count() == 1 and thread.context['stage_approved'] is True
    assert client.post(f'{ROOT}/{resource.id}/stage-reviews/{review.id}', headers=actors[0], json={'approved': True}).status_code == 200
    assert db.query(CRMTask).count() == 1
    route = f'{ROOT}/{resource.id}/conversations/{thread.id}/stage'
    result = client.post(route, headers=actors[0], json={'target': 'completed', 'expected_revision': 1})
    assert result.status_code == 200, result.text
    assert thread.context['service_stage'] == 'completed'
    assert client.post(route, headers=actors[0], json={'target': 'received', 'expected_revision': 1}).status_code == 409
