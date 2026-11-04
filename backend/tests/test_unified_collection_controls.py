from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.apps.srm.models import SRMInvoice, SRMReceipt, SRMReceiptAllocation
from app.apps.srm.services.collections import reminder_block_reason
from tests.srm_test_utils import seed_invoice_parties, create_sales_order


def issued_invoice(client, db, headers):
    seed_invoice_parties(db)
    order = create_sales_order(client, headers)
    response = client.post(f"/api/v1/srm/invoices/draft-from-sales-order/{order['id']}", headers=headers)
    assert response.status_code == 201, response.text
    invoice = response.json()
    response = client.post(f"/api/v1/srm/invoices/{invoice['id']}/approve", headers=headers)
    assert response.status_code == 200, response.text
    return invoice


def test_advance_allocation_retry_conflict_and_partial_balance(client, db, superuser_headers):
    headers = superuser_headers
    invoice = issued_invoice(client, db, headers)
    response = client.post('/api/v1/srm/receipts', headers=headers,
        json={'customer_id': 101, 'currency': 'INR', 'amount': '80000.00'})
    assert response.status_code == 201, response.text
    receipt = response.json()
    path = f"/api/v1/srm/receipts/{receipt['id']}/allocate"
    payload = {'invoice_id': invoice['id'], 'amount': '30000.00', 'request_id': str(uuid4())}
    first = client.post(path, headers=headers, json=payload)
    assert first.status_code == 200, first.text
    retried = client.post(path, headers=headers, json=payload)
    assert retried.status_code == 200, retried.text
    assert first.json()['allocation']['id'] == retried.json()['allocation']['id']
    assert db.query(SRMReceiptAllocation).count() == 1
    db.expire_all()
    assert db.get(SRMInvoice, invoice['id']).paid_amount == Decimal('30000.00')
    assert db.get(SRMReceipt, receipt['id']).unallocated_amount == Decimal('50000.00')
    assert client.post(path, headers=headers, json={**payload, 'amount': '1.00'}).status_code == 409
    assert client.post(path, headers=headers, json={**payload, 'amount': '0.001', 'request_id': str(uuid4())}).status_code == 422
    row = db.get(SRMReceipt, receipt['id'])
    row.status = 'cancelled'
    db.commit()
    assert client.post(path, headers=headers, json={**payload, 'request_id': str(uuid4())}).status_code == 409


def test_dispute_hold_blocks_manual_reminders_and_audits_resume(client, db, superuser_headers):
    invoice = issued_invoice(client, db, superuser_headers)
    path = f"/api/v1/srm/collections/{invoice['id']}/control"
    result = client.put(path, headers=superuser_headers, json={'hold': True, 'reason': 'Customer disputes quantity'})
    assert result.status_code == 200, result.text
    assert result.json()['collection_hold'] is True
    blocked = client.post('/api/v1/srm/collections/reminders/send', headers=superuser_headers,
        json={'invoice_id': invoice['id']})
    assert blocked.status_code == 409, blocked.text
    result = client.put(path, headers=superuser_headers, json={'hold': False, 'reason': 'Accounts resolved dispute'})
    assert result.status_code == 200, result.text
    db.expire_all()
    assert reminder_block_reason(db.get(SRMInvoice, invoice['id'])) is None
    from app.apps.srm.models import SRMInvoiceHistory
    assert db.query(SRMInvoiceHistory).filter(SRMInvoiceHistory.notes.like('Collections %')).count() == 2
    assert client.put(path, headers=superuser_headers, json={'hold': True, 'reason': 'Pause', 'resume_at': '2020-01-01T00:00:00Z'}).status_code == 422


