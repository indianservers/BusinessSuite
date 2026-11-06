"""Provider-free coverage for the communication page's scheduling boundary."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.whatsapp_cloud import SendInput, WorkspaceScheduleInput, WorkspaceRecipientInput
from app.services import whatsapp_communication as workspace
from app.shared.whatsapp_models import WhatsAppContact
from app.apps.communication.customer_models import CustomerRecipient, CustomerDelivery


def request(**overrides):
    values = dict(message=SendInput(requestId='workspace-test-request', to='+919876543210', body='',
        template={'name': 'payment_update', 'language': {'code': 'en'}}, entityType='contact', entityId=12),
        scheduledAt=datetime.now(timezone.utc)+timedelta(days=1), purpose='transactional')
    values.update(overrides)
    return WorkspaceScheduleInput(**values)


@pytest.mark.parametrize('change,expected', [
    ({'scheduledAt': datetime(2030, 1, 1)}, 'timezone'),
    ({'scheduledAt': datetime.now(timezone.utc)-timedelta(days=1)}, 'future'),
    ({'message': SendInput(requestId='workspace-test-request', to='+919876543210', body='Hello')}, 'approved template'),
    ({'message': SendInput(requestId='workspace-test-request', to='+919876543210', template={'name': 'payment_update', 'language': {'code': 'en'}, 'components': [{'type': 'body', 'parameters': [{'type': 'text', 'text': '{{contact_name}}'}]}]})}, 'Complete all'),
])
def test_schedule_rejects_invalid_intents_without_queuing(change, expected):
    db = MagicMock()
    with pytest.raises(HTTPException, match=expected):
        workspace.schedule(db, SimpleNamespace(is_superuser=True), request(**change))
    db.commit.assert_not_called()


def test_scheduling_requires_communication_permission(monkeypatch):
    monkeypatch.setattr('app.services.email_schedules.permitted', lambda *args: False)
    with pytest.raises(HTTPException) as error:
        workspace.schedule(MagicMock(), SimpleNamespace(is_superuser=False), request())
    assert error.value.status_code == 403


def fixture_database(monkeypatch, *, consent='opted_in', entity_id=12, existing=None):
    contact = SimpleNamespace(id=9, consent=consent, entity_type='contact', entity_id=entity_id)
    recipient = SimpleNamespace(id=8, organization_id=1, branch_id=1)
    db = MagicMock()
    db.info = {'branch_context': SimpleNamespace(branch_id=1, writable={1})}
    def query(model):
        if model is WhatsAppContact:
            value = contact
        elif model is CustomerRecipient:
            value = recipient
        elif model is CustomerDelivery:
            value = existing
        else:
            # The binding subquery is compiled, never executed in these tests.
            return Session().query(model)
        result = MagicMock()
        result.filter_by.return_value = result
        result.filter.return_value = result
        result.order_by.return_value = result
        result.first.return_value = value
        return result
    db.query.side_effect = query
    monkeypatch.setattr(workspace.wa, 'organization', lambda user: 1)
    monkeypatch.setattr(workspace.wa, 'contact_access', lambda *args: None)
    monkeypatch.setattr(workspace.wa, 'record_access', lambda *args: None)
    return db, recipient


@pytest.mark.parametrize('consent,identity,expected', [('opted_out',12,'opted in'),('opted_in',99,'linked CRM')])
def test_schedule_cannot_bypass_consent_or_shared_phone_link(monkeypatch, consent, identity, expected):
    db, _ = fixture_database(monkeypatch, consent=consent, entity_id=identity)
    with pytest.raises(HTTPException, match=expected):
        workspace.schedule(db, SimpleNamespace(is_superuser=True), request())
    db.commit.assert_not_called()


def test_schedule_reuses_durable_queue_and_replays_idempotently(monkeypatch):
    from app.apps.communication import customer_service
    db, recipient = fixture_database(monkeypatch)
    monkeypatch.setattr(customer_service, 'preference_allowed', lambda *args: True)
    row = SimpleNamespace(id=77, status='queued', due_at=request().scheduledAt)
    queued = MagicMock(return_value=row)
    monkeypatch.setattr(customer_service, 'queue_delivery', queued)
    connection = SimpleNamespace(waba_id='account')
    monkeypatch.setattr(workspace.wa, 'live_connection', lambda *args: connection)
    monkeypatch.setattr(workspace.wa, 'connection_token', lambda *args: 'synthetic-token')
    graph = MagicMock()
    graph.request.return_value = {'data': [{'name':'payment_update','language':'en','status':'APPROVED','category':'UTILITY'}]}
    monkeypatch.setattr('app.services.whatsapp.WhatsAppGraph', lambda *args: graph)
    data = request()
    result = workspace.schedule(db, SimpleNamespace(is_superuser=True, id=4), data)
    assert result['id'] == 77
    assert queued.call_args.kwargs['channel'] == 'whatsapp'
    assert queued.call_args.kwargs['due_at'] == data.scheduledAt
    assert row.whatsapp_template == data.message.template
    row.snapshot = queued.call_args.kwargs['snapshot']
    replay_db, _ = fixture_database(monkeypatch, existing=row)
    assert workspace.schedule(replay_db, SimpleNamespace(is_superuser=True,id=4), data)['id'] == 77
    assert queued.call_count == 1
    data.message.body = 'Changed content'
    with pytest.raises(HTTPException, match='different scheduled message'):
        workspace.schedule(replay_db, SimpleNamespace(is_superuser=True,id=4), data)


def test_shared_phone_directory_never_loads_other_records_invoices(monkeypatch):
    from app.services import whatsapp_hub
    db, _ = fixture_database(monkeypatch, entity_id=99)
    monkeypatch.setattr(workspace.wa, 'contact_data', lambda row: {'id':row.id})
    context = MagicMock(side_effect=AssertionError('Must not load another CRM record'))
    monkeypatch.setattr(whatsapp_hub, 'context', context)
    result = workspace.directory(db, object(), [WorkspaceRecipientInput(to='+919876543210',entityType='contact',entityId=12)])
    assert result['items'][0]['invoices'] == []
    context.assert_not_called()


def test_schedule_does_not_create_consent_or_register_recipients(monkeypatch):
    from app.apps.communication import customer_service
    db, _ = fixture_database(monkeypatch)
    monkeypatch.setattr(customer_service, 'preference_allowed', lambda *args: False)
    with pytest.raises(HTTPException, match='Register this contact'):
        workspace.schedule(db, SimpleNamespace(is_superuser=True, id=4), request())
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize('category,status,expected', [('MARKETING','APPROVED','Marketing templates'),('UTILITY','PENDING','currently approved')])
def test_schedule_checks_live_template_status_and_category(monkeypatch, category, status, expected):
    from app.apps.communication import customer_service
    db, _ = fixture_database(monkeypatch)
    monkeypatch.setattr(customer_service, 'preference_allowed', lambda *args: True)
    monkeypatch.setattr(workspace.wa, 'live_connection', lambda *args: SimpleNamespace(waba_id='account'))
    monkeypatch.setattr(workspace.wa, 'connection_token', lambda *args: 'synthetic-token')
    graph = MagicMock()
    graph.request.return_value = {'data':[{'name':'payment_update','language':'en','category':category,'status':status}]}
    monkeypatch.setattr('app.services.whatsapp.WhatsAppGraph', lambda *args: graph)
    with pytest.raises(HTTPException, match=expected):
        workspace.schedule(db, SimpleNamespace(is_superuser=True,id=4), request())
    db.commit.assert_not_called()
