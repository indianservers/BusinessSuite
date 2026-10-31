"""Read-only statistics diagnostics; only the audit snapshot is persisted."""
import json
from pathlib import Path
from datetime import datetime,timezone
from dataclasses import asdict
from fastapi import APIRouter,Depends,HTTPException,Query,Response
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy.orm import Session
from app.core.deps import get_current_user,get_db
from app.models.user import User
from app.models.audit import AuditLog
from .queries import business_context,company_id
from .registry import REGISTRY,catalog,evaluate,access_admin

router=APIRouter(prefix="/metrics",tags=["Canonical statistics"])


def administrator(db=Depends(get_db),user=Depends(get_current_user)):
    if not access_admin(db,user):raise HTTPException(403,"Organization access administrator required for statistics diagnostics")
    return user


def headers(response):
    response.headers["Cache-Control"]="no-store"
    response.headers["Vary"]="Authorization, X-Suite-Organization"


@router.get("/definitions")
def definitions(response:Response,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    headers(response)
    return {"items":catalog(db,user),"context":business_context(db,user)}


@router.get("/values")
def values(response:Response,ids:str=Query(...,max_length=2000),workspace:int|None=None,project:int|None=None,team:int|None=None,department:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    headers(response)
    selected=list(dict.fromkeys(ids.split(",")))
    if len(selected)>40:raise HTTPException(422,"Request at most 40 metric identifiers")
    filters={key:value for key,value in {"workspace":workspace,"project":project,"team":team,"department":department}.items() if value is not None}
    # Each metric validates supported filters; never quietly discard an unsupported scope.
    return {"context":business_context(db,user),"filters":filters,"items":[{"id":code,"value":evaluate(db,user,code,filters),"definition":asdict(REGISTRY[code])} for code in selected]}


@router.get("/inventory")
def inventory(response:Response,db:Session=Depends(get_db),user:User=Depends(administrator)):
    headers(response)
    return json.loads(Path(__file__).with_name("inventory.json").read_text(encoding="utf-8"))


class AuditInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    metrics:list[str]=Field(default_factory=list,max_length=40)
    project:int|None=None
    workspace:int|None=None


def source_values(db,user,code,filters):
    """Read actual API source functions; never substitute canonical for an observation."""
    if code.startswith("users."):
        from app.access.api import account_statistics
        result=account_statistics(companyId=company_id(user),db=db,actor=user)
        key={"users.total_registered":"registered","users.total_active":"loginEnabled","users.total_accounts":"provisioned"}[code]
        observations=[("Master Suite / access/statistics",result[key],True)]
        if code!="users.total_accounts":
            from app.apps.project_management.people_workspace import stats,scope
            from app.services.metrics.queries import registered_users
            from app.models.user import User
            canonical=registered_users(db,user).with_entities(User.id)
            permitted=scope(db,user).with_entities(User.id)
            same=not registered_users(db,user).filter(User.id.notin_(permitted)).first() and not scope(db,user).filter(User.id.notin_(canonical)).first()
            observations.append(("PMS / people-workspace/reference",stats(db,user)["total" if code=="users.total_registered" else "active"],same))
        return observations

    if code.startswith("employees."):
        from app.api.v1.employees import employee_count,employee_stats
        from app.api.v1.reports import dashboard_stats
        key={"employees.total":"total","employees.total_active":"active","employees.on_leave":"on_leave"}[code]
        return [("HRMS / employees/count",employee_count(db,user)[key]),("HRMS / employees/stats",employee_stats(db,user)[key]),("HRMS / reports/dashboard",dashboard_stats(db,user)["headcount"][key])]
    if code.startswith("pms.tasks.") and filters.get("project"):
        from app.apps.project_management.api.router import get_project_dashboard
        key={"pms.tasks.total":"total_tasks","pms.tasks.completed":"completed_tasks","pms.tasks.overdue":"overdue_tasks"}.get(code)
        if key:return [("PMS / dashboard/project",get_project_dashboard(filters["project"],db,user)["metrics"][key])]
    if code=="notifications.unread":
        from app.api.v1.notifications import unread_count,notification_summary
        return [("Notifications / unread-count",unread_count(db,user)["unread"]),("Notifications / summary",sum(row["count"] for row in notification_summary(db,user)["groups"]))]
    if code.startswith("interns.") or code.startswith("internhub.batches."):
        from app.apps.interns_hub.management_api import dashboard,filters as intern_filters
        body=dashboard(f=intern_filters(),user=user,db=db)
        key={"interns.total":"total_interns","interns.total_active":"active_interns","internhub.batches.active":"active_batches","internhub.batches.upcoming":"upcoming_batches","internhub.batches.completed":"completed_batches"}[code]
        return [("InternHub / management/dashboard",body[key])]
    if code=="teams.total" and not filters:
        from app.apps.project_management.people_workspace import stats
        return [("PMS / people-workspace/reference",stats(db,user)["teams"])]
    if code=="srm.orders.total":
        from app.apps.srm.api.router import srm_dashboard
        return [("Sales / dashboard",srm_dashboard(db,user)["total_sales_orders"])]
    if code.startswith("crm."):
        from app.apps.crm.api.router import crm_dashboard
        key={"crm.contacts.total":"contacts","crm.leads.total":"leads","crm.deals.open":"openDeals","crm.pipeline.value":"pipelineByCurrency"}.get(code)
        if key:return [("CRM / dashboard",crm_dashboard(db,user)["summary"][key])]
    return []


@router.post("/audits",status_code=201)
def run_audit(data:AuditInput,response:Response,db:Session=Depends(get_db),user:User=Depends(administrator)):
    headers(response)
    from .registry import allowed
    codes=data.metrics or [m["id"] for m in catalog(db,user)]
    results=[]
    for code in dict.fromkeys(codes):
        definition=REGISTRY.get(code)
        if not definition:raise HTTPException(422,"Unknown audit metric: "+code)
        if not allowed(db,user,definition):
            results.append({"id":code,"result":"not_permitted","canonical":None,"observed":None,"source":None,"classification":"permission-context mismatch"});continue
        filters={k:v for k,v in {"workspace":data.workspace,"project":data.project}.items() if v is not None and k in definition.supported_filters}
        try:
            canonical=evaluate(db,user,code,filters)
            sources=source_values(db,user,code,filters)
            after=evaluate(db,user,code,filters) if sources else canonical
            if not sources:results.append({"id":code,"canonical":canonical,"observed":None,"result":"definition_only","source":definition.source,"classification":"Independent API adapter not yet verified","filters":filters});continue
            for observation in sources:
                source,value=observation[:2]
                same_scope=observation[2] if len(observation)>2 else True
                comparable=after==canonical and same_scope
                results.append({"id":code,"canonical":canonical,"observed":value,"source":source,"filters":filters,
                    "result":("match" if value==canonical else "mismatch") if comparable else "not_comparable",
                    "classification":None if comparable and value==canonical else "calculation mismatch" if comparable else "scope mismatch" if not same_scope else "Concurrent data changed during audit"})
        except __import__("sqlalchemy").exc.SQLAlchemyError:
            db.rollback()
            __import__("logging").getLogger(__name__).exception("Statistics audit query unavailable metric=%s",code)
            results.append({"id":code,"result":"unavailable","canonical":None,"observed":None,"source":definition.source,"classification":"Database query unavailable","error":"Query could not be verified; inspect authorized server diagnostics","filters":filters})
        except HTTPException as error:
            results.append({"id":code,"result":"unavailable","canonical":None,"observed":None,"source":definition.source,"classification":"permission-context mismatch" if error.status_code==403 else "Query unavailable","error":str(error.detail),"filters":filters})
    context=business_context(db,user)
    from .quality import inspect_identities
    quality=inspect_identities(db,user)
    snapshot={"data_quality":quality,"context":context,"filters":data.model_dump(exclude={"metrics"}),"results":results,"observation":"Current API source values; does not claim to inspect a browser's rendered or cached values"}
    row=AuditLog(organization_id=company_id(user),user_id=user.id,actor_email=user.email,actor_authenticated=True,method="POST",module="statistics",entity_type="statistics_audit",action="STATISTICS_AUDIT",new_values=json.dumps(snapshot,default=str),description="Read-only statistics reconciliation; no business data modified",status_code=201)
    db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,**snapshot}


@router.get("/audits")
def audits(response:Response,db:Session=Depends(get_db),user:User=Depends(administrator)):
    headers(response)
    rows=db.query(AuditLog).filter_by(organization_id=company_id(user),module="statistics",action="STATISTICS_AUDIT").order_by(AuditLog.id.desc()).limit(30).all()
    return {"items":[{"id":row.id,"created_at":row.created_at,"actor":row.actor_email,"snapshot":json.loads(row.new_values)} for row in rows]}


@router.get("/audits/{audit_id}")
def export_audit(audit_id:int,response:Response,db:Session=Depends(get_db),user:User=Depends(administrator)):
    row=db.query(AuditLog).filter_by(id=audit_id,organization_id=company_id(user),module="statistics",action="STATISTICS_AUDIT").first()
    if not row:raise HTTPException(404,"Audit not found in this organization")
    return Response(row.new_values,media_type="application/json",headers={"Cache-Control":"no-store","Content-Disposition":f'attachment; filename="statistics-audit-{row.id}.json"'})
