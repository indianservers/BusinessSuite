from datetime import date,datetime,timezone,timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
import io
import pytest
from fastapi import HTTPException
from app.apps.srm import reporting as r
from app.apps.srm.reporting_models import SRMReportFlag,SRMReportJob,SRMReportView
from app.apps.srm.models import SRMInvoiceLine,SRMReceiptAllocation,SRMInventoryBalance,SRMInventoryMovement,SRMPOSReturn
from app.models.company import Company,Branch
from app.models.user import User,Role
from app.apps.crm.models import CRMCompany
from app.branches.models import BranchOwnership
from tests.tenant_test_utils import assign_company


@pytest.fixture
def report_case(db):
    if not db.get(Company,1):db.add(Company(id=1,name='Reporting Company',default_timezone='Asia/Kolkata',default_currency='INR'))
    role=Role(name='srm_admin');db.add(role);db.flush()
    user=User(email='report-owner@example.com',hashed_password='unused',role_id=role.id,is_superuser=True,is_active=True)
    db.add(user);db.flush();assign_company(db,user,1)
    b=Branch(company_id=1,organization_id=1,name='Report Main',code='REP-MAIN');db.add(b);db.flush()
    warehouse=r.Warehouse(organization_id=1,warehouse_code='REP-WH',warehouse_name='Report warehouse',branch='Report Main');db.add(warehouse);db.flush()
    customer=CRMCompany(organization_id=1,name='Report customer');db.add(customer);db.flush()
    product=r.Product(organization_id=1,sku='REP-P1',item_name='Report product',default_warehouse_id=warehouse.id,unit_code='PCS',product_type='stock',track_inventory=True,purchase_rate=20,sales_rate=60,current_quantity=8,average_cost=20,reorder_level=8,max_stock=20,metadata_json={'currency':'INR'})
    test_product=r.Product(organization_id=1,sku='REP-QA',item_name='Explicit test product',default_warehouse_id=warehouse.id,product_type='stock',track_inventory=True,metadata_json={'currency':'INR','test_only':True})
    db.add_all([product,test_product]);db.flush()
    orders=[];invoices=[]
    for index,(currency,total,paid) in enumerate([('INR',118,100),('USD',20,0),('INR',100,100)]):
        order=r.Order(organization_id=1,order_number=f'REP-SO{index}',status='confirmed',title=f'Report sale {index}',customer_id=customer.id,currency=currency,created_by=user.id,subtotal=120 if index==0 else total,discount_amount=20 if index==0 else 0,tax_amount=18 if index==0 else 0,total_amount=total,created_at=datetime(2026,11,18,10,tzinfo=timezone.utc))
        db.add(order);db.flush();orders.append(order)
        invoice=r.Invoice(organization_id=1,invoice_number=f'REP-INV{index}',sales_order_id=order.id,customer_id=customer.id,status='partially_paid' if index==0 else 'approved',issue_date=date(2026,11,18),due_date=date(2026,11,19),currency=currency,subtotal=120 if index==0 else total,discount_amount=20 if index==0 else 0,tax_amount=18 if index==0 else 0,total_amount=total,paid_amount=paid,balance_amount=total-paid,created_by=user.id)
        db.add(invoice);db.flush();invoices.append(invoice)
    line=r.OrderLine(sales_order_id=orders[0].id,product_id=product.id,item_code=product.sku,description=product.item_name,quantity=2,unit_price=60,discount_amount=20,tax_amount=18,line_total=118)
    db.add(line);db.flush();db.add(SRMInvoiceLine(invoice_id=invoices[0].id,source_type='sales_order_line',source_id=line.id,description=product.item_name,quantity=2,unit_price=60,discount_amount=20,tax_amount=18,line_total=118))
    receipts=[]
    for index in (0,2):
        receipt=r.Receipt(organization_id=1,receipt_number=f'REP-R{index}',customer_id=customer.id,status='confirmed',receipt_date=date(2026,11,18),payment_method='cash',currency='INR',amount=100,unallocated_amount=0,created_by=user.id)
        db.add(receipt);db.flush();db.add(SRMReceiptAllocation(receipt_id=receipt.id,invoice_id=invoices[index].id,amount=100));receipts.append(receipt)
    db.add(SRMReportFlag(organization_id=1,branch_id=b.id,entity='invoice',resource_id=invoices[2].id,is_test=True,reason='Explicit test fixture',updated_by=user.id))
    balance=SRMInventoryBalance(organization_id=1,product_id=product.id,warehouse_id=warehouse.id,quantity=8,average_cost=20);db.add(balance)
    movements=[SRMInventoryMovement(organization_id=1,movement_number='REP-OPEN',movement_type='opening_stock',movement_date=date(2026,11,1),product_id=product.id,warehouse_id=warehouse.id,quantity_in=10,quantity_out=0,rate=20,value=200),SRMInventoryMovement(organization_id=1,movement_number='REP-SALE',movement_type='pos_sale',movement_date=date(2026,11,18),product_id=product.id,warehouse_id=warehouse.id,quantity_in=0,quantity_out=2,rate=20,value=40,reference_number=orders[0].order_number)]
    db.add_all(movements);db.flush()
    # Explicit native ownership lets HTTP checks exercise the real branch layer.
    objects=[warehouse,customer,product,test_product,*orders,*invoices,line,*receipts,balance,*movements]
    for obj in objects:db.add(BranchOwnership(company_id=1,branch_id=b.id,resource_table=obj.__tablename__,resource_key=str(obj.id),source='report-test-fixture'))
    db.commit()
    return SimpleNamespace(db=db,user=user,branch=b,warehouse=warehouse,customer=customer,product=product,test_product=test_product,orders=orders,invoices=invoices,balance=balance,filters=r.Filters(start=date(2026,11,18),end=date(2026,11,18)))


