import hashlib
import json
from datetime import date, timedelta
from urllib.parse import unquote

import pytest
from app.apps.power_apps.models import PowerResource, TelegramIdentity, TelegramConversation, TelegramMessage, TelegramLinkChallenge
from app.apps.power_apps.runtime_models import AutomationTrigger as Trigger, AutomationEvent
from app.apps.power_apps.telegram import accept_update
from app.apps.power_apps.integrations import adapters
from app.apps.power_apps.integrations.transport import Response
from app.apps.power_apps.runtime import now
from app.access.service import background_scope
from app.models.user import User, Permission
from app.models.employee import Employee
from app.models.company import Branch
from app.apps.crm.models import CRMLead, CRMTask
from tests.test_power_runtime import db
from tests.test_power_apps import actors

ROOT = '/api/v1/power-apps/automations/telegram'


@pytest.fixture
def bot(client, db, actors, monkeypatch):
    owner = db.query(User).filter_by(email='power-0@example.com').one()
    for name, module in [('crm_manage', 'crm'), ('employee_update', 'hrms'), ('employee_view', 'hrms')]:
        permission = db.query(Permission).filter_by(name=name).first()
        if not permission:
            permission = Permission(name=name, module=module)
            db.add(permission)
        owner.role.permissions.append(permission)
    db.commit()

    class Transport:
        def __init__(self, policy):
            pass
        def request(self, method, url, **kwargs):
            method = unquote(url).rsplit('/', 1)[-1]
            result = {'id': 7123, 'username': 'operations_fixture_bot'} if method == 'getMe' else {'url': ''}
            return Response(200, {}, json.dumps({'ok': True, 'result': result}).encode(), 1)
    monkeypatch.setattr(adapters, 'HTTP_FACTORY', Transport)
    response = client.post(ROOT + '/setup', headers=actors[0], json={'token': '7123:fixture_only'})
    assert response.status_code == 201, response.text
    resource = db.get(PowerResource, response.json()['resource_id'])
    trigger = db.query(Trigger).filter_by(resource_id=resource.id, kind='telegram').one()
    branch = db.get(Branch, trigger.config['branch_id']) if trigger.config.get('branch_id') else db.query(Branch).filter_by(company_id=1).first()
    from app.branches.models import BranchOwnership
    for candidate in db.query(Branch).filter_by(company_id=1).all():
        if not db.query(BranchOwnership).filter_by(resource_table='branches', resource_key=str(candidate.id)).first():
            db.add(BranchOwnership(company_id=1, branch_id=candidate.id, resource_table='branches', resource_key=str(candidate.id), source='telegram-test-fixture'))
    db.flush()
    # Existing shared-bot regressions intentionally exercise the legacy mode;
    # newly created production bots now default to a dedicated public audience.
    trigger.config = {**trigger.config, 'audience': 'shared', 'branch_id': branch.id, 'interfaces': {'public_enabled': True, 'company_enabled': True, 'create_crm_records': True}}
    db.commit()
    owner.organization_id = 1
    counter = [0]

    def receive(text, sender_id=42, update_id=None):
        counter[0] += 1
        update = {'update_id': update_id or counter[0], 'message': {'date': trigger.config['started_at'] + 1,
            'chat': {'id': sender_id, 'type': 'private'}, 'from': {'id': sender_id, 'first_name': 'Alex', 'is_bot': False}, 'text': text}}
        with background_scope(db, owner, 'power_apps', 'create', branch_id=branch.id):
            result = accept_update(db, resource, trigger, owner, update)
        db.commit()
        return result
    return resource, trigger, owner, branch, receive


def test_public_sales_creates_native_lead_and_task_once(db, bot):
    resource, _, _, branch, receive = bot
    for text in ['/public', 'Sales', 'Alex Customer', 'Need ten units']:
        receive(text)
    lead = db.query(CRMLead).filter_by(source='Telegram').one()
    task = db.query(CRMTask).filter_by(lead_id=lead.id).one()
    assert lead.full_name == 'Alex Customer' and lead.organization_id == 1 and lead.branch_id == branch.id
    assert task.description == 'Need ten units'
    identity = db.query(TelegramIdentity).filter_by(resource_id=resource.id, interface='public').one()
    assert identity.lead_id == lead.id and identity.verified_at is None
    receive('Need ten units', update_id=4)
    assert db.query(CRMLead).count() == 1 and db.query(CRMTask).count() == 1
    for text in ['Sales', 'Alex Customer', 'Another enquiry']:
        receive(text)
    assert db.query(CRMLead).count() == 1 and db.query(CRMTask).count() == 2


