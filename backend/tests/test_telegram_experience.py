from datetime import timedelta
import json

import pytest
from pydantic import ValidationError
from app.apps.power_apps.telegram_experience import ExperienceConfiguration, KnowledgeFact, IndustryWorkflow, IntakeQuestion, UrgencyRule, knowledge_answer, qualify
from app.apps.power_apps import telegram_dialogue, telegram_routing
from app.apps.power_apps.models import TelegramConversation, TelegramMessage
from app.apps.power_apps.telegram import accept_update
from app.apps.power_apps.runtime import now
from app.access.service import background_scope
from app.apps.crm.models import CRMLead, CRMTask
from tests.test_power_runtime import db
from tests.test_power_apps import actors
from tests.test_telegram_operations import bot, ROOT


def fact(**extra):
    return {'id': 'opening-hours', 'title': 'Showroom opening hours', 'content': 'The showroom opens at 9 AM.', 'kind': 'policy',
        'source_url': 'https://example.com/opening-hours', 'source_reference': 'Business policy, page 2', 'approved': True,
        'expires_at': (now() + timedelta(days=30)).isoformat(), **extra}


def publish(client, actors, resource, **extra):
    data = ExperienceConfiguration(**extra).model_dump(mode='json')
    response = client.put(f'{ROOT}/{resource.id}/experience', headers=actors[0], json=data)
    assert response.status_code == 200, response.text
    return response.json()['configuration']


def deliver(db, bot, update_id, *, text=None, location=None, document=None, callback=None, sender_id=42):
    resource, trigger, owner, branch, _ = bot
    message = {'date': trigger.config['started_at'] + 1, 'chat': {'id': sender_id, 'type': 'private'}, 'from': {'id': sender_id, 'first_name': 'Customer', 'is_bot': False}}
    if text is not None:
        message['text'] = text
    if location:
        message['location'] = location
    if document:
        message['document'] = document
    update = {'update_id': update_id, 'message': message}
    if callback:
        update = {'update_id': update_id, 'callback_query': {'id': str(update_id), 'from': message['from'], 'message': message, 'data': callback}}
    with background_scope(db, owner, 'power_apps', 'create', branch_id=branch.id):
        result = accept_update(db, resource, trigger, owner, update)
    db.commit()
    return result


@pytest.mark.parametrize('lang', ['te', 'hi'])
def test_translated_human_menu_enters_real_handoff(db, bot, lang):
    deliver(db, bot, 1, text='/language ' + lang)
    deliver(db, bot, 2, text=telegram_dialogue.TEXT[lang]['human'])
    thread = db.query(TelegramConversation).one()
    assert thread.status in {'waiting', 'assigned'}
    assert thread.context['sla_waiting'] is True
    assert thread.assignee_user_id == bot[2].id


@pytest.mark.parametrize('lang,name,question', [('te', 'సాయి Alex', 'మీ పేరు'), ('hi', 'रवि Alex', 'आपका नाम')])
def test_basic_intake_uses_selected_language_and_preserves_name(db, bot, lang, name, question):
    deliver(db, bot, 1, text='/language ' + lang)
    deliver(db, bot, 2, text=telegram_dialogue.TEXT[lang]['sales'])
    assert question in db.query(TelegramMessage).filter_by(direction='outgoing').order_by(TelegramMessage.id.desc()).first().text
    deliver(db, bot, 3, text=name)
    assert db.query(TelegramConversation).one().state['name'] == name


def test_published_knowledge_has_server_approval_provenance_and_expiry(client, db, actors, bot):
    resource, trigger, owner, _, _ = bot
    config = publish(client, actors, resource, knowledge=[fact(approved_by_user_id=999)])
    assert config['revision'] == 1
    assert config['knowledge'][0]['approved_by_user_id'] == owner.id
    assert config['knowledge'][0]['approved_at']
    db.refresh(trigger)
    answer = knowledge_answer(trigger, 'public', 'What are your showroom opening hours?')
    assert '9 AM' in answer['reply'] and 'https://example.com/opening-hours' in answer['reply']
    assert 'Valid until:' in answer['reply'] and answer['source_ids'] == ['opening-hours']
    assert knowledge_answer(trigger, 'public', 'opening hours', now() + timedelta(days=31)) is None
    changed = {**config, 'knowledge': [fact(interface='company')]}
    assert client.put(f'{ROOT}/{resource.id}/experience', headers=actors[0], json=changed).status_code == 200
    db.refresh(trigger)
    assert knowledge_answer(trigger, 'public', 'opening hours') is None
    assert knowledge_answer(trigger, 'company', 'opening hours')
    assert client.put(f'{ROOT}/{resource.id}/experience', headers=actors[0], json=config).status_code == 409
    assert client.get(f'{ROOT}/{resource.id}/experience', headers=actors[1]).status_code == 404
    expired = {**changed, 'revision': 2, 'knowledge': [fact(expires_at=(now() - timedelta(days=1)).isoformat())]}
    assert client.put(f'{ROOT}/{resource.id}/experience', headers=actors[0], json=expired).status_code == 422


