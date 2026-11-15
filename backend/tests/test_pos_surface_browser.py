"""Real selected POS React workflow, production auth, disposable native database."""
import os,json
import pytest
from decimal import Decimal
from tests.test_business_pack_http_integration import hospital_http,scenario,catalog,directory_identity
from tests.test_stock_resource import stock
from app.business_packs.models import PackMasterAvailability,PackUserGrant

@pytest.mark.skipif(os.getenv('RUN_SELECTED_POS_BROWSER')!='1',reason='Opt-in native browser workflow')
@pytest.mark.parametrize('role',['business_owner','service_desk'])
def test_selected_pos_named_customer_stock_two_bookings_split_native_payment(client,db,hospital_http,scenario,monkeypatch,role):
    from tests.test_control_browser import test_control_center_real_browser
    headers,actor,branch,context,grant_id,payload=hospital_http
    _,_,catalog,_=scenario;product,service=catalog[2][:2];warehouse=catalog[1]
    assignment=db.get(PackUserGrant,grant_id);assignment.role=role
    for table,ident in [('srm_products',product),('srm_warehouses',warehouse)]:
        db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=context,resource_table=table,resource_key=str(ident),active=True))
    from app.apps.crm.models import CRMCustomField
    for key,label,kind in [('browser_reference','Customer reference','text'),('browser_boolean','Consent answer','checkbox'),('browser_zero','Initial counter','number')]:
        db.add(CRMCustomField(organization_id=1,entity='companies',field_key=key,label=label,field_type=kind,is_required=True,is_active=True,is_visible=True))
    db.commit()
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT','pos-selected-live.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH',json.dumps({'token':headers['Authorization'].split(' ',1)[1],'user_id':actor.id,'branch':str(branch),'context':str(context),
        'date':payload['lines'][0]['booking']['starts_at'][:10],'custom_fields':True}))
    test_control_center_real_browser(client,db,None,headers)
    from app.apps.srm.models import SRMSalesOrder,SRMInvoice,SRMReceipt,SRMInventoryBalance
    from app.apps.srm.service_checkout_models import POSServiceCheckout,POSServiceOccurrence
    from app.apps.crm.models import CRMCompany
    from app.apps.project_management.models import PMSTimesheet
    buyer=db.query(CRMCompany).filter_by(name='Native POS selected customer').one()
    checkout=db.query(POSServiceCheckout).one();invoice=db.get(SRMInvoice,checkout.invoice_id)
    from app.apps.crm.models import CRMCustomFieldValue
    values=db.query(CRMCustomFieldValue).filter_by(entity='companies',record_id=buyer.id).all()
    assert len(values)==3 and any(value.value_boolean is False for value in values) and any(value.value_number==Decimal(0) for value in values)
    assert checkout.customer_id==buyer.id and invoice.customer_id==buyer.id
    assert invoice.total_amount==invoice.paid_amount==Decimal('354') and invoice.balance_amount==0
    assert db.query(SRMReceipt).count()==2
    assert sorted(row.payment_method.lower() for row in db.query(SRMReceipt))==['card','cash']
    assert db.query(POSServiceOccurrence).count()==2
    assert db.query(SRMInventoryBalance).filter_by(product_id=product,warehouse_id=warehouse).one().quantity==4
    assert db.query(PMSTimesheet).count()==0


@pytest.mark.skipif(os.getenv('RUN_SELECTED_POS_BROWSER')!='1',reason='Opt-in native browser workflow')
def test_selected_cashier_pos_has_no_provider_fanout_and_posts_native_split_sale(client,db,stock,monkeypatch):
    from tests.test_control_browser import test_control_center_real_browser
    from app.apps.srm.service_checkout_models import POSServiceCheckout,POSServiceOccurrence
    from app.apps.srm.models import SRMInvoice,SRMReceipt,SRMInventoryBalance
    s=stock;role=db.query(PackUserGrant).filter_by(context_id=s.contexts['retail'],user_id=s.actor.id).one();role.role='cashier';db.commit()
    headers=s.headers('retail')
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT','pos-selected-live.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH',json.dumps({'token':headers['Authorization'].split(' ',1)[1],'user_id':s.actor.id,'branch':str(s.branch),'context':str(s.contexts['retail']),'mode':'cashier'}))
    test_control_center_real_browser(client,db,None,headers)
    checkout=db.query(POSServiceCheckout).filter_by(pack_context_id=s.contexts['retail']).one();invoice=db.get(SRMInvoice,checkout.invoice_id)
    assert invoice.total_amount==invoice.paid_amount==Decimal('236') and invoice.balance_amount==0
    assert db.query(SRMReceipt).filter_by(customer_id=101).count()==3 # One genuine legacy receipt +two scoped native payments.
    assert db.query(POSServiceOccurrence).count()==0
    assert db.query(SRMInventoryBalance).filter_by(product_id=s.product,warehouse_id=s.warehouse).one().quantity==3
