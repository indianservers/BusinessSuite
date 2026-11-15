"""Failure/retry proofs use native sources and the original request keys."""
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.apps.srm import service_checkout as service
from app.apps.srm.models import SRMInvoice, SRMReceipt, SRMReceiptAllocation, SRMSalesOrder, SRMProduct
from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.service_checkout_models import POSServiceCheckout, POSServiceOccurrence
from app.apps.srm.service_checkout_schemas import AppendPaymentInput
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer


@pytest.mark.parametrize('ddl', [
    'ALTER TABLE srm_pos_checkout_payments RENAME TO missing_checkout_payments',
    'ALTER TABLE srm_pos_checkout_payments RENAME COLUMN request_sha256 TO missing_request_sha256',
    'ALTER TABLE srm_receipts RENAME TO missing_checkout_receipts',
], ids=['checkout-table', 'required-column', 'native-foreign-key-table'])
def test_installation_probe_rechecks_live_schema_and_checkout_fails_closed(db, scenario, ddl):
    user, branch, _, basket = scenario
    assert service.installation_ready(db)
    savepoint = db.begin_nested()
    try:
        db.connection().exec_driver_sql(ddl)
        assert service.installation_ready(db) is False
        with native_writer(db, user, branch), pytest.raises(HTTPException) as error:
            service.checkout(basket(False), db, user)
        assert error.value.status_code == 503
        assert db.query(SRMInvoice).count() == db.query(SRMSalesOrder).count() == 0
    finally:
        savepoint.rollback()
    assert service.installation_ready(db)


def test_checkout_and_later_payment_retry_original_keys_after_allocation_failure(db, scenario, monkeypatch):
    from app.apps.srm.api import router as native
    user, branch, catalog, basket = scenario
    data = basket()
    allocate = native.allocate_receipt_operation

    def fail_allocation(*args, **kwargs):
        raise HTTPException(409, 'Synthetic allocation failure')

    with native_writer(db, user, branch):
        with monkeypatch.context() as failure:
            failure.setattr(native, 'allocate_receipt_operation', fail_allocation)
            with pytest.raises(HTTPException) as error:
                service.checkout(data, db, user)
            assert error.value.status_code == 409
        assert db.query(SRMReceipt).count() == db.query(SRMInvoice).count() == db.query(POSServiceOccurrence).count() == 0
        assert db.connection().scalar(select(SRMProduct.current_quantity).where(SRMProduct.id == catalog[2][0])) == 5
        assert db.get(SRMProduct, catalog[2][0]).current_quantity == 5
        committed = service.checkout(data, db, user)
        assert service.checkout(data, db, user) == committed
        assert db.query(SRMSalesOrder).count() == db.query(SRMInvoice).count() == db.query(POSServiceCheckout).count() == 1
        assert db.query(POSServiceOccurrence).count() == 2
        assert db.query(SRMReceipt).count() == db.query(SRMReceiptAllocation).count() == 2
        assert db.get(SRMProduct, catalog[2][0]).current_quantity == 4

        payment = AppendPaymentInput.model_validate({'expected_revision': committed['revision'],
            'payment': {'payment_key': str(uuid4()), 'method': 'upi', 'amount': committed['invoice']['balance']}})
        with monkeypatch.context() as failure:
            failure.setattr(native, 'allocate_receipt_operation', fail_allocation)
            with pytest.raises(HTTPException):
                service.append_payment(committed['id'], payment, db, user)
        assert db.query(SRMReceipt).count() == db.query(SRMReceiptAllocation).count() == 2
        assert service.servicecheckout_state(db, user, db.info['branch_context'], committed['id']) == committed
        assert native.allocate_receipt_operation is allocate
        settled = service.append_payment(committed['id'], payment, db, user)
        assert Decimal(settled['invoice']['balance']) == 0
        assert Decimal(settled['invoice']['paid']) == Decimal(settled['invoice']['total'])
        assert service.append_payment(committed['id'], payment, db, user) == settled
        assert db.query(SRMReceipt).count() == db.query(SRMReceiptAllocation).count() == 3


def test_caller_savepoint_rollback_restores_quantity_even_after_cache_was_read(db, scenario):
    user, branch, catalog, basket = scenario
    data = basket(False)
    product_id = catalog[2][0]
    with native_writer(db, user, branch):
        with pytest.raises(RuntimeError, match='caller aborted'):
            with db.begin_nested():
                service.checkout(data, db, user, commit=False)
                assert db.get(SRMProduct, product_id).current_quantity == 4
                raise RuntimeError('caller aborted')
        assert db.connection().scalar(select(SRMProduct.current_quantity).where(SRMProduct.id == product_id)) == 5
        assert db.get(SRMProduct, product_id).current_quantity == 5
        assert db.query(SRMInvoice).count() == db.query(SRMReceipt).count() == db.query(POSServiceOccurrence).count() == 0
        committed = service.checkout(data, db, user)
        assert service.checkout(data, db, user) == committed
        assert db.get(SRMProduct, product_id).current_quantity == 4


@pytest.mark.parametrize('unavailable', ['inactive', 'opening_hours', 'approved_leave'])
def test_unavailable_employee_blocks_entire_cart_then_same_request_can_retry(db, scenario, unavailable):
    from app.models.leave import LeaveRequest, LeaveType
    user, branch, catalog, basket = scenario
    data = basket(False)
    provider = db.get(IndustryRecord, data.lines[1].booking.provider_resource_id)
    original = dict(provider.data)
    leave = None
    if unavailable == 'approved_leave':
        kind = LeaveType(name='Synthetic scheduling leave', code='SRV-' + uuid4().hex[:8], days_allowed=10)
        db.add(kind); db.flush()
        day = data.lines[1].booking.starts_at.date()
        leave = LeaveRequest(company_id=1, employee_id=original['employee_id'], leave_type_id=kind.id,
            from_date=day, to_date=day, days_count=1, status='Approved')
        db.add(leave); db.commit()
    with native_writer(db, user, branch):
        if unavailable == 'inactive': provider.status = 'inactive'
        elif unavailable == 'opening_hours': provider.data = {**original, 'opens': '15:00:00'}
        db.commit()
        with pytest.raises(HTTPException): service.checkout(data, db, user)
        assert db.query(SRMSalesOrder).count() == db.query(SRMInvoice).count() == db.query(POSServiceOccurrence).count() == 0
        assert db.get(SRMProduct, catalog[2][0]).current_quantity == 5
        provider.status = 'active'; provider.data = original
        if leave: leave.status = 'Cancelled'
        db.commit()
        result = service.checkout(data, db, user)
        assert service.checkout(data, db, user) == result
        assert len([line for line in result['lines'] if line['appointment_id']]) == 2
        assert db.query(SRMInvoice).count() == 1