def test_linked_employee_auto_authorization_and_revocation(client, db, actors, bot):
    resource, _, owner, branch, receive = bot
    employee = Employee(employee_id='TG-EMP-1', first_name='Staff', last_name='Member', user_id=owner.id,
        branch_id=branch.id, date_of_joining=date(2020, 1, 1), status='Active')
    with background_scope(db, owner, 'power_apps', 'create', branch_id=branch.id):
        db.add(employee)
        db.commit()
    receive('/id', 77)
    response = client.post(f'{ROOT}/{resource.id}/employee-links', headers=actors[0], json={'employee_id': employee.id, 'telegram_user_id': '77'})
    assert response.status_code == 201, response.text
    receive('/start', 77)
    for text in ['Create task', 'Prepare the customer quotation']:
        receive(text, 77)
    task = db.query(CRMTask).one()
    assert task.created_by_user_id == owner.id
    thread = db.query(TelegramConversation).filter_by(interface='company').one()
    assert thread.task_id == task.id
    receive('/human', 77)
    route = f'{ROOT}/{resource.id}/conversations/{thread.id}'
    assert client.put(route, headers=actors[0], json={'action': 'claim'}).status_code == 200
    queued = client.post(route + '/reply', headers=actors[0], json={'text': 'We will arrange the equipment.', 'client_key': 'company-reply-key-123'})
    assert queued.status_code == 202, queued.text
    from app.apps.power_apps.runtime_models import AutomationRun
    from app.apps.power_apps.telegram_operations import authorize_delivery
    from fastapi import HTTPException
    run = db.get(AutomationRun, queued.json()['run_id'])
    authorize_delivery(db, run, {'chat_id': '77'}, resource_id=resource.id)
    employee.status = 'Suspended'
    db.commit()
    with pytest.raises(HTTPException):
        authorize_delivery(db, run, {'chat_id': '77'}, resource_id=resource.id)
    receive('Create task', 77)
    assert db.query(CRMTask).count() == 1
    assert 'Link your signed-in' in db.query(TelegramMessage).filter_by(direction='outgoing').order_by(TelegramMessage.id.desc()).first().text
    employee.status = 'Active'
    db.commit()
    assert client.delete(f'{ROOT}/{resource.id}/identities/{response.json()["identity_id"]}', headers=actors[0]).status_code == 200
    receive('/company', 77)
    assert db.query(CRMTask).count() == 1


def test_link_codes_are_hashed_expiring_single_use_and_redacted(client, db, actors, bot):
    resource, _, _, _, receive = bot
    response = client.post(f'{ROOT}/{resource.id}/link-code', headers=actors[0], json={'interface': 'company'})
    assert response.status_code == 200, response.text
    command = response.json()['command']
    token = command.split()[1]
    challenge = db.query(TelegramLinkChallenge).one()
    assert challenge.token_hash == hashlib.sha256(token.encode()).hexdigest()
    receive(command, 88)
    assert db.query(TelegramIdentity).filter_by(interface='company', telegram_id='88').one().verified_at
    assert all(token not in message.text for message in db.query(TelegramMessage).all())
    assert all(token not in json.dumps(event.details) for event in db.query(AutomationEvent).all())
    receive(command, 99)
    assert db.query(TelegramIdentity).filter_by(interface='company', telegram_id='99').first() is None
    response = client.post(f'{ROOT}/{resource.id}/link-code', headers=actors[0], json={'interface': 'company'})
    challenge = db.query(TelegramLinkChallenge).order_by(TelegramLinkChallenge.id.desc()).first()
    challenge.expires_at = now() - timedelta(minutes=1)
    db.commit()
    receive(response.json()['command'], 99)
    assert db.query(TelegramIdentity).filter_by(interface='company', telegram_id='99').first() is None


def test_handoff_pauses_bot_claim_reply_idempotency_and_resume(client, db, actors, bot):
    resource, _, owner, _, receive = bot
    receive('/human')
    thread = db.query(TelegramConversation).one()
    assert thread.status == 'waiting'
    before = db.query(TelegramMessage).filter_by(direction='outgoing').count()
    receive('Can someone help with my order?')
    assert db.query(TelegramMessage).filter_by(direction='outgoing').count() == before
    route = f'{ROOT}/{resource.id}/conversations/{thread.id}'
    assert client.post(route + '/reply', headers=actors[0], json={'text': 'Hello', 'client_key': 'fixture-reply-key-123'}).status_code == 409
    response = client.put(route, headers=actors[0], json={'action': 'claim'})
    assert response.status_code == 200, response.text
    payload = {'text': 'A person is helping you now.', 'client_key': 'fixture-reply-key-123'}
    response = client.post(route + '/reply', headers=actors[0], json=payload)
    assert response.status_code == 202, response.text
    duplicate = client.post(route + '/reply', headers=actors[0], json=payload)
    assert duplicate.status_code == 202 and duplicate.json()['run_id'] == response.json()['run_id']
    assert db.query(TelegramMessage).filter_by(client_key=payload['client_key']).count() == 1
    assert client.get(f'{ROOT}/{resource.id}/operations', headers=actors[1]).status_code == 404
    assert client.put(route, headers=actors[0], json={'action': 'resume'}).status_code == 200
    receive('/start')
    assert db.query(TelegramMessage).filter_by(direction='outgoing').count() == before + 2


