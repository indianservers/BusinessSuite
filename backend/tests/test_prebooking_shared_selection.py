"""Reservations reuse checkout eligibility without creating financial records."""
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.apps.srm.industry_api import AppointmentInput, appointment_operation
from app.apps.srm.models import SRMInvoice, SRMReceipt, SRMSalesOrder
from app.apps.srm.service_checkout_options import validate_prebooking
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer


def selection(basket):
    cart = basket(False)
    line = next(line for line in cart.lines if line.booking)
    b = line.booking
    return AppointmentInput(request_id=uuid4(), title="Shared prebooking", customer_id=cart.customer_id,
        service_id=line.product_id, resource_ids=[b.provider_resource_id, *b.additional_resource_ids],
        starts_at=b.starts_at, duration_minutes=b.duration_minutes, booking=b)


def test_prebooking_reserves_once_without_invoice_receipt_or_order(db, scenario):
    user, branch, _, basket = scenario
    data = selection(basket)
    with native_writer(db, user, branch):
        before = [db.query(model).count() for model in (SRMInvoice, SRMReceipt, SRMSalesOrder)]
        result = appointment_operation(data, db, user)
        assert result['status'] == 'booked'
        assert [db.query(model).count() for model in (SRMInvoice, SRMReceipt, SRMSalesOrder)] == before
        assert appointment_operation(data, db, user)['id'] == result['id']
        data.request_id = uuid4()
        with pytest.raises(HTTPException) as conflict:
            appointment_operation(data, db, user)
        assert conflict.value.status_code == 409


def test_prebooking_rejects_stale_eligibility_and_changed_interval(db, scenario):
    user, branch, _, basket = scenario
    with native_writer(db, user, branch):
        stale = selection(basket)
        stale.booking.expected_eligibility_revision += 1
        with pytest.raises(HTTPException) as rejected:
            validate_prebooking(db, user, stale)
        assert rejected.value.status_code == 409
        altered = selection(basket)
        altered.duration_minutes += 5
        with pytest.raises(HTTPException) as rejected:
            validate_prebooking(db, user, altered)
        assert rejected.value.status_code == 422

