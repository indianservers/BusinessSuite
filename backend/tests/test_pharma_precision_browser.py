"""Use the unchanged native POS Qty control for paid three-decimal sales."""
import json
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
import pytest
from app.apps.srm.models import SRMPOSSession, SRMProduct, SRMInventoryBatch, SRMInvoice
from app.apps.crm.models import CRMCompany
from app.business_packs.models import PackUserGrant
from app.business_packs.pharma.models import PharmaBatchReceipt, PharmaBatchAllocation
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from tests.test_pharma_receipts import pharma
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer


@pytest.mark.parametrize('quantity,price', [('0.001','100'), ('0.125','100'), ('0.125','1.09')])
def test_existing_desktop_mobile_pos_dispenses_exact_three_decimals(client, db, pharma, monkeypatch, quantity, price):
    from tests.test_control_browser import test_control_center_real_browser
    role = db.query(PackUserGrant).filter_by(context_id=pharma[3], user_id=pharma[1].id).one()
    role.role = 'business_owner'
    db.commit()
    with native_writer(db, pharma[1], pharma[2]):
        scope = resolve_context(db, pharma[1], db.info['branch_context'], pharma[3])
        cleanup = install(db, scope, policy=native_srm_policy('pharma').policy)
        try:
            db.add(SRMPOSSession(organization_id=1, session_number='PRECISION-'+uuid4().hex,
                                status='open', cashier_user_id=pharma[1].id, created_by=pharma[1].id))
            db.commit()
        finally:
            cleanup()
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT', 'pharma-native.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH', json.dumps({
        'token': pharma[0]['Authorization'].split(' ', 1)[1], 'branch': str(pharma[2]),
        'context': str(pharma[3]), 'warehouse': pharma[5], 'customer_name': db.get(CRMCompany, 101).name,
        'dispense_quantity': quantity, 'dispense_price': price}))
    test_control_center_real_browser(client, db, None, pharma[0])
    medicine = db.query(SRMProduct).filter_by(sku='PHARMA-NATIVE-MED').one()
    assert medicine.unit_code == 'PCS'
    receipt = db.query(PharmaBatchReceipt).filter_by(product_id=medicine.id).one()
    lot = db.get(SRMInventoryBatch, receipt.batch_id)
    assert lot.quantity == 3 and lot.available_quantity == Decimal(3)-Decimal(quantity)
    allocation = db.query(PharmaBatchAllocation).filter_by(product_id=medicine.id).one()
    assert allocation.batch_id == lot.id and allocation.quantity == Decimal(quantity)
    invoice = db.query(SRMInvoice).one()
    base = (Decimal(quantity)*Decimal(price)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    total = base+(base*Decimal('.18')).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    assert invoice.paid_amount == invoice.total_amount == total and invoice.balance_amount == 0