def test_public_customer_link_and_company_permissions_remain_separate(client, db, actors, bot):
    resource, _, owner, branch, receive = bot
    lead = CRMLead(organization_id=1, branch_id=branch.id, first_name='Known', full_name='Known Customer', owner_user_id=owner.id, created_by_user_id=owner.id)
    with background_scope(db, owner, 'power_apps', 'create', branch_id=branch.id):
        db.add(lead)
        db.commit()
    response = client.post(f'{ROOT}/{resource.id}/link-code', headers=actors[0], json={'interface': 'public', 'lead_id': lead.id})
    assert response.status_code == 200, response.text
    receive(response.json()['command'])
    linked = db.query(TelegramIdentity).filter_by(interface='public', telegram_id='42').one()
    assert linked.lead_id == lead.id and linked.verified_at
    receive('/company')
    assert db.query(TelegramConversation).filter_by(interface='company').count() == 0
    for text in ['/public', 'Support', 'Known Customer', 'Need help']:
        receive(text)
    assert db.query(CRMTask).filter_by(lead_id=lead.id).count() == 1
    assert db.query(CRMTask).count() == 1
    response = client.delete(f'{ROOT}/{resource.id}/identities/{linked.id}', headers=actors[0])
    assert response.status_code == 200
    receive('/public')
    db.refresh(linked)
    assert linked.verified_at is None and linked.lead_id is None


def test_missing_crm_permission_creates_handoff_without_partial_records(db, bot):
    _, _, owner, _, receive = bot
    owner.role.permissions = [permission for permission in owner.role.permissions if permission.module != 'crm']
    owner._suite_permission_objects = None
    db.commit()
    for text in ['/public', 'Sales', 'Alex', 'Need a quotation']:
        receive(text)
    assert db.query(CRMLead).count() == 0 and db.query(CRMTask).count() == 0
    thread = db.query(TelegramConversation).one()
    assert thread.status == 'waiting' and thread.state['crm_error'] is True


def test_delivery_rechecks_handoff_and_employee_authorization(db, bot):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from app.apps.power_apps.telegram_operations import authorize_delivery
    resource, _, _, _, receive = bot
    receive('/public')
    thread = db.query(TelegramConversation).one()
    run = SimpleNamespace(resource_id=resource.id, organization_id=1, environment='development', input_payload={'telegram_conversation_id': thread.id})
    authorize_delivery(db, run, {'chat_id': '42'})
    receive('/human')
    with pytest.raises(HTTPException):
        authorize_delivery(db, run, {'chat_id': '42'})
    run.input_payload['telegram_handoff_notice'] = True
    authorize_delivery(db, run, {'chat_id': '42'})
    with pytest.raises(HTTPException):
        authorize_delivery(db, run, {'chat_id': '99'})


def test_employee_actions_use_employee_permissions_and_owner_independent_identity(client, db, actors, bot):
    from app.access.models import AccessPolicy
    resource, _, owner, branch, receive = bot
    staff = db.query(User).filter_by(email='power-3@example.com').one()
    policy = db.query(AccessPolicy).filter_by(user_id=staff.id, company_id=1).one()
    policy.grants = {**policy.grants, 'crm': {'enabled': True, 'permissions': ['crm_manage'], 'actions': ['view', 'create', 'edit'], 'scope': 'own', 'role': 'contributor'}}
    employee = Employee(employee_id='TG-STAFF-2', first_name='Another', last_name='Employee', user_id=staff.id,
        branch_id=branch.id, date_of_joining=date(2020, 1, 1), status='Active')
    with background_scope(db, owner, 'power_apps', 'create', branch_id=branch.id):
        db.add(employee)
        db.commit()
    response = client.post(f'{ROOT}/{resource.id}/employee-links', headers=actors[0], json={'employee_id': employee.id, 'telegram_user_id': '123'})
    assert response.status_code == 201, response.text
    for text in ['/company', 'Create task', 'An employee-owned task']:
        receive(text, 123)
    task = db.query(CRMTask).one()
    assert task.owner_user_id == staff.id and task.created_by_user_id == staff.id
    policy.grants = {**policy.grants, 'crm': {**policy.grants['crm'], 'enabled': False}}
    db.commit()
    for text in ['Create task', 'Must not inherit owner CRM permissions']:
        receive(text, 123)
    assert db.query(CRMTask).count() == 1
    assert db.query(TelegramConversation).filter_by(interface='company').one().status == 'waiting'


def test_task_failure_rolls_back_new_lead_in_same_transaction(db, bot):
    _, _, owner, _, receive = bot
    owner.role.permissions = [permission for permission in owner.role.permissions if permission.module != 'crm']
    permission = db.query(Permission).filter_by(name='crm_leads_manage').first()
    if not permission:
        permission = Permission(name='crm_leads_manage', module='crm')
        db.add(permission)
    owner.role.permissions.append(permission)
    owner._suite_permission_objects = None
    db.commit()
    for text in ['/public', 'Sales', 'Customer', 'Lead creation succeeds but task creation is denied']:
        receive(text)
    assert db.query(CRMLead).count() == 0 and db.query(CRMTask).count() == 0
    assert db.query(TelegramConversation).one().status == 'waiting'
