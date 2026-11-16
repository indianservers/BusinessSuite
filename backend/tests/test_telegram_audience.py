import asyncio
import json
from datetime import date
from urllib.parse import unquote

import pytest
from fastapi import HTTPException

from app.apps.crm.models import CRMLead, CRMTask
from app.apps.power_apps.models import TelegramConversation, TelegramIdentity, TelegramMessage, TelegramLinkChallenge
from app.apps.power_apps.runtime_models import AutomationRun, AutomationEvent
from app.apps.power_apps import telegram_ai, telegram_approvals, telegram_audience
from app.apps.power_apps.telegram_operations import authorize_delivery
from app.apps.power_apps.integrations.transport import Response
from app.ai_operator.suite_models import SuiteRun
from tests.test_power_runtime import db
from tests.test_power_apps import actors
from tests.test_telegram_operations import bot, ROOT
from tests.test_telegram_action_approvals import proposed
from tests.test_telegram_experience import deliver
from tests.test_telegram_ai import ai_permission
from tests.test_telegram_customer_privacy import customer_link


def set_purpose(db, bot, selected):
    trigger = bot[1]
    trigger.config = {**trigger.config, 'audience': selected,
        'interfaces': {**trigger.config.get('interfaces', {}), 'public_enabled': selected != 'company', 'company_enabled': selected != 'public'}}
    db.commit()


def test_new_setup_is_public_company_needs_own_token_and_same_bot_cannot_listen_twice(client, db, actors, monkeypatch):
    calls = []

    class Transport:
        def __init__(self, policy):
            pass

        def request(self, method, url, **kwargs):
            calls.append(unquote(url).rsplit('/', 1)[-1])
            bot_id = 88003 if '88003' in url else 88001
            result = {'id': bot_id, 'username': 'dedicated_fixture_bot'} if calls[-1] == 'getMe' else {'url': ''}
            return Response(200, {}, json.dumps({'ok': True, 'result': result}).encode(), 1)

    monkeypatch.setattr('app.apps.power_apps.integrations.adapters.HTTP_FACTORY', Transport)
    missing = client.post(ROOT + '/setup', headers=actors[0], json={'audience': 'company'})
    assert missing.status_code == 422 and not calls
    monkeypatch.setattr('app.apps.power_apps.telegram_api.DEFAULT_BOT_TOKEN', '88002:public_bootstrap_fixture')
    same_bootstrap = client.post(ROOT + '/setup', headers=actors[0], json={'audience': 'company', 'token': '88002:public_bootstrap_fixture'})
    assert same_bootstrap.status_code == 422 and not calls
    created = client.post(ROOT + '/setup', headers=actors[0], json={'token': '88001:fixture_only'})
    assert created.status_code == 201 and created.json()['audience'] == 'public'
    listing = client.get(ROOT + '/bots', headers=actors[0]).json()['items'][0]
    assert listing['configuration']['audience'] == 'public'
    assert not listing['configuration']['company_enabled']
    duplicate = client.post(ROOT + '/setup', headers=actors[0], json={'audience': 'company', 'token': '88001:fixture_only'})
    assert duplicate.status_code == 409
    company = client.post(ROOT + '/setup', headers=actors[0], json={'audience': 'company', 'token': '88003:separate_employee_fixture'})
    assert company.status_code == 201 and company.json()['audience'] == 'company'
    company_listing = next(item for item in client.get(ROOT + '/bots', headers=actors[0]).json()['items'] if item['resource_id'] == company.json()['resource_id'])
    assert company_listing['configuration']['company_enabled'] and not company_listing['configuration']['public_enabled']
    company_id = company.json()['resource_id']
    assert client.put(f'{ROOT}/{company_id}/configuration', headers=actors[0], json={'audience': 'company'}).status_code == 200
    assert client.put(f'{ROOT}/{company_id}/configuration', headers=actors[0], json={'audience': 'public'}).status_code == 200
    assert client.put(f'{ROOT}/{company_id}/configuration', headers=actors[0], json={'audience': 'company'}).status_code == 200


