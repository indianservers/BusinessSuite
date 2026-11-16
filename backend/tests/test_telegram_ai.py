import asyncio
import json
from types import SimpleNamespace
from datetime import timedelta

import pytest
from fastapi import HTTPException
from app.apps.power_apps import telegram_ai
from app.apps.power_apps.models import TelegramConversation, TelegramIdentity, TelegramMessage
from app.apps.power_apps.runtime_models import AutomationEvent as Event
from app.apps.power_apps.runtime import now
from app.models.user import Permission
from app.apps.crm.models import CRMLead, CRMTask
from app.ai_operator.suite_models import SuiteRun
from tests.test_power_runtime import db
from tests.test_power_apps import actors
from tests.test_telegram_operations import bot, ROOT


def ai_permission(db, owner):
    permission = db.query(Permission).filter_by(name='ai_assistant').first()
    if not permission:
        permission = Permission(name='ai_assistant', module='ai')
        db.add(permission)
    owner.role.permissions.append(permission)
    owner._suite_permission_objects = None
    db.commit()


def test_public_uses_existing_local_model_and_continues_crm_intake(client, db, bot, monkeypatch):
    resource, trigger, owner, branch, receive = bot
    ai_permission(db, owner)
    from app.ai_operator.local_nlp import Interpretation
    calls = []
    def parse(text, **kwargs):
        calls.append((text, kwargs))
        return Interpretation('CRM', 'tasks.create', 1)
    monkeypatch.setattr('app.ai_operator.local_nlp.parse', parse)
    receive('Please create a request for someone to call me back')
    assert db.query(Event).filter_by(kind='telegram_ai_request').count() == 1
    assert asyncio.run(telegram_ai.dispatch(db, client.app)) == 1
    thread = db.query(TelegramConversation).one()
    assert thread.state['stage'] == 'name' and thread.state['topic'] == 'Support'
    assert calls[0][1]['model_scope'] == {'company_id': 1, 'branch_id': branch.id, 'workspace_id': None}
    assert db.query(SuiteRun).count() == 0  # Public users never enter the privileged planner.
    receive('Alex Customer')
    receive('Call me tomorrow about an order')
    assert db.query(CRMTask).count() == 1
    assert asyncio.run(telegram_ai.dispatch(db, client.app)) == 0
    assert db.query(Event).filter_by(kind='telegram_ai_request').one().details['status'] == 'completed'


def test_company_calls_canonical_actionbot_but_cancels_internal_write(client, db, actors, bot):
    resource, _, owner, _, receive = bot
    ai_permission(db, owner)
    response = client.post(f'{ROOT}/{resource.id}/link-code', headers=actors[0], json={'interface': 'company'})
    assert response.status_code == 200, response.text
    receive(response.json()['command'], 77)
    receive('CRM: create a task titled Telegram agent follow-up', 77)
    asyncio.run(telegram_ai.dispatch(db, client.app))
    job = db.query(Event).filter_by(kind='telegram_ai_request').one()
    assert job.details['status'] == 'completed', job.details
    run = db.query(SuiteRun).one()
    assert run.user_id == owner.id and run.status in {'cancelled', 'needs_clarification'}
    assert db.query(CRMTask).count() == 0
    assert job.details['ai_run_id'] == run.id
    assert db.query(TelegramConversation).filter_by(interface='company').one().state['ai_conversation_id']


@pytest.mark.parametrize('selected_language', ['en', 'te', 'hi'])
def test_public_cloud_prompt_contains_only_public_context_and_own_chat(client, db, bot, monkeypatch, selected_language):
    resource, trigger, owner, _, receive = bot
    ai_permission(db, owner)
    trigger.config = {**trigger.config, 'ai': {'enabled': True, 'provider': 'openai', 'public_context': 'The showroom opens at 9 AM.'}}
    db.commit()
    monkeypatch.setattr('app.ai_operator.provider_scope.resolve_provider', lambda *args, **kwargs: SimpleNamespace(provider='openai', enabled=True, data_sharing_allowed=True, model='fixture-model'))
    from app.apps.power_apps.telegram_experience import ExperienceConfiguration, KnowledgeFact, save
    from tests.test_telegram_experience import fact
    save(db, resource, trigger, owner, ExperienceConfiguration(knowledge=[KnowledgeFact(**fact(title='Business hours policy'))]))
    db.commit()
    packets = []
    def generate(db, user, model, **kwargs):
        packets.append(json.loads(kwargs['prompt']))
        assert kwargs['output_type'] is telegram_ai.PublicAnswer
        return {'reply': 'The showroom opens at 9 AM.', 'topic': 'Answer', 'source_ids': ['opening-hours']}
    monkeypatch.setattr('app.ai_operator.providers.generate_json', generate)
    receive('This is a private question in a different chat', 99)
    receive('When does the showroom open?', 42)
    customer_thread = db.query(TelegramConversation).filter_by(telegram_id='42').one()
    customer_thread.context = {**(customer_thread.context or {}), 'language': selected_language}
    db.commit()
    asyncio.run(telegram_ai.dispatch(db, client.app))
    packet = next(packet for packet in packets if packet['customer_message'] == 'When does the showroom open?')
    assert packet['approved_public_information'] == 'The showroom opens at 9 AM.'
    assert 'different chat' not in json.dumps(packet)
    assert packet['response_language'] == selected_language
    assert 'Preserve names, dates, amounts and identifiers verbatim' in packet['instructions']
    assert set(packet) == {'channel', 'response_language', 'instructions', 'approved_public_information', 'history', 'customer_message', 'knowledge_sources'}
    assert db.query(SuiteRun).count() == 0


