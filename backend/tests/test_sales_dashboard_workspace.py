from tests.rich_text_test_utils import organization_context
from tests.test_settings_hub import actor
from datetime import datetime,date,timedelta,timezone
from decimal import Decimal
import pytest
from app.models.company import Company
from app.apps.srm.models import SRMSalesOrder,SRMInvoice,SRMReceipt,SRMReceiptAllocation,SRMRevenueEvent
from app.apps.crm.models import CRMCompany,CRMQuotation,CRMSalesTarget
from app.shared.models import ServiceEvent
BASE='/api/v1/srm/dashboard-workspace'

@pytest.fixture
def sales(db):
    headers,user=actor(db,role='sales-dashboard-admin',superuser=True)
    from test_identity_utils import attach_workflow_branch, attach_test_identity
    attach_test_identity(db,user)
    branch=attach_workflow_branch(db,user)
    headers["X-Suite-Branch"]=str(branch.id)
    from app.services.metrics.queries import business_context
    today=date.fromisoformat(business_context(db,user)['business_date'])
    customer=CRMCompany(organization_id=1,name='Dashboard customer',owner_user_id=user.id);db.add(customer);db.flush()
    order=SRMSalesOrder(organization_id=1,order_number='SO-DASHBOARD-NEW',title='Delivered dashboard order',customer_id=customer.id,assigned_user_id=user.id,status='delivered',currency='USD',total_amount=1500,created_at=datetime.now(timezone.utc));db.add(order);db.flush()
    invoice=SRMInvoice(organization_id=1,invoice_number='INV-DASHBOARD-NEW',sales_order_id=order.id,customer_id=customer.id,status='sent',currency='USD',total_amount=1000,paid_amount=200,balance_amount=750,issue_date=today,due_date=today-timedelta(days=35),created_by=user.id);db.add(invoice);db.flush()
    receipt=SRMReceipt(organization_id=1,receipt_number='RCPT-DASHBOARD',customer_id=customer.id,status='confirmed',currency='USD',amount=250,unallocated_amount=50,receipt_date=today,created_by=user.id);db.add(receipt);db.flush()
    db.add(SRMReceiptAllocation(receipt_id=receipt.id,invoice_id=invoice.id,amount=200))
    db.add(SRMRevenueEvent(organization_id=1,invoice_id=invoice.id,event_type='credit_note',currency='USD',amount=50,recognized_on=today))
    db.add(Company(id=77,name='Foreign sales company'));db.flush()
    db.add(SRMInvoice(organization_id=77,invoice_number='FOREIGN-SALES',status='sent',currency='USD',total_amount=999999,issue_date=today))
    db.commit();return headers,user,today,order,invoice,customer

def test_sections_currency_cash_and_adjustments(client,db,sales):
    h,u,today,order,invoice,customer=sales
    context=client.get(BASE+'/context',headers=h);assert context.status_code==200,context.text
    assert len(context.json()['sections'])==7
    response=client.get(BASE+'/summary',headers=h,params={'period':'today'});assert response.status_code==200,response.text
    values={r['metric']:r['amount'] for r in response.json()['series']}
    assert values=={'invoiced':'1000.00','collected':'200.00','outstanding':'750.00','overdue':'750.00'}
    assert len(response.json()['rows'])==1
    cash=client.get(BASE+'/cash',headers=h,params={'period':'today'});assert cash.status_code==200,cash.text
    assert cash.json()['series'][0]['cash_received']=='250.00'
    assert cash.json()['metrics']['unclassified_balance_reduction'][0]['amount']=='50.00'
    assert cash.json()['metrics']['adjustments'][0]['type']=='credit_note'
    filtered=client.get(BASE+'/cash',headers=h,params={'period':'today','owner_id':u.id}).json()
    assert filtered['series'][0]['cash_received']=='200.00'

def test_promises_audited_no_accounting_mutation_and_partial_fulfillment(client,db,sales):
    h,u,today,order,invoice,_=sales
    response=client.put(BASE+f'/invoices/{invoice.id}/commitment',headers=h,json={'promised_date':str(today-timedelta(days=1)),'amount':'100.00','next_action':'Call customer','owner_id':u.id})
    assert response.status_code==200,response.text
    assert db.get(SRMInvoice,invoice.id).balance_amount==750
    assert db.query(ServiceEvent).filter_by(entity_id=invoice.id,event_type='dashboard.payment_commitment').count()==1
    result=client.get(BASE+'/collections',headers=h,params={'period':'today'});assert result.status_code==200,result.text
    assert result.json()['rows'][0]['broken_promise'] is True
    assert result.json()['rows'][0]['aging']=='31–60'
    invoice.paid_amount=300;invoice.balance_amount=650;db.commit()
    assert client.get(BASE+'/collections',headers=h,params={'period':'today'}).json()['rows'][0]['broken_promise'] is False
    assert client.put(BASE+f'/invoices/{invoice.id}/commitment',headers=h,json={'promised_date':str(today),'amount':'99999','next_action':'Call customer'}).status_code==422

