from datetime import timedelta
from unittest.mock import Mock
from app.apps.communication import customer_service as service
from app.apps.communication.customer_models import CustomerRecipient, CustomerBinding, CustomerAutomation, CustomerDelivery, CustomerEvent
from app.apps.srm.models import SRMSalesOrder, SRMInvoice
from app.models.email_outbox import EmailOutbox
import pytest


@pytest.fixture(autouse=True)
def organization_context(db):
    from app.models.company import Company, Branch
    if not db.get(Company, 1):
        db.add(Company(id=1, name='Synthetic communications company', is_active=True))
        db.flush()
    if not db.query(Branch).filter_by(company_id=1).first():
        db.add(Branch(company_id=1, organization_id=1, name='Synthetic branch', code='COMMS', is_active=True))
    db.flush()
    from app.branches.models import BranchOwnership
    branch = db.query(Branch).filter_by(company_id=1).first()
    if not db.get(BranchOwnership, ('branches', str(branch.id))):
        db.add(BranchOwnership(resource_table='branches', resource_key=str(branch.id), company_id=1, branch_id=branch.id, source='synthetic-test'))
    db.commit()

BASE = '/api/v1/communication/customers'


def recipient(client, headers, **changes):
    data = {'name': 'Synthetic customer', 'email': 'customer@example.com', 'role': 'billing',
        'consent_source': 'Synthetic test opt-in', 'preferences': {'email.transactional': True, 'email.marketing': True}}
    data.update(changes)
    response = client.post(BASE+'/recipients', headers=headers, json=data)
    assert response.status_code == 201, response.text
    return response.json()


def rule(client, headers, **changes):
    data = {'name': 'Order updates', 'trigger': 'order.changed', 'subject': 'Order {{reference}}',
        'body': 'Hello {{name}}, order {{reference}} is {{status}}.', 'status': 'active', 'quiet_start': 0, 'quiet_end': 0}
    data.update(changes)
    response = client.post(BASE+'/automations', headers=headers, json=data)
    assert response.status_code == 201, response.text
    return response.json()


def seed_order(db):
    order = SRMSalesOrder(organization_id=1, order_number='TEST-COMMS', title='Synthetic order', status='confirmed')
    db.add(order)
    db.commit()
    return order


