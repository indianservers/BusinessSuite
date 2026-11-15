"""Real implicit selected POS, mixed payment and native grant-swap race."""
import json
from decimal import Decimal
import pytest
from tests.test_business_pack_http_integration import hospital_http,native_actor,grant
from tests.test_service_checkout import scenario,catalog,directory_identity


@pytest.mark.parametrize('case',['sale','swap'])
def test_native_implicit_pos_pins_exact_context_and_never_retags_uncertain_intent(client,db,hospital_http,superuser_headers,monkeypatch,case):
    from tests.test_control_browser import test_control_center_real_browser
    from app.apps.crm.models import CRMCompany
    from app.apps.srm.models import SRMProduct,SRMInvoice,SRMReceipt,SRMPOSSession,SRMInventoryBalance
    from app.apps.srm.service_checkout_models import POSServiceCheckout,POSServiceOccurrence
    from app.apps.project_management.models import PMSTimesheet
    from app.business_packs.models import PackMasterAvailability
    from app.business_packs.runtime import RUNTIME_SUPPORT
    headers,actor,branch,context,_,existing=hospital_http
    product=db.query(SRMProduct).filter_by(track_inventory=True,active=True).first()
    assert product is not None and product.default_warehouse_id
    service=db.get(SRMProduct,existing['lines'][0]['product_id']);buyer=db.get(CRMCompany,101)
    for table,ident in [('srm_products',product.id),('srm_warehouses',product.default_warehouse_id)]:
        db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=context,resource_table=table,resource_key=str(ident),active=True))
    other=None
    if case=='swap':
        _,other_actor=native_actor(db,branch)
        other,_=grant(db,other_actor,branch,'restaurant','restaurant_manager')
        for table,ident in [('crm_companies',101),('srm_products',product.id),('srm_products',service.id),('srm_warehouses',product.default_warehouse_id)]:
            db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=other.id,resource_table=table,resource_key=str(ident),active=True))
    db.commit()
    before_time=db.query(PMSTimesheet).count();before_registers=db.query(SRMPOSSession).count()
    before_stock=db.query(SRMInventoryBalance).filter_by(organization_id=1,product_id=product.id,warehouse_id=product.default_warehouse_id).one().quantity
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT','pos-implicit-native.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH',json.dumps({'token':headers['Authorization'].split(' ',1)[1],
        'admin_token':superuser_headers['Authorization'].split(' ',1)[1],'implicit':True,'case':case,
        'user_id':actor.id,'branch':str(branch),'context':str(context),'other_context':str(other.id) if other else None,
        'customer_name':buyer.name,'product_name':product.item_name,'service_name':service.item_name,'service_id':service.id,
        'starts_at':existing['lines'][0]['booking']['starts_at']}))
    test_control_center_real_browser(client,db,None,headers)
    if case=='sale':
        checkout=db.query(POSServiceCheckout).one();invoice=db.get(SRMInvoice,checkout.invoice_id)
        assert invoice.status=='paid' and invoice.total_amount==invoice.paid_amount==Decimal('236') and invoice.balance_amount==0
        assert sorted((row.payment_method,row.amount) for row in db.query(SRMReceipt))==[('card',Decimal('136')),('cash',Decimal('100'))]
        assert db.query(POSServiceOccurrence).count()==1
        assert db.query(SRMInventoryBalance).filter_by(organization_id=1,product_id=product.id,warehouse_id=product.default_warehouse_id).one().quantity==before_stock-1
    else:
        assert db.query(POSServiceCheckout).count()==db.query(SRMInvoice).count()==db.query(SRMReceipt).count()==db.query(POSServiceOccurrence).count()==0
        assert db.query(SRMInventoryBalance).filter_by(organization_id=1,product_id=product.id,warehouse_id=product.default_warehouse_id).one().quantity==before_stock
    assert db.query(SRMPOSSession).count()==before_registers
    assert db.query(PMSTimesheet).count()==before_time
    assert not RUNTIME_SUPPORT
