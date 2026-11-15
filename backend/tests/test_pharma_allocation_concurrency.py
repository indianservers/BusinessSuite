"""Competing real checkouts use independent PostgreSQL sessions."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.user import User
from app.apps.srm.models import SRMInventoryBatch
from app.apps.srm.service_checkout import checkout
from app.apps.srm.service_checkout_schemas import CheckoutInput
from app.business_packs.pharma.models import PharmaBatchAllocation
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from tests.test_pharma_recall_concurrency import seed, writer
from tests.test_payroll_qa_concurrency import payroll_engine
from tests.srm_test_utils import seed_invoice_parties
from app.business_packs.models import PackUserGrant, PackMasterAvailability
from app.apps.srm.models import SRMPOSSession
from uuid import uuid4
from tests.test_srm_native_transaction_operations import native_writer


@pytest.mark.parametrize('same_key', [False, True])
def test_competing_native_checkouts_cannot_oversell_or_duplicate_allocations(payroll_engine, same_key):
    db_engine = payroll_engine
    case = seed(db_engine)
    actor_id, branch, context = case['actor'], case['branch'], case['context']
    with Session(db_engine) as setup:
        actor = setup.get(User, actor_id)
        actor.organization_id = 1
        role = setup.query(PackUserGrant).filter_by(context_id=context, user_id=actor_id).one()
        role.role = 'business_owner'
        setup.commit()
        with native_writer(setup, actor, branch):
            seed_invoice_parties(setup)
        setup.add(PackMasterAvailability(company_id=1, branch_id=branch, context_id=context,
                                        resource_table='crm_companies', resource_key='101', active=True))
        setup.commit()
    with writer(db_engine, case) as (setup, actor):
        register = SRMPOSSession(organization_id=1, session_number='ALLOCATION-'+uuid4().hex,
                                status='open', cashier_user_id=actor_id, created_by=actor_id)
        setup.add(register)
        setup.commit()
        register_id = register.id
    def sale():
        return {'request_id': str(uuid4()), 'customer_id': 101, 'pos_session_id': register_id,
                'lines': [{'client_line_key': str(uuid4()), 'line_kind': 'product',
                           'product_id': case['product'], 'quantity': '7.125'}], 'payments': []}
    payloads = [sale(), sale()]
    if same_key:
        payloads[1] = payloads[0]
    start = Barrier(2)
    def run(payload):
        with Session(db_engine) as session:
            actor = session.get(User, actor_id)
            actor.organization_id = 1
            with native_writer(session, actor, branch):
                scope = resolve_context(session, actor, session.info['branch_context'], context)
                cleanup = install(session, scope, policy=native_srm_policy('pharma').policy)
                try:
                    start.wait(timeout=20)
                    try:
                        return 201, checkout(CheckoutInput.model_validate(payload), session, actor)
                    except HTTPException as error:
                        session.rollback()
                        return error.status_code, error.detail
                finally:
                    cleanup()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, payloads))
    assert sorted(code for code, _ in results) == ([201, 201] if same_key else [201, 409]), results
    if same_key:
        assert results[0][1] == results[1][1]
    with Session(db_engine) as db:
        from app.apps.srm.models import SRMInventoryBalance, SRMInventoryMovement, SRMSalesOrderLine, SRMInvoiceLine
        remaining = db.connection().scalar(select(SRMInventoryBatch.available_quantity).where(SRMInventoryBatch.id == case['batch']))
        assert remaining == Decimal('2.875')
        assert db.query(PharmaBatchAllocation).count() == 1
        assert db.query(PharmaBatchAllocation).one().quantity == Decimal('7.125')
        assert db.query(SRMSalesOrderLine).one().quantity == db.query(SRMInvoiceLine).one().quantity == Decimal('7.125')
        assert db.query(SRMInventoryMovement).filter_by(movement_type='pos_sale').one().quantity_out == Decimal('7.125')
        balance = db.connection().scalar(select(SRMInventoryBalance.quantity).where(
            SRMInventoryBalance.product_id == case['product'], SRMInventoryBalance.warehouse_id == case['warehouse']))
        assert balance == Decimal('2.875')


@pytest.mark.parametrize('same_key', [False, True])
def test_competing_receipts_create_one_batch_and_one_stock_movement(payroll_engine, same_key):
    from datetime import date, timedelta
    from app.business_packs.pharma.receipts import create
    from app.business_packs.pharma.schemas import ReceiptInput
    from app.business_packs.pharma.models import PharmaBatchReceipt
    from app.apps.srm.models import SRMInventoryBalance, SRMInventoryMovement
    engine = payroll_engine
    case = seed(engine)
    key = uuid4()
    batch_number = 'DUPLICATE-'+uuid4().hex
    start = Barrier(2)
    def run(index):
        with writer(engine, case) as (db, actor):
            payload = ReceiptInput(request_key=key if same_key else uuid4(), product_id=case['product'],
                                   warehouse_id=case['warehouse'], batch_number=batch_number,
                                   received_date=date.today(), expiry_date=date.today()+timedelta(days=100),
                                   quantity='2.500', unit_cost='1.2500')
            start.wait(timeout=20)
            try:
                return 201, create(payload, db, actor)
            except HTTPException as error:
                db.rollback()
                return error.status_code, error.detail
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert sorted(code for code, _ in results) == ([201, 201] if same_key else [201, 409]), results
    if same_key:
        assert results[0][1] == results[1][1]
    with Session(engine) as db:
        assert db.query(PharmaBatchReceipt).count() == 2
        assert db.query(SRMInventoryMovement).count() == 2
        assert db.query(SRMInventoryBatch).count() == 2
        balance = db.connection().scalar(select(SRMInventoryBalance.quantity).where(
            SRMInventoryBalance.product_id == case['product'], SRMInventoryBalance.warehouse_id == case['warehouse']))
        assert balance == Decimal('12.5')
