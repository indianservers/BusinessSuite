from decimal import Decimal
from uuid import uuid4
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer
from app.apps.srm.service_checkout import checkout, append_payment
from app.apps.srm.service_checkout_schemas import AppendPaymentInput
from app.apps.srm.service_checkout_register import group_register_cash
from app.apps.srm.service_checkout_models import POSCheckoutPayment, POSServiceCheckout
from app.apps.srm.models import SRMPOSSession, SRMReceipt, SRMSalesOrder
from app.branches.models import BranchOwnership
from app.business_packs.models import PackActivation, PackContext, PackRecordOwnership


def test_cash_is_actual_receipts_not_basket_or_split_metadata(db, scenario):
    user, branch, catalog, basket = scenario
    with native_writer(db, user, branch):
        result = checkout(basket(), db, user)
        root = db.get(POSServiceCheckout, result['id'])
        session = db.get(SRMPOSSession, root.pos_session_id)
        orders = db.query(SRMSalesOrder).all()
        orders[0].metadata_json = {**(orders[0].metadata_json or {}), 'payment_mode': 'Split'}
        db.flush()
        cash = group_register_cash(db, session, orders)
        assert cash == {'group_order_ids': {orders[0].id}, 'cash_received': Decimal('100'), 'unattributed_cash_count': 0}
        card = db.query(SRMReceipt).filter_by(payment_method='card').one()
        card.status = 'cancelled'; db.flush()
        assert group_register_cash(db, session, orders)['cash_received'] == 100
        actual = db.query(SRMReceipt).filter_by(payment_method='cash').one()
        actual.status = 'cancelled'; db.flush()
        assert group_register_cash(db, session, orders)['cash_received'] == 0


def test_ambiguous_historical_cash_warns_without_inventing_cash(db, scenario):
    user, branch, catalog, basket = scenario
    with native_writer(db, user, branch):
        result = checkout(basket(), db, user)
        root = db.get(POSServiceCheckout, result['id'])
        session = db.get(SRMPOSSession, root.pos_session_id)
        db.connection().execute(POSCheckoutPayment.__table__.update().values(collection_session_id=None))
        cash = group_register_cash(db, session, db.query(SRMSalesOrder).all())
        assert cash['cash_received'] == 0 and cash['unattributed_cash_count'] == 1


def test_corrupt_source_branch_fails_closed(db, scenario):
    user, branch, catalog, basket = scenario
    with native_writer(db, user, branch):
        result = checkout(basket(), db, user)
        root = db.get(POSServiceCheckout, result['id'])
        session = db.get(SRMPOSSession, root.pos_session_id)
        db.connection().execute(BranchOwnership.__table__.delete().where(BranchOwnership.resource_table == POSCheckoutPayment.__tablename__))
        with pytest.raises(HTTPException) as error:
            group_register_cash(db, session, db.query(SRMSalesOrder).all())
        assert error.value.status_code == 503


def test_no_group_checkout_leaves_legacy_order_untouched(db, scenario):
    user, branch, catalog, basket = scenario
    with native_writer(db, user, branch):
        session = db.query(SRMPOSSession).one()
        db.connection().execute(BranchOwnership.__table__.delete().where(BranchOwnership.resource_table == SRMPOSSession.__tablename__))
        assert group_register_cash(db, session, []) == {'group_order_ids': set(), 'cash_received': Decimal('0'), 'unattributed_cash_count': 0}


def test_source_anchored_to_pack_cannot_leak_into_legacy_register_summary(db, scenario):
    user, branch, catalog, basket = scenario
    with native_writer(db, user, branch):
        result = checkout(basket(), db, user)
        root = db.get(POSServiceCheckout, result['id'])
        session = db.get(SRMPOSSession, root.pos_session_id)
        activation = PackActivation(company_id=1, pack_key='hospital', state='active')
        db.add(activation); db.flush()
        context = PackContext(company_id=1, branch_id=branch, activation_id=activation.id, pack_key='hospital', pack_version=1, state='active')
        db.add(context); db.flush()
        receipt = db.query(SRMReceipt).first()
        db.add(PackRecordOwnership(company_id=1, branch_id=branch, context_id=context.id,
            resource_table=SRMReceipt.__tablename__, resource_key=str(receipt.id)))
        db.flush()
        with pytest.raises(HTTPException) as error:
            group_register_cash(db, session, db.query(SRMSalesOrder).all())
        assert error.value.status_code == 503


def test_old_schema_legacy_and_partial_schema_with_data_fail_closed():
    engine = create_engine('sqlite://')
    with Session(engine) as db:
        session = SimpleNamespace(id=1, organization_id=1)
        assert group_register_cash(db, session, [])['cash_received'] == 0
        db.connection().exec_driver_sql('CREATE TABLE srm_pos_service_checkouts (id INTEGER PRIMARY KEY)')
        assert group_register_cash(db, session, [])['group_order_ids'] == set()
        db.connection().exec_driver_sql('INSERT INTO srm_pos_service_checkouts VALUES (1)')
        with pytest.raises(HTTPException) as error:
            group_register_cash(db, session, [])
        assert error.value.status_code == 503
    engine.dispose()


def test_later_payment_counts_only_actual_new_register(db, scenario):
    user, branch, catalog, basket = scenario
    with native_writer(db, user, branch):
        result = checkout(basket(), db, user)
        root = db.get(POSServiceCheckout, result['id'])
        old = db.get(SRMPOSSession, root.pos_session_id)
        old.status = 'closed'
        new = SRMPOSSession(organization_id=1, session_number='LATER-' + uuid4().hex,
            status='open', created_by=user.id, cashier_user_id=user.id)
        db.add(new); db.commit()
        append_payment(root.id, AppendPaymentInput.model_validate({'expected_revision': root.revision,
            'pos_session_id': new.id, 'payment': {'payment_key': str(uuid4()), 'method': 'cash', 'amount': '30'}}), db, user)
        orders = db.query(SRMSalesOrder).all()
        assert group_register_cash(db, old, orders)['cash_received'] == 100
        assert group_register_cash(db, new, orders)['cash_received'] == 30


@pytest.mark.parametrize('case', ['receipt_company', 'receipt_currency', 'receipt_customer', 'root_currency'])
def test_corrupt_native_links_are_not_counted(db, scenario, case):
    user, branch, catalog, basket = scenario
    with native_writer(db, user, branch):
        result = checkout(basket(), db, user)
        root = db.get(POSServiceCheckout, result['id'])
        session = db.get(SRMPOSSession, root.pos_session_id)
        if case == 'root_currency':
            db.connection().execute(POSServiceCheckout.__table__.update().values(currency='USD'))
        else:
            values = {'receipt_company': {'organization_id': 2}, 'receipt_currency': {'currency': 'USD'},
                'receipt_customer': {'customer_id': 999}}[case]
            db.connection().execute(SRMReceipt.__table__.update().values(**values))
        with pytest.raises(HTTPException) as error:
            group_register_cash(db, session, db.query(SRMSalesOrder).all())
        assert error.value.status_code == 503