def test_filters_date_validation_events_and_unbilled(client,db,sales):
    h,u,today,order,invoice,customer=sales
    assert client.get(BASE+'/summary',headers=h,params={'customer_id':999999}).json()['rows']==[]
    assert client.get(BASE+'/summary',headers=h,params={'owner_id':999999}).json()['rows']==[]
    assert client.get(BASE+'/summary',headers=h,params={'period':'custom','start_date':'2026-12-01','end_date':'2026-01-01'}).status_code==422
    event=client.get(BASE+'/events',headers=h).json()['series'][0];assert event['currency']=='USD' and event['event_type']=='credit_note'
    response=client.get(BASE+'/orders',headers=h);assert response.status_code==200,response.text
    assert response.json()['rows'][0]['unbilled']=='500.00'

def test_quotes_targets_and_read_only_access(client,db,sales):
    h,u,today,order,invoice,customer=sales
    quote=CRMQuotation(organization_id=1,quote_number='QUO-DASHBOARD',company_id=customer.id,owner_user_id=u.id,issue_date=today,expiry_date=today+timedelta(days=3),status='Sent',currency='USD',total_amount=1500);db.add(quote);db.flush();order.crm_quote_id=quote.id
    db.add(CRMSalesTarget(organization_id=1,target_owner_type='user',target_owner_id=u.id,target_amount=3000,currency='USD',period_start=today.replace(day=1),period_end=today));db.commit()
    quotes=client.get(BASE+'/quotations',headers=h);assert quotes.status_code==200,quotes.text
    assert quotes.json()['metrics']['conversion_rate']==100 and quotes.json()['rows'][0]['converted'] is True
    target=client.get(BASE+'/targets',headers=h);assert target.status_code==200,target.text
    assert target.json()['rows'][0]['attainment']==50
    from tests.srm_test_utils import auth_headers_for
    readonly=auth_headers_for(client,db,'dashboard-readonly@example.com','srm_viewer',permissions=['srm_view'])
    ctx=client.get(BASE+'/context',headers=readonly);assert ctx.status_code==200,ctx.text
    assert not ctx.json()['can_plan'] and not ctx.json()['can_create'] and not ctx.json()['can_pos']
    assert client.get(BASE+'/targets',headers=readonly).status_code==403
    assert client.put(BASE+f'/invoices/{invoice.id}/commitment',headers=readonly,json={'promised_date':str(today),'amount':1,'next_action':'Call customer'}).status_code==403


def test_prior_only_currency_and_old_invoice_receipt(client,db,sales):
    h,u,today,order,invoice,customer=sales
    invoice.issue_date=today-timedelta(days=1);db.commit()
    response=client.get(BASE+'/summary',headers=h,params={'period':'today'}).json()
    invoiced=next(r for r in response['series'] if r['metric']=='invoiced')
    assert invoiced['amount']=='0.00' and invoiced['previous']=='1000.00'
    assert response['rows']==[]
    assert client.get(BASE+'/cash',headers=h,params={'period':'today'}).json()['series'][0]['cash_received']=='250.00'


def test_holds_zero_forecast_and_foreign_owner_rejected(client,db,sales):
    h,u,today,order,invoice,customer=sales
    invoice.collection_hold=True;db.commit()
    response=client.get(BASE+'/collections',headers=h).json()
    assert response['metrics']['forecast'][0]['scenario']=='0.00'
    response=client.put(BASE+f'/invoices/{invoice.id}/commitment',headers=h,json={'promised_date':str(today),'amount':'10','next_action':'Call tomorrow','owner_id':99999})
    assert response.status_code==403


def test_stage_age_and_stock_blockers_use_recorded_sources(client,db,sales):
    from app.apps.srm.models import SRMProduct,SRMSalesOrderLine
    h,u,today,order,invoice,customer=sales
    order.status='pending_approval';order.expected_end_date=today-timedelta(days=1)
    product=SRMProduct(organization_id=1,sku='DASH-STOCK',item_name='Tracked stock',product_type='stock',track_inventory=True);db.add(product);db.flush()
    db.add(SRMSalesOrderLine(sales_order_id=order.id,product_id=product.id,quantity=5))
    db.add(ServiceEvent(organization_id=1,module_key='srm',entity_type='sales_order',entity_id=order.id,actor_id=u.id,event_type='pipeline.stage_entered',request_key='dashboard-stage-test',payload_json={'data':{'stage':'pending_approval'}},status='completed',created_at=datetime.now(timezone.utc)-timedelta(days=20)));db.commit()
    response=client.get(BASE+'/orders',headers=h);assert response.status_code==200,response.text
    record=response.json()['rows'][0]
    assert record['stage_age_days']>=19
    assert 'Pending approval' in record['blockers'] and 'Delivery date passed' in record['blockers']
    assert any('Stock availability not verified' in b for b in record['blockers'])


def test_drilldown_limits_after_currency_and_metric(client,db,sales):
    h,u,today,order,invoice,customer=sales
    for i in range(255):db.add(SRMInvoice(organization_id=1,invoice_number=f'DASH-PAID-{i}',sales_order_id=order.id,customer_id=customer.id,status='paid',currency='USD',issue_date=today,total_amount=1,paid_amount=1,balance_amount=0))
    db.commit()
    response=client.get(BASE+'/summary',headers=h,params={'period':'today','metric':'overdue','currency':'USD'})
    assert response.status_code==200,response.text
    assert response.json()['total_rows']==1 and response.json()['rows'][0]['id']==str(invoice.id)
