"""Inventory margin must not recognize draft invoices as sales."""
from decimal import Decimal
from datetime import datetime,timezone
import pytest
from tests.fam_inventory_test_utils import create_stock_item,inventory_headers
from app.apps.srm.models import SRMInvoice,SRMInvoiceLine
from test_identity_utils import own_workflow_records

@pytest.mark.parametrize('status,approved,deleted',[('draft',False,False),('pending_approval',False,False),('approved',False,False),('cancelled',True,False),('approved',True,True),('approved',True,False)])
def test_inventory_margin_excludes_unissued_invoice_revenue(client,db,status,approved,deleted):
    headers=inventory_headers(client,db,'qa-margin@example.com')
    item,_=create_stock_item(client,headers,'QA-MARGIN')
    invoice=SRMInvoice(organization_id=1,invoice_number='QA-DRAFT-MARGIN',status=status,currency='INR',approved_at=datetime.now(timezone.utc) if approved else None,deleted_at=datetime.now(timezone.utc) if deleted else None)
    db.add(invoice);db.flush()
    line=SRMInvoiceLine(invoice_id=invoice.id,description=item['sku'],quantity=1,unit_price=100,line_total=100)
    db.add(line);own_workflow_records(db,invoice,line);db.commit()
    response=client.get('/api/v1/fam/inventory/reports/gross-margin',headers=headers)
    assert response.status_code==200,response.text
    row=next(r for r in response.json()['items'] if r['id']==item['id'])
    assert Decimal(str(row['revenue']))==0
    assert row['gross_margin'] is None
    assert response.json()['attribution']['unattributed_invoice_lines']==(1 if status=='approved' and approved and not deleted else 0)


def test_inventory_margin_uses_historical_posted_delivery_cost(client,db):
    from tests.fam_inventory_accounting_cases import accounting_setup,create_posted_delivery
    from app.apps.fam.models import FAMStockItem,FAMStockMovement,FAMStockMovementLine
    from datetime import date
    headers,item,warehouse,_=accounting_setup(client,db,'QA-HIST-MARGIN')
    create_posted_delivery(client,headers,item,warehouse,'QA-HIST-MARGIN')
    db.get(FAMStockItem,item['id']).average_cost=300
    for number,status,kind in [('DRAFT','draft','delivery_note'),('TRANSFER','posted','stock_transfer')]:
        movement=FAMStockMovement(company_id=1,movement_number=number,movement_date=date(2026,6,8),movement_type=kind,status=status)
        db.add(movement);db.flush()
        line=FAMStockMovementLine(movement_id=movement.id,company_id=1,stock_item_id=item['id'],warehouse_id=warehouse['id'],quantity_out=1,rate=999,value=999)
        db.add(line);own_workflow_records(db,movement,line)
    db.commit()
    response=client.get('/api/v1/fam/inventory/reports/gross-margin',headers=headers)
    assert response.status_code==200,response.text
    row=next(r for r in response.json()['items'] if r['id']==item['id'])
    assert Decimal(str(row['cogs']))==200


