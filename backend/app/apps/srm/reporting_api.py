from __future__ import annotations
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.deps import get_db, RequirePermission
from app.access.service import require_module_action
from app.apps.srm.access import has_any_permission, sales_order_query
from app.apps.srm.services.commercial import tenant, invoice_query, lock_tenant
from app.apps.srm.models import SRMInvoice, SRMReceipt, SRMProduct, SRMWarehouse, SRMPurchaseOrder, SRMPurchaseOrderLine, SRMAuditLog
from app.apps.srm.reporting_models import SRMReportView as View, SRMReportFlag as Flag, SRMReportJob as Job, SRMReportSchedule as Schedule
from . import reporting as reports

router=APIRouter(prefix='/reporting',tags=['Sales reports'])
reader=RequirePermission('srm_view','srm_invoice_view','srm_collection_view','srm_profitability_view','srm_admin')


def writable(user,action='edit'):
    require_module_action(user,'srm',action)
    if not has_any_permission(user,{'srm_manage','srm_admin','srm_settings_manage'}):
        raise HTTPException(403,'Sales management permission is required')


def branch(db):
    context=db.info.get('branch_context')
    if context is None or not context.branch_id:
        raise HTTPException(422,'Choose one branch before saving reports, exports or schedules')
    return context.branch_id


def audit(db,user,kind,identity,action,before=None,after=None):
    db.add(SRMAuditLog(organization_id=tenant(user),entity_type=kind,entity_id=identity,
        actor_user_id=user.id,action=action,before_json=before,after_json=after))


def filters_from(request):
    try:return reports.Filters.model_validate({k:v for k,v in request.query_params.items() if k not in {'page','page_size'}})
    except ValidationError as error:raise HTTPException(422, [{'loc':list(e['loc']),'msg':e['msg'],'type':e['type']} for e in error.errors()]) from None


def owned(db,model,identity,user):
    row=db.query(model).filter_by(id=identity,organization_id=tenant(user),owner_id=user.id).first()
    if not row:raise HTTPException(404,'Report record not found in your current scope')
    return row


def view_payload(row):
    return {'id':row.id,'name':row.name,'report':row.report,'filters':row.filters_json,'columns':row.columns_json,'updated_at':row.updated_at,'branch_id':row.branch_id,'revision':row.revision,'deleted_at':row.deleted_at}


def job_payload(row):
    return {'id':row.id,'report':row.report,'format':row.format,'status':row.status,'row_count':row.row_count,
        'created_at':row.created_at,'completed_at':row.completed_at,'expires_at':row.expires_at,'error':row.error,
        'download_url':f'/srm/reporting/exports/{row.id}/download' if row.status=='ready' else None}


@router.get('/metadata')
def metadata(db=Depends(get_db),user=Depends(reader)):
    reports.native(db)
    grants=getattr(user,'_suite_grants',None)
    actions=(grants or {}).get('srm',{}).get('actions',[]) if grants is not None and not user.is_superuser else None
    can_edit=(actions is None or 'edit' in actions) and has_any_permission(user,{'srm_manage','srm_admin','srm_settings_manage'})
    from app.core.config import settings
    return {'reports':[{'key':key,'title':value} for key,value in reports.REPORTS.items()],
        'context':reports.business_context(db,user),'can_export':actions is None or 'export' in actions,
        'can_edit':can_edit,'can_create':(actions is None or 'create' in actions) and has_any_permission(user,{'srm_manage','srm_admin','srm_settings_manage'}),'can_delete':(actions is None or 'delete' in actions) and has_any_permission(user,{'srm_manage','srm_admin','srm_settings_manage'}),'schedule_recipient':user.email,'worker_enabled':settings.EMAIL_WORKER_ENABLED,
        'export_limit':10000,'formats':['csv','xlsx','pdf'],'data_source':'Native Sales & POS; connected accounting retains its separate report.'}


