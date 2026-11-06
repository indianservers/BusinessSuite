"""Source-labelled accounting views with explicit CRM identities and financial RBAC."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, exists, or_, and_
from app.core.deps import get_db, get_current_user, RequirePermission
from app.shared.accounting_sync.models import SyncConnection, SyncRecord, SyncCustomerLink
from app.services.metrics.queries import business_context

router=APIRouter()
Source=Literal["crm","srm"]
FINANCIAL=("srm_invoice_view","srm_admin","fam_ar_view","fam_ar_manage","fam_admin","analytics_financial_view")
EXCLUDED={"draft","void","cancelled","canceled"}

def authorize(db,user,source):
    from app.shared.master_data import authorize as master_authorize
    from app.shared.record_360 import module_access
    RequirePermission(*FINANCIAL)(user)
    module_access(db,user,source)
    master_authorize(user,source)

def connection_query(db,user):
    from app.branches.service import context
    ctx=db.info.get("branch_context") or context(db,user,user.organization_id)
    query=db.query(SyncConnection).filter(SyncConnection.organization_id==user.organization_id)
    return query.filter(SyncConnection.branch_id==ctx.branch_id) if ctx.branch_id else query.filter(SyncConnection.branch_id.in_(ctx.allowed))

def visible_links(db,user,source):
    from app.shared.master_data import companies
    from app.apps.crm.models import CRMCompany
    return db.query(SyncCustomerLink).filter(SyncCustomerLink.organization_id==user.organization_id,
        SyncCustomerLink.crm_company_id.in_(companies(db,user,source).with_entities(CRMCompany.id)))

def record_query(db,user,source,entity,connection_id=None,crm_company_id=None):
    connections=connection_query(db,user)
    if connection_id: connections=connections.filter(SyncConnection.id==connection_id)
    key=SyncRecord.external_id if entity=="customers" else SyncRecord.data["customer_external_id"].as_string()
    links=visible_links(db,user,source)
    if crm_company_id is not None: links=links.filter(SyncCustomerLink.crm_company_id==crm_company_id)
    linked=exists(select(SyncCustomerLink.id).where(SyncCustomerLink.id.in_(links.with_entities(SyncCustomerLink.id)),
        SyncCustomerLink.connection_id==SyncRecord.connection_id,SyncCustomerLink.external_id==key))
    query=db.query(SyncRecord).filter(SyncRecord.present.is_(True),SyncRecord.entity==entity,
        SyncRecord.connection_id.in_(connections.with_entities(SyncConnection.id)))
    # Account owners can inspect unlinked rows. Other financial readers need a visible CRM link.
    guard=linked if crm_company_id is not None else or_(linked,SyncRecord.connection_id.in_(connections.filter(SyncConnection.created_by==user.id).with_entities(SyncConnection.id)))
    return query.filter(guard)

def connection_info(connection):
    stamp=connection.last_success_at
    instant=stamp.replace(tzinfo=stamp.tzinfo or timezone.utc) if stamp else None
    stale=instant is None or datetime.now(timezone.utc)-instant>timedelta(minutes=max(30,2*(connection.interval_minutes or 15)))
    return {"connection_id":connection.id,"provider":connection.provider,"account_id":connection.account_id,
        "as_of":stamp,"stale":stale,"paused":not connection.enabled,"error":connection.schedule_error}

def decorate(db,user,source,records):
    ids={r.connection_id for r in records}
    connections={c.id:c for c in connection_query(db,user).filter(SyncConnection.id.in_(ids))} if ids else {}
    links={(link.connection_id,link.external_id):link.crm_company_id for link in visible_links(db,user,source).filter(SyncCustomerLink.connection_id.in_(ids))} if ids else {}
    customers={(r.connection_id,r.external_id):r.data.get("name") for r in db.query(SyncRecord).filter(SyncRecord.connection_id.in_(ids),SyncRecord.entity=="customers",SyncRecord.present.is_(True))} if ids else {}
    return [{**r.data,**connection_info(connections[r.connection_id]),"record_id":r.id,
        "customer_name":customers.get((r.connection_id,r.data.get("customer_external_id"))),
        "crm_company_id":links.get((r.connection_id,r.data.get("customer_external_id")))} for r in records]

class CustomerMapping(BaseModel):
    external_id:str=Field(min_length=1,max_length=160)
    crm_company_id:int=Field(gt=0)
    source:Source="crm"

@router.put("/connections/{identity}/customer-links")
def map_customer(identity:str,data:CustomerMapping,request:Request,db=Depends(get_db),user=Depends(get_current_user)):
    from app.shared.accounting_sync.api import connection_for, context
    from app.shared.master_data import owner
    ctx=context(request,db,user); connection=connection_for(db,identity,ctx,user)
    owner(db,user,"company",data.crm_company_id,data.source)
    external=db.query(SyncRecord).filter_by(connection_id=identity,entity="customers",external_id=data.external_id,present=True).first()
    if external is None: raise HTTPException(404,"Synced customer not found")
    link=db.query(SyncCustomerLink).filter_by(connection_id=identity,external_id=data.external_id).first()
    if link is None:
        link=SyncCustomerLink(id=str(uuid4()),organization_id=ctx.company_id,branch_id=ctx.branch_id,connection_id=identity,external_id=data.external_id,crm_company_id=data.crm_company_id,created_by=user.id)
        db.add(link)
    else: link.crm_company_id=data.crm_company_id
    db.commit()
    return {"id":link.id,"external_id":link.external_id,"crm_company_id":link.crm_company_id}

@router.delete("/connections/{identity}/customer-links/{link_id}",status_code=204)
def unmap_customer(identity:str,link_id:str,request:Request,db=Depends(get_db),user=Depends(get_current_user)):
    from app.shared.accounting_sync.api import connection_for, context
    connection_for(db,identity,context(request,db,user),user)
    link=db.query(SyncCustomerLink).filter_by(id=link_id,connection_id=identity).first()
    if link is None: raise HTTPException(404,"Customer link not found")
    db.delete(link);db.commit();return Response(status_code=204)

@router.get("/customer-360/{kind}/{ident}")
def customer_360(kind:Literal["company","contact","lead","deal"],ident:int,response:Response,source:Source="crm",db=Depends(get_db),user=Depends(get_current_user)):
    from app.shared.record_360 import context
    authorize(db,user,source);response.headers["Cache-Control"]="no-store"
    row,project,customer=context(db,user,kind,ident,source)
    if customer is None: return {"customer_id":None,"links":[],"invoices":[],"payments":[],"balances":[]}
    links=list(visible_links(db,user,source).filter(SyncCustomerLink.crm_company_id==customer.id))
    invoices=decorate(db,user,source,list(record_query(db,user,source,"invoices",crm_company_id=customer.id).order_by(SyncRecord.external_id)))
    payments=decorate(db,user,source,list(record_query(db,user,source,"payments",crm_company_id=customer.id).order_by(SyncRecord.external_id)))
    totals={}
    for item in invoices:
        if item.get("status") in EXCLUDED:continue
        key=(item["connection_id"],item["provider"],item["currency"])
        totals[key]=totals.get(key,Decimal(0))+Decimal(item["outstanding"])
    return {"customer_id":customer.id,"links":[{"id":link.id,"connection_id":link.connection_id,"external_id":link.external_id} for link in links],
        "invoices":invoices[:20],"invoice_count":len(invoices),"payments":payments[:20],"payment_count":len(payments),
        "balances":[{"connection_id":key[0],"provider":key[1],"currency":key[2],"outstanding":str(amount)} for key,amount in sorted(totals.items())],
        "basis":"External records only; unapplied credits/advances excluded; no conversion or native totals combined"}

@router.get("/invoices")
def invoices(response:Response,source:Source="srm",connection_id:str|None=None,crm_company_id:int|None=None,
             status:str|None=None,q:str=Query("",max_length=120),page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),
             db=Depends(get_db),user=Depends(get_current_user)):
    authorize(db,user,source);response.headers["Cache-Control"]="no-store"
    query=record_query(db,user,source,"invoices",connection_id,crm_company_id)
    if status:query=query.filter(SyncRecord.data["status"].as_string()==status)
    if q:query=query.filter(SyncRecord.data["number"].as_string().ilike("%"+q.replace("!","!!").replace("%","!%").replace("_","!_")+"%",escape="!"))
    total=query.count();records=list(query.order_by(SyncRecord.connection_id,SyncRecord.external_id).offset((page-1)*page_size).limit(page_size))
    return {"items":decorate(db,user,source,records),"total":total,"page":page,"page_size":page_size,"read_only":True}

def document_day(value,zone):
    if not value:return None
    try:
        if len(value)==10:return date.fromisoformat(value)
        instant=datetime.fromisoformat(value.replace("Z","+00:00"))
        return instant.astimezone(zone).date() if instant.tzinfo else instant.replace(tzinfo=zone).date()
    except (ValueError,TypeError):return None

@router.get("/report-sources")
def report_sources(response:Response,source:Source="srm",db=Depends(get_db),user=Depends(get_current_user)):
    authorize(db,user,source);response.headers["Cache-Control"]="no-store"
    linked=visible_links(db,user,source).with_entities(SyncCustomerLink.connection_id)
    query=connection_query(db,user).filter(or_(SyncConnection.created_by==user.id,SyncConnection.id.in_(linked)))
    return {"items":[connection_info(c) for c in query.order_by(SyncConnection.provider,SyncConnection.account_id)]}

@router.get("/daily-sales")
def daily_sales(response:Response,source:Source="srm",start_date:date|None=None,end_date:date|None=None,
                connection_id:str|None=None,db=Depends(get_db),user=Depends(get_current_user)):
    authorize(db,user,source);response.headers["Cache-Control"]="no-store"
    ctx=business_context(db,user);zone=ZoneInfo(ctx["timezone"])
    end=end_date or date.fromisoformat(ctx["business_date"]);start=start_date or end-timedelta(days=6)
    if start>end or (end-start).days>365:raise HTTPException(422,"Choose a date range of at most 366 days")
    daily={};outstanding={};undated=0
    allowed=visible_links(db,user,source).with_entities(SyncCustomerLink.connection_id)
    source_query=connection_query(db,user).filter(or_(SyncConnection.created_by==user.id,SyncConnection.id.in_(allowed)))
    if connection_id:source_query=source_query.filter(SyncConnection.id==connection_id)
    sources={c.id:connection_info(c) for c in source_query}
    for entity in ("invoices","payments"):
        records=list(record_query(db,user,source,entity,connection_id))
        for item in decorate(db,user,source,records):
            sources[item["connection_id"]]={k:item[k] for k in ("connection_id","provider","account_id","as_of","stale","paused","error")}
            if entity=="invoices" and item.get("status") in EXCLUDED:continue
            if entity=="invoices":
                key=(item["connection_id"],item["provider"],item["currency"])
                outstanding[key]=outstanding.get(key,Decimal(0))+Decimal(item["outstanding"])
            day=document_day(item.get("date"),zone)
            if day is None:undated+=1;continue
            if not start<=day<=end:continue
            key=(day.isoformat(),item["connection_id"],item["provider"],item["currency"])
            totals=daily.setdefault(key,{"invoiced":Decimal(0),"receipts":Decimal(0),"invoice_count":0,"payment_count":0})
            metric="invoiced" if entity=="invoices" else "receipts"
            totals[metric]+=Decimal(item["amount"]);totals["invoice_count" if entity=="invoices" else "payment_count"]+=1
    return {"start_date":start,"end_date":end,"timezone":ctx["timezone"],"sources":list(sources.values()),"undated_records":undated,
        "items":[{"date":key[0],"connection_id":key[1],"provider":key[2],"currency":key[3],**{k:str(v) if isinstance(v,Decimal) else v for k,v in totals.items()}} for key,totals in sorted(daily.items())],
        "current_outstanding":[{"connection_id":key[0],"provider":key[1],"currency":key[2],"outstanding":str(amount)} for key,amount in sorted(outstanding.items())],
        "basis":"Source document dates in company timezone; current invoice balances, not historical receivables. Separate from native sales; accounts/currencies are never merged."}