def test_dashboard_keeps_currencies_and_excludes_explicit_tests(report_case):
    n=report_case;data=r.run(n.db,n.user,'overview',n.filters)
    totals={row['currency']:row for row in data['items']}
    assert totals['INR']['invoiced']=='118.00' and totals['INR']['collections']=='100.00'
    assert totals['USD']['invoiced']=='20.00' and totals['USD']['collections']=='0.00'
    assert totals['INR']['gross']=='120.00' and totals['INR']['discounts']=='20.00'
    assert totals['INR']['outstanding']=='18.00'
    included=r.run(n.db,n.user,'overview',n.filters.model_copy(update={'include_test':True}))
    assert next(row for row in included['items'] if row['currency']=='INR')['invoiced']=='218.00'


@pytest.mark.parametrize('report',list(r.REPORTS))
def test_all_report_surfaces_have_real_rows_or_explicit_empty_state(report_case,report):
    n=report_case;data=r.run(n.db,n.user,report,n.filters,1,1)
    assert data['report']==report and data['columns']
    assert len(data['items'])<=1 or report=='overview'
    assert data['context']['timezone']=='Asia/Kolkata'


def test_filter_paging_and_test_badges(report_case):
    n=report_case
    first=r.run(n.db,n.user,'invoices',n.filters,1,1);second=r.run(n.db,n.user,'invoices',n.filters,2,1)
    assert first['total']==2 and first['has_more'] and first['items'][0]['id']!=second['items'][0]['id']
    assert all(not row['is_test'] for row in first['items']+second['items'])
    assert r.run(n.db,n.user,'invoices',n.filters.model_copy(update={'currency':'USD'}))['total']==1
    assert r.run(n.db,n.user,'invoices',n.filters.model_copy(update={'product_id':n.product.id}))['total']==1
    assert r.run(n.db,n.user,'invoices',n.filters.model_copy(update={'payment_method':'card'}))['total']==0
    assert r.run(n.db,n.user,'invoices',n.filters.model_copy(update={'start':date(2026,11,19),'end':date(2026,11,19)}))['total']==0


def test_stock_reconciliation_and_reorder_are_ledger_based(report_case):
    n=report_case;data=r.run(n.db,n.user,'reconciliation',n.filters);row=data['items'][0]
    assert data['total']==1 and row['opening']==10 and row['sales_issues']==2 and row['expected_closing']==8 and row['reconciled']
    stock=r.run(n.db,n.user,'stock',n.filters)['items'][0]
    assert stock['on_hand']==8 and stock['stock_value']=='160.00' and stock['suggested_reorder']==12 and stock['low_stock']
    n.balance.quantity=9;n.db.flush()
    assert r.run(n.db,n.user,'reconciliation',n.filters)['items'][0]['quantity_difference']==1
    historic=r.run(n.db,n.user,'reconciliation',n.filters.model_copy(update={'start':date(2026,11,1),'end':date(2026,11,17)}))['items'][0]
    assert historic['ledger_closing']==10 and historic['quantity_difference'] is None


