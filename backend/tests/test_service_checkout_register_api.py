"""Native register summaries and closing use the actual collection register."""
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.apps.srm.models import SRMPOSSession, SRMSalesOrder, SRMReceipt, SRMPOSCashierClosing
from app.apps.srm.service_checkout import checkout, append_payment
from app.apps.srm.service_checkout_models import POSCheckoutPayment
from app.apps.srm.service_checkout_schemas import AppendPaymentInput
from tests.test_service_checkout import scenario
from tests.test_srm_native_transaction_operations import native_writer
from tests.test_business_suite_pos_integrity import catalog
from tests.test_contact_directory import directory_identity


def test_native_summary_counts_cash_receipts_once_and_closes_correctly(client, db, scenario):
    actor, branch, catalog_data, basket = scenario
    data = basket()
    with native_writer(db, actor, branch):
        result = checkout(data, db, actor)
        order = db.get(SRMSalesOrder, result['sales_order_id'])
        order.metadata_json = {**order.metadata_json, 'payment_mode': 'Split'}
        db.commit()
    summaries = client.get('/api/v1/srm/pos/sessions', headers=catalog_data[0])
    assert summaries.status_code == 200, summaries.text
    register = next(row for row in summaries.json() if row['session']['id'] == data.pos_session_id)
    assert register['sales_count'] == 1
    assert register['cash_sales'] == register['expected_cash'] == 100
    assert register['unattributed_cash_count'] == 0 and not register['reconciliation_required']
    closed = client.post('/api/v1/srm/pos/cashier-closing', headers=catalog_data[0],
                         json={'session_id': data.pos_session_id, 'counted_cash': '100'})
    assert closed.status_code == 201, closed.text
    assert Decimal(str(closed.json()['closing']['variance'])) == 0


def test_later_collection_appears_in_new_register_without_rewriting_closed_cash(client, db, scenario):
    actor, branch, catalog_data, basket = scenario
    data = basket()
    with native_writer(db, actor, branch):
        result = checkout(data, db, actor)
    closed = client.post('/api/v1/srm/pos/cashier-closing', headers=catalog_data[0],
                         json={'session_id': data.pos_session_id, 'counted_cash': '100'})
    assert closed.status_code == 201, closed.text
    with native_writer(db, actor, branch):
        next_register = SRMPOSSession(organization_id=1, session_number='NEXT-' + uuid4().hex,
            cashier_user_id=actor.id, created_by=actor.id, status='open', opening_cash=0)
        db.add(next_register); db.commit()
        append_payment(result['id'], AppendPaymentInput(expected_revision=result['revision'],
            pos_session_id=next_register.id, payment={'payment_key': str(uuid4()), 'method': 'cash', 'amount': '30'}), db, actor)
    summaries = client.get('/api/v1/srm/pos/sessions', headers=catalog_data[0])
    assert summaries.status_code == 200, summaries.text
    by_id = {row['session']['id']: row for row in summaries.json()}
    assert by_id[data.pos_session_id]['cash_sales'] == 100
    assert by_id[next_register.id]['cash_sales'] == 30
    assert by_id[next_register.id]['sales_count'] == 0
    assert Decimal(str(by_id[data.pos_session_id]['closing']['expected_cash'])) == 100


def test_unattributed_historical_cash_cannot_silently_close_or_change_money(client, db, scenario):
    actor, branch, catalog_data, basket = scenario
    data = basket()
    with native_writer(db, actor, branch):
        checkout(data, db, actor)
    receipts_before = db.connection().execute(select(SRMReceipt.id, SRMReceipt.amount, SRMReceipt.status)).all()
    payment = POSCheckoutPayment.__table__
    cash_ids = select(SRMReceipt.id).where(SRMReceipt.payment_method == 'cash')
    # Simulate an intentionally unassigned historical mapping after migration104.
    db.connection().execute(payment.update().where(payment.c.receipt_id.in_(cash_ids)).values(collection_session_id=None))
    db.commit()
    summaries = client.get('/api/v1/srm/pos/sessions', headers=catalog_data[0])
    assert summaries.status_code == 200, summaries.text
    register = next(row for row in summaries.json() if row['session']['id'] == data.pos_session_id)
    assert register['reconciliation_required'] and register['unattributed_cash_count'] == 1
    assert register['cash_sales'] == 0
    closed = client.post('/api/v1/srm/pos/cashier-closing', headers=catalog_data[0],
                         json={'session_id': data.pos_session_id, 'counted_cash': '100'})
    assert closed.status_code == 409, closed.text
    assert db.get(SRMPOSSession, data.pos_session_id).status == 'open'
    assert db.query(SRMPOSCashierClosing).count() == 0
    assert db.connection().execute(select(SRMReceipt.id, SRMReceipt.amount, SRMReceipt.status)).all() == receipts_before