@pytest.mark.parametrize('lang,name,service,contact', [('en', 'Alex Customer', 'Dental cleaning', '2026-12-01 10:30 IST'), ('te', 'సాయి Customer', 'దంత సేవ Dental', '2026-12-01 ఉదయం 10:30'), ('hi', 'रवि Customer', 'दंत सेवा Dental', '2026-12-01 सुबह 10:30')])
def test_multilingual_qualification_preserves_values_and_creates_crm_records(client, db, actors, bot, lang, name, service, contact):
    resource, trigger, _, _, _ = bot
    flow = IndustryWorkflow(id='dental', name='Dental enquiry', industry='Dental', questions=[
        IntakeQuestion(key='full_name', label='Your name', translations={'te': 'మీ పేరు', 'hi': 'आपका नाम'}),
        IntakeQuestion(key='service', label='Required service', translations={'te': 'కావలసిన సేవ', 'hi': 'आवश्यक सेवा'}),
        IntakeQuestion(key='location', label='Your location', type='location'),
        IntakeQuestion(key='urgency', label='Urgency', type='choice', choices=['Routine', 'Emergency']),
        IntakeQuestion(key='budget', label='Budget', type='number', minimum=0),
        IntakeQuestion(key='preferred_contact_time', label='Preferred contact time'),
    ], urgency_rules=[UrgencyRule(field='urgency', value='Emergency', priority='Urgent', reason='Customer reported an emergency.')])
    publish(client, actors, resource, workflows=[flow], lead_workflow_id='dental')
    for ident, command in [(1, '/language ' + lang), (2, 'Sales'), (3, name), (4, service)]:
        deliver(db, bot, ident, text=command)
    deliver(db, bot, 5, location={'latitude': 17.385, 'longitude': 78.4867})
    for ident, command in [(6, 'Emergency'), (7, '₹1,250.50'), (8, contact)]:
        deliver(db, bot, ident, text=command)
    thread = db.query(TelegramConversation).one()
    assert thread.context['language'] == lang
    assert thread.state['answers']['full_name'] == name
    assert thread.state['answers']['service'] == service
    assert thread.state['answers']['budget'] == {'text': '₹1,250.50', 'value': '1250.50'}
    assert thread.state['answers']['preferred_contact_time'] == contact
    assert thread.context['qualification']['qualified'] is True
    assert thread.context['qualification']['priority'] == 'Urgent'
    assert 'Customer reported an emergency.' in thread.context['qualification']['reasons']
    assert db.query(CRMLead).one().full_name == name
    task = db.query(CRMTask).one()
    assert task.priority == 'High'
    assert task.task_details['telegram']['qualification']['priority'] == 'Urgent'
    deliver(db, bot, 9, text='/start')
    deliver(db, bot, 10, text='/memory')
    latest = db.query(TelegramMessage).filter_by(direction='outgoing').order_by(TelegramMessage.id.desc()).first()
    assert name in latest.text and contact in latest.text
    assert thread.context['requests'][0]['task_id'] == task.id
    deliver(db, bot, 11, text='/forget')
    assert 'memory' not in thread.context


def test_workflow_buttons_documents_and_revision_validation(client, db, actors, bot):
    resource, _, _, _, _ = bot
    flow = IndustryWorkflow(id='legal', name='Legal intake', industry='Legal', result='handoff', questions=[
        IntakeQuestion(key='document', label='Upload the agreement', type='document', accepted_mime_types=['application/pdf'])])
    config = publish(client, actors, resource, workflows=[flow])
    deliver(db, bot, 1, callback='wf:legal')
    deliver(db, bot, 2, text='I have no document')
    assert db.query(TelegramConversation).one().state['stage'] == 'workflow'
    deliver(db, bot, 3, document={'file_id': 'fixture-file', 'file_unique_id': 'fixture-unique', 'file_name': 'Agreement.pdf', 'mime_type': 'application/pdf', 'file_size': 100})
    thread = db.query(TelegramConversation).one()
    assert thread.state['answers']['document']['file_name'] == 'Agreement.pdf'
    assert thread.status == 'waiting' and thread.assignee_user_id
    assert thread.context['sla_due_at'] and thread.context['sla_waiting']
    assert db.query(CRMLead).count() == 0
    bad = {**config, 'workflows': [{**flow.model_dump(mode='json'), 'urgency_rules': [{'field': 'missing', 'operator': 'equals', 'value': 'yes', 'priority': 'High', 'reason': 'Bad reference'}]}]}
    assert client.put(f'{ROOT}/{resource.id}/experience', headers=actors[0], json=bad).status_code == 422


def test_sla_escalation_is_deduplicated_and_does_not_reset_on_more_messages(db, bot):
    resource, trigger, owner, _, receive = bot
    receive('/human')
    thread = db.query(TelegramConversation).one()
    due = thread.context['sla_due_at']
    receive('Still waiting')
    assert thread.context['sla_due_at'] == due
    instant = now() + timedelta(minutes=16)
    assert telegram_routing.tick(db, resource, trigger, instant) == 1
    db.commit()
    assert thread.context['sla_breached'] and thread.assignee_user_id == owner.id
    assert telegram_routing.tick(db, resource, trigger, instant) == 0
    telegram_routing.staff_responded(thread, owner.id, instant)
    assert not thread.context['sla_waiting']


def test_keyboard_is_bounded_and_does_not_accept_extra_capabilities():
    assert telegram_dialogue.validate_markup(json.dumps({'keyboard': [[{'text': 'Share location', 'request_location': True}]], 'resize_keyboard': True}))
    from app.apps.power_apps.integrations.contracts import IntegrationFailure
    with pytest.raises(IntegrationFailure):
        telegram_dialogue.validate_markup(json.dumps({'inline_keyboard': [[{'text': 'Unsafe', 'url': 'https://example.com'}]]}))
    with pytest.raises(ValidationError):
        IndustryWorkflow(id='invalid', name='Invalid', industry='Dental', questions=[IntakeQuestion(key='name', label='Name')], stages=[])