def test_product_profit_uses_matched_historical_cost(report_case):
    n=report_case;row=r.run(n.db,n.user,'products',n.filters)['items'][0]
    assert row['billed_ex_tax']=='100.00' and row['recorded_issue_cost']=='40.00' and row['gross_profit']=='60.00'


@pytest.mark.parametrize('status,expected',[('confirmed','100.00'),('allocated','100.00'),('partially_allocated','100.00'),('cancelled','0.00')])
def test_collections_include_all_active_native_receipt_states(report_case,status,expected):
    n=report_case;receipt=n.db.query(r.Receipt).filter_by(receipt_number='REP-R0').one();receipt.status=status;n.db.flush()
    row=next(x for x in r.run(n.db,n.user,'overview',n.filters)['items'] if x['currency']=='INR')
    assert row['collections']==expected


def test_anonymous_invoices_are_never_claimed_as_repeat_people(report_case):
    n=report_case
    for invoice in n.invoices[:2]:invoice.customer_id=None;invoice.currency='INR'
    n.db.flush()
    row=r.run(n.db,n.user,'customers',n.filters)['items'][0]
    assert row['purchases']==2 and row['repeat_customer'] is False
    assert r.run(n.db,n.user,'customers',n.filters.model_copy(update={'customer_segment':'repeat'}))['total']==0
    for invoice in n.invoices[:2]:invoice.issue_date=date(2018,1,1)
    n.db.flush();assert r.run(n.db,n.user,'customers',n.filters)['items'][0]['inactive'] is False
    assert r.run(n.db,n.user,'customers',n.filters.model_copy(update={'customer_segment':'inactive'}))['total']==0


def test_repeat_and_inactive_customers_are_identified_across_currencies(report_case):
    n=report_case
    data=r.run(n.db,n.user,'customers',n.filters.model_copy(update={'customer_segment':'repeat'}))
    assert data['total']==2 and all(x['repeat_customer'] and x['lifetime_purchases']==2 for x in data['items'])
    n.invoices[0].issue_date=date(2018,1,1);n.db.flush()
    data=r.run(n.db,n.user,'customers',n.filters.model_copy(update={'customer_segment':'inactive','currency':'INR'}))
    assert data['total']==0,'A recent USD purchase must keep the named customer active'


def test_export_contains_every_filtered_page_and_escapes_spreadsheet_formulas(report_case):
    from app.apps.srm.reporting_exports import collect,render,fingerprint
    from openpyxl import load_workbook
    n=report_case;data=collect(n.db,n.user,'invoices',n.filters)
    assert len(data['items'])==2 and data['currency_totals']['INR']['total']=='118.00'
    data['items'][0]['customer']='=HYPERLINK("bad")'
    csv=render(data,'csv').decode('utf-8-sig');assert "'=HYPERLINK" in csv and 'Report context' not in csv
    workbook=load_workbook(io.BytesIO(render(data,'xlsx')))
    index=data['columns'].index('customer')+1
    assert workbook['Report'].cell(2,index).data_type=='s'
    pdf=render(data,'pdf');assert pdf.startswith(b'%PDF')
    import os
    if os.environ.get('REPORT_ARTIFACT_DIR'):
        from pathlib import Path
        path=Path(os.environ['REPORT_ARTIFACT_DIR']);path.mkdir(parents=True,exist_ok=True)
        (path/'sample-report.pdf').write_bytes(pdf)
        (path/'sample-report.xlsx').write_bytes(render(data,'xlsx'))
    assert fingerprint(data)==fingerprint({**data,'context':{**data['context'],'as_of':'changed'}})


def test_filters_reject_reversed_dates_and_native_scope_cannot_replace_pack(report_case):
    with pytest.raises(ValueError):r.Filters(start=date(2026,11,20),end=date(2026,11,1))
    n=report_case;n.db.info['business_pack_scope']=object()
    try:
        with pytest.raises(HTTPException):r.run(n.db,n.user,'overview',n.filters)
    finally:n.db.info.pop('business_pack_scope')


def api_case(n):
    from app.branches.service import context
    n.db.info['branch_context']=context(n.db,n.user,1,n.branch.id)
    from app.apps.srm import reporting_api
    return reporting_api


