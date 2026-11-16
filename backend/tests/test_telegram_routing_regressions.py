from datetime import date, datetime, timedelta, timezone

import pytest

from app.access.service import background_scope
from app.apps.power_apps import telegram_routing
from app.apps.power_apps.models import TelegramConversation, TelegramIdentity
from app.apps.power_apps.runtime import now
from app.apps.power_apps.runtime_models import AutomationEvent
from app.apps.power_apps.telegram_experience import ExperienceConfiguration, RoutingAgent
from app.models.employee import Employee
from tests.test_power_runtime import db
from tests.test_power_apps import actors
from tests.test_telegram_operations import bot


def conversation(resource, owner, number, context):
    return TelegramConversation(organization_id=resource.organization_id, environment=resource.environment, resource_id=resource.id, chat_id=str(number),
        telegram_id=str(number), interface='public', status='assigned', assignee_user_id=owner.id,
        state={}, context=context)


@pytest.mark.parametrize('blocker', ['answered', 'future', 'exhausted'])
def test_new_overdue_thread_is_not_starved_by_older_threads(db, bot, blocker):
    resource, trigger, owner, branch, _ = bot
    instant = now()
    context = {'sla_waiting': blocker != 'answered', 'sla_due_at': (instant + timedelta(days=1) if blocker == 'future' else instant - timedelta(minutes=1)).isoformat(),
        'sla_escalation_level': 1 if blocker == 'exhausted' else 0}
    with background_scope(db, owner, 'power_apps', 'create', branch_id=branch.id):
        db.add_all([conversation(resource, owner, number, context) for number in range(1, 202)])
        overdue = conversation(resource, owner, 202, {'sla_waiting': True, 'sla_due_at': (instant - timedelta(minutes=1)).isoformat(), 'sla_cycle': 1})
        db.add(overdue)
        db.commit()
        assert telegram_routing.tick(db, resource, trigger, instant) == 1
        assert overdue.context['sla_breached'] is True
        assert overdue.context['sla_escalation_level'] == 1
        db.flush()
        assert db.query(AutomationEvent).filter_by(kind='telegram_sla_breach').count() == 1
        assert telegram_routing.tick(db, resource, trigger, instant) == 0
        db.commit()


@pytest.mark.parametrize('disqualifier', [None, 'unmapped', 'revoked', 'language', 'skill', 'unavailable', 'hours', 'capacity'])
def test_routing_requires_current_mapping_and_matches_availability_and_capacity(db, bot, disqualifier):
    resource, trigger, owner, branch, _ = bot
    instant = datetime(2026, 11, 16, 5, 0, tzinfo=timezone.utc)  # Monday 10:30 India
    with background_scope(db, owner, 'power_apps', 'create', branch_id=branch.id):
        employee = Employee(employee_id='ROUTING-1', first_name='Available', last_name='Agent', user_id=owner.id,
            branch_id=branch.id, date_of_joining=date(2020, 1, 1), status='Active')
        db.add(employee)
        db.flush()
        if disqualifier != 'unmapped':
            db.add(TelegramIdentity(organization_id=resource.organization_id, environment=resource.environment, resource_id=resource.id, telegram_id='900', interface='company',
                user_id=owner.id, employee_id=employee.id, verified_at=now(), revoked_at=now() if disqualifier == 'revoked' else None))
        agent = RoutingAgent(user_id=owner.id, branch_id=branch.id, skills=[] if disqualifier == 'skill' else ['Dental'],
            languages=['en'] if disqualifier == 'language' else ['te'], available=disqualifier != 'unavailable',
            capacity=1, opens='11:00' if disqualifier == 'hours' else '09:00')
        trigger.config = {**trigger.config, 'experience': ExperienceConfiguration(routing_agents=[agent]).model_dump(mode='json')}
        thread = conversation(resource, owner, 800, {'language': 'te', 'required_skills': ['dental']})
        db.add(thread)
        if disqualifier == 'capacity':
            db.add(conversation(resource, owner, 801, {}))
        db.commit()
        ident, explanation = telegram_routing.select_agent(db, resource, trigger, thread, instant)
        assert ident == owner.id
        assert explanation['fallback'] is (disqualifier is not None)
        if disqualifier is None:
            assert explanation['matched_skills'] == ['dental']
            assert explanation['workload'] == 0 and explanation['capacity'] == 1
