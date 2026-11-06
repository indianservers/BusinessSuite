"""All mirrors use the existing finance company/branch authorization boundary."""
from typing import Literal
from uuid import uuid4
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from app.core.deps import get_db, get_current_user
from app.shared.import_api import finance_context
from app.shared.import_connectors import get_connection, seal, unseal
from app.shared.accounting_sync.models import SyncConnection, SyncRun, SyncRecord
from app.shared.accounting_sync import service

router=APIRouter(prefix="/accounting-sync",tags=["accounting-sync"])

def context(request,db,user): return finance_context(db,user,request)
def connection_for(db,identity,ctx,user):
    row=db.query(SyncConnection).filter_by(id=identity,organization_id=ctx.company_id,branch_id=ctx.branch_id,created_by=user.id).first()
    if row is None: raise HTTPException(404,"Accounting sync connection not found")
    return row

def public(row):
    return {key:getattr(row,key) for key in ("id","provider","account_id","source_connection_id","sandbox","enabled","last_success_at")}
def run_public(row):
    return {key:getattr(row,key) for key in ("id","status","started_at","completed_at","counts","error")}

class Connect(BaseModel):
    provider: Literal["zoho","quickbooks","tally"]
    source_connection_id: str | None = Field(default=None,max_length=36)
    account_id: str | None = Field(default=None,min_length=1,max_length=120)
    sandbox: bool = True

@router.get("/connections")
def connections(request:Request,db=Depends(get_db),user=Depends(get_current_user)):
    ctx=context(request,db,user)
    rows=db.query(SyncConnection).filter_by(organization_id=ctx.company_id,branch_id=ctx.branch_id,created_by=user.id).all()
    return {"items":[public(row) for row in rows],"mode":"read_only","strategy":"full_snapshot_changed_record_upsert"}

@router.post("/connections",status_code=201)
def connect(data:Connect,request:Request,db=Depends(get_db),user=Depends(get_current_user)):
    ctx=context(request,db,user); token=None
    if data.provider=="tally":
        if not data.account_id: raise HTTPException(422,"Tally company GUID is required")
        account=data.account_id; source=None; token=secrets.token_urlsafe(32)
    else:
        source=get_connection(db,data.source_connection_id,user,ctx)
        if source.provider!=data.provider or source.account_id=="pending": raise HTTPException(409,"Complete the matching provider OAuth connection first")
        account=source.account_id
    row=SyncConnection(id=str(uuid4()),organization_id=ctx.company_id,branch_id=ctx.branch_id,created_by=user.id,provider=data.provider,account_id=account,source_connection_id=source.id if source else None,sandbox=data.sandbox,enabled=True,bridge_secret=seal({"token":token}) if token else None)
    db.add(row)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409,"This provider account already has a sync connection in this branch")
    result=public(row)
    if token: result["bridge_token"]=token
    return result

class Reconnect(BaseModel):
    source_connection_id:str=Field(min_length=1,max_length=36)
    sandbox:bool | None=None
@router.post("/connections/{identity}/reconnect")
def reconnect(identity:str,data:Reconnect,request:Request,db=Depends(get_db),user=Depends(get_current_user)):
    ctx=context(request,db,user); row=connection_for(db,identity,ctx,user)
    source=get_connection(db,data.source_connection_id,user,ctx)
    if source.provider!=row.provider or source.account_id!=row.account_id: raise HTTPException(409,"Reconnect the same provider account")
    if row.active_token: raise HTTPException(409,"Wait for the current sync to finish before reconnecting")
    if row.provider=="quickbooks" and data.sandbox is not None and data.sandbox!=row.sandbox:
        if row.last_success_at: raise HTTPException(409,"Cannot change environment after a successful sync")
        row.sandbox=data.sandbox
    row.source_connection_id=source.id; db.commit(); return public(row)

class Enabled(BaseModel): enabled:bool
@router.patch("/connections/{identity}")
def set_enabled(identity:str,data:Enabled,request:Request,db=Depends(get_db),user=Depends(get_current_user)):
    row=connection_for(db,identity,context(request,db,user),user); row.enabled=data.enabled; db.commit(); return public(row)