def test_customer_workspace_api_and_validation(client, db, superuser_headers):
    headers = superuser_headers
    r = recipient(client, headers)
    response = client.get(BASE+'/recipients', headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['items'][0]['id'] == r['id']
    assert client.post(BASE+'/recipients', headers=headers, json={'name': 'Bad', 'email': 'bad', 'consent_source': 'test'}).status_code == 422
    assert client.post(BASE+'/recipients', headers=headers, json={'name': 'Bad', 'phone': '123', 'consent_source': 'test'}).status_code == 422
    assert client.post(BASE+'/automations', headers=headers, json={'name': 'Bad', 'trigger': 'birthday', 'subject': 'Hi', 'body': 'Hi', 'purpose': 'transactional'}).status_code == 422
    assert client.get(BASE+'/dashboard', headers=headers).status_code == 200
    assert client.post(BASE+f"/recipients/{r['id']}/notes", headers=headers, json={'body': 'Internal only'}).status_code == 201
    history = client.get(BASE+f"/recipients/{r['id']}/history", headers=headers).json()
    assert history['internal_notes'][0]['body'] == 'Internal only'
    assert history['email_reply_ingestion'] is False


def test_campaign_deduplication_and_preference_withdrawal(client, db, superuser_headers, monkeypatch):
    headers = superuser_headers
    r = recipient(client, headers)
    automation = rule(client, headers, trigger='campaign', purpose='marketing', subject='Hello {{name}}', body='Synthetic offer')
    path = BASE+f"/automations/{automation['id']}"
    preview = client.post(path+'/preview', headers=headers, json={})
    assert preview.status_code == 200, preview.text
    assert preview.json()['eligible'] == 1
    assert client.post(path+'/launch', headers=headers, json={}).json()['queued'] == 1
    assert client.post(path+'/launch', headers=headers, json={}).json()['queued'] == 0
    link = client.post(BASE+f"/recipients/{r['id']}/preference-link", headers=headers).json()['url']
    token = link.rsplit('/', 1)[1]
    public = client.get('/api/v1/public/customer-preferences/'+token)
    assert public.status_code == 200, public.text
    assert client.post('/api/v1/public/customer-preferences/'+token).status_code == 200
    send = Mock(return_value='synthetic-provider-id')
    monkeypatch.setattr('app.core.email.email_configured', lambda: True)
    monkeypatch.setattr('app.core.email.send_email', send)
    service.process_customer_communications(db)
    assert db.query(CustomerDelivery).one().status == 'blocked'
    send.assert_not_called()


def test_template_and_quiet_hours():
    import pytest
    from types import SimpleNamespace
    from datetime import datetime, timezone
    with pytest.raises(ValueError):
        service.render('Hello {{missing}}', {'name': 'Test'})
    with pytest.raises(ValueError):
        service.render('Due {{due_date}}', {'due_date': ''})
    customer = SimpleNamespace(timezone='Asia/Kolkata')
    automation = SimpleNamespace(quiet_start=20, quiet_end=8, weekdays=list(range(7)))
    assert not service.permitted_time(customer, automation, datetime(2026, 11, 3, 18, tzinfo=timezone.utc))
    assert service.permitted_time(customer, automation, datetime(2026, 11, 3, 6, tzinfo=timezone.utc))


def test_event_outbox_is_transactional_and_source_changes_cancel(db):
    order = seed_order(db)
    assert db.query(CustomerEvent).filter_by(source_type='order', source_id=order.id).count() == 1
    identity = order.id
    transaction = db.begin_nested()
    order.status = 'cancelled'
    db.flush()
    transaction.rollback()
    assert db.query(CustomerEvent).filter_by(source_type='order', source_id=identity).count() == 1


def test_source_event_to_provider_acceptance(client, db, superuser_headers, monkeypatch):
    headers = superuser_headers
    from tests.srm_test_utils import create_sales_order
    order = create_sales_order(client, headers)
    r = recipient(client, headers)
    bind = client.post(BASE+f"/recipients/{r['id']}/bindings", headers=headers, json={'source_type': 'order', 'source_id': order['id']})
    assert bind.status_code == 201, bind.text
    automation = rule(client, headers)
    obj = db.get(SRMSalesOrder, order['id'])
    obj.status = 'confirmed'
    db.commit()
    monkeypatch.setattr('app.core.email.email_configured', lambda: True)
    send = Mock(return_value='synthetic-provider-id')
    monkeypatch.setattr('app.core.email.send_email', send)
    service.process_customer_communications(db)
    rows = db.query(CustomerDelivery).filter_by(automation_id=automation['id']).all()
    assert len(rows) == 1
    assert rows[0].status == 'waiting_provider', rows[0].error
    from app.services.email_dispatch import drain_outbox
    drain_outbox(db)
    db.refresh(rows[0])
    assert rows[0].status == 'accepted', rows[0].error
    send.assert_called_once()
    service.process_customer_communications(db)
    drain_outbox(db)
    send.assert_called_once()


def test_collection_requires_real_recipient_and_outstanding_invoice(client, db, superuser_headers):
    from tests.srm_test_utils import create_sales_order
    order = create_sales_order(client, superuser_headers)
    invoice = client.post(f"/api/v1/srm/invoices/draft-from-sales-order/{order['id']}", headers=superuser_headers).json()
    result = client.post('/api/v1/srm/collections/reminders/send', headers=superuser_headers, json={'invoice_id': invoice['id']})
    assert result.status_code == 409, result.text
    assert client.post('/api/v1/srm/collections/reminders/send', headers=superuser_headers, json={'invoice_id': 999999}).status_code == 404


def test_preference_link_rotation_and_expiry(client, db, superuser_headers):
    r = recipient(client, superuser_headers)
    path = BASE+f"/recipients/{r['id']}/preference-link"
    first = client.post(path, headers=superuser_headers).json()['url'].rsplit('/', 1)[1]
    second = client.post(path, headers=superuser_headers).json()['url'].rsplit('/', 1)[1]
    assert client.get('/api/v1/public/customer-preferences/'+first).status_code == 404
    from app.apps.communication.customer_models import CustomerPreferenceToken
    from hashlib import sha256
    token = db.get(CustomerPreferenceToken, sha256(second.encode()).hexdigest())
    token.expires_at = service.now()-timedelta(seconds=1)
    db.commit()
    assert client.get('/api/v1/public/customer-preferences/'+second).status_code == 404


def test_payment_and_address_changes_cancel_before_send(client, db, superuser_headers, monkeypatch):
    from tests.srm_test_utils import create_sales_order
    from app.apps.communication.customer_events import values
    headers = superuser_headers
    order = create_sales_order(client, headers)
    r = recipient(client, headers)
    assert client.post(BASE+f"/recipients/{r['id']}/bindings", headers=headers, json={'source_type':'order','source_id':order['id']}).status_code == 201
    customer = db.get(CustomerRecipient, r['id'])
    invoice = SRMInvoice(organization_id=1, sales_order_id=order['id'], invoice_number='TEST-CANCEL', status='issued', balance_amount=100, total_amount=100)
    db.add(invoice); db.commit()
    with service.actor_scope(db, r['created_by'], 1, customer.branch_id):
        delivery = service.queue_delivery(db, customer, key='test-payment', kind='invoice', identity=invoice.id,
            snapshot=values(invoice), actor=r['created_by'], subject='Payment', body='Please pay')
        db.commit()
    invoice.balance_amount, invoice.status = 0, 'paid'
    db.commit()
    state, reason = service.check_delivery(db, delivery)
    assert state == 'cancelled'
    with service.actor_scope(db, r['created_by'], 1, customer.branch_id):
        other = service.queue_delivery(db, customer, key='test-address', kind='recipient', identity=customer.id,
            snapshot={}, actor=r['created_by'], subject='Hello', body='Hello')
        db.commit()
    monkeypatch.setattr('app.core.email.email_configured', lambda: True)
    # Keep test delivery inside business hours without relying on the host clock.
    monkeypatch.setattr(service, 'permitted_time', lambda *args: True)
    service.process_customer_communications(db)
    db.refresh(other)
    assert other.email_outbox_id
    customer.email = 'new-address@example.com'
    db.commit()
    send = Mock(return_value='must-not-send')
    monkeypatch.setattr('app.core.email.send_email', send)
    from app.services.email_dispatch import drain_outbox
    drain_outbox(db)
    db.refresh(other)
    assert other.status == 'cancelled'
    send.assert_not_called()


def test_tenant_and_branch_isolation(client, db, superuser_headers):
    from app.models.company import Company, Branch
    r = recipient(client, superuser_headers)
    db.add(Company(id=2, name='Other tenant', is_active=True)); db.flush()
    db.add(Branch(company_id=2, name='Other branch', code='OTHER', is_active=True)); db.commit()
    other = {**superuser_headers, 'X-Suite-Organization': '2'}
    assert client.get(BASE+'/recipients', headers=other).json()['items'] == []
    assert client.get(BASE+f"/recipients/{r['id']}/history", headers=other).status_code == 404
    branch = Branch(company_id=1, name='Private second branch', code='SECOND', is_active=True)
    db.add(branch); db.commit()
    other_branch = {**superuser_headers, 'X-Suite-Branch': str(branch.id)}
    assert client.get(BASE+'/recipients', headers=other_branch).json()['items'] == []
    assert client.get(BASE+f"/recipients/{r['id']}/history", headers=other_branch).status_code == 404


def test_missing_provider_blocked_and_safe_retry(client, db, superuser_headers, monkeypatch):
    r = recipient(client, superuser_headers)
    automation = rule(client, superuser_headers, trigger='campaign', purpose='marketing', subject='Hello {{name}}', body='Hello')
    client.post(BASE+f"/automations/{automation['id']}/launch", headers=superuser_headers, json={})
    monkeypatch.setattr('app.core.email.email_configured', lambda: False)
    service.process_customer_communications(db)
    row = db.query(CustomerDelivery).one()
    assert row.status == 'blocked' and row.email_outbox_id is None
    assert client.post(BASE+f'/deliveries/{row.id}/retry', headers=superuser_headers).status_code == 200
    row.status = 'reconciliation_required'; db.commit()
    assert client.post(BASE+f'/deliveries/{row.id}/retry', headers=superuser_headers).status_code == 409


def test_due_schedule_dedup_and_reschedule(client, db, superuser_headers, monkeypatch):
    from tests.srm_test_utils import create_sales_order
    from app.apps.srm.models import SRMEngagement
    r = recipient(client, superuser_headers)
    order = create_sales_order(client, superuser_headers)
    client.post(BASE+f"/recipients/{r['id']}/bindings", headers=superuser_headers, json={'source_type':'order','source_id':order['id']})
    engagement = SRMEngagement(organization_id=1, sales_order_id=order['id'], engagement_number='SVC-TEST', name='Test service', status='in_progress', planned_end_date=service.now().astimezone(__import__('zoneinfo').ZoneInfo('Asia/Kolkata')).date())
    db.add(engagement)
    # Branch ownership for the fixture is inherited from its real order.
    db.flush()
    from app.branches.models import BranchOwnership
    branch_id = db.query(CustomerRecipient).first().branch_id
    db.add(BranchOwnership(resource_table=engagement.__tablename__, resource_key=str(engagement.id), company_id=1, branch_id=branch_id, source='synthetic-test'))
    db.commit()
    # Both a direct service link and its parent order must still produce one
    # message per step, even before the current transaction has flushed.
    result = client.post(BASE+f"/recipients/{r['id']}/bindings", headers=superuser_headers, json={'source_type':'service','source_id':engagement.id})
    assert result.status_code == 201, result.text
    rule(client, superuser_headers, trigger='service.due', subject='Service {{reference}}', body='Due {{due_date}}', steps=[0, 60])
    assert service.schedule_due(db) == 2
    assert service.schedule_due(db) == 0
    row = db.query(CustomerDelivery).first()
    engagement.planned_end_date += timedelta(days=1)
    db.commit()
    assert service.check_delivery(db, row)[0] == 'cancelled'


def test_email_credentials_encrypted_and_tenant_scoped(client, db, superuser_headers):
    from app.apps.communication.customer_models import CustomerEmailConnection
    payload = {'host':'smtp.example.com', 'port':587, 'username':'synthetic', 'password':'synthetic-secret', 'from_email':'sender@example.com', 'from_name':'Synthetic business'}
    response = client.put(BASE+'/email-connection', headers=superuser_headers, json=payload)
    assert response.status_code == 200, response.text
    row = db.query(CustomerEmailConnection).one()
    assert row.password_ciphertext.startswith('enc:')
    assert 'synthetic-secret' not in row.password_ciphertext
    result = client.get(BASE+'/email-connection', headers=superuser_headers)
    assert result.status_code == 200
    assert 'password' not in result.text and 'ciphertext' not in result.text


def test_marketing_unsubscribe_link_and_provider_throttle_retry(client, db, superuser_headers, monkeypatch):
    import smtplib
    r = recipient(client, superuser_headers)
    automation = rule(client, superuser_headers, trigger='campaign', purpose='marketing', subject='Hello {{name}}', body='Synthetic campaign')
    client.post(BASE+f"/automations/{automation['id']}/launch", headers=superuser_headers, json={})
    monkeypatch.setattr('app.core.email.email_configured', lambda: True)
    service.process_customer_communications(db)
    row = db.query(CustomerDelivery).one()
    outbox = db.get(EmailOutbox, row.email_outbox_id)
    assert outbox is not None, (row.status, row.error)
    assert '/public/customer-preferences/' in outbox.body
    send = Mock(side_effect=smtplib.SMTPDataError(451, b'temporary rejection'))
    monkeypatch.setattr('app.core.email.send_email', send)
    from app.services.email_dispatch import drain_outbox
    drain_outbox(db)
    db.refresh(row)
    assert row.status == 'retry_wait'
    assert service.utc(row.due_at) > service.now()
    send.assert_called_once()
    service.process_customer_communications(db)
    drain_outbox(db)
    send.assert_called_once()


def test_automation_edit_cancels_old_version_and_invalid_schedule(client, db, superuser_headers):
    recipient(client, superuser_headers)
    automation = rule(client, superuser_headers, trigger='campaign', purpose='marketing', subject='Hello {{name}}', body='Hello')
    path = BASE+f"/automations/{automation['id']}"
    assert client.post(path+'/launch', headers=superuser_headers, json={'scheduled_at':'2027-01-01T10:00:00'}).status_code == 422
    client.post(path+'/launch', headers=superuser_headers, json={})
    row = db.query(CustomerDelivery).one()
    response = client.put(path, headers=superuser_headers, json={**automation, 'status':'paused'})
    assert response.status_code == 200, response.text
    assert service.check_delivery(db, row)[0] == 'cancelled'


def test_signed_email_replies_dedup_and_stop_followups(client, db, superuser_headers):
    import json, time, hashlib, hmac
    from app.apps.communication.customer_models import CustomerEmailReply
    r = recipient(client, superuser_headers)
    automation = rule(client, superuser_headers, trigger='campaign', purpose='marketing', subject='Hello {{name}}', body='Synthetic campaign')
    client.post(BASE+f"/automations/{automation['id']}/launch", headers=superuser_headers, json={})
    data = {'host':'smtp.example.com', 'port':587, 'username':'synthetic', 'password':'synthetic-secret', 'from_email':'sender@example.com', 'from_name':'Synthetic business'}
    assert client.put(BASE+'/email-connection', headers=superuser_headers, json=data).status_code == 200
    result = client.post(BASE+'/email-connection/receiver-secret', headers=superuser_headers)
    assert result.status_code == 200, result.text
    secret = result.json()['secret']
    delivery = db.query(CustomerDelivery).one()
    outbox = EmailOutbox(organization_id=1, module='customer_communication', recipient=r['email'],
        event_key='synthetic-inbound-thread', subject='Test', body='Test', status='accepted', provider_message_id='<synthetic@example.com>')
    db.add(outbox); db.flush(); delivery.email_outbox_id = outbox.id; db.commit()
    payload = {'event_id':'synthetic-reply-1', 'in_reply_to':outbox.provider_message_id, 'from_email':r['email'],
        'to_email':'sender@example.com', 'subject':'Re: test', 'body':'Please contact me', 'authenticated_sender':True}
    raw = json.dumps(payload).encode()
    timestamp = str(int(time.time()))
    signature = 'sha256='+hmac.new(secret.encode(), timestamp.encode()+b'.'+raw, hashlib.sha256).hexdigest()
    headers = {'X-BusinessSuite-Timestamp':timestamp, 'X-BusinessSuite-Signature':signature, 'Content-Type':'application/json'}
    path = '/api/v1/integrations/customer-email/1'
    assert client.post(path, content=raw, headers={**headers,'X-BusinessSuite-Signature':'sha256=wrong'}).status_code == 401
    response = client.post(path, content=raw, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['duplicate'] is False
    assert client.post(path, content=raw, headers=headers).json()['duplicate'] is True
    assert db.query(CustomerEmailReply).count() == 1
    history = client.get(BASE+f"/recipients/{r['id']}/history", headers=superuser_headers)
    assert history.status_code == 200, history.text
    assert history.json()['email_replies'][0]['body'] == 'Please contact me'
    assert history.json()['unread_email_count'] == 1
    assert service.check_delivery(db, delivery)[0] == 'cancelled'
    assert client.post(BASE+f"/recipients/{r['id']}/read", headers=superuser_headers).status_code == 200
    assert client.get(BASE+f"/recipients/{r['id']}/history", headers=superuser_headers).json()['unread_email_count'] == 0


def test_whatsapp_customer_consent_uses_canonical_phone(client, db, superuser_headers):
    from app.shared.whatsapp_models import WhatsAppContact
    customer = recipient(client, superuser_headers, phone='+919876543210', preferences={'whatsapp.transactional':True})
    contact = db.query(WhatsAppContact).filter_by(organization_id=1, recipient='919876543210').one()
    assert contact.consent == 'opted_in'
    result = client.put(BASE+f"/recipients/{customer['id']}", headers=superuser_headers, json={**customer, 'preferences':{'whatsapp.transactional':False}})
    assert result.status_code == 200, result.text
    db.refresh(contact)
    assert contact.consent == 'opted_out'


def test_existing_service_followup_generates_customer_reminder(client, db, superuser_headers):
    from tests.srm_test_utils import create_sales_order
    from app.shared.follow_ups import FollowUp
    from app.apps.crm.models import CRMCompany
    r = recipient(client, superuser_headers)
    from app.models.user import User
    from test_identity_utils import attach_test_identity
    attach_test_identity(db, db.get(User, r['created_by']), 1)
    db.commit()
    order = create_sales_order(client, superuser_headers)
    assert client.post(BASE+f"/recipients/{r['id']}/bindings", headers=superuser_headers, json={'source_type':'order','source_id':order['id']}).status_code == 201
    with service.actor_scope(db, r['created_by'], 1, r['branch_id']):
        customer = CRMCompany(organization_id=1, branch_id=r['branch_id'], name='Synthetic service customer')
        db.add(customer); db.flush()
        follow_up = FollowUp(organization_id=1, customer_id=customer.id, order_id=order['id'],
            assigned_user_id=r['created_by'], created_by=r['created_by'], title='Pending maintenance', due_at=service.now(), status='Scheduled')
        db.add(follow_up); db.commit()
    rule(client, superuser_headers, trigger='follow_up.due', subject='Service {{reference}}', body='Due {{due_date}}')
    assert service.schedule_due(db) == 1
    delivery = db.query(CustomerDelivery).one()
    assert delivery.source_type == 'follow_up'
    follow_up.status = 'Completed'; db.commit()
    assert service.check_delivery(db, delivery)[0] == 'cancelled'


def test_ordinary_sender_permissions_and_background_revocation(client, db, monkeypatch):
    # Production worker rollbacks must not roll back this fixture's enclosing
    # transaction; each committed worker transaction gets its own savepoint.
    db.join_transaction_mode = 'create_savepoint'
    from tests.communication_test_utils import communication_headers
    from app.access.models import AccessPolicy
    from app.models.user import User
    viewer = communication_headers(client, db, email='viewer-comms@example.com', permissions=['communication_view'])
    assert client.get(BASE+'/recipients', headers=viewer).status_code == 200
    assert client.post(BASE+'/recipients', headers=viewer, json={'name':'Blocked', 'email':'blocked@example.com', 'consent_source':'test'}).status_code == 403
    headers = communication_headers(client, db, email='sender-comms@example.com')
    r = recipient(client, headers)
    automation = rule(client, headers, trigger='campaign', purpose='marketing', subject='Hello {{name}}', body='Synthetic campaign')
    response = client.post(BASE+f"/automations/{automation['id']}/launch", headers=headers, json={})
    assert response.status_code == 200, response.text
    monkeypatch.setattr('app.core.email.email_configured', lambda: True)
    service.process_customer_communications(db)
    delivery = db.query(CustomerDelivery).one()
    assert delivery.email_outbox_id, (delivery.status, delivery.error)
    user = db.query(User).filter_by(email='sender-comms@example.com').one()
    policy = db.query(AccessPolicy).filter_by(user_id=user.id, company_id=1).one()
    policy.grants = {}
    db.commit()
    send = Mock(return_value='must-not-send')
    monkeypatch.setattr('app.core.email.send_email', send)
    from app.services.email_dispatch import drain_outbox
    drain_outbox(db)
    db.refresh(delivery)
    assert delivery.status == 'blocked'
    send.assert_not_called()


def test_definitive_rejection_can_be_retried_but_unknown_cannot(client, db, superuser_headers, monkeypatch):
    import smtplib
    recipient(client, superuser_headers)
    automation = rule(client, superuser_headers, trigger='campaign', purpose='marketing', subject='Hello {{name}}', body='Synthetic campaign')
    client.post(BASE+f"/automations/{automation['id']}/launch", headers=superuser_headers, json={})
    monkeypatch.setattr('app.core.email.email_configured', lambda: True)
    monkeypatch.setattr('app.core.email.send_email', Mock(side_effect=smtplib.SMTPDataError(550, b'rejected')))
    service.process_customer_communications(db)
    from app.services.email_dispatch import drain_outbox
    drain_outbox(db)
    delivery = db.query(CustomerDelivery).one()
    assert delivery.status == 'failed'
    response = client.post(BASE+f'/deliveries/{delivery.id}/retry', headers=superuser_headers)
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'retry_wait'
    sender = Mock(return_value='synthetic-retry-accepted')
    monkeypatch.setattr('app.core.email.send_email', sender)
    service.process_customer_communications(db)
    drain_outbox(db)
    db.refresh(delivery)
    assert delivery.status == 'accepted'
    sender.assert_called_once()
    assert client.post(BASE+f'/deliveries/{delivery.id}/retry', headers=superuser_headers).status_code == 409


def test_pause_after_queue_does_not_consume_provider_attempts(client, db, superuser_headers, monkeypatch):
    recipient(client, superuser_headers)
    automation = rule(client, superuser_headers, trigger='campaign', purpose='marketing', subject='Hello {{name}}', body='Synthetic campaign')
    client.post(BASE+f"/automations/{automation['id']}/launch", headers=superuser_headers, json={})
    monkeypatch.setattr('app.core.email.email_configured', lambda: True)
    sender = Mock(return_value='synthetic-pause-accepted')
    monkeypatch.setattr('app.core.email.send_email', sender)
    service.process_customer_communications(db)
    assert client.put(BASE+'/settings', headers=superuser_headers, json={'paused':True}).status_code == 200
    from app.services.email_dispatch import drain_outbox
    assert drain_outbox(db)['processed'] == 1
    delivery = db.query(CustomerDelivery).one()
    outbox = db.get(EmailOutbox, delivery.email_outbox_id)
    assert outbox.status == 'retry_wait' and outbox.attempts == 0
    assert drain_outbox(db)['processed'] == 0
    sender.assert_not_called()
    client.put(BASE+'/settings', headers=superuser_headers, json={'paused':False})
    delivery.due_at = service.now()-timedelta(seconds=1); db.commit()
    service.process_customer_communications(db)
    drain_outbox(db)
    sender.assert_called_once()
