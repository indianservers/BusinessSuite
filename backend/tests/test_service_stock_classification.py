"""Legacy service inventory flags never create physical stock requirements."""
import pytest
from fastapi import HTTPException

from app.apps.srm.models import SRMProduct, SRMInventoryMovement
from app.apps.srm.service_checkout import checkout
from tests.test_service_checkout import scenario
from tests.test_srm_native_transaction_operations import native_writer
from tests.test_business_suite_pos_integrity import catalog
from tests.test_contact_directory import directory_identity


@pytest.mark.parametrize('kind', ['service', 'services', 'SERVICE'])
def test_booked_services_with_legacy_stock_flag_can_checkout_without_stock(db, scenario, kind):
    actor, branch, catalog_data, basket = scenario
    service = db.get(SRMProduct, catalog_data[2][1])
    service.product_type = kind
    service.track_inventory = True
    service.batch_tracking = True
    service.serial_tracking = True
    service.current_quantity = 0
    service.default_warehouse_id = None
    db.commit()
    data = basket(False)
    data.lines = data.lines[1:]  # Two independently booked occurrences, no product.
    movements_before = db.query(SRMInventoryMovement).count()
    with native_writer(db, actor, branch):
        result = checkout(data, db, actor)
    assert len(result['lines']) == 2
    assert len({line['appointment_id'] for line in result['lines']}) == 2
    assert db.query(SRMInventoryMovement).count() == movements_before
    assert db.query(SRMInventoryMovement).filter_by(product_id=service.id).count() == 0
    assert db.get(SRMProduct, service.id).current_quantity == 0


@pytest.mark.parametrize('tracking', ['batch_tracking', 'serial_tracking'])
def test_physical_tracking_requires_allocation_before_checkout_writes(db, scenario, tracking):
    from app.apps.srm.models import SRMSalesOrder, SRMInvoice, SRMReceipt
    from app.apps.srm.service_checkout_models import POSServiceCheckout
    actor, branch, catalog_data, basket = scenario
    product = db.get(SRMProduct, catalog_data[2][0])
    setattr(product, tracking, True)
    db.commit()
    models = (POSServiceCheckout, SRMSalesOrder, SRMInvoice, SRMReceipt, SRMInventoryMovement)
    before = tuple(db.query(model).count() for model in models)
    quantity = product.current_quantity
    with native_writer(db, actor, branch), pytest.raises(HTTPException) as error:
        checkout(basket(), db, actor)
    assert error.value.status_code == 409
    assert 'allocation' in error.value.detail
    assert tuple(db.query(model).count() for model in models) == before
    assert db.get(SRMProduct, product.id).current_quantity == quantity
