"""Private CRM report definitions using the existing analytics query engine."""
import csv
from io import StringIO
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from app.core.deps import get_db, RequirePermission
from app.models.user import User
from app.services.metrics.queries import company_id
from app.apps.analytics.models import AnalyticsReport
from app.apps.analytics.services.engine import run_report, report_query
from .models import CRMDeal
from .productivity import READ
from . import lead_management as lm

router=APIRouter(prefix="/report-builder",tags=["CRM reporting"])
from app.services.domain_report_delivery import router_for as delivery_router
router.include_router(delivery_router("crm"), prefix="/report-delivery")
Column=Literal["id","name","amount","currency","status","probability","owner_user_id","pipeline_id","stage_id","expected_close_date"]


class Definition(BaseModel):
    model_config=ConfigDict(extra="forbid")
    name:str=Field(min_length=1,max_length=120)
    columns:list[Column]=Field(default_factory=lambda:["name","amount","currency","status"],min_length=1,max_length=10)
    group_by:Literal["","status","owner_user_id","stage_id"]=""
    status:Literal["","Open","Won","Lost"]=""
    currency:str=Field(default="",pattern=r"^(?:[A-Z]{3})?$")
    owner_user_id:int|None=Field(default=None,gt=0)
    expected_revision:int|None=Field(default=None,ge=1)


def _authorize(user): lm.core()._assert_entity_permission("deals",user,"view")


def _definition(row,user):
    source=row.data_source_json or {}
    if row.owner_id!=user.id or source.get("company_id")!=company_id(user) or source.get("domain_builder")!="crm":
        raise HTTPException(404,"CRM report not found")
    try: return Definition.model_validate(source["definition"])
    except (KeyError,ValueError): raise HTTPException(404,"CRM report definition unavailable") from None


def _row(db,identity,user,lock=False):
    _authorize(user)
    query=db.query(AnalyticsReport).filter_by(id=identity,owner_id=user.id)
    if lock: query=query.with_for_update()
    row=query.populate_existing().first()
    if not row: raise HTTPException(404,"CRM report not found")
    _definition(row,user)
    return row


def _payload(row,user):return {"id":row.id,"revision":row.data_source_json["revision"],**_definition(row,user).model_dump(exclude={"expected_revision"})}


def _virtual(data):
    filters={k:v for k,v in {"status":data.status,"currency":data.currency,"owner_user_id":data.owner_user_id}.items() if v not in (None,"")}
    # Currency is always a grouping dimension for monetary aggregates.
    grouping={"group_by":[data.group_by,"currency"],"aggregates":{"deal_count":{"function":"count"},"total_amount":{"function":"sum","field":"amount"}}} if data.group_by else None
    return AnalyticsReport(name=data.name,module_name="crm_deals",report_type="summary" if grouping else "table",fields_json=list(dict.fromkeys(data.columns)),filters_json=filters,grouping_json=grouping)


def _execute(db,row,user,page,page_size):
    definition=_definition(row,user);virtual=_virtual(definition)
    if definition.group_by and report_query(db,"crm_deals",virtual.filters_json or {},user).filter(or_(CRMDeal.currency.is_(None),func.length(func.trim(CRMDeal.currency))!=3)).first():
        raise HTTPException(422,"Fix missing deal currencies or filter to a currency before totaling amounts")
    return run_report(db,virtual,False,page,page_size,user=user,max_page_size=5000)


@router.get("")
def list_reports(db:Session=Depends(get_db),user:User=Depends(RequirePermission(*READ))):
    _authorize(user)
    rows=db.query(AnalyticsReport).filter(AnalyticsReport.owner_id==user.id,AnalyticsReport.module_name=="crm_deals").order_by(AnalyticsReport.id.desc()).all()
    return [_payload(row,user) for row in rows if (row.data_source_json or {}).get("domain_builder")=="crm" and row.data_source_json.get("company_id")==company_id(user)]


def _save(db,user,data,row=None):
    _authorize(user)
    if not data.name.strip():raise HTTPException(422,"Enter a report name")
    if not row:
        count=db.query(AnalyticsReport).filter_by(owner_id=user.id,module_name="crm_deals").count()
        if count>=100:raise HTTPException(422,"You already have 100 saved deal reports")
    revision=(row.data_source_json or {}).get("revision",0) if row else 0
    if row and data.expected_revision!=revision:raise HTTPException(409,"Report changed. Reload before saving")
    definition=data.model_dump(exclude={"expected_revision"});definition["name"]=data.name.strip()
    report=row or AnalyticsReport(owner_id=user.id)
    virtual=_virtual(data)
    for key in ("name","module_name","report_type","fields_json","filters_json","grouping_json"):setattr(report,key,getattr(virtual,key))
    report.visibility="private"
    report.data_source_json={"domain_builder":"crm","company_id":company_id(user),"revision":revision+1,"definition":definition}
    db.add(report);db.commit();db.refresh(report)
    return _payload(report,user)


@router.post("",status_code=201)
def create_report(data:Definition,db:Session=Depends(get_db),user:User=Depends(RequirePermission(*READ))):return _save(db,user,data)


@router.put("/{identity}")
def update_report(identity:int,data:Definition,db:Session=Depends(get_db),user:User=Depends(RequirePermission(*READ))):return _save(db,user,data,_row(db,identity,user,True))


@router.delete("/{identity}",status_code=204)
def delete_report(identity:int,db:Session=Depends(get_db),user:User=Depends(RequirePermission(*READ))):
    row=_row(db,identity,user,True)
    db.delete(row);db.commit()
    return Response(status_code=204)


@router.get("/{identity}/run")
def execute(identity:int,page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=200),db:Session=Depends(get_db),user:User=Depends(RequirePermission(*READ))):
    row=_row(db,identity,user)
    from .deal_grid import capabilities
    return {**_execute(db,row,user,page,page_size),"report":_payload(row,user),"can_export":capabilities(user)["export"],"basis":"Current authorized deal records; monetary groups remain separated by currency"}


@router.get("/{identity}/export")
def export(identity:int,file_format:Literal["csv","xlsx"]=Query("csv",alias="format"),expected_revision:int|None=Query(None,ge=1),db:Session=Depends(get_db),user:User=Depends(RequirePermission(*READ))):
    row=_row(db,identity,user)
    if expected_revision is not None and row.data_source_json["revision"]!=expected_revision:raise HTTPException(409,"Report changed. Run it again before exporting")
    from .deal_grid import capabilities
    if not capabilities(user).get("export"):raise HTTPException(403,"Deal export is not allowed")
    result=_execute(db,row,user,1,5000)
    if result["total"]>5000:raise HTTPException(422,"Narrow this report to 5,000 rows/groups before synchronous export")
    headers=result["fields"]; values=[[r.get(key) for key in headers] for r in result["items"]]
    if file_format=="xlsx":
        from app.apps.project_management.report_files import xlsx_bytes
        content=xlsx_bytes(headers,values,sheet_name="Deal report");media="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        output=StringIO();writer=csv.writer(output);writer.writerow(headers)
        for r in values:writer.writerow(["'"+v if isinstance(v,str) and v.lstrip().startswith(("=","+","-","@","\t","\r")) else v for v in r])
        content=output.getvalue().encode("utf-8-sig");media="text/csv; charset=utf-8"
    return Response(content,media_type=media,headers={"Content-Disposition":f'attachment; filename="crm-deal-report.{file_format}"',"Cache-Control":"private, no-store"})