def test_classification_is_atomic_and_does_not_change_financials(report_case):
    n=report_case;api=api_case(n);before=n.invoices[0].total_amount
    with pytest.raises(HTTPException):api.mark_test(api.TestInput(entity='invoice',ids=[n.invoices[0].id,999999],is_test=True,reason='Explicit QA selection'),n.db,n.user)
    assert n.db.query(SRMReportFlag).filter_by(resource_id=n.invoices[0].id,entity='invoice').count()==0
    api.mark_test(api.TestInput(entity='invoice',ids=[n.invoices[0].id],is_test=True,reason='Explicit QA selection'),n.db,n.user)
    assert r.run(n.db,n.user,'invoices',n.filters)['total']==1
    assert n.db.get(r.Invoice,n.invoices[0].id).total_amount==before


def test_report_owner_and_action_permissions_are_enforced(report_case):
    n=report_case;api=api_case(n)
    view=SRMReportView(organization_id=1,branch_id=n.branch.id,owner_id=n.user.id,name='Private',report='invoices',filters_json={},columns_json=[])
    n.db.add(view);n.db.commit()
    stranger=SimpleNamespace(id=n.user.id+99,organization_id=1,company_id=1)
    with pytest.raises(HTTPException):api.owned(n.db,SRMReportView,view.id,stranger)
    n.user.is_superuser=False;n.user._suite_grants={'srm':{'enabled':True,'actions':['view']}}
    with pytest.raises(HTTPException):api.writable(n.user)


def test_export_idempotency_and_reused_key_rejection(report_case):
    from fastapi import BackgroundTasks
    n=report_case;api=api_case(n);key=uuid4();tasks=BackgroundTasks()
    data=api.ExportInput(request_key=key,report='invoices',format='csv',filters=n.filters)
    first=api.queue_export(data,tasks,n.db,n.user)
    assert api.queue_export(data,tasks,n.db,n.user)['id']==first['id']
    with pytest.raises(HTTPException):api.queue_export(data.model_copy(update={'format':'pdf'}),tasks,n.db,n.user)
    assert n.db.query(SRMReportJob).count()==1


def test_draft_reorder_deduplicates_and_never_posts_stock(report_case):
    n=report_case;api=api_case(n);before=n.balance.quantity
    data=api.ReorderInput(request_key=uuid4(),product_id=n.product.id,warehouse_id=n.warehouse.id,quantity=3,vendor_name='QA supplier')
    result=api.reorder_draft(data,n.db,n.user)
    assert result['status']=='draft' and api.reorder_draft(data,n.db,n.user)['id']==result['id']
    assert n.db.get(SRMInventoryBalance,n.balance.id).quantity==before
    stock=r.run(n.db,n.user,'stock',n.filters)['items'][0]
    assert stock['open_purchase_quantity']==3 and stock['suggested_reorder']==9


def test_schedules_are_paused_by_default_and_validate_timezone(report_case):
    n=report_case;api=api_case(n)
    result=api.save_schedule(api.ScheduleInput(),n.db,n.user)
    assert result['enabled'] is False and result['next_run_at'] is None
    with pytest.raises(HTTPException):api.save_schedule(api.ScheduleInput(timezone='Not/AZone'),n.db,n.user)


def test_low_only_schedule_does_not_spin_or_repeat_alerts(report_case,monkeypatch):
    from contextlib import contextmanager
    from app.apps.srm import reporting_jobs as jobs
    from app.apps.srm.reporting_models import SRMReportSchedule
    n=report_case;now=datetime(2026,11,18,12,tzinfo=timezone.utc)
    row=SRMReportSchedule(organization_id=1,branch_id=n.branch.id,owner_id=n.user.id,enabled=True,config_json={'digest':False,'watch_low_stock':True,'channels':['in_app'],'timezone':'Asia/Kolkata'},state_json={})
    n.db.add(row);n.db.commit();sent=[]
    @contextmanager
    def owner(db,row):yield n.user
    monkeypatch.setattr(jobs,'owner_scope',owner)
    monkeypatch.setattr(jobs,'notify',lambda *args:sent.append(args[3]))
    jobs.run_schedule(n.db,row,now)
    assert jobs.aware(row.next_run_at)==now+timedelta(minutes=5) and len(sent)==1
    jobs.run_schedule(n.db,row,now+timedelta(minutes=5));assert len(sent)==1
    n.balance.quantity=30;n.db.commit()
    jobs.run_schedule(n.db,row,now+timedelta(minutes=10));assert len(sent)==2 and 'replenished' in sent[-1]


