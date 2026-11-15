"""Selected native catalogue -> scheduling configuration -> paid POS browser."""
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import json

from tests.test_business_pack_http_integration import hospital_http
from tests.test_service_checkout import scenario,catalog,directory_identity


def test_selected_service_catalog_configures_existing_hrms_provider_and_pays_same_id(client,db,hospital_http,monkeypatch):
    from tests.test_control_browser import test_control_center_real_browser
    from app.apps.crm.models import CRMCompany
    from app.apps.srm.models import SRMProduct,SRMInvoice,SRMReceipt
    from app.apps.srm.service_checkout_models import POSServiceCheckout,POSServiceOccurrence,ServiceBookingPolicy
    from app.apps.project_management.models import PMSTimesheet
    from app.business_packs.runtime import RUNTIME_SUPPORT
    headers,actor,branch,context,_,existing=hospital_http
    starts=(datetime.now(timezone.utc)+timedelta(days=2)).replace(hour=10,minute=0,second=0,microsecond=0)
    buyer=db.get(CRMCompany,101)
    before=db.query(PMSTimesheet).count()
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT','catalog-service-native.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH',json.dumps({'token':headers['Authorization'].split(' ',1)[1],
        'branch':str(branch),'context':str(context),'provider':existing['lines'][0]['booking']['provider_resource_id'],
        'customer_name':buyer.name,'starts_at':starts.isoformat()}))
    test_control_center_real_browser(client,db,None,headers)
    product=db.query(SRMProduct).filter_by(sku='NATIVE-CATALOG-CONFIGURED').one()
    policy=db.query(ServiceBookingPolicy).filter_by(service_product_id=product.id,pack_context_id=context).one()
    assert policy.default_duration_minutes==45 and policy.min_duration_minutes==15 and policy.max_duration_minutes==90
    checkout=db.query(POSServiceCheckout).one()
    occurrence=db.query(POSServiceOccurrence).one()
    assert occurrence.service_product_id==product.id and occurrence.employee_id==existing['lines'][0]['booking']['employee_id']
    invoice=db.get(SRMInvoice,checkout.invoice_id)
    receipt=db.query(SRMReceipt).one()
    assert invoice.status=='paid' and invoice.total_amount==invoice.paid_amount==receipt.amount==Decimal('117.99')
    assert invoice.balance_amount==0 and receipt.status=='allocated'
    assert db.query(PMSTimesheet).count()==before
    assert not RUNTIME_SUPPORT