def test_public_bot_does_not_elevate_existing_employee_and_hides_company_history(client, db, actors, bot):
    resource, _, owner, _, receive = bot
    code = client.post(f'{ROOT}/{resource.id}/link-code', headers=actors[0], json={'interface': 'company'}).json()['command']
    receive(code, 77)
    company_thread = db.query(TelegramConversation).filter_by(interface='company').one()
    company_thread.context = {'memory': {'name': 'Private employee memory'}}
    company_thread.status, company_thread.assignee_user_id = 'assigned', owner.id
    db.commit()
    unused_code = client.post(f'{ROOT}/{resource.id}/link-code', headers=actors[0], json={'interface': 'company'}).json()['command']
    old_reply = db.query(TelegramMessage).filter_by(conversation_id=company_thread.id, direction='outgoing').one()
    set_purpose(db, bot, 'public')  # Also exercise current-purpose checks without cleanup.
    for command in ['/start', '/company', '/memory', unused_code]:
        receive(command, 77)
    assert db.query(TelegramConversation).filter_by(interface='company').count() == 1
    public_thread = db.query(TelegramConversation).filter_by(interface='public').one()
    assert public_thread.identity_id != company_thread.identity_id
    replies = db.query(TelegramMessage).filter_by(conversation_id=public_thread.id, direction='outgoing').all()
    assert all('Private employee memory' not in reply.text for reply in replies)
    assert any(reply.text == telegram_audience.PUBLIC_NOTICE for reply in replies)
    assert db.query(TelegramLinkChallenge).filter_by(interface='company', consumed_at=None).count() == 1
    assert client.get(f'{ROOT}/{resource.id}/employee-options', headers=actors[0]).status_code == 403
    assert client.post(f'{ROOT}/{resource.id}/link-code', headers=actors[0], json={'interface': 'company'}).status_code == 403
    operations = client.get(f'{ROOT}/{resource.id}/operations', headers=actors[0]).json()
    assert operations['audience'] == 'public'
    assert all(thread['interface'] == 'public' for thread in operations['conversations'])
    assert 'Private employee memory' not in json.dumps(operations)
    assert client.post(f'{ROOT}/{resource.id}/conversations/{company_thread.id}/reply', headers=actors[0],
        json={'text': 'Old company reply', 'client_key': 'old-company-staff-reply'}).status_code == 403
    assert client.post(f'{ROOT}/{resource.id}/conversations/{company_thread.id}/draft', headers=actors[0]).status_code == 403
    with pytest.raises(HTTPException):
        authorize_delivery(db, db.get(AutomationRun, old_reply.run_id), {'chat_id': '77'}, resource_id=resource.id)


def test_company_bot_unknown_user_gets_only_verification_and_id_without_public_intake(client, db, actors, bot):
    resource, _, _, _, receive = bot
    set_purpose(db, bot, 'company')
    for text in ['/start', '/public', 'Sales', 'Customer Name', 'Need a quotation', '/human', '/memory', '/orders', '/id']:
        receive(text, 42)
    assert db.query(TelegramIdentity).count() == 0
    thread = db.query(TelegramConversation).one()
    assert thread.interface == 'company' and not thread.identity_id and not thread.context
    assert db.query(CRMTask).count() == db.query(CRMLead).count() == 0
    assert db.query(AutomationEvent).filter_by(kind='telegram_ai_request').count() == 0
    replies = db.query(TelegramMessage).filter_by(direction='outgoing').all()
    assert len(replies) == 9
    for reply in replies:
        run = db.get(AutomationRun, reply.run_id)
        assert run.input_payload['telegram_verification_notice'] is True
        authorize_delivery(db, run, {'chat_id': '42', 'text': reply.text}, resource_id=resource.id)
    # A caller cannot use the notice marker to deliver an arbitrary private reply.
    with pytest.raises(HTTPException):
        authorize_delivery(db, db.get(AutomationRun, replies[-1].run_id), {'chat_id': '42', 'text': 'Private CRM result'}, resource_id=resource.id)
    assert client.post(f'{ROOT}/{resource.id}/link-code', headers=actors[0], json={'interface': 'public', 'customer_id': 1}).status_code == 403


