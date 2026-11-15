"""Grouped POS visits never collect or invoice the whole basket independently."""
from decimal import Decimal
from uuid import uuid4

from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.models import SRMInvoice, SRMReceipt
from app.apps.srm.service_checkout import checkout
from tests.test_service_checkout import scenario
from tests.test_srm_native_transaction_operations import native_writer
from tests.test_business_suite_pos_integrity import catalog
from tests.test_contact_directory import directory_identity


def test_group_visits_read_service_charge_and_one_checkout_invoice(client, db, scenario):
    actor, branch, catalog_data, basket = scenario
    with native_writer(db, actor, branch):
        result = checkout(basket(), db, actor)
    visits = [line for line in result['lines'] if line['appointment_id']]
    for line in visits:
        response = client.get(f'/api/v1/srm/industry/appointments/{line["appointment_id"]}/billing', headers=catalog_data[0])
        assert response.status_code == 200, response.text
        panel = response.json()
        assert panel['group_checkout']['id'] == result['id']
        assert Decimal(panel['group_checkout']['service_charge']) == Decimal(line['total'])
        assert Decimal(panel['checkout']['invoice']['total']) == 354
        assert 'total' not in panel  # Never label the group total as this visit's charge.
        assert db.get(IndustryRecord, line['appointment_id']).invoice_id is None


def test_standalone_collection_advance_and_invoice_paths_reject_group_visits(client, db, scenario):
    actor, branch, catalog_data, basket = scenario
    with native_writer(db, actor, branch):
        result = checkout(basket(), db, actor)
    ident = next(line['appointment_id'] for line in result['lines'] if line['appointment_id'])
    headers = catalog_data[0]
    row = db.get(IndustryRecord, ident)
    revision = row.revision
    for status in ['checked_in', 'in_service', 'completed']:
        changed = client.post(f'/api/v1/srm/industry/records/{ident}/transition', headers=headers,
                              json={'expected_revision': revision, 'status': status})
        assert changed.status_code == 200, changed.text
        revision = changed.json()['revision']
    invoices, receipts = db.query(SRMInvoice).count(), db.query(SRMReceipt).count()
    payloads = [
        (f'/api/v1/srm/industry/appointments/{ident}/payments', {'request_id': str(uuid4()), 'expected_revision': revision, 'amount': '1', 'payment_method': 'cash'}),
        (f'/api/v1/srm/industry/appointments/{ident}/apply-advances', {'expected_revision': revision}),
        (f'/api/v1/srm/industry/records/{ident}/invoice', {'expected_revision': revision}),
    ]
    for path, payload in payloads:
        rejected = client.post(path, headers=headers, json=payload)
        assert rejected.status_code == 409, rejected.text
        assert 'linked checkout' in rejected.json()['detail']
    assert db.query(SRMInvoice).count() == invoices
    assert db.query(SRMReceipt).count() == receipts