@pytest.mark.parametrize('receipt_kind',['grn_receipt','stock_in'])
def test_reconciliation_splits_equation_and_highlights_only_real_discrepancies(report_case,receipt_kind):
    n=report_case
    for index,(kind,received,issued) in enumerate([(receipt_kind,5,0),('pos_return',2,0),('pos_sale',0,3),('adjustment',0,1),('transfer_in',4,0)]):
        n.db.add(SRMInventoryMovement(organization_id=1,movement_number=f'EQUATION-{index}',movement_type=kind,movement_date=date(2026,11,18),product_id=n.product.id,warehouse_id=n.warehouse.id,quantity_in=received,quantity_out=issued,rate=20,value=0))
    n.balance.quantity=15;n.db.flush()
    row=r.run(n.db,n.user,'reconciliation',n.filters)['items'][0]
    assert (row['opening'],row['receipts'],row['customer_returns'],row['sales_issues'],row['adjustments'])==(10,5,2,5,3)
    assert row['expected_closing']==15 and row['reconciled'] is True
    f=n.filters.model_copy(update={'discrepancy_only':True})
    assert r.run(n.db,n.user,'reconciliation',f)['total']==0
    n.balance.quantity=14;n.db.flush();row=r.run(n.db,n.user,'reconciliation',f)['items'][0]
    assert row['quantity_difference']==-1 and row['reconciled'] is False


def test_manual_stock_out_is_an_adjustment_not_a_sale(report_case):
    n=report_case;n.db.add(SRMInventoryMovement(organization_id=1,movement_number='MANUAL-LOSS',movement_type='stock_out',movement_date=date(2026,11,18),product_id=n.product.id,warehouse_id=n.warehouse.id,quantity_in=0,quantity_out=1,rate=20,value=20));n.balance.quantity=7;n.db.flush()
    row=r.run(n.db,n.user,'reconciliation',n.filters)['items'][0]
    assert row['sales_issues']==2 and row['adjustments']==-1 and row['expected_closing']==7 and row['reconciled'] is True


def test_first_day_opening_posting_appears_in_opening_column(report_case):
    n=report_case;f=n.filters.model_copy(update={'start':date(2026,11,1)})
    row=r.run(n.db,n.user,'reconciliation',f)['items'][0]
    assert row['opening']==10 and row['adjustments']==0 and row['sales_issues']==2 and row['expected_closing']==8


def test_out_of_stock_without_threshold_is_prioritized_and_supplier_is_recovered(report_case):
    n=report_case;n.test_product.metadata_json={};n.test_product.reorder_level=0
    po=r.Purchase(organization_id=1,po_number='SUPPLIER-HISTORY',vendor_name='Last known supplier',status='received',order_date=date(2026,11,1))
    n.db.add(po);n.db.flush();n.db.add(r.PurchaseLine(purchase_order_id=po.id,product_id=n.product.id,warehouse_id=n.warehouse.id,quantity=5,received_quantity=5));n.db.flush()
    data=r.run(n.db,n.user,'stock',n.filters.model_copy(update={'low_only':True}))
    assert data['items'][0]['id']==n.test_product.id and data['items'][0]['priority']=='Out of stock'
    normal=next(x for x in data['items'] if x['id']==n.product.id)
    assert normal['supplier']=='Last known supplier' and normal['supplier_last_po']=='SUPPLIER-HISTORY'
    assert r.low_stock_ids(n.db,n.user,n.filters)=={str(n.product.id),str(n.test_product.id)}


def test_supplier_recovery_from_goods_receipt_without_purchase_order(report_case):
    n=report_case;grn=r.GoodsReceipt(organization_id=1,grn_number='SUPPLIER-GRN',vendor_name='Received stock supplier',status='posted',receipt_date=date(2026,11,18))
    n.db.add(grn);n.db.flush();n.db.add(r.GoodsReceiptLine(goods_receipt_id=grn.id,product_id=n.product.id,warehouse_id=n.warehouse.id,quantity=10,accepted_quantity=10));n.db.flush()
    row=r.run(n.db,n.user,'stock',n.filters)['items'][0]
    assert row['supplier']=='Received stock supplier' and row['supplier_source']=='SUPPLIER-GRN'