@pytest.mark.parametrize('mapping',['missing','explicit','ambiguous'])
def test_inventory_margin_requires_explicit_source_item_mapping(client,db,mapping):
    from app.apps.fam.models import FAMInventoryIntegrationLink
    from app.apps.srm.models import SRMProduct,SRMSalesOrder,SRMSalesOrderLine
    headers=inventory_headers(client,db,'qa-margin-source@example.com')
    item,_=create_stock_item(client,headers,'QA-SOURCE')
    other=create_stock_item(client,headers,'QA-OTHER')[0] if mapping=='ambiguous' else None
    product=SRMProduct(organization_id=1,sku='Different SKU',item_name='Different name',product_type='product',active=True)
    order=SRMSalesOrder(organization_id=1,order_number='QA-SOURCE',title='Sales',status='confirmed')
    db.add_all([product,order]);db.flush()
    source=SRMSalesOrderLine(sales_order_id=order.id,product_id=product.id,description='Unrelated text',quantity=1,unit_price=100,line_total=118,tax_amount=18)
    invoice=SRMInvoice(organization_id=1,invoice_number='QA-SOURCE',status='approved',currency='INR',approved_at=datetime.now(timezone.utc))
    db.add_all([source,invoice]);db.flush()
    line=SRMInvoiceLine(invoice_id=invoice.id,source_type='sales_order_line',source_id=source.id,description='Unrelated text',quantity=1,unit_price=100,line_total=118,tax_amount=18)
    db.add(line);records=[product,order,source,invoice,line]
    if mapping!='missing':
        link=FAMInventoryIntegrationLink(company_id=1,stock_item_id=item['id'],target_module='srm',target_record_type='product',target_record_id=str(product.id),active=True)
        db.add(link);records.append(link)
    if mapping=='ambiguous':
        link=FAMInventoryIntegrationLink(company_id=1,stock_item_id=other['id'],target_module='srm',target_record_type='product',target_record_id=str(product.id),active=True)
        db.add(link);records.append(link)
    own_workflow_records(db,*records);db.commit()
    response=client.get('/api/v1/fam/inventory/reports/gross-margin',headers=headers)
    assert response.status_code==200,response.text
    row=next(r for r in response.json()['items'] if r['id']==item['id'])
    assert row['revenue']==(100 if mapping=='explicit' else 0)
    assert row['revenue_complete']==(mapping=='explicit')
    assert row['gross_margin']==(100 if mapping=='explicit' else None)


@pytest.mark.parametrize('source_case',['valid','wrong_order','foreign_plan','malformed'])
def test_inventory_margin_attributes_milestone_installment_from_valid_order_line(client,db,source_case):
    from app.apps.fam.models import FAMInventoryIntegrationLink
    from app.apps.srm.models import SRMProduct,SRMSalesOrder,SRMSalesOrderLine,SRMEngagement,SRMBillingPlan,SRMBillingMilestone
    headers=inventory_headers(client,db,'qa-margin-milestone@example.com')
    item,_=create_stock_item(client,headers,'QA-MILESTONE')
    product=SRMProduct(organization_id=1,sku='MILESTONE',item_name='Stock product',product_type='product',active=True)
    orders=[SRMSalesOrder(organization_id=1,order_number='MILESTONE-'+str(i),title='Sales',status='confirmed') for i in range(2)]
    db.add_all([product,*orders]);db.flush()
    line=SRMSalesOrderLine(sales_order_id=orders[1 if source_case=='wrong_order' else 0].id,product_id=product.id,quantity=2,unit_price=100,line_total=236,tax_amount=36)
    engagement=SRMEngagement(organization_id=1,engagement_number='MILESTONE',name='Commercial work',sales_order_id=orders[0].id)
    db.add_all([line,engagement]);db.flush()
    plan=SRMBillingPlan(organization_id=2 if source_case=='foreign_plan' else 1,engagement_id=engagement.id,name='Installments')
    db.add(plan);db.flush()
    milestone=SRMBillingMilestone(billing_plan_id=plan.id,name='Quarter installment',amount=59,metadata_json={'sales_order_line_id':'bad' if source_case=='malformed' else line.id})
    invoice=SRMInvoice(organization_id=1,invoice_number='QA-MILESTONE',status='approved',currency='INR',approved_at=datetime.now(timezone.utc),sales_order_id=orders[0].id,engagement_id=engagement.id)
    db.add_all([milestone,invoice]);db.flush()
    invoiced=SRMInvoiceLine(invoice_id=invoice.id,source_type='billing_milestone',source_id=milestone.id,description='Not an item name',quantity=1,unit_price=50,line_total=59,tax_amount=9)
    link=FAMInventoryIntegrationLink(company_id=1,stock_item_id=item['id'],target_module='srm',target_record_type='product',target_record_id=str(product.id),active=True)
    db.add_all([invoiced,link]);own_workflow_records(db,product,*orders,line,engagement,plan,milestone,invoice,invoiced,link);db.commit()
    response=client.get('/api/v1/fam/inventory/reports/gross-margin',headers=headers)
    assert response.status_code==200,response.text
    row=next(r for r in response.json()['items'] if r['id']==item['id'])
    assert row['revenue']==(50 if source_case=='valid' else 0)
    assert row['revenue_complete']==(source_case=='valid')
    assert response.json()['attribution']['unattributed_invoice_lines']==(0 if source_case=='valid' else 1)
