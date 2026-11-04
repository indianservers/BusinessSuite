"""Scoped pipeline preferences and transactional stage-entry events.

Configuration reuses ServicePolicy; record activity stays in branch-owned events.
Native modules remain authoritative for record movement and approval decisions.
"""
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, ConfigDict, Field, EmailStr
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.access.catalog import permission_objects
from app.apps.srm.services.commercial import tenant
from app.shared.models import ServicePolicy, ServiceEvent

router = APIRouter(prefix="/pipeline-workspaces", tags=["Pipeline workspaces"])
Module = Literal["crm", "project_management", "srm", "hrms"]


def access(db, user, module, scope, manage=False):
    from app.shared.record_360 import module_access
    module_access(db, user, module)
    permissions = {p.name for p in permission_objects(user)}
    allowed = {"crm": {"crm_view", "crm_manage", "crm_admin", "crm_deals_view", "crm_deals_manage"}, "project_management": {"pms_view", "pms_manage", "pms_admin"}, "srm": {"srm_view", "srm_manage", "srm_admin", "srm_sales_manage"}, "hrms": {"recruitment_view", "recruitment_manage", "hrms_view", "hrms_admin"}}[module]
    if not user.is_superuser and not permissions.intersection(allowed):
        raise HTTPException(403, "Module permission required")
    if module == "project_management" and scope.startswith("project:"):
        from app.apps.project_management.access import get_project_for_action
        try: project_id = int(scope.split(":")[1])
        except ValueError: raise HTTPException(422, "Invalid project scope")
        get_project_for_action(db, project_id, user, "edit_project" if manage else "browse")
        return
    if manage and not user.is_superuser:
        managers = {"crm": {"crm_admin", "crm_pipeline_manage"}, "project_management": {"pms_admin", "pms_manage"}, "srm": {"srm_admin", "srm_manage"}, "hrms": {"recruitment_manage", "hrms_admin"}}[module]
        if not permissions.intersection(managers):
            raise HTTPException(403, "Manager permission required to publish a team view")


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    module_filters: dict[str, str | bool] = Field(default_factory=dict, max_length=30)
    density: Literal["compact", "comfortable"] = "compact"
    fields: list[Literal["subtitle", "owner", "value", "activity", "age", "content"]] = Field(default_factory=lambda: ["subtitle", "owner", "value", "activity", "age", "content"], max_length=6)
    queue: Literal["all", "mine", "attention", "overdue", "unassigned"] = "all"
    owner: str = Field(default="", max_length=120)
    search: str = Field(default="", max_length=200)
    sort: Literal["manual", "name", "due", "age"] = "manual"


class ViewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    shared: bool = False
    preferences: Preferences


def policy_key(module, scope, org, user_id=None):
    return f"pipeline-ui:{org}:{module}:{scope}:{user_id or 'team'}"


def policy(db, module, scope, org, user_id=None):
    return db.query(ServicePolicy).filter_by(scope_key=policy_key(module, scope, org, user_id), organization_id=org, kind="pipeline_ui").with_for_update().first()


def write_policy(db, module, scope, user, values, personal=True):
    org = tenant(user)
    row = policy(db, module, scope, org, user.id if personal else None)
    if row is None:
        row = ServicePolicy(scope_key=policy_key(module, scope, org, user.id if personal else None), organization_id=org, module_key=module, kind="pipeline_ui", values_json={}, updated_by=user.id)
        db.add(row)
    row.values_json = {**(row.values_json or {}), **values}
    row.updated_by = user.id
    row.version = (row.version or 0) + 1
    db.commit()
    return row