def test_company_bot_verified_employee_stays_company_and_has_employee_menu(client, db, actors, bot):
    resource, trigger, _, _, receive = bot
    set_purpose(db, bot, 'company')
    response = client.post(f'{ROOT}/{resource.id}/link-code', headers=actors[0], json={'interface': 'company'})
    assert response.status_code == 200
    receive(response.json()['command'], 77)
    receive('/start', 77)
    menu_run = db.get(AutomationRun, db.query(TelegramMessage).filter_by(direction='outgoing').order_by(TelegramMessage.id.desc()).first().run_id)
    markup = json.loads(menu_run.input_payload['reply_markup_json'])
    callbacks = {item.get('callback_data') for row in markup['inline_keyboard'] for item in row}
    assert {'menu:lead', 'menu:task', 'menu:internal'} <= callbacks
    assert not {'menu:support', 'menu:order'} & callbacks
    receive('/public', 77)
    receive('/orders', 77)
    receive('Internal request', 77)
    receive('Need employee equipment', 77)
    assert db.query(TelegramConversation).one().interface == 'company'
    assert db.query(TelegramIdentity).filter_by(interface='public').count() == 0
    assert db.query(CRMTask).one().description == 'Need employee equipment'


def test_configuration_preserves_dedicated_audience_and_closes_legacy_incompatible_context(client, db, actors, bot):
    resource, trigger, _, _, receive = bot
    code = client.post(f'{ROOT}/{resource.id}/link-code', headers=actors[0], json={'interface': 'company'}).json()['command']
    other_code = client.post(f'{ROOT}/{resource.id}/link-code', headers=actors[0], json={'interface': 'company'}).json()['command']
    receive(other_code, 77)
    receive('Private employee request', 77)
    promoted = client.put(f'{ROOT}/{resource.id}/configuration', headers=actors[0], json={'audience': 'company'})
    assert promoted.status_code == 422
    assert telegram_audience.audience(trigger) == 'shared'
    assert db.query(TelegramIdentity).filter_by(interface='company', revoked_at=None).count() == 1
    changed = client.put(f'{ROOT}/{resource.id}/configuration', headers=actors[0], json={'audience': 'public'})
    assert changed.status_code == 200 and changed.json()['configuration']['audience'] == 'public'
    assert db.query(TelegramIdentity).filter_by(interface='company', revoked_at=None).count() == 0
    assert db.query(TelegramLinkChallenge).filter_by(interface='company', consumed_at=None).count() == 0
    assert not db.query(TelegramConversation).filter_by(interface='company').one().context
    saved = client.put(f'{ROOT}/{resource.id}/configuration', headers=actors[0], json={'public_welcome': 'Public only'})
    assert saved.status_code == 200 and saved.json()['configuration']['audience'] == 'public'
    assert not saved.json()['configuration']['company_enabled']
    assert client.put(f'{ROOT}/{resource.id}/configuration', headers=actors[0], json={'audience': 'company'}).status_code == 422
    assert telegram_audience.audience(trigger) == 'public'
    assert client.put(f'{ROOT}/{resource.id}/configuration', headers=actors[0], json={'audience': 'shared'}).status_code == 422
    receive(code, 88)
    assert not db.query(TelegramIdentity).filter_by(interface='company', revoked_at=None).count()


def test_queued_company_ai_is_superseded_after_purpose_change(client, db, actors, bot, monkeypatch):
    resource, _, owner, _, receive = bot
    ai_permission(db, owner)
    response = client.post(f'{ROOT}/{resource.id}/link-code', headers=actors[0], json={'interface': 'company'})
    receive(response.json()['command'], 77)
    receive('Create a CRM task called "Do not execute old bot request"', 77)
    set_purpose(db, bot, 'public')
    monkeypatch.setattr(telegram_ai, 'company_answer', lambda *args: pytest.fail('Wrong audience reached the employee model'))
    asyncio.run(telegram_ai.dispatch(db, client.app))
    assert db.query(AutomationEvent).filter_by(kind='telegram_ai_request').one().details['status'] == 'superseded'
    assert db.query(SuiteRun).count() == db.query(CRMTask).count() == 0


