from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.apps.power_apps import telegram_followups as followups

INSTANT = datetime(2026, 11, 17, 6, 0, tzinfo=timezone.utc)  # 11:30 IST


def thread():
    return SimpleNamespace(id=1, interface='public', status='bot', last_at=INSTANT-timedelta(hours=25),
        context={'requests': [{'update_id': 10, 'lead_id': 5, 'task_id': 6, 'status': 'received'}]})


def test_followup_requires_explicit_consent_and_qualified_enquiry():
    row = thread()
    settings = followups.FollowupPolicy()
    assert not followups.eligible(row, settings, INSTANT)
    assert followups.consent(row, '/followup on')
    assert followups.eligible(row, settings, INSTANT)
    row.context['requests'] = []
    assert not followups.eligible(row, settings, INSTANT)


@pytest.mark.parametrize('status', ['waiting', 'assigned', 'resolved'])
def test_followup_pauses_for_human_handoff_and_closed_thread(status):
    row = thread()
    followups.consent(row, '/followup on')
    row.status = status
    assert not followups.eligible(row, followups.FollowupPolicy(), INSTANT)


def test_quiet_hours_delay_and_once_per_enquiry():
    row = thread()
    followups.consent(row, '/followup on')
    settings = followups.FollowupPolicy()
    assert not followups.eligible(row, settings, INSTANT.replace(hour=18))  # 23:30 IST
    row.last_at = INSTANT-timedelta(hours=2)
    assert not followups.eligible(row, settings, INSTANT)
    row.last_at = INSTANT-timedelta(hours=25)
    row.context['followup_queued_for'] = '10'
    assert not followups.eligible(row, settings, INSTANT)
    row.context['requests'].append({'update_id': 11, 'lead_id': 5, 'task_id': 7, 'status': 'received'})
    assert followups.eligible(row, settings, INSTANT)


def test_delivery_rechecks_consent_and_new_activity(monkeypatch):
    monkeypatch.setattr(followups, 'now', lambda: INSTANT)
    row = thread()
    trigger = SimpleNamespace(config={})
    followups.consent(row, '/followup on')
    payload = {'telegram_followup_binding': followups.binding(row)}
    followups.authorize_delivery(trigger, row, payload)
    row.last_at = INSTANT
    with pytest.raises(HTTPException):
        followups.authorize_delivery(trigger, row, payload)
    row.last_at = INSTANT-timedelta(hours=25)
    followups.consent(row, '/stop')
    with pytest.raises(HTTPException):
        followups.authorize_delivery(trigger, row, payload)


def test_company_and_ordinary_messages_cannot_opt_in():
    row = thread()
    assert followups.consent(row, 'yes') is None
    row.interface = 'company'
    followups.consent(row, '/followup on')
    assert 'followup_consent' not in row.context


def test_policy_validates_hours():
    with pytest.raises(ValidationError):
        followups.FollowupPolicy(opens='19:00', closes='08:00')


from tests.test_power_runtime import db
from tests.test_power_apps import actors
from tests.test_telegram_operations import bot


def test_outbox_queues_once_and_does_not_send(db, bot, monkeypatch):
    from app.apps.power_apps.models import TelegramConversation, PowerExecution
    from app.apps.power_apps.runtime_models import AutomationRun
    from app.access.service import background_scope
    resource, trigger, owner, branch, receive = bot
    for message in ['/public', 'Sales', 'Followup Customer', 'Need consultation']:
        receive(message)
    row = db.query(TelegramConversation).filter_by(resource_id=resource.id, interface='public').one()
    monkeypatch.setattr(followups, 'now', lambda: INSTANT)
    row.last_at = INSTANT-timedelta(hours=25)
    followups.consent(row, '/followup on')
    db.commit()
    with background_scope(db, owner, 'power_apps', 'create', branch_id=branch.id):
        assert followups.queue_due(db, resource, trigger, owner) == 1
        db.flush()
        assert followups.queue_due(db, resource, trigger, owner) == 0
        execution = db.query(PowerExecution).filter_by(resource_id=resource.id).order_by(PowerExecution.id.desc()).first()
        run = db.get(AutomationRun, execution.id)
        assert execution.status == 'queued'
        assert run.input_payload['telegram_followup_binding'] == followups.binding(row)
        followups.authorize_delivery(trigger, row, run.input_payload)
        followups.consent(row, '/stop')
        with pytest.raises(HTTPException):
            followups.authorize_delivery(trigger, row, run.input_payload)


def test_real_ingress_opt_in_and_stop_preserve_existing_lead(db, bot):
    from app.apps.power_apps.models import TelegramConversation
    from app.apps.crm.models import CRMLead, CRMTask
    resource, _, _, _, receive = bot
    for message in ['/public', 'Sales', 'Reminder Customer', 'Need a quotation', '/followup on']:
        receive(message)
    row = db.query(TelegramConversation).filter_by(resource_id=resource.id, interface='public').one()
    assert row.context['followup_consent']['enabled'] is True
    receive('/stop')
    assert row.context['followup_consent']['enabled'] is False
    assert db.query(CRMLead).count() == 1
    assert db.query(CRMTask).count() == 1