def test_queued_reminder_rechecks_hold_billing_role_and_settlement(client, db, superuser_headers):
    from app.apps.communication.customer_models import CustomerDelivery, CustomerRecipient
    from app.apps.communication.customer_service import check_delivery
    invoice = issued_invoice(client, db, superuser_headers)
    recipient = client.post('/api/v1/communication/customers/recipients', headers=superuser_headers, json={
        'name': 'Synthetic accounts contact', 'email': 'accounts@example.com', 'role': 'billing',
        'consent_source': 'Test opt-in', 'preferences': {'email.transactional': True}})
    assert recipient.status_code == 201, recipient.text
    rid = recipient.json()['id']
    bound = client.post(f'/api/v1/communication/customers/recipients/{rid}/bindings', headers=superuser_headers,
        json={'source_type': 'invoice', 'source_id': invoice['id']})
    assert bound.status_code == 201, bound.text
    response = client.post('/api/v1/srm/collections/reminders/send', headers=superuser_headers, json={'invoice_id': invoice['id']})
    assert response.status_code == 200, response.text
    row = db.query(CustomerDelivery).one()
    assert check_delivery(db, row) == (None, None)
    held = client.put(f"/api/v1/srm/collections/{invoice['id']}/control", headers=superuser_headers,
        json={'hold': True, 'reason': 'Invoice disputed'})
    assert held.status_code == 200, held.text
    db.expire_all()
    assert check_delivery(db, row)[0] == 'defer'
    client.put(f"/api/v1/srm/collections/{invoice['id']}/control", headers=superuser_headers,
        json={'hold': False, 'reason': 'Dispute resolved'})
    db.expire_all()
    assert check_delivery(db, row) == (None, None)
    db.get(CustomerRecipient, rid).role = 'purchasing'
    db.flush()
    assert check_delivery(db, row)[0] == 'blocked'
    db.get(CustomerRecipient, rid).role = 'billing'
    obj = db.get(SRMInvoice, invoice['id'])
    obj.status, obj.balance_amount = 'paid', Decimal('0')
    db.flush()
    assert check_delivery(db, row)[0] == 'cancelled'


def test_collection_control_requires_permission_and_scoped_invoice(client, db, superuser_headers):
    from fastapi import HTTPException
    from app.apps.srm.payments import collection_control, CollectionControlInput
    from app.models.user import User
    invoice = issued_invoice(client, db, superuser_headers)
    data = CollectionControlInput(hold=True, reason='Dispute review')
    unauthorized = SimpleNamespace(is_superuser=False, permissions=[], role=None)
    with pytest.raises(HTTPException) as error:
        collection_control(invoice['id'], data, db, unauthorized)
    assert error.value.status_code == 403
    user = db.query(User).filter_by(email='testadmin@test.com').one()
    outsider = SimpleNamespace(is_superuser=True, organization_id=2, id=user.id, role=None)
    with pytest.raises(HTTPException) as error:
        collection_control(invoice['id'], data, db, outsider)
    assert error.value.status_code == 404


@pytest.mark.parametrize('status,balance,hold,offset,blocked', [
    ('draft', '100', False, None, True),
    ('pending_approval', '100', False, None, True),
    ('paid', '0', False, None, True),
    ('issued', '0', False, None, True),
    ('partially_paid', '50000', False, None, False),
    ('overdue', '50000', True, None, True),
    ('issued', '100', True, 60, True),
    ('issued', '100', True, -60, False),
])
def test_shared_reminder_eligibility(status, balance, hold, offset, blocked):
    at = datetime.now(timezone.utc)
    invoice = SimpleNamespace(deleted_at=None, status=status, balance_amount=Decimal(balance),
        collection_hold=hold, collection_resume_at=at+timedelta(seconds=offset) if offset else None)
    assert bool(reminder_block_reason(invoice, at)) is blocked


def test_collection_migration_preserves_rows_and_is_repeatable():
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.apps.srm import collection_schema
    engine = sa.create_engine('sqlite://')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE srm_invoices (id INTEGER PRIMARY KEY, total_amount NUMERIC)')
        connection.exec_driver_sql('CREATE TABLE srm_receipt_allocations (id INTEGER PRIMARY KEY, receipt_id INTEGER, amount NUMERIC)')
        connection.exec_driver_sql('INSERT INTO srm_invoices VALUES (1, 80000)')
        connection.exec_driver_sql('INSERT INTO srm_receipt_allocations VALUES (1, 1, 30000)')
        op = Operations(MigrationContext.configure(connection))
        collection_schema.upgrade(op)
        collection_schema.upgrade(op)
        assert connection.exec_driver_sql('SELECT total_amount, collection_hold FROM srm_invoices').one() == (80000, 0)
        assert connection.exec_driver_sql('SELECT amount, request_id FROM srm_receipt_allocations').one() == (30000, None)
        collection_schema.downgrade(op)
        assert connection.exec_driver_sql('SELECT amount FROM srm_receipt_allocations').scalar() == 30000
