"""Independent deferred SQL proof: no ORM outer before_commit call."""
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
import pytest

from app.apps.srm.models import SRMPOSSession, SRMInvoice, SRMReceipt, SRMReceiptAllocation
from app.business_packs.restaurant.models import RestaurantServiceOrder
from app.business_packs.restaurant.split_models import RestaurantBillReceipt
from app.business_packs.restaurant.split_bills import pay
from app.business_packs.restaurant.split_schemas import SplitPayment
from app.models.user import User
from tests.test_restaurant_split_concurrency import live, prepared, split_input, BASE
from tests.test_restaurant_split_bills import selected


def test_raw_connection_commit_rejects_late_register_mutations_without_session_guard(live):
    headers, order_id, whole = prepared(live)
    issued = live.client.post(BASE+f'/tabs/{order_id}/bills', headers=headers, json=split_input(live, headers, order_id, whole))
    assert issued.status_code == 201, issued.text
    bill = issued.json()
    initial = live.client.post(BASE+f"/tabs/{order_id}/bills/{bill['bill_id']}/payments", headers=headers, json={
        'request_key': str(uuid4()), 'expected_revision': bill['order_revision'], 'expected_balance': '59',
        'pos_session_id': whole['pos_session_id'], 'payment': {'payment_key': str(uuid4()), 'method': 'cash', 'amount': '10'}})
    assert initial.status_code == 201, initial.text
    revision = initial.json()['order_revision']
    for fault in ('close', 'reassign', 'delete', 'currency', 'shared'):
        with live.engine.connect() as connection:
            transaction = connection.begin()
            factory = sessionmaker(bind=connection, autoflush=False, join_transaction_mode='rollback_only')
            db = factory()
            outer_orm_commits = []
            def observed(session):
                if not session.in_nested_transaction(): outer_orm_commits.append(True)
            event.listen(db, 'before_commit', observed)
            try:
                parent = db.get(RestaurantServiceOrder, order_id)
                actor = db.get(User, parent.created_by)
                # Match the verified company binding normally supplied by the
                # HTTP authentication dependency for this direct service call.
                actor.organization_id = parent.organization_id
                other = connection.scalar(select(User.id).where(User.id != actor.id).limit(1))
                assert other is not None
                case = {'manager': actor, 'branch': parent.branch_id, 'context': parent.pack_context_id}
                with selected(db, case):
                    result = pay(order_id, bill['bill_id'], SplitPayment.model_validate({
                        'request_key': str(uuid4()), 'expected_revision': revision, 'expected_balance': '49',
                        'pos_session_id': whole['pos_session_id'], 'payment': {'payment_key': str(uuid4()), 'method': 'cash', 'amount': '20'}}),
                        db, actor, commit=False)
                    assert Decimal(result['bill']['balance']) == 29
                    register = SRMPOSSession.__table__
                    with pytest.raises(IntegrityError) as denied:
                        if fault == 'delete':
                            connection.execute(register.delete().where(register.c.id == whole['pos_session_id']))
                        else:
                            values = {'close': {'status': 'closed'}, 'reassign': {'cashier_user_id': other},
                                'currency': {'metadata_json': {'cash_currency': 'USD'}}, 'shared': {'cashier_user_id': None}}[fault]
                            connection.execute(register.update().where(register.c.id == whole['pos_session_id']).values(**values))
                        # Deliberately bypass only the Session listener in this
                        # isolated owned test. Production guards stay installed.
                        connection.commit()
                    state = getattr(denied.value.orig, 'sqlstate', None) or getattr(denied.value.orig, 'pgcode', None)
                    if fault == 'delete':
                        assert state == '23503'
                    else:
                        assert state == '23514'
                        assert 'Restaurant collection register/source changed before commit' in str(denied.value.orig)
                    assert outer_orm_commits == []
            finally:
                event.remove(db, 'before_commit', observed)
                db.rollback(); db.close()
                if transaction.is_active: transaction.rollback()
        with live.factory() as check:
            assert check.query(SRMReceipt).count() == check.query(SRMReceiptAllocation).count() == check.query(RestaurantBillReceipt).count() == 1
            invoice = check.get(SRMInvoice, bill['invoice_id'])
            register = check.get(SRMPOSSession, whole['pos_session_id'])
            assert invoice.paid_amount == 10 and invoice.balance_amount == 49
            assert register.status == 'open' and register.cashier_user_id is not None and register.metadata_json['cash_currency'] == 'INR'
        summary = live.client.get('/api/v1/srm/pos/sessions', headers=headers)
        assert summary.status_code == 200, summary.text
        active = next(row for row in summary.json() if row['session']['id'] == whole['pos_session_id'])
        assert Decimal(str(active['cash_sales'])) == 10