def test_relative_saved_period_resolves_and_exports_freeze_dates(report_case):
    n=report_case;f=r.resolved(n.db,n.user,n.filters.model_copy(update={'period_preset':'yesterday'}))
    assert f.start==r.business_day(n.db,n.user)-timedelta(days=1) and f.end==f.start and f.period_preset=='custom'
    api=api_case(n)
    result=api.create_view(api.ViewInput(name='Daily Main',report='invoices',filters=n.filters.model_copy(update={'period_preset':'today'}),columns=['invoice','total']),n.db,n.user)
    assert result['filters']['period_preset']=='today' and result['columns']==['invoice','total']
    with pytest.raises(HTTPException):api.create_view(api.ViewInput(name='   ',report='invoices',filters=n.filters),n.db,n.user)


def test_customer_purchase_history_is_not_limited_to_dashboard_dates(report_case):
    n=report_case;n.invoices[0].issue_date=date(2018,1,1);n.db.flush();api=api_case(n)
    assert r.run(n.db,n.user,'invoices',n.filters)['total']==1
    history=api.customer_history(n.customer.id,'INR',False,1,25,n.db,n.user)
    assert history['total']==1 and history['items'][0]['date']==date(2018,1,1)


def test_summary_open_rechecks_current_authorized_figures(report_case):
    from app.apps.srm.reporting_models import SRMReportSchedule
    n=report_case;api=api_case(n)
    row=SRMReportSchedule(organization_id=1,branch_id=n.branch.id,owner_id=n.user.id,enabled=False,config_json={},state_json={'last_digest':{'period':n.filters.model_dump(mode='json'),'generated_at':'2026-11-18T10:00:00Z','totals':[{'currency':'INR','invoiced':'999999.00'}]}})
    n.db.add(row);n.db.flush();data=api.schedule_payload(row,n.user,n.db)
    assert next(x for x in data['state']['last_digest']['totals'] if x['currency']=='INR')['invoiced']=='118.00'
    assert data['state']['last_digest']['refreshed_at']


def test_stock_monitor_tracks_more_than_one_display_page(report_case):
    n=report_case
    n.db.add_all([r.Product(organization_id=1,sku=f'ALERT-{i}',item_name=f'Alert item {i}',product_type='stock',track_inventory=True,metadata_json={}) for i in range(205)])
    n.db.flush()
    assert len(r.low_stock_ids(n.db,n.user,n.filters))==206


@pytest.mark.parametrize('frequency',['daily','weekly'])
def test_summary_worker_generates_once_and_keeps_next_occurrence(report_case,monkeypatch,frequency):
    from contextlib import contextmanager
    from app.apps.srm import reporting_jobs as jobs
    from app.apps.srm.reporting_models import SRMReportSchedule
    n=report_case;now=datetime(2026,11,19,12,tzinfo=timezone.utc);sent=[]
    row=SRMReportSchedule(organization_id=1,branch_id=n.branch.id,owner_id=n.user.id,enabled=True,config_json={'frequency':frequency,'at':'09:00','weekday':0,'timezone':'Asia/Kolkata','period':'yesterday','digest':True,'watch_low_stock':False,'channels':['in_app']},state_json={})
    n.db.add(row);n.db.commit()
    @contextmanager
    def owner(db,row):yield n.user
    monkeypatch.setattr(jobs,'owner_scope',owner);monkeypatch.setattr(jobs,'notify',lambda *args:sent.append(args[3]))
    jobs.run_schedule(n.db,row,now);jobs.run_schedule(n.db,row,now+timedelta(seconds=1))
    assert len(sent)==1 and row.state_json['last_digest']['period']['start']=='2026-11-18'
    assert jobs.aware(row.next_run_at)>now
    if frequency=='weekly':assert jobs.aware(row.next_run_at).weekday()==0


def test_summary_preview_is_read_only_and_rejects_invalid_zone(report_case):
    from app.apps.srm.reporting_models import SRMReportSchedule
    n=report_case;api=api_case(n)
    preview=api.preview_schedule('today','Asia/Kolkata',False,None,n.db,n.user)
    assert preview['report']=='overview' and n.db.query(SRMReportSchedule).count()==0
    with pytest.raises(HTTPException):api.preview_schedule('today','Invalid/Zone',False,None,n.db,n.user)