@router.get("/{module}/{scope}/views")
def list_views(module: Module, scope: str = Path(..., min_length=1, max_length=60, pattern=r"^[a-zA-Z0-9:_-]+$"), db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(db, user, module, scope)
    rows = db.query(ServicePolicy).filter(ServicePolicy.organization_id == tenant(user), ServicePolicy.scope_key.in_([policy_key(module, scope, tenant(user), user.id), policy_key(module, scope, tenant(user))]), ServicePolicy.kind == "pipeline_ui").all()
    result = {"preferences": Preferences().model_dump(), "views": []}
    for row in rows:
        if row.scope_key.endswith(f":{user.id}"):
            result["preferences"] = (row.values_json or {}).get("preferences", result["preferences"])
        result["views"].extend((row.values_json or {}).get("views", []))
    try:
        access(db, user, module, scope, manage=True)
        result["can_share"] = True
    except HTTPException:
        result["can_share"] = False
    return result


@router.put("/{module}/{scope}/preferences")
def save_preferences(module: Module, scope: str, data: Preferences, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not 1 <= len(scope) <= 60 or any(not (c.isalnum() or c in ":_-") for c in scope):
        raise HTTPException(422, "Invalid board scope")
    access(db, user, module, scope)
    write_policy(db, module, scope, user, {"preferences": data.model_dump()})
    return data.model_dump()


@router.post("/{module}/{scope}/views", status_code=201)
def create_view(module: Module, scope: str, data: ViewInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not 1 <= len(scope) <= 60 or any(not (c.isalnum() or c in ":_-") for c in scope):
        raise HTTPException(422, "Invalid board scope")
    access(db, user, module, scope, manage=data.shared)
    if not data.name.strip(): raise HTTPException(422, "Name the view")
    row = policy(db, module, scope, tenant(user), None if data.shared else user.id)
    views = list((row.values_json or {}).get("views", [])) if row else []
    if len(views) >= 30: raise HTTPException(422, "At most 30 views are allowed per workspace")
    if any(v["name"].casefold() == data.name.strip().casefold() for v in views): raise HTTPException(409, "A view with this name already exists")
    view = {"id": uuid.uuid4().hex, "name": data.name.strip(), "shared": data.shared, "preferences": data.preferences.model_dump()}
    write_policy(db, module, scope, user, {"views": [*views, view]}, personal=not data.shared)
    return view


def stage_entry(db, user, module, kind, record_id, previous, destination, owner_id=None, scope=None):
    """Called only after native validators, before the native transaction commits."""
    if str(previous) == str(destination): return
    org = tenant(user)
    previous_name = str(previous) if previous is not None else "Created"
    stage_name = str(destination)
    if module == "crm":
        from app.apps.crm.models import CRMPipelineStage
        named = {str(stage.id):stage.name for stage in db.query(CRMPipelineStage).filter(CRMPipelineStage.organization_id==org,CRMPipelineStage.id.in_([int(value) for value in [previous,destination] if value is not None])).all()}
        previous_name = named.get(str(previous),previous_name);stage_name=named.get(str(destination),stage_name)
    from app.shared.runtime import DEPTH
    depth = DEPTH.get()
    event = ServiceEvent(organization_id=org, module_key=module, entity_type=kind, entity_id=record_id, actor_id=user.id, event_type="pipeline.stage_entered", request_key=f"pipeline:{module}:{record_id}:{uuid.uuid4().hex}", payload_json={"origin":"pipeline_workspace","data": {"previous_stage": str(previous), "stage": str(destination), "previous_stage_name":previous_name,"stage_name":stage_name, "owner_id": owner_id, "scope": scope}, "depth": depth}, status="pending" if depth < 6 else "depth_limited")
    db.add(event)
    if module == "crm" and owner_id:
        from app.apps.crm.models import CRMPipelineStage
        stage = db.query(CRMPipelineStage).filter_by(id=int(destination),organization_id=org).first()
        if stage and (stage.policy_json or {}).get("notify_owner"):
            from app.models.notification import Notification
            from app.models.user import User
            owner = db.get(User,owner_id)
            if owner and owner.is_active and tenant(owner) == org:
                db.add(Notification(company_id=org,user_id=owner.id,title="Pipeline stage changed",message="A deal assigned to you entered a new stage. Open the deal to review its next action.",module=module,event_type="pipeline.stage_entered",related_entity_type=kind,related_entity_id=record_id,action_url=f"/crm/deals/{record_id}"))
    return event


def record_access(db, user, module, kind, ident, check_module=True):
    if check_module: access(db, user, module, "records")
    if module == "crm" and kind == "deal":
        from app.apps.crm.api import router as crm
        resource = crm._get_resource("deals")
        crm._assert_entity_permission("deals", user, "view")
        crm._assert_record_visible(db, resource, ident, tenant(user), user)
        return crm._get_record(db, resource, ident, tenant(user))
    if module == "project_management" and kind == "task":
        from app.apps.project_management.access import get_task_project_for_action
        return get_task_project_for_action(db, ident, user, "browse")[0]
    if module == "hrms" and kind == "candidate":
        from app.apps.srm.services.commercial import require
        require(user,"recruitment_view","recruitment_manage")
        from app.models.recruitment import Candidate
        row = db.query(Candidate).filter_by(id=ident).first()
        if row: return row
    if module == "srm" and kind == "sales_order":
        from app.apps.srm.services.commercial import require
        require(user,"srm_view","srm_manage","srm_admin")
        from app.apps.srm.access import get_sales_order_for_user
        return get_sales_order_for_user(db,ident,user)
    raise HTTPException(404, "Record not found in your permitted scope")


def sales_records(db, user, identifiers):
    from app.apps.srm.access import sales_order_query
    from app.apps.srm.models import SRMSalesOrder
    from app.apps.srm.services.commercial import require
    require(user, "srm_view", "srm_manage", "srm_admin")
    records = {row.id: row for row in sales_order_query(db, user).filter(SRMSalesOrder.id.in_(identifiers)).all()}
    if set(records) != set(identifiers): raise HTTPException(404, "Sales order not found")
    return records


def bulk_records(db, user, module, kind, identifiers):
    if module == "srm" and kind == "sales_order": return sales_records(db, user, identifiers)
    if module == "project_management" and kind == "task":
        from app.apps.project_management.models import PMSTask
        from app.apps.project_management.access import get_project_for_action
        records = {row.id:row for row in db.query(PMSTask).filter(PMSTask.id.in_(identifiers),PMSTask.deleted_at.is_(None)).all()}
        if set(records) != set(identifiers): raise HTTPException(404, "Task not found")
        for project_id in {row.project_id for row in records.values()}: get_project_for_action(db,project_id,user,"browse")
        return records
    if module == "hrms" and kind == "candidate":
        from app.apps.srm.services.commercial import require
        from app.models.recruitment import Candidate
        require(user,"recruitment_view","recruitment_manage")
        records = {row.id:row for row in db.query(Candidate).filter(Candidate.id.in_(identifiers)).all()}
        if set(records) != set(identifiers): raise HTTPException(404,"Candidate not found")
        return records
    return {ident:record_access(db,user,module,kind,ident,check_module=False) for ident in identifiers}


@router.get("/{module}/records/{kind}/{ident}/history")
def history(module: Module, kind: str, ident: int, limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db), user=Depends(get_current_user)):
    record_access(db, user, module, kind, ident)
    events = db.query(ServiceEvent).filter_by(organization_id=tenant(user), module_key=module, entity_type=kind, entity_id=ident, event_type="pipeline.stage_entered").filter(ServiceEvent.payload_json["origin"].as_string()=="pipeline_workspace").order_by(ServiceEvent.id.desc()).limit(limit).all()
    return {"items": [{"id": e.id, "at": e.created_at, "actor_id": e.actor_id, **(e.payload_json or {}).get("data", {})} for e in events], "basis": "Recorded stage transitions since pipeline history was enabled; earlier durations are unknown."}


HIRING_STAGES = ["Applied", "Screening", "Interview", "Assessment", "Offer", "Hired", "Rejected", "Withdrawn"]


def hiring_policy(db, user, job_id):
    from app.models.recruitment import Job
    job = db.query(Job).filter_by(id=job_id).first()
    if not job: raise HTTPException(404, "Job not found in your permitted scope")
    row = db.query(ServicePolicy).filter_by(scope_key=f"hiring-pipeline:{tenant(user)}:{job_id}", organization_id=tenant(user), kind="hiring_pipeline").first()
    return job, row


class HiringStage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=30)
    wip_limit: int | None = Field(default=None, ge=1, le=10000)
    aging_days: int = Field(default=14, ge=1, le=365)
    required: list[Literal["email", "phone", "source", "resume_url"]] = Field(default_factory=list, max_length=4)
    require_interview: bool = False
    require_offer: bool = False


class HiringConfiguration(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1, max_length=160)
    stages: list[HiringStage] = Field(min_length=1, max_length=40)
    expected_version: int = Field(ge=0)


@router.get("/hrms/jobs/{job_id}/configuration")
def get_hiring_configuration(job_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(db, user, "hrms", f"job:{job_id}")
    job, row = hiring_policy(db, user, job_id)
    from app.models.recruitment import Candidate
    used = {status for status, in db.query(Candidate.status).filter_by(job_id=job_id).distinct()}
    defaults = list(dict.fromkeys([*HIRING_STAGES, *sorted("Offer" if status == "Offered" else status for status in used)]))
    values = row.values_json if row else {"name": f"{job.title} hiring", "stages": [{"id": s, "name": s} for s in defaults]}
    return {**values, "version": row.version if row else 0}


@router.put("/hrms/jobs/{job_id}/configuration")
def save_hiring_configuration(job_id: int, data: HiringConfiguration, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(db, user, "hrms", f"job:{job_id}", manage=True)
    from app.models.recruitment import Job, Candidate
    job, row = hiring_policy(db, user, job_id)
    db.query(Job).filter_by(id=job.id).with_for_update().one()
    if data.expected_version != (row.version if row else 0): raise HTTPException(409, "Hiring pipeline changed. Reload before saving.")
    names = [s.name.strip() for s in data.stages]
    if any(not name for name in names) or len(set(n.casefold() for n in names)) != len(names): raise HTTPException(422, "Stage names must be unique")
    used = {status for status, in db.query(Candidate.status).filter_by(job_id=job_id).distinct()}
    if "Offer" in names and "Offered" not in names: used = {"Offer" if status == "Offered" else status for status in used}
    if not used.issubset(set(names)): raise HTTPException(409, "Move candidates out of a stage before renaming or removing it")
    if not {"Hired", "Rejected", "Withdrawn"}.issubset(set(names)): raise HTTPException(422, "Retain the Hired, Rejected and Withdrawn outcome stages")
    values = {"name": data.name.strip(), "stages": [{**s.model_dump(), "id": name, "name": name} for s, name in zip(data.stages, names)]}
    if row is None:
        row = ServicePolicy(scope_key=f"hiring-pipeline:{tenant(user)}:{job_id}", organization_id=tenant(user), module_key="hrms", kind="hiring_pipeline", values_json=values, version=1, updated_by=user.id)
        db.add(row)
    else:
        row.values_json = values; row.version += 1; row.updated_by = user.id
    db.commit()
    return {**values, "version": row.version}


def validate_hiring_move(db, user, candidate, destination):
    from app.models.recruitment import Candidate, Job, Interview
    job, row = hiring_policy(db, user, candidate.job_id)
    db.query(Job).filter_by(id=job.id).with_for_update().one()
    stages = (row.values_json or {}).get("stages", []) if row else [{"name": s} for s in [*HIRING_STAGES, "Offered"]]
    target = next((s for s in stages if s["name"] == destination), None)
    if not target: raise HTTPException(422, "Choose a stage from this job's hiring pipeline")
    if candidate.id is not None and candidate.status == destination: return
    for key in target.get("required", []):
        if not getattr(candidate, key, None): raise HTTPException(422, f"Complete {key.replace('_', ' ')} before entering this stage")
    if target.get("require_interview") and not db.query(Interview).filter_by(candidate_id=candidate.id, status="Completed").first():
        raise HTTPException(409, "Complete an interview before entering this stage")
    if target.get("require_offer") and (not candidate.offer or candidate.offer.status.lower() != "accepted"):
        raise HTTPException(409, "An accepted offer is required for this stage")
    if target.get("wip_limit") and db.query(Candidate).filter(Candidate.job_id == job.id, Candidate.status.in_(["Offer", "Offered"] if destination == "Offer" and not any(s["name"] == "Offered" for s in stages) else [destination]), Candidate.id != candidate.id).count() >= target["wip_limit"]:
        raise HTTPException(409, "The destination hiring stage is at capacity")


class QuickCandidate(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: EmailStr = Field(max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    phone_country_code: str | None = Field(default=None,max_length=8)
    source: str | None = Field(default=None,max_length=50)
    stage: str = Field(default="Applied", max_length=30)


@router.post("/hrms/jobs/{job_id}/candidates", status_code=201)
def quick_candidate(job_id: int, data: QuickCandidate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(db,user,"hrms",f"job:{job_id}",manage=True)
    hiring_policy(db,user,job_id)
    from app.schemas.recruitment import CandidateCreate
    from app.models.recruitment import Candidate
    values = CandidateCreate(job_id=job_id,first_name=data.first_name,last_name=data.last_name,email=data.email,phone=data.phone,phone_country_code=data.phone_country_code,source=data.source)
    candidate = Candidate(**values.model_dump(),status=data.stage)
    with db.no_autoflush:
        validate_hiring_move(db,user,candidate,data.stage)
    db.add(candidate);db.flush()
    stage_entry(db,user,"hrms","candidate",candidate.id,None,data.stage,scope=f"job:{job_id}")
    db.commit()
    return {"id":candidate.id,"status":candidate.status}


@router.get("/{module}/ages")
def stage_ages(module: Module, kind: str, ids: str = Query(max_length=1500), scope: str = Query(default="",max_length=60), db: Session = Depends(get_db), user=Depends(get_current_user)):
    from sqlalchemy import func
    try: identifiers = list(dict.fromkeys(int(value) for value in ids.split(",") if value))
    except ValueError: raise HTTPException(422,"Expected numeric record identifiers")
    if not identifiers or len(identifiers)>100 or min(identifiers)<1: raise HTTPException(422,"Choose 1 to 100 records")
    access(db,user,module,"records")
    records = bulk_records(db,user,module,kind,identifiers)
    query = db.query(ServiceEvent.entity_id,func.max(ServiceEvent.created_at)).filter(ServiceEvent.organization_id==tenant(user),ServiceEvent.module_key==module,ServiceEvent.entity_type==kind,ServiceEvent.entity_id.in_(identifiers),ServiceEvent.event_type=="pipeline.stage_entered",ServiceEvent.payload_json["origin"].as_string()=="pipeline_workspace")
    if module=="srm":
        if scope.startswith("sales-pipeline:"):
            try: pipeline_id=int(scope.split(":")[1])
            except ValueError: raise HTTPException(422,"Invalid Sales pipeline scope")
            query=query.filter(ServiceEvent.payload_json["data"]["stream"].as_string()=="sales_pipeline",ServiceEvent.payload_json["data"]["pipeline_id"].as_integer()==pipeline_id)
        else: query=query.filter(ServiceEvent.payload_json["data"]["stream"].as_string().is_(None))
    rows=query.group_by(ServiceEvent.entity_id).all()
    now=datetime.now(timezone.utc)
    items = {str(ident):{"next_action_at":getattr(record,"next_follow_up_at",None) if module=="crm" else getattr(record,"due_date",None)} for ident,record in records.items()}
    for ident,at in rows: items[str(ident)].update(entered_at=at,days=max(0,(now-at.replace(tzinfo=at.tzinfo or timezone.utc)).days))
    if module=="project_management":
        from app.apps.project_management.models import PMSTaskUpdateEntry
        next_rows=db.query(PMSTaskUpdateEntry.task_id,func.min(PMSTaskUpdateEntry.follow_up_date)).filter(PMSTaskUpdateEntry.task_id.in_(identifiers),PMSTaskUpdateEntry.kind=="followup",PMSTaskUpdateEntry.resolved.is_(False),PMSTaskUpdateEntry.deleted_at.is_(None)).group_by(PMSTaskUpdateEntry.task_id).all()
        for ident,at in next_rows:
            if at: items[str(ident)]["next_action_at"]=at
    elif module=="hrms":
        from app.models.recruitment import Interview
        for ident,at in db.query(Interview.candidate_id,func.min(Interview.scheduled_at)).filter(Interview.candidate_id.in_(identifiers),Interview.status=="Scheduled").group_by(Interview.candidate_id).all():
            if at: items[str(ident)]["next_action_at"]=at
    elif module=="srm":
        from app.shared.follow_ups import FollowUp
        for ident,at in db.query(FollowUp.order_id,func.min(FollowUp.due_at)).filter(FollowUp.organization_id==tenant(user),FollowUp.order_id.in_(identifiers),FollowUp.status=="Scheduled").group_by(FollowUp.order_id).all():
            if at: items[str(ident)]["next_action_at"]=at
    return {"items":items,"basis":"Recorded transitions only; missing history is unknown. Next actions come from native activities, follow-ups and interviews."}


class SalesStage(HiringStage):
    is_terminal: bool = False
    required: list[Literal["customer_id","title","expected_start_date","expected_end_date"]] = Field(default_factory=list,max_length=4)
    required_statuses: list[Literal["draft","pending_approval","approved","confirmed","closed","cancelled"]] = Field(default_factory=list,max_length=6)


class SalesPipelineInput(BaseModel):
    name: str = Field(min_length=1,max_length=160)
    stages: list[SalesStage] = Field(min_length=1,max_length=30)
    expected_version: int = 0


def sales_definition(db,user,pipeline_id,lock=False):
    query=db.query(ServicePolicy).filter_by(id=pipeline_id,organization_id=tenant(user),module_key="srm",kind="sales_pipeline")
    if lock: query=query.with_for_update().populate_existing()
    row=query.first()
    if not row: raise HTTPException(404,"Sales pipeline not found")
    return row


@router.get("/srm/pipelines")
def sales_pipelines(db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(db,user,"srm","sales-orders")
    rows=db.query(ServicePolicy).filter_by(organization_id=tenant(user),module_key="srm",kind="sales_pipeline").order_by(ServicePolicy.id).all()
    try: access(db,user,"srm","sales-orders",manage=True); can_manage=True
    except HTTPException: can_manage=False
    return {"items":[{"id":row.id,"version":row.version,**row.values_json} for row in rows],"can_manage":can_manage}


@router.post("/srm/pipelines",status_code=201)
def create_sales_pipeline(data:SalesPipelineInput,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(db,user,"srm","sales-orders",manage=True)
    names=[s.name.strip() for s in data.stages]
    if not data.name.strip() or any(not n for n in names) or len(set(n.casefold() for n in names))!=len(names): raise HTTPException(422,"Pipeline and stage names must be nonempty and stage names unique")
    values={"name":data.name.strip(),"stages":[{**s.model_dump(),"id":uuid.uuid4().hex,"name":name} for s,name in zip(data.stages,names)]}
    row=ServicePolicy(scope_key=f"sales-pipeline:{tenant(user)}:{uuid.uuid4().hex}",organization_id=tenant(user),module_key="srm",kind="sales_pipeline",values_json=values,version=1,updated_by=user.id)
    db.add(row);db.commit()
    return {"id":row.id,"version":row.version,**values}


@router.put("/srm/pipelines/{pipeline_id}")
def update_sales_pipeline(pipeline_id:int,data:SalesPipelineInput,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(db,user,"srm","sales-orders",manage=True)
    row=sales_definition(db,user,pipeline_id,lock=True)
    if data.expected_version!=row.version: raise HTTPException(409,"Sales pipeline changed. Reload before saving.")
    existing={s["id"] for s in row.values_json["stages"]}
    if not existing.issubset({s.id for s in data.stages}): raise HTTPException(409,"Retain existing Sales stages so assigned orders keep their history. Stages can be renamed or reordered.")
    names=[s.name.strip() for s in data.stages]
    if not data.name.strip() or any(not n for n in names) or len(set(n.casefold() for n in names))!=len(names): raise HTTPException(422,"Use unique named stages")
    if any(s.id not in existing and not s.id.startswith("new:") for s in data.stages): raise HTTPException(422,"Invalid stage identifier")
    if len({s.id for s in data.stages})!=len(data.stages): raise HTTPException(422,"Stage identifiers must be unique")
    row.values_json={"name":data.name.strip(),"stages":[{**s.model_dump(),"id":uuid.uuid4().hex if s.id.startswith("new:") else s.id,"name":name} for s,name in zip(data.stages,names)]}
    row.version+=1;row.updated_by=user.id;db.commit()
    return {"id":row.id,"version":row.version,**row.values_json}


def sales_positions_query(db,user,identifiers=None):
    from sqlalchemy import func
    from app.apps.srm.models import SRMSalesOrder
    active_orders=db.query(SRMSalesOrder.id).filter(SRMSalesOrder.organization_id==tenant(user),SRMSalesOrder.deleted_at.is_(None))
    query=db.query(ServiceEvent.entity_id.label("record_id"),func.max(ServiceEvent.id).label("event_id")).filter(ServiceEvent.organization_id==tenant(user),ServiceEvent.module_key=="srm",ServiceEvent.entity_type=="sales_order",ServiceEvent.event_type=="pipeline.stage_entered",ServiceEvent.payload_json["data"]["stream"].as_string()=="sales_pipeline",ServiceEvent.payload_json["origin"].as_string()=="pipeline_workspace",ServiceEvent.entity_id.in_(active_orders))
    if identifiers is not None: query=query.filter(ServiceEvent.entity_id.in_(identifiers))
    latest=query.group_by(ServiceEvent.entity_id).subquery()
    return db.query(ServiceEvent).join(latest,ServiceEvent.id==latest.c.event_id)


@router.get("/srm/positions")
def get_sales_positions(ids:str=Query(max_length=1500),db:Session=Depends(get_db),user=Depends(get_current_user)):
    try: identifiers=list(dict.fromkeys(int(i) for i in ids.split(",") if i))
    except ValueError: raise HTTPException(422,"Expected numeric order identifiers")
    if not identifiers or len(identifiers)>100: raise HTTPException(422,"Choose between 1 and 100 orders")
    access(db,user,"srm","records")
    sales_records(db,user,identifiers)
    return {"items":{str(row.entity_id):{"event_id":row.id,**row.payload_json["data"]} for row in sales_positions_query(db,user,identifiers)}}


class SalesPosition(BaseModel):
    pipeline_id:int=Field(gt=0)
    stage_id:str=Field(min_length=1,max_length=100)
    expected_event_id:int|None=None


@router.post("/srm/orders/{order_id}/position")
def move_sales_position(order_id:int,data:SalesPosition,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(db,user,"srm","sales-orders",manage=True)
    order=record_access(db,user,"srm","sales_order",order_id)
    from app.apps.srm.models import SRMSalesOrder
    db.query(SRMSalesOrder).filter_by(id=order.id,organization_id=tenant(user)).with_for_update().one()
    definition=sales_definition(db,user,data.pipeline_id,lock=True)
    previous=sales_positions_query(db,user,[order.id]).first()
    if (previous.id if previous else None)!=data.expected_event_id: raise HTTPException(409,"This order moved in another session. Refresh before moving it.")
    target=next((s for s in definition.values_json["stages"] if s["id"]==data.stage_id),None)
    if not target and data.stage_id!="unassigned": raise HTTPException(422,"Choose a configured Sales stage")
    if target:
        if any(not getattr(order,key,None) for key in target.get("required",[])): raise HTTPException(422,"Complete the required order fields before entering this stage")
        if target.get("required_statuses") and order.status not in target["required_statuses"]: raise HTTPException(409,"Complete the required document approval/confirmation before entering this stage")
        if target.get("wip_limit"):
            occupied=sum(1 for event in sales_positions_query(db,user) if event.entity_id!=order.id and event.payload_json["data"].get("pipeline_id")==definition.id and event.payload_json["data"].get("stage")==target["id"])
            if occupied>=target["wip_limit"]: raise HTTPException(409,"The destination operational stage is at capacity")
    old=previous.payload_json["data"] if previous else {}
    destination=target["id"] if target else "unassigned"
    if old.get("pipeline_id")==definition.id and old.get("stage")==destination:return {"event_id":previous.id,**old}
    values={"stream":"sales_pipeline","pipeline_id":definition.id if target else None,"pipeline_name":definition.values_json["name"],"previous_stage":old.get("stage","unassigned"),"previous_stage_name":old.get("stage_name","Unassigned"),"stage":destination,"stage_name":target["name"] if target else "Unassigned","document_status":order.status}
    from app.shared.runtime import DEPTH
    depth=DEPTH.get()
    event=ServiceEvent(organization_id=tenant(user),module_key="srm",event_type="pipeline.stage_entered",entity_type="sales_order",entity_id=order.id,actor_id=user.id,request_key=f"sales-position:{uuid.uuid4().hex}",payload_json={"origin":"pipeline_workspace","data":values,"depth":depth},status="pending" if depth<6 else "depth_limited")
    db.add(event);db.commit()
    return {"event_id":event.id,**values}