@router.get('/options')
def options(search:str=Query('',max_length=100),include_test:bool=False,db=Depends(get_db),user=Depends(reader)):
    reports.native(db)
    f=reports.resolved(db,user,reports.Filters(search=search,include_test=include_test))
    q=reports.invoices(db,user,f,dates=False)
    customers=db.query(reports.CRMCompany.id,reports.CRMCompany.name).filter(reports.CRMCompany.id.in_(q.with_entities(SRMInvoice.customer_id)))
    products=reports.product_query(db,user,f).order_by(SRMProduct.item_name,SRMProduct.id).limit(100).all()
    warehouses=db.query(SRMWarehouse).filter_by(organization_id=tenant(user),active=True).order_by(SRMWarehouse.warehouse_name).limit(100).all()
    cashier_ids=[identity for identity, in q.with_entities(SRMInvoice.created_by).filter(SRMInvoice.created_by.is_not(None)).distinct().limit(100).all()]
    return {'customers':[{'id':ident,'label':name} for ident,name in customers.order_by(reports.CRMCompany.name).limit(100).all()],
        'products':[{'id':p.id,'label':f'{p.item_name} · {p.sku}'} for p in products],
        'warehouses':[{'id':w.id,'label':w.warehouse_name} for w in warehouses],
        'cashiers':[{'id':identity,'label':f'User #{identity}'} for identity in cashier_ids],
        'payment_methods':['cash','upi','card','bank_transfer','cheque','wallet','other'],
        'currencies':[str(code) for code, in q.with_entities(SRMInvoice.currency).distinct().limit(50).all() if code],
        'bounded':True,'limit':100}


class ViewInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=100)
    report:str=Field(max_length=40)
    filters:reports.Filters
    columns:list[str]=Field(default_factory=list,max_length=40)


@router.get('/views')
def views(archived:bool=False,db=Depends(get_db),user=Depends(reader)):
    reports.native(db)
    q=db.query(View).filter_by(organization_id=tenant(user),branch_id=branch(db),owner_id=user.id)
    q=q.filter(View.deleted_at.is_not(None) if archived else View.deleted_at.is_(None))
    return [view_payload(row) for row in q.order_by(View.name,View.id).limit(100).all()]


@router.post('/views',status_code=201)
def create_view(data:ViewInput,db=Depends(get_db),user=Depends(reader)):
    reports.native(db);writable(user,'create')
    if not data.name.strip():raise HTTPException(422,'Enter a report view name')
    if data.report not in reports.REPORTS:raise HTTPException(422,'Choose a registered report')
    available=reports.run(db,user,data.report,data.filters,1,1)['columns']
    if len(set(data.columns))!=len(data.columns) or any(name not in available for name in data.columns):raise HTTPException(422,'Choose valid report columns')
    lock_tenant(db,user)
    if db.query(View).filter_by(organization_id=tenant(user),branch_id=branch(db),owner_id=user.id).count()>=100:raise HTTPException(422,'You can save up to 100 report views, including Recently deleted')
    row=View(organization_id=tenant(user),branch_id=branch(db),owner_id=user.id,name=data.name.strip(),report=data.report,
        filters_json=data.filters.model_dump(mode='json'),columns_json=data.columns)
    db.add(row);db.flush();audit(db,user,'report_view',row.id,'CREATE');db.commit();db.refresh(row);return view_payload(row)


class ViewUpdate(ViewInput):
    expected_revision:int=Field(ge=1)


def locked_view(db,identity,user,expected_revision):
    lock_tenant(db,user)
    row=db.query(View).filter_by(id=identity,organization_id=tenant(user),branch_id=branch(db),owner_id=user.id).populate_existing().with_for_update().first()
    if not row:raise HTTPException(404,'Report record not found in your current scope')
    if row.revision!=expected_revision:raise HTTPException(409,'This saved report changed in another tab. Reload saved reports and load it again before editing.')
    return row