def test_saved_view_crud_is_recoverable_and_rejects_stale_edits(report_case):
    n=report_case;api=api_case(n)
    financial_before=[(x.id,x.total_amount,x.balance_amount) for x in n.invoices]
    data=dict(name='CRUD report',report='invoices',filters=n.filters,columns=['invoice','total'])
    first=api.create_view(api.ViewInput(**data),n.db,n.user)
    assert first['revision']==1 and first['deleted_at'] is None
    assert first['id'] in [v['id'] for v in api.views(False,n.db,n.user)]
    updated=api.update_view(first['id'],api.ViewUpdate(**{**data,'name':'Renamed report'},expected_revision=1),n.db,n.user)
    assert updated['name']=='Renamed report' and updated['revision']==2
    with pytest.raises(HTTPException) as stale:api.update_view(first['id'],api.ViewUpdate(**data,expected_revision=1),n.db,n.user)
    assert stale.value.status_code==409
    n.db.rollback()
    with pytest.raises(HTTPException) as stale:api.delete_view(first['id'],1,n.db,n.user)
    assert stale.value.status_code==409
    n.db.rollback()
    api.delete_view(first['id'],2,n.db,n.user)
    assert first['id'] not in [v['id'] for v in api.views(False,n.db,n.user)]
    deleted=api.views(True,n.db,n.user)[0]
    assert deleted['deleted_at'] and deleted['revision']==3
    with pytest.raises(HTTPException):api.update_view(first['id'],api.ViewUpdate(**data,expected_revision=3),n.db,n.user)
    n.db.rollback()
    restored=api.restore_view(first['id'],3,n.db,n.user)
    assert restored['deleted_at'] is None and restored['revision']==4
    assert restored['name']=='Renamed report' and restored['columns']==['invoice','total']
    assert n.db.get(SRMReportView,first['id']) is not None
    assert [(x.id,x.total_amount,x.balance_amount) for x in n.invoices]==financial_before


def test_saved_view_writes_require_owner_branch_and_correct_action(report_case,monkeypatch):
    n=report_case;api=api_case(n)
    data=dict(name='Private report',report='invoices',filters=n.filters,columns=['invoice'])
    row=api.create_view(api.ViewInput(**data),n.db,n.user)
    other=User(email='other-report@example.com',hashed_password='unused',is_superuser=True,is_active=True,role_id=n.user.role_id)
    n.db.add(other);n.db.flush();assign_company(n.db,other,1);n.db.commit()
    with pytest.raises(HTTPException) as denied:api.update_view(row['id'],api.ViewUpdate(**data,expected_revision=1),n.db,other)
    assert denied.value.status_code==404
    n.db.rollback()
    calls=[]
    monkeypatch.setattr(api,'require_module_action',lambda user,module,action:calls.append((module,action)))
    api.update_view(row['id'],api.ViewUpdate(**data,expected_revision=1),n.db,n.user)
    api.delete_view(row['id'],2,n.db,n.user)
    api.restore_view(row['id'],3,n.db,n.user)
    assert calls==[('srm','edit'),('srm','delete'),('srm','edit')]

def test_saved_view_branch_scope_cannot_be_bypassed(report_case):
    n=report_case;api=api_case(n)
    data=dict(name='Branch private report',report='invoices',filters=n.filters,columns=['invoice'])
    row=api.create_view(api.ViewInput(**data),n.db,n.user)
    from app.branches.service import context
    second=Branch(company_id=1,organization_id=1,name='Other report branch',code='REP-OTHER');n.db.add(second);n.db.commit()
    n.db.info['branch_context']=context(n.db,n.user,1,second.id)
    assert api.views(False,n.db,n.user)==[]
    for operation in [lambda:api.delete_view(row['id'],1,n.db,n.user),lambda:api.restore_view(row['id'],1,n.db,n.user)]:
        with pytest.raises(HTTPException) as denied:operation()
        assert denied.value.status_code==404
        n.db.rollback()

def test_saved_view_revision_checks_refresh_cached_orm_state(report_case):
    from sqlalchemy import update
    n=report_case;api=api_case(n)
    row=api.create_view(api.ViewInput(name='Cached report',report='invoices',filters=n.filters,columns=['invoice']),n.db,n.user)
    cached=n.db.get(SRMReportView,row['id']);assert cached.revision==1
    n.db.execute(update(SRMReportView).where(SRMReportView.id==row['id']).values(revision=2).execution_options(synchronize_session=False))
    assert cached.revision==1
    with pytest.raises(HTTPException) as stale:api.delete_view(row['id'],1,n.db,n.user)
    assert stale.value.status_code==409 and cached.revision==2