@pytest.mark.parametrize('cancel', ['/human', '/cancel'])
def test_ai_does_not_answer_after_handoff_or_new_control_message(client, db, bot, monkeypatch, cancel):
    _, _, _, _, receive = bot
    receive('Please explain your services')
    receive(cancel)
    monkeypatch.setattr(telegram_ai, 'public_answer', lambda *args: pytest.fail('A stale AI request must not reach a model'))
    asyncio.run(telegram_ai.dispatch(db, client.app))
    assert db.query(Event).filter_by(kind='telegram_ai_request').one().details['status'] == 'superseded'


def test_ai_failure_is_sanitized_and_handed_to_staff(client, db, bot, monkeypatch):
    _, _, _, _, receive = bot
    receive('Help me understand your services')
    def failure(*args):
        raise HTTPException(502, 'sensitive-provider-url-and-secret')
    monkeypatch.setattr(telegram_ai, 'public_answer', failure)
    asyncio.run(telegram_ai.dispatch(db, client.app))
    assert db.query(TelegramConversation).one().status == 'waiting'
    assert db.query(Event).filter_by(kind='telegram_ai_request').one().details['status'] == 'failed'
    assert all('sensitive-provider' not in json.dumps(event.details) for event in db.query(Event).all())
    assert all('sensitive-provider' not in message.text for message in db.query(TelegramMessage).all())


def test_ai_config_controls_and_duplicate_updates(client, db, actors, bot):
    resource, _, owner, _, receive = bot
    ai_permission(db, owner)
    route = f'{ROOT}/{resource.id}/ai-configuration'
    response = client.get(route, headers=actors[0])
    assert response.status_code == 200, response.text
    assert response.json()['engine'] == 'actionbot'
    assert 'active' in response.json()['local_model']
    receive('A natural-language enquiry', update_id=10)
    receive('A natural-language enquiry', update_id=10)
    assert db.query(Event).filter_by(kind='telegram_ai_request').count() == 1
    saved = client.put(route, headers=actors[0], json={'enabled': False, 'provider': 'local', 'public_context': ''})
    assert saved.status_code == 200, saved.text
    assert client.put(route, headers=actors[1], json={'enabled': False}).status_code == 404
    asyncio.run(telegram_ai.dispatch(db, client.app))
    assert db.query(Event).filter_by(kind='telegram_ai_request').one().details['status'] == 'superseded'


def test_company_model_uses_distinct_employees_ai_identity(client, db, actors, bot):
    from datetime import date
    from app.models.user import User
    from app.models.employee import Employee
    from app.access.models import AccessPolicy
    from app.access.service import background_scope
    resource, _, owner, branch, receive = bot
    ai_permission(db, owner)
    staff = db.query(User).filter_by(email='power-3@example.com').one()
    policy = db.query(AccessPolicy).filter_by(user_id=staff.id, company_id=1).one()
    policy.grants = {**policy.grants,
        'ai': {'enabled': True, 'permissions': ['ai_assistant'], 'actions': ['view', 'create'], 'scope': 'own', 'role': 'contributor'},
        'crm': {'enabled': True, 'permissions': ['crm_manage'], 'actions': ['view', 'create', 'edit'], 'scope': 'own', 'role': 'contributor'}}
    employee = Employee(employee_id='TG-AI-EMP', first_name='AI', last_name='Employee', user_id=staff.id, branch_id=branch.id, date_of_joining=date(2020, 1, 1), status='Active')
    with background_scope(db, owner, 'power_apps', 'create', branch_id=branch.id):
        db.add(employee); db.commit()
    response = client.post(f'{ROOT}/{resource.id}/employee-links', headers=actors[0], json={'employee_id': employee.id, 'telegram_user_id': '123'})
    assert response.status_code == 201, response.text
    receive('/start', 123)
    receive('CRM: create a task titled Employee AI follow-up', 123)
    asyncio.run(telegram_ai.dispatch(db, client.app))
    job = db.query(Event).filter_by(kind='telegram_ai_request').one()
    assert job.details['status'] == 'completed', job.details
    assert db.query(SuiteRun).one().user_id == staff.id
    assert db.query(CRMTask).count() == 0