@router.post("/connections/{identity}/rotate-bridge-token")
def rotate(identity:str,request:Request,db=Depends(get_db),user=Depends(get_current_user)):
    row=connection_for(db,identity,context(request,db,user),user)
    if row.provider!="tally": raise HTTPException(422,"Only Tally uses a bridge token")
    token=secrets.token_urlsafe(32); row.bridge_secret=seal({"token":token}); db.commit(); return {"bridge_token":token}

@router.post("/connections/{identity}/sync")
def sync(identity:str,request:Request,db=Depends(get_db),user=Depends(get_current_user)):
    row=connection_for(db,identity,context(request,db,user),user)
    if row.provider=="tally": raise HTTPException(409,"Run the local Tally agent to send a complete snapshot")
    return run_public(service.execute(db,row))

class Customer(BaseModel):
    external_id:str=Field(min_length=1,max_length=160)
    name:str=Field(min_length=1,max_length=300)
    currency:str=Field(min_length=1,max_length=20)
    email:str | None=None
    active:bool=True
class Invoice(BaseModel):
    external_id:str=Field(min_length=1,max_length=160)
    customer_external_id:str=Field(min_length=1,max_length=160)
    currency:str=Field(min_length=1,max_length=20)
    amount:str=Field(max_length=80)
    outstanding:str=Field(max_length=80)
    number:str | None=None
    date:str | None=None
    due_date:str | None=None
    status:Literal["open","paid","cancelled","draft","void","provider_reported"]="provider_reported"
class Payment(BaseModel):
    external_id:str=Field(min_length=1,max_length=160)
    customer_external_id:str=Field(min_length=1,max_length=160)
    currency:str=Field(min_length=1,max_length=20)
    amount:str=Field(max_length=80)
    date:str | None=None
    reference:str | None=None
class Snapshot(BaseModel):
    account_id:str=Field(min_length=1,max_length=120)
    customers:list[Customer]=Field(max_length=50000)
    invoices:list[Invoice]=Field(max_length=50000)
    payments:list[Payment]=Field(max_length=50000)

@router.post("/connections/{identity}/snapshot")
def snapshot(identity:str,data:Snapshot,request:Request,db=Depends(get_db),user=Depends(get_current_user)):
    row=connection_for(db,identity,context(request,db,user),user)
    if row.provider!="tally" or not row.bridge_secret: raise HTTPException(422,"This connection does not accept bridge snapshots")
    # Bridge token is additional to the user's scoped session, never standalone tenant authority.
    expected=unseal(type("Secret",(),{"secret":row.bridge_secret})()).get("token", "")
    if not secrets.compare_digest(request.headers.get("X-Accounting-Bridge-Token", ""),expected): raise HTTPException(403,"Invalid bridge token")
    if data.account_id!=row.account_id: raise HTTPException(409,"Tally company does not match this connection")
    return run_public(service.execute(db,row,data.model_dump(exclude={"account_id"})))

@router.get("/connections/{identity}/runs")
def runs(identity:str,request:Request,db=Depends(get_db),user=Depends(get_current_user),limit:int=Query(20,ge=1,le=100)):
    row=connection_for(db,identity,context(request,db,user),user)
    return {"items":[run_public(run) for run in db.query(SyncRun).filter_by(connection_id=row.id).order_by(SyncRun.started_at.desc()).limit(limit)]}

@router.get("/connections/{identity}/records")
def records(identity:str,request:Request,entity:Literal["customers","invoices","payments"],page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=200),db=Depends(get_db),user=Depends(get_current_user)):
    row=connection_for(db,identity,context(request,db,user),user)
    query=db.query(SyncRecord).filter_by(connection_id=row.id,entity=entity,present=True)
    return {"items":[r.data for r in query.order_by(SyncRecord.external_id).offset((page-1)*page_size).limit(page_size)],"total":query.count(),"page":page,"page_size":page_size,"as_of":row.last_success_at}

@router.get("/connections/{identity}/balances")
def balances(identity:str,request:Request,db=Depends(get_db),user=Depends(get_current_user)):
    row=connection_for(db,identity,context(request,db,user),user)
    return {"items":service.balances(db,row.id),"as_of":row.last_success_at,"basis":"Invoice outstanding only; excludes unapplied customer credits/advances; no currency conversion"}