@router.put('/views/{identity}')
def update_view(identity:int,data:ViewUpdate,db=Depends(get_db),user=Depends(reader)):
    reports.native(db);writable(user)
    if not data.name.strip():raise HTTPException(422,'Enter a report view name')
    if data.report not in reports.REPORTS:raise HTTPException(422,'Choose a registered report')
    available=reports.run(db,user,data.report,data.filters,1,1)['columns']
    if len(set(data.columns))!=len(data.columns) or any(name not in available for name in data.columns):raise HTTPException(422,'Choose valid report columns')
    row=locked_view(db,identity,user,data.expected_revision)
    if row.deleted_at:raise HTTPException(409,'Restore this saved report before editing it')
    before=view_payload(row);before={k:v for k,v in before.items() if k not in {'updated_at','deleted_at'}}
    row.name=data.name.strip();row.report=data.report;row.filters_json=data.filters.model_dump(mode='json');row.columns_json=data.columns;row.revision+=1
    audit(db,user,'report_view',row.id,'UPDATE',before,{'name':row.name,'revision':row.revision})
    db.commit();db.refresh(row);return view_payload(row)


@router.delete('/views/{identity}',status_code=204)
def delete_view(identity:int,expected_revision:int=Query(...,ge=1),db=Depends(get_db),user=Depends(reader)):
    reports.native(db);writable(user,'delete');row=locked_view(db,identity,user,expected_revision)
    if row.deleted_at:raise HTTPException(409,'This saved report is already in Recently deleted')
    row.deleted_at=datetime.now(timezone.utc);row.revision+=1
    audit(db,user,'report_view',row.id,'TRASH');db.commit()


@router.patch('/views/{identity}/restore')
def restore_view(identity:int,expected_revision:int=Query(...,ge=1),db=Depends(get_db),user=Depends(reader)):
    reports.native(db);writable(user);row=locked_view(db,identity,user,expected_revision)
    if not row.deleted_at:raise HTTPException(409,'This saved report is already active')
    if db.query(View).filter_by(organization_id=tenant(user),branch_id=branch(db),owner_id=user.id).filter(View.deleted_at.is_(None)).count()>=100:raise HTTPException(422,'You can save up to 100 report views')
    row.deleted_at=None;row.revision+=1;audit(db,user,'report_view',row.id,'RESTORE');db.commit();db.refresh(row);return view_payload(row)


class TestInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    entity:str=Field(pattern=r'^(invoice|sales_order|receipt|product)$')
    ids:list[int]=Field(min_length=1,max_length=200)
    is_test:bool
    reason:str=Field(min_length=3,max_length=500)


@router.put('/test-flags')
def mark_test(data:TestInput,db=Depends(get_db),user=Depends(reader)):
    reports.native(db);writable(user);branch_id=branch(db);identities=set(data.ids)
    if any(type(identity) is not int or identity<1 for identity in identities):raise HTTPException(422,'Choose valid record identifiers')
    sources={'invoice':invoice_query(db,user),'sales_order':sales_order_query(db,user),
        'receipt':reports.receipt_query(db,user,reports.resolved(db,user,reports.Filters(include_test=True)),dates=False),
        'product':reports.product_query(db,user,reports.Filters(include_test=True))}
    model={'invoice':SRMInvoice,'sales_order':reports.Order,'receipt':SRMReceipt,'product':SRMProduct}[data.entity]
    visible=sources[data.entity].filter(model.id.in_(identities)).all()
    if {row.id for row in visible}!=identities:raise HTTPException(404,'One or more records are outside your current scope')
    lock_tenant(db,user)
    for identity in sorted(identities):
        row=db.query(Flag).filter_by(organization_id=tenant(user),entity=data.entity,resource_id=identity).with_for_update().first()
        before={'is_test':row.is_test} if row else None
        if row is None:
            row=Flag(organization_id=tenant(user),branch_id=branch_id,entity=data.entity,resource_id=identity)
            db.add(row)
        row.is_test=data.is_test;row.reason=data.reason;row.updated_by=user.id;db.flush()
        audit(db,user,'report_test_flag',row.id,'CLASSIFY',before,{'entity':data.entity,'resource_id':identity,'is_test':data.is_test,'reason':data.reason})
    db.commit();return {'updated':len(identities),'is_test':data.is_test}


class ExportInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_key:UUID
    report:str=Field(max_length=40)
    format:str=Field(pattern=r'^(csv|xlsx|pdf)$')
    filters:reports.Filters
    columns:list[str]=Field(default_factory=list,max_length=40)


