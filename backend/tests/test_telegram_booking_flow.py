import asyncio
from datetime import timedelta
import json
from uuid import uuid4

import pytest
from app.access.service import background_scope
from app.models.user import Permission
from app.apps.crm.models import CRMCompany
from app.apps.srm.models import SRMProduct
from app.apps.srm.industry_models import IndustryRecord
from app.apps.power_apps.models import TelegramActionApproval, TelegramMessage, TelegramConversation
from app.apps.power_apps.runtime_models import AutomationRun
from app.apps.power_apps.runtime import now
from app.apps.power_apps import telegram_approvals
from tests.test_power_runtime import db
from tests.test_power_apps import actors
from tests.test_telegram_operations import bot, ROOT
from tests.test_telegram_experience import deliver, publish


@pytest.fixture
def appointment_setup(client, db, actors, bot):
    resource, trigger, owner, branch, _ = bot
    permission = db.query(Permission).filter_by(name='srm_admin').first()
    if not permission:
        permission = Permission(name='srm_admin', module='srm'); db.add(permission)
    owner.role.permissions.append(permission); owner._suite_permission_objects = None; db.commit()
    with background_scope(db, owner, 'power_apps', 'create', branch_id=branch.id):
        buyer = CRMCompany(organization_id=1, name='Telegram Customer', owner_user_id=owner.id, created_by_user_id=owner.id)
        service = SRMProduct(organization_id=1, sku='TELEGRAM-CONSULT', item_name='Consultation', product_type='service', sales_rate=500, gst_rate=18, track_inventory=False)
        db.add_all([buyer, service]); db.commit()
    headers = {**actors[0], 'X-Suite-Branch': str(branch.id)}
    resources = []
    for kind in ['consultant', 'room', 'equipment']:
        response = client.post('/api/v1/srm/industry/resources', headers=headers, json={'request_id': str(uuid4()), 'title': 'Telegram ' + kind,
            'resource_type': kind, 'timezone': 'UTC', 'weekdays': list(range(7)), 'opens': '09:00', 'closes': '19:00'})
        assert response.status_code == 201, response.text
        resources.append(response.json()['id'])
    publish(client, actors, resource, booking_services=[{'service_id': service.id, 'label': 'Consultation', 'resource_ids': resources, 'duration_minutes': 30}])
    code = client.post(f'{ROOT}/{resource.id}/link-code', headers=actors[0], json={'interface': 'public', 'customer_id': buyer.id})
    assert code.status_code == 200, code.text
    deliver(db, bot, 1, text=code.json()['command'])
    return buyer, service, resources, headers


def review_button(db, text='Approve'):
    message = db.query(TelegramMessage).filter_by(direction='outgoing').order_by(TelegramMessage.id.desc()).first()
    run = db.get(AutomationRun, message.run_id)
    keyboard = json.loads(run.input_payload['reply_markup_json'])
    return next(button['callback_data'] for row in keyboard['inline_keyboard'] for button in row if button['text'] == text)


def propose_booking(db, bot, service_id, base=10, sender_id=42):
    deliver(db, bot, base, text='/book', sender_id=sender_id)
    deliver(db, bot, base + 1, callback=f'book:{service_id}', sender_id=sender_id)
    deliver(db, bot, base + 2, text=(now() + timedelta(days=2)).date().isoformat(), sender_id=sender_id)
    deliver(db, bot, base + 3, callback='slot:0', sender_id=sender_id)
    return review_button(db)


def test_verified_customer_can_book_reschedule_cancel_and_retries_do_not_duplicate(client, db, actors, bot, appointment_setup):
    buyer, service, resources, _ = appointment_setup
    button = propose_booking(db, bot, service.id)
    assert db.query(IndustryRecord).filter_by(kind='appointment').count() == 0
    deliver(db, bot, 20, callback=button)
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    row = db.query(IndustryRecord).filter_by(kind='appointment').one()
    assert row.customer_id == buyer.id and row.status == 'booked' and row.data['resource_ids'] == resources
    assert row.invoice_id is None
    assert db.query(TelegramActionApproval).one().status == 'approved'
    deliver(db, bot, 21, callback=button)
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    assert db.query(IndustryRecord).filter_by(kind='appointment').count() == 1
    deliver(db, bot, 30, text=f'/reschedule {row.id}')
    deliver(db, bot, 31, text=(now() + timedelta(days=3)).date().isoformat())
    deliver(db, bot, 32, callback='slot:1')
    deliver(db, bot, 33, callback=review_button(db))
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    db.refresh(row)
    assert row.revision == 2 and row.data['starts_at'].startswith((now() + timedelta(days=3)).date().isoformat())
    deliver(db, bot, 40, text=f'/cancelbooking {row.id}')
    deliver(db, bot, 41, text='Customer requested another day')
    deliver(db, bot, 42, callback=review_button(db))
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    db.refresh(row)
    assert row.status == 'cancelled' and row.revision == 3


def test_customer_verification_and_price_recheck_before_booking(client, db, actors, bot, appointment_setup):
    _, service, _, _ = appointment_setup
    deliver(db, bot, 2, text='/book', sender_id=99)
    assert 'verify' in db.query(TelegramMessage).filter_by(direction='outgoing').order_by(TelegramMessage.id.desc()).first().text.lower()
    button = propose_booking(db, bot, service.id)
    service.sales_rate = 700; db.commit()
    deliver(db, bot, 20, callback=button)
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    assert db.query(IndustryRecord).filter_by(kind='appointment').count() == 0
    assert db.query(TelegramActionApproval).one().status == 'failed'


def test_conflicting_native_booking_prevents_telegram_double_booking(client, db, actors, bot, appointment_setup):
    buyer, service, resources, headers = appointment_setup
    button = propose_booking(db, bot, service.id)
    approval = db.query(TelegramActionApproval).one()
    response = client.post('/api/v1/srm/industry/appointments', headers=headers, json={'request_id': str(uuid4()), 'title': 'Reception booking',
        'customer_id': buyer.id, 'service_id': service.id, 'resource_ids': resources, 'starts_at': approval.operation['starts_at'], 'duration_minutes': 30})
    assert response.status_code == 201, response.text
    deliver(db, bot, 20, callback=button)
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    assert db.query(IndustryRecord).filter_by(kind='appointment').count() == 1
    db.refresh(approval)
    assert approval.status == 'failed'
