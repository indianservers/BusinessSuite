import asyncio
import json
from datetime import date, timedelta
from uuid import uuid4

from app.access.service import background_scope
from app.apps.crm.models import CRMCompany
from app.apps.power_apps import telegram_approvals
from app.apps.power_apps.models import TelegramActionApproval, TelegramConversation, TelegramMessage
from app.apps.power_apps.runtime import now
from app.apps.power_apps.runtime_models import AutomationRun
from app.apps.srm.industry_models import IndustryRecord
from app.models.company import Branch
from app.models.employee import Employee
from app.models.user import User
from app.branches.models import BranchPolicy
from tests.test_power_runtime import db
from tests.test_power_apps import actors
from tests.test_telegram_operations import bot, ROOT
from tests.test_telegram_experience import deliver
from tests.test_telegram_booking_flow import appointment_setup, review_button
from tests.tenant_test_utils import assign_company


def latest_reply(db, sender_id):
    thread = db.query(TelegramConversation).filter_by(telegram_id=str(sender_id)).one()
    return db.query(TelegramMessage).filter_by(conversation_id=thread.id, direction='outgoing').order_by(TelegramMessage.id.desc()).first()


def test_employee_booking_selects_visible_customer_and_executes_exact_native_proposal(client, db, actors, bot, appointment_setup):
    buyer, service, resources, _ = appointment_setup
    resource, _, owner, branch, _ = bot
    employee_user = User(email='telegram-booking-employee@example.com', hashed_password='unused', role_id=owner.role_id, is_active=True)
    db.add(employee_user); db.flush()
    assign_company(db, employee_user, 1)
    db.add(BranchPolicy(user_id=employee_user.id, company_id=1, all_branches=True, use_home_branch=False))
    db.commit()
    with background_scope(db, owner, 'power_apps', 'create', branch_id=branch.id):
        employee = Employee(employee_id='TELEGRAM-BOOKING-STAFF', first_name='Booking', last_name='Employee', user_id=employee_user.id,
            branch_id=branch.id, date_of_joining=date(2020, 1, 1), status='Active')
        db.add(employee); db.commit()
    response = client.post(f'{ROOT}/{resource.id}/employee-links', headers=actors[0],
        json={'employee_id': employee.id, 'telegram_user_id': '77'})
    assert response.status_code == 201, response.text
    foreign_actor = db.query(User).filter_by(email='power-1@example.com').one()
    foreign_actor.organization_id = 2
    foreign_branch = db.query(Branch).filter_by(company_id=2).one()
    with background_scope(db, foreign_actor, 'power_apps', 'create', branch_id=foreign_branch.id):
        foreign_customer = CRMCompany(organization_id=2, name='Foreign confidential customer',
            owner_user_id=foreign_actor.id, created_by_user_id=foreign_actor.id)
        db.add(foreign_customer); db.commit()

    deliver(db, bot, 10, text='/book', sender_id=77)
    reply = latest_reply(db, 77)
    keyboard = json.loads(db.get(AutomationRun, reply.run_id).input_payload['reply_markup_json'])
    choices = [button for row in keyboard['inline_keyboard'] for button in row]
    assert any(button['callback_data'] == f'customer:{buyer.id}' for button in choices)
    assert all(button['callback_data'] != f'customer:{foreign_customer.id}' for button in choices)
    assert 'Foreign confidential customer' not in json.dumps(keyboard)
    deliver(db, bot, 11, callback=f'customer:{foreign_customer.id}', sender_id=77)
    assert 'not found' in latest_reply(db, 77).text.lower()
    assert db.query(TelegramActionApproval).count() == 0

    deliver(db, bot, 12, callback=f'customer:{buyer.id}', sender_id=77)
    deliver(db, bot, 13, callback=f'book:{service.id}', sender_id=77)
    day = (now() + timedelta(days=2)).date().isoformat()
    deliver(db, bot, 14, text=day, sender_id=77)
    deliver(db, bot, 15, callback='slot:0', sender_id=77)
    approval = db.query(TelegramActionApproval).one()
    assert approval.operation['customer_id'] == buyer.id
    assert approval.operation['resource_ids'] == resources
    assert approval.operation['service_id'] == service.id
    preview = latest_reply(db, 77).text
    assert buyer.name in preview and day in preview and '500' in preview and '18' in preview
    assert db.query(IndustryRecord).filter_by(kind='appointment').count() == 0
    deliver(db, bot, 16, callback=review_button(db), sender_id=77)
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    appointment = db.query(IndustryRecord).filter_by(kind='appointment').one()
    assert appointment.customer_id == buyer.id and appointment.status == 'booked'
    assert appointment.data['resource_ids'] == resources
    assert appointment.starts_at.isoformat().startswith(day)
    assert appointment.invoice_id is None
    db.refresh(approval)
    assert approval.status == 'approved'


def test_public_customer_cannot_reschedule_cancel_or_select_another_account(client, db, actors, bot, appointment_setup):
    _, service, resources, headers = appointment_setup
    _, _, owner, branch, _ = bot
    with background_scope(db, owner, 'power_apps', 'create', branch_id=branch.id):
        other_customer = CRMCompany(organization_id=1, name='Another private customer', owner_user_id=owner.id, created_by_user_id=owner.id)
        db.add(other_customer); db.commit()
    response = client.post('/api/v1/srm/industry/appointments', headers=headers, json={'request_id': str(uuid4()),
        'title': 'Another customer appointment', 'customer_id': other_customer.id, 'service_id': service.id,
        'resource_ids': resources, 'starts_at': (now() + timedelta(days=2)).date().isoformat() + 'T10:00:00+00:00', 'duration_minutes': 30})
    assert response.status_code == 201, response.text
    appointment_id = response.json()['id']
    for update_id, command in enumerate([f'/reschedule {appointment_id}', f'/cancelbooking {appointment_id}'], start=10):
        deliver(db, bot, update_id, text=command)
        assert 'not available for your verified account' in latest_reply(db, 42).text
        assert 'Another private customer' not in latest_reply(db, 42).text
    deliver(db, bot, 12, callback=f'customer:{other_customer.id}')
    assert 'not linked to your identity' in latest_reply(db, 42).text
    assert db.query(TelegramActionApproval).count() == 0
    appointment = db.get(IndustryRecord, appointment_id)
    assert appointment.status == 'booked' and appointment.revision == 1