@router.get('/exports')
def exports(db=Depends(get_db),user=Depends(reader)):
    reports.native(db);require_module_action(user,'srm','export')
    return [job_payload(row) for row in db.query(Job).filter_by(organization_id=tenant(user),owner_id=user.id).order_by(Job.id.desc()).limit(20).all()]


@router.post('/exports',status_code=202)
def queue_export(data:ExportInput,tasks:BackgroundTasks,db=Depends(get_db),user=Depends(reader)):
    reports.native(db);require_module_action(user,'srm','export');branch_id=branch(db)
    if data.report not in reports.REPORTS:raise HTTPException(422,'Choose a registered report')
    f=reports.resolved(db,user,data.filters)
    lock_tenant(db,user)
    row=db.query(Job).filter_by(organization_id=tenant(user),request_key=str(data.request_key)).first()
    if row:
        if row.owner_id!=user.id or row.branch_id!=branch_id or row.report!=data.report or row.format!=data.format or row.filters_json!=f.model_dump(mode='json') or row.columns_json!=data.columns:
            raise HTTPException(409,'This export request key was already used for different options')
        return job_payload(row)
    active=db.query(Job).filter(Job.organization_id==tenant(user),Job.owner_id==user.id,Job.status.in_(['queued','running'])).count()
    if active>=3:raise HTTPException(429,'Wait for your queued exports to finish before starting another')
    row=Job(organization_id=tenant(user),branch_id=branch_id,owner_id=user.id,request_key=str(data.request_key),report=data.report,
        format=data.format,filters_json=f.model_dump(mode='json'),columns_json=data.columns,status='queued',row_count=0,
        expires_at=datetime.now(timezone.utc)+timedelta(hours=24))
    db.add(row);db.flush();audit(db,user,'report_export',row.id,'QUEUE',after={'report':row.report,'format':row.format});db.commit();db.refresh(row)
    from .reporting_jobs import prepare_job
    from app.db.tenant import current_tenant
    tasks.add_task(prepare_job,row.id,current_tenant.get())
    return job_payload(row)


@router.get('/exports/{identity}/download')
def download(identity:int,db=Depends(get_db),user=Depends(reader)):
    reports.native(db);require_module_action(user,'srm','export');row=owned(db,Job,identity,user)
    expiry=row.expires_at.replace(tzinfo=timezone.utc) if row.expires_at.tzinfo is None else row.expires_at
    if row.status!='ready' or expiry<=datetime.now(timezone.utc):raise HTTPException(409,'Prepare a new export; this job is unfinished or expired')
    from .reporting_exports import collect,fingerprint
    data=collect(db,user,row.report,reports.Filters.model_validate(row.filters_json),row.columns_json)
    if fingerprint(data)!=row.content_sha256:raise HTTPException(409,'Report data or access changed. Prepare a fresh export to download current authorized rows.')
    from .reporting_jobs import export_directory
    path=export_directory()/str(row.file_path)
    if path.resolve().parent!=export_directory().resolve() or not path.is_file():raise HTTPException(404,'Export file unavailable; prepare it again')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=path.stem.split('-')[-1]:raise HTTPException(409,'Export verification failed; prepare it again')
    audit(db,user,'report_export',row.id,'DOWNLOAD');db.commit()
    types={'csv':'text/csv; charset=utf-8','xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','pdf':'application/pdf'}
    return FileResponse(path,filename=f'{row.report}-{data["filters"]["start"]}-{data["filters"]["end"]}.{row.format}',media_type=types[row.format],headers={'Cache-Control':'private, no-store'})


class ScheduleInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    enabled:bool=False
    frequency:str=Field(default='daily',pattern='^(daily|weekly)$')
    at:str=Field(default='09:00',pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')
    timezone:str=Field(default='Asia/Kolkata',max_length=80)
    weekday:int=Field(default=0,ge=0,le=6)
    period:str=Field(default='yesterday',pattern='^(today|yesterday|last7days)$')
    channels:list[str]=Field(default_factory=lambda:['in_app'],min_length=1,max_length=2)
    watch_low_stock:bool=True
    digest:bool=True
    include_test:bool=False
    warehouse_id:int|None=Field(default=None,gt=0)


def schedule_payload(row,user,db):
    if not row:return None
    state=dict(row.state_json or {})
    if state.get('last_digest'):
        original=state['last_digest']
        fresh=reports.overview(db,user,reports.resolved(db,user,reports.Filters.model_validate(original['period'])))
        state['last_digest']={**original,'totals':fresh['items'],'refreshed_at':datetime.now(timezone.utc).isoformat()}
    return {'id':row.id,'enabled':row.enabled,'config':row.config_json,'state':state,
        'next_run_at':row.next_run_at,'last_run_at':row.last_run_at,'last_error':row.last_error,
        'recipient':user.email,'delivery':'Detailed data stays in the signed-in app. Email contains a report link only.'} if row else None


@router.get('/schedule')
def read_schedule(db=Depends(get_db),user=Depends(reader)):
    reports.native(db)
    row=db.query(Schedule).filter_by(organization_id=tenant(user),owner_id=user.id,branch_id=branch(db)).first()
    return schedule_payload(row,user,db)


@router.put('/schedule')
def save_schedule(data:ScheduleInput,db=Depends(get_db),user=Depends(reader)):
    reports.native(db);writable(user);require_module_action(user,'srm','export')
    from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
    try:ZoneInfo(data.timezone)
    except (ZoneInfoNotFoundError,ValueError):raise HTTPException(422,'Choose a valid IANA timezone') from None
    if set(data.channels)-{'in_app','email'} or len(set(data.channels))!=len(data.channels):raise HTTPException(422,'Choose in-app and/or email delivery')
    if not data.digest and not data.watch_low_stock:raise HTTPException(422,'Enable a digest or low-stock monitoring')
    from app.core.config import settings
    if data.enabled and not settings.EMAIL_WORKER_ENABLED:raise HTTPException(409,'The reporting background worker must be enabled before schedules can run')
    if 'email' in data.channels and data.enabled:
        from app.services.email_dispatch import user_can_receive
        if not user_can_receive(db,user.id,user.email,tenant(user)):raise HTTPException(422,'Your active company email must be available')
    if data.warehouse_id and not db.query(SRMWarehouse.id).filter_by(id=data.warehouse_id,organization_id=tenant(user),active=True).first():raise HTTPException(404,'Warehouse outside your current scope')
    lock_tenant(db,user);branch_id=branch(db)
    row=db.query(Schedule).filter_by(organization_id=tenant(user),owner_id=user.id,branch_id=branch_id).with_for_update().first()
    if not row:
        row=Schedule(organization_id=tenant(user),branch_id=branch_id,owner_id=user.id,state_json={});db.add(row)
    old=row.config_json
    row.enabled=data.enabled;row.config_json=data.model_dump(exclude={'enabled'})
    from app.services.domain_report_delivery import next_occurrence
    now=datetime.now(timezone.utc);next_digest=next_occurrence(row.config_json,now)
    row.state_json={**(row.state_json or {}),'next_digest_at':next_digest.isoformat()}
    row.next_run_at=now if data.enabled and data.watch_low_stock else next_digest if data.enabled else None
    row.last_error=None;db.flush();audit(db,user,'report_schedule',row.id,'CONFIGURE',old,{'enabled':data.enabled,**row.config_json});db.commit();db.refresh(row)
    return schedule_payload(row,user,db)


@router.get('/schedule/preview')
def preview_schedule(period:str=Query('yesterday',pattern='^(today|yesterday|last7days)$'),timezone_name:str=Query('Asia/Kolkata',max_length=80),include_test:bool=False,warehouse_id:int|None=Query(None,gt=0),db=Depends(get_db),user=Depends(reader)):
    reports.native(db)
    from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
    try:ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError,ValueError):raise HTTPException(422,'Choose a valid IANA timezone') from None
    from .reporting_jobs import schedule_filters
    f=schedule_filters(db,user,{'timezone':timezone_name,'period':period,'include_test':include_test,'warehouse_id':warehouse_id},datetime.now(timezone.utc))
    return reports.overview(db,user,reports.resolved(db,user,f))


class ReorderInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_key:UUID
    product_id:int=Field(gt=0)
    warehouse_id:int=Field(gt=0)
    quantity:Decimal=Field(gt=0,le=1000000000)
    vendor_id:int|None=Field(default=None,gt=0)
    vendor_name:str=Field(min_length=2,max_length=220)
    expected_date:reports.date|None=None


@router.post('/reorder-drafts',status_code=201)
def reorder_draft(data:ReorderInput,db=Depends(get_db),user=Depends(reader)):
    reports.native(db);writable(user);require_module_action(user,'srm','create');branch(db);lock_tenant(db,user)
    product=reports.product_query(db,user,reports.Filters(include_test=True,product_id=data.product_id)).first()
    warehouse=db.query(SRMWarehouse).filter_by(id=data.warehouse_id,organization_id=tenant(user),active=True).first()
    if not product or not warehouse:raise HTTPException(404,'Product or warehouse outside your current scope')
    if product.product_type=='service' or not product.track_inventory:raise HTTPException(422,'Reorder drafts require an inventory-tracked product')
    if data.vendor_id:
        vendor=db.query(reports.CRMCompany).filter_by(id=data.vendor_id).first()
        if not vendor:raise HTTPException(404,'Supplier outside your current scope')
    digest=hashlib.sha256(data.model_dump_json().encode()).hexdigest()
    prior=db.query(SRMPurchaseOrder).filter(SRMPurchaseOrder.organization_id==tenant(user),SRMPurchaseOrder.metadata_json['report_request_key'].as_string()==str(data.request_key)).first()
    if prior:
        if prior.metadata_json.get('report_fingerprint')!=digest:raise HTTPException(409,'Reorder request was already used for different details')
        return {'id':prior.id,'number':prior.po_number,'status':prior.status,'replayed':True}
    from app.apps.srm.api.router import _next_number
    row=SRMPurchaseOrder(organization_id=tenant(user),po_number=_next_number(db,SRMPurchaseOrder,'PO','po_number',tenant(user),actor=user),
        vendor_id=data.vendor_id,vendor_name=data.vendor_name.strip(),status='draft',order_date=reports.business_day(db,user),expected_date=data.expected_date,
        notes='Draft from stock report. Review quantities, supplier, currency and open purchase orders before placing.',created_by=user.id,
        metadata_json={'report_request_key':str(data.request_key),'report_fingerprint':digest,'currency':(product.metadata_json or {}).get('currency','INR')})
    db.add(row);db.flush();amount=data.quantity*Decimal(str(product.purchase_rate or 0));row.subtotal=amount;row.tax_amount=0;row.total_amount=amount
    db.add(SRMPurchaseOrderLine(purchase_order_id=row.id,product_id=product.id,warehouse_id=warehouse.id,item_code=product.sku,description=product.item_name,quantity=data.quantity,unit_price=product.purchase_rate or 0,tax_amount=0,line_total=amount))
    audit(db,user,'purchase_order',row.id,'REPORT_DRAFT',after={'product_id':product.id,'quantity':str(data.quantity),'status':'draft'});db.commit();db.refresh(row)
    return {'id':row.id,'number':row.po_number,'status':row.status,'supplier':row.vendor_name,'quantity':str(data.quantity),'currency':row.metadata_json['currency'],'total':reports.money(amount),'replayed':False}


@router.get('/customer-history/{identity}')
def customer_history(identity:int,currency:str=Query('',pattern=r'^(|[A-Z]{3})$'),include_test:bool=False,page:int=Query(1,ge=1,le=10000),page_size:int=Query(25,ge=1,le=200),db=Depends(get_db),user=Depends(reader)):
    reports.native(db)
    if identity<1:raise HTTPException(422,'Choose a customer')
    data=reports.invoice_details(db,user,reports.Filters(customer_id=identity,currency=currency,include_test=include_test),'invoices',page,page_size,dates=False)
    data['history_basis']='All authorized invoice history, independent of the dashboard period. Test-data and currency filters still apply.'
    return data


@router.get('/{report}')
def report_data(report:str,request:Request,page:int=Query(1,ge=1,le=10000),page_size:int=Query(50,ge=1,le=200),db=Depends(get_db),user=Depends(reader)):
    return reports.run(db,user,report,filters_from(request),page,page_size)
