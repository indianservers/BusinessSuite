from datetime import datetime, timedelta, timezone
from uuid import uuid4

from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite
from app.ai_operator.reminders import dispatch, after_quiet, next_occurrence
from app.apps.automation.models import AutomationScheduledJob as Job
from app.models.email_outbox import EmailOutbox
from app.models.notification import Notification

ROOT = '/api/v1/ai-operator/suite/reminders'


def draft(client, db, **extra):
    headers, user, project, task = setup_suite(client, db)
    at = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {'request_key': str(uuid4()), 'module': 'PMS', 'entity': 'task', 'record_id': task,
               'title': 'Reviewed delivery reminder', 'scheduled_at': at.isoformat(),
               'expires_at': (at + timedelta(days=3)).isoformat(), 'channels': ['in_app', 'email'], **extra}
    result = client.post(ROOT + '/preview', headers=headers, json=payload)
    assert result.status_code == 200, result.text
    return headers, user, result.json(), payload


def approve(client, headers, row):
    result = client.post(ROOT + f'/{row["id"]}/approve', headers=headers, json={'preview_hash': row['preview_hash']})
    assert result.status_code == 200, result.text
    return result.json()


def test_reviewed_reminder_atomic_deduplication_and_cancelled_outbox(client, db):
    headers, user, row, spec = draft(client, db)
    again = client.post(ROOT + '/preview', headers=headers, json=spec)
    assert again.json()['id'] == row['id']
    assert db.query(EmailOutbox).filter_by(module='ai_reminder').count() == 0
    assert client.post(ROOT + f'/{row["id"]}/approve', headers=headers, json={'preview_hash': '0' * 64}).status_code == 409
    approve(client, headers, row)
    instant = datetime.fromisoformat(spec['scheduled_at']) + timedelta(minutes=1)
    assert dispatch(db, instant)['processed'] == 1
    assert dispatch(db, instant)['processed'] == 0
    assert db.query(Notification).filter_by(event_type='ai.reminder').count() == 1
    email = db.query(EmailOutbox).filter_by(module='ai_reminder').one()
    assert email.status == 'queued' and 'Reviewed delivery reminder' not in email.body
    assert 'security_context' not in email.body
    client.post(ROOT + f'/{row["id"]}/cancel', headers=headers)
    db.refresh(email)
    assert email.status == 'suppressed'


def test_expiry_owner_revocation_and_completed_source_block_delivery(client, db):
    headers, user, row, spec = draft(client, db)
    approve(client, headers, row)
    user.is_active = False; db.commit()
    dispatch(db, datetime.fromisoformat(spec['scheduled_at']) + timedelta(minutes=1))
    db.expire_all()
    assert db.get(Job, row['id']).status == 'ai_blocked'
    assert db.query(EmailOutbox).filter_by(module='ai_reminder').count() == 0


def test_quiet_hours_and_wall_clock_recurrence():
    spec = {'timezone': 'Asia/Kolkata', 'quiet_start': '22:00', 'quiet_end': '08:00'}
    at = datetime(2030, 1, 1, 18, 0, tzinfo=timezone.utc)
    assert after_quiet(at, spec) == datetime(2030, 1, 2, 2, 30, tzinfo=timezone.utc)
    assert after_quiet(datetime(2030, 1, 1, 10, 0, tzinfo=timezone.utc), spec).hour == 10
    recurrence = {'timezone': 'America/New_York', 'scheduled_at': '2030-03-09T14:00:00+00:00', 'frequency': 'daily'}
    assert next_occurrence(recurrence, datetime(2030, 3, 9, 15, tzinfo=timezone.utc)) == datetime(2030, 3, 10, 13, tzinfo=timezone.utc)


def test_completed_source_expiry_and_quiet_hours_prevent_delivery(client, db):
    from app.apps.project_management.models import PMSTask
    headers, _, row, spec = draft(client, db)
    approve(client, headers, row)
    db.get(PMSTask, spec['record_id']).status = 'Done'; db.commit()
    dispatch(db, datetime.fromisoformat(spec['scheduled_at']) + timedelta(minutes=1))
    assert db.get(Job, row['id']).status == 'ai_blocked'
    assert db.query(Notification).filter_by(event_type='ai.reminder').count() == 0


def test_unknown_email_outcome_is_not_replayed_and_manual_resolution_is_audited(client, db, monkeypatch):
    from app.services import email_dispatch
    from app.ai_operator import reminders
    headers, _, row, spec = draft(client, db)
    approve(client, headers, row)
    instant = datetime.fromisoformat(spec['scheduled_at']) + timedelta(minutes=1)
    dispatch(db, instant)
    email = db.query(EmailOutbox).filter_by(module='ai_reminder').one()
    monkeypatch.setattr(reminders, 'now', lambda: instant)
    db.query(EmailOutbox).filter(EmailOutbox.module != 'ai_reminder').update({'status': 'suppressed'}, synchronize_session=False)
    db.commit()
    calls = []
    def uncertain(*args, **kwargs):
        calls.append(True)
        raise TimeoutError('Uncertain provider outcome')
    monkeypatch.setattr(email_dispatch.email, 'email_configured', lambda: True)
    monkeypatch.setattr(email_dispatch.email, 'send_email', uncertain)
    email_dispatch.drain_outbox(db)
    db.refresh(email)
    assert email.status == 'reconciliation_required' and len(calls) == 1
    email_dispatch.drain_outbox(db)
    assert len(calls) == 1
    response = client.post(ROOT + f'/{row["id"]}/receipts/{email.id}/reconcile', headers=headers,
        json={'decision': 'confirmed_not_sent', 'evidence_reference': 'Provider log checked: fixture-123'})
    assert response.status_code == 200 and response.json()['manual'] is True and response.json()['resent'] is False, response.text
    assert db.get(EmailOutbox, email.id).status == 'manually_confirmed_not_sent'


def test_failed_occurrence_rolls_back_partially_prepared_notifications(client, db, monkeypatch):
    from app.services import notifications
    from fastapi import HTTPException
    headers, _, row, spec = draft(client, db)
    approve(client, headers, row)
    original = notifications.create_notification
    def fail_after_flush(*args, **kwargs):
        original(*args, **kwargs)
        raise HTTPException(403, 'Recipient permission changed')
    monkeypatch.setattr(notifications, 'create_notification', fail_after_flush)
    dispatch(db, datetime.fromisoformat(spec['scheduled_at']) + timedelta(minutes=1))
    assert db.query(Notification).filter_by(event_type='ai.reminder').count() == 0
    assert db.query(EmailOutbox).filter_by(module='ai_reminder').count() == 0
    assert db.get(Job, row['id']).status == 'ai_blocked'
