from datetime import timedelta

import pytest
from fastapi import HTTPException
from app.access.service import background_scope
from app.models.user import Permission
from app.apps.crm.models import CRMCompany, CRMTask
from app.apps.power_apps.models import TelegramConversation, TelegramIdentity, TelegramMessage
from app.apps.power_apps.runtime_models import AutomationRun
from app.apps.power_apps.runtime import now
from app.apps.power_apps.telegram_operations import authorize_delivery, queue_reply
from tests.test_power_runtime import db
from tests.test_power_apps import actors
from tests.test_telegram_operations import bot, ROOT


@pytest.fixture
def customer_link(client, db, actors, bot):
    resource, _, owner, branch, receive = bot
    with background_scope(db, owner, 'power_apps', 'create', branch_id=branch.id):
        customer = CRMCompany(organization_id=1, branch_id=branch.id, name='Verified customer',
            owner_user_id=owner.id, created_by_user_id=owner.id)
        db.add(customer); db.commit()
    response = client.post(f'{ROOT}/{resource.id}/link-code', headers=actors[0],
        json={'interface': 'public', 'customer_id': customer.id})
    assert response.status_code == 200, response.text
    receive(response.json()['command'])
    linked = db.query(TelegramIdentity).filter_by(interface='public', telegram_id='42').one()
    return customer, linked


@pytest.mark.parametrize('change', ['revoked', 'reverified', 'different_target'])
def test_queued_private_reply_requires_unchanged_customer_verification(db, bot, customer_link, change):
    resource, trigger, owner, branch, _ = bot
    _, linked = customer_link
    thread = db.query(TelegramConversation).one()
    with background_scope(db, owner, 'power_apps', 'create', branch_id=branch.id):
        run_id = queue_reply(db, resource, trigger, owner, thread, 'Private order total: INR 500',
            'customer-private-fixture', private_identity=linked, private_command='/myrequests')
        db.commit()
    run = db.get(AutomationRun, run_id)
    authorize_delivery(db, run, {'chat_id': '42'}, resource_id=resource.id)
    if change == 'revoked':
        linked.revoked_at = now()
    elif change == 'reverified':
        linked.verified_at = now() + timedelta(seconds=1)
    else:
        linked.customer_id = None
    db.commit()
    with pytest.raises(HTTPException) as denied:
        authorize_delivery(db, run, {'chat_id': '42'}, resource_id=resource.id)
    assert denied.value.status_code == 403


def test_customer_account_intake_remains_visible_in_myrequests(db, bot, customer_link):
    resource, _, _, _, receive = bot
    customer, linked = customer_link
    for text in ['Support', 'Verified customer', 'Need account help']:
        receive(text)
    task = db.query(CRMTask).one()
    assert task.company_id == customer.id and task.contact_id is None and task.lead_id is None
    receive('/myrequests')
    reply = db.query(TelegramMessage).filter_by(direction='outgoing').order_by(TelegramMessage.id.desc()).first()
    assert f'#{task.id}' in reply.text and 'Need account help' in reply.text
    run = db.get(AutomationRun, reply.run_id)
    assert run.input_payload['telegram_private_identity_id'] == linked.id
    authorize_delivery(db, run, {'chat_id': '42'}, resource_id=resource.id)
    linked.revoked_at = now(); db.commit()
    with pytest.raises(HTTPException):
        authorize_delivery(db, run, {'chat_id': '42'}, resource_id=resource.id)


def test_unverified_public_menu_can_still_be_delivered(db, bot):
    resource, _, _, _, receive = bot
    receive('/public')
    reply = db.query(TelegramMessage).filter_by(direction='outgoing').order_by(TelegramMessage.id.desc()).first()
    run = db.get(AutomationRun, reply.run_id)
    assert not run.input_payload.get('telegram_private_binding')
    authorize_delivery(db, run, {'chat_id': '42'}, resource_id=resource.id)


@pytest.mark.parametrize('command,module', [('/myrequests', 'crm'), ('/orders', 'srm')])
def test_private_delivery_rechecks_source_permissions_after_queueing(db, bot, customer_link, command, module):
    resource, trigger, owner, branch, _ = bot
    _, linked = customer_link
    if module == 'srm':
        permission = db.query(Permission).filter_by(name='srm_admin').first()
        if not permission:
            permission = Permission(name='srm_admin', module='srm')
            db.add(permission)
        owner.role.permissions.append(permission)
        owner._suite_permission_objects = None
        db.commit()
    thread = db.query(TelegramConversation).one()
    with background_scope(db, owner, 'power_apps', 'create', branch_id=branch.id):
        run_id = queue_reply(db, resource, trigger, owner, thread, 'Private request details',
            'customer-private-permission-fixture', private_identity=linked, private_command=command)
        db.commit()
    run = db.get(AutomationRun, run_id)
    authorize_delivery(db, run, {'chat_id': '42'}, resource_id=resource.id)
    owner.role.permissions = [permission for permission in owner.role.permissions if permission.module != module]
    owner._suite_permission_objects = None
    db.commit()
    with pytest.raises(HTTPException) as denied:
        authorize_delivery(db, run, {'chat_id': '42'}, resource_id=resource.id)
    assert denied.value.status_code == 403