def test_queued_approved_company_origin_cannot_execute_after_bot_becomes_public(client, db, actors, bot, proposed):
    _, _, run, button = proposed
    deliver(db, bot, 3, callback=button, sender_id=77)
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    assert run.status == 'cancelled'
    set_purpose(db, bot, 'public')
    deliver(db, bot, 4, callback=button, sender_id=77)
    assert db.query(TelegramMessage).filter_by(direction='outgoing').order_by(TelegramMessage.id.desc()).first().text == 'This action review is unavailable'
    from app.ai_operator.suite import process_suite_batch
    asyncio.run(process_suite_batch(db, client.app, telegram_only=True))
    db.refresh(run)
    assert run.status == 'cancelled'
    assert db.query(CRMTask).count() == 0


def test_public_routing_options_use_authorized_erp_roster_without_employee_bot_link(client, db, actors, bot):
    from app.models.employee import Employee
    from app.access.service import background_scope
    resource, _, owner, branch, _ = bot
    set_purpose(db, bot, 'public')
    employee = Employee(employee_id='TG-PUBLIC-ROSTER', first_name='Routing', last_name='Employee',
        user_id=owner.id, branch_id=branch.id, date_of_joining=date(2020, 1, 1), status='Active')
    with background_scope(db, owner, 'power_apps', 'create', branch_id=branch.id):
        db.add(employee)
        db.commit()
    assert db.query(TelegramIdentity).count() == 0
    options = client.get(f'{ROOT}/{resource.id}/experience-options', headers=actors[0])
    assert options.status_code == 200
    assert any(item['id'] == employee.id for item in options.json()['employees'])
    assert client.get(f'{ROOT}/{resource.id}/employee-options', headers=actors[0]).status_code == 403


def test_old_public_customer_link_outbox_and_ai_cannot_cross_to_company_bot(client, db, actors, bot, customer_link, monkeypatch):
    from app.apps.power_apps.telegram_operations import queue_reply
    from app.access.service import background_scope
    resource, trigger, owner, branch, receive = bot
    customer, linked = customer_link
    thread = db.query(TelegramConversation).filter_by(interface='public').one()
    response = client.post(f'{ROOT}/{resource.id}/link-code', headers=actors[0],
        json={'interface': 'public', 'customer_id': customer.id})
    assert response.status_code == 200
    with background_scope(db, owner, 'power_apps', 'create', branch_id=branch.id):
        run_id = queue_reply(db, resource, trigger, owner, thread, 'Private customer request',
            'public-outbox-before-company', private_identity=linked, private_command='/myrequests')
        db.commit()
    receive('What services do you offer?')
    set_purpose(db, bot, 'company')
    receive(response.json()['command'])
    assert db.query(TelegramIdentity).filter_by(interface='company').count() == 0
    assert db.query(TelegramLinkChallenge).filter_by(interface='public', consumed_at=None).count() == 1
    monkeypatch.setattr(telegram_ai, 'public_answer', lambda *args: pytest.fail('Company bot reached customer AI'))
    asyncio.run(telegram_ai.dispatch(db, client.app))
    assert db.query(AutomationEvent).filter_by(kind='telegram_ai_request').one().details['status'] == 'superseded'
    with pytest.raises(HTTPException):
        authorize_delivery(db, db.get(AutomationRun, run_id), {'chat_id': '42'}, resource_id=resource.id)
    operations = client.get(f'{ROOT}/{resource.id}/operations', headers=actors[0]).json()
    assert all(item['interface'] == 'company' for item in operations['conversations'])
    assert 'Private customer request' not in json.dumps(operations)


def test_workflow_menu_never_exposes_company_flow_on_public_bot(db, bot):
    from app.apps.power_apps.telegram_dialogue import menu
    resource, trigger, _, _, _ = bot
    set_purpose(db, bot, 'public')
    trigger.config = {**trigger.config, 'experience': {'workflows': [
        {'id': 'employee-only', 'name': 'Private employee process', 'interface': 'company', 'industry': 'General', 'questions': [{'key': 'request', 'label': 'Request'}]},
        {'id': 'customer-only', 'name': 'Customer request', 'interface': 'public', 'industry': 'General', 'questions': [{'key': 'request', 'label': 'Request'}]}]}}
    value = json.dumps(menu(trigger, 'public', 'en'))
    assert 'customer-only' in value and 'employee-only' not in value
    with pytest.raises(HTTPException):
        menu(trigger, 'company', 'en')
