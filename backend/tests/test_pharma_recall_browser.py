"""Actual existing UI paid sale -> quarantine -> recall -> close, stock stays blocked."""
import json
from decimal import Decimal
from uuid import uuid4
from app.apps.srm.models import SRMPOSSession,SRMProduct,SRMInventoryBatch,SRMInvoice
from app.apps.crm.models import CRMCompany
from app.business_packs.models import PackUserGrant
from app.business_packs.pharma.models import PharmaBatchReceipt
from app.business_packs.pharma.recall_models import PharmaRecall,PharmaRecallEvent,PharmaBatchControl
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from tests.test_pharma_receipts import pharma
from tests.test_service_checkout import scenario,catalog,directory_identity
from tests.test_srm_native_transaction_operations import native_writer


def test_real_existing_batch_ui_quarantine_recall_close_does_not_release_stock(client,db,pharma,monkeypatch):
    from tests.test_control_browser import test_control_center_real_browser
    role=db.query(PackUserGrant).filter_by(context_id=pharma[3],user_id=pharma[1].id).one();role.role='business_owner';db.commit()
    with native_writer(db,pharma[1],pharma[2]):
        scope=resolve_context(db,pharma[1],db.info['branch_context'],pharma[3]);cleanup=install(db,scope,policy=native_srm_policy('pharma').policy)
        try:
            db.add(SRMPOSSession(organization_id=1,session_number='PHARMA-RECALL-'+uuid4().hex,status='open',cashier_user_id=pharma[1].id,created_by=pharma[1].id));db.commit()
        finally:cleanup()
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT','pharma-recall-native.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH',json.dumps({'token':pharma[0]['Authorization'].split(' ',1)[1],'branch':str(pharma[2]),'context':str(pharma[3]),
        'warehouse':pharma[5],'customer_name':db.get(CRMCompany,101).name}))
    test_control_center_real_browser(client,db,None,pharma[0])
    medicine=db.query(SRMProduct).filter_by(sku='PHARMA-NATIVE-MED').one()
    receipt=db.query(PharmaBatchReceipt).filter_by(product_id=medicine.id).one()
    lot=db.get(SRMInventoryBatch,receipt.batch_id)
    assert lot.status=='recalled' and lot.quantity==3 and lot.available_quantity==2
    root=db.query(PharmaRecall).one()
    assert root.state=='closed' and root.revision==3
    assert db.query(PharmaRecallEvent).count()==3 and db.query(PharmaBatchControl).one().revision==2
    invoice=db.query(SRMInvoice).one()
    assert invoice.paid_amount==invoice.total_amount==Decimal('118') and invoice.balance_amount==0
