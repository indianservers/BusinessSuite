"""Authorized, side-effect-free authoring endpoints and versioned reusable blocks."""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field, ValidationError
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.deps import get_db, RequirePermission
from app.apps.power_apps.contracts import Contract
from app.apps.power_apps.graph import VisualWorkflowDefinition
from app.apps.power_apps.authoring_contracts import FieldMapping
from app.apps.power_apps.authoring import bounded, map_value
from app.apps.power_apps.intelligence import portable, analyze
from app.apps.power_apps.models import PowerResource, PowerVersion
from app.apps.power_apps.service import scoped, organization, validate_environment, serialize, record_change
from app.apps.power_apps.studio_api import validate_references, VersionRequest
from app.apps.power_apps.node_registry import NODES

router=APIRouter(prefix="/power-apps/automations",tags=["Intelligent Automation Authoring"],dependencies=[Depends(RequirePermission("power_apps_view"))])

class GraphRequest(Contract):
    definition: VisualWorkflowDefinition
class AnalysisRequest(GraphRequest):
    workflow_id: int | None = Field(default=None,ge=1,le=2147483647)
    name: str = Field(default="Workflow",max_length=180)
    description: str = Field(default="",max_length=2000)
    version: int = Field(default=0,ge=0)
class MappingRequest(Contract):
    node_type: str | None = Field(default=None,max_length=80)
    field: str | None = Field(default=None,max_length=80)
    mapping: FieldMapping
    context: dict = Field(default_factory=dict,max_length=100)
class AIRequest(GraphRequest):
    prompt: str = Field(min_length=1,max_length=6000)
    mode: str = Field(default="design",pattern=r"^(design|explain|improve|conditions|mappings|errors)$")
    provider: str = Field(default="gemini",pattern=r"^(gemini|openai|claude)$")
class Proposal(Contract):
    summary: str = Field(max_length=4000)
    findings: list[str] = Field(default_factory=list,max_length=30)
    definition: VisualWorkflowDefinition | None = None

@router.post("/intelligence/analyze")
def analysis(data:AnalysisRequest,environment:str="development",db:Session=Depends(get_db),user=Depends(RequirePermission("power_apps_view"))):
    validate_environment(db,user,environment)
    history=[]
    if data.workflow_id:
        from app.apps.power_apps.router import find_draft
        row=find_draft(db,user,environment,data.workflow_id)
        history=[{"version":v.version,"name":v.snapshot["name"]} for v in db.query(PowerVersion).filter_by(resource_id=row.id,organization_id=organization(user)).order_by(PowerVersion.version.desc()).limit(100)]
    result=analyze(data.definition,data.name,data.description,data.version,history)
    result["validation"]=validate_references(data.definition,db,user,environment)
    existing={(item["code"],item.get("node_id"),item["message"]) for item in result["quality"]["findings"]}
    extra=[item for item in result["validation"]["issues"] if (item["code"],item.get("node_id"),item["message"]) not in existing]
    result["quality"]["findings"].extend(extra)
    result["quality"]["score"]=max(0,result["quality"]["score"]-sum(8 if item["severity"]=="error" else 2 for item in extra))
    return result

@router.post("/intelligence/review")
def review(data:GraphRequest,environment:str="development",db:Session=Depends(get_db),user=Depends(RequirePermission("power_apps_view"))):
    validate_environment(db,user,environment)
    return {"definition":data.definition.model_dump(),"validation":validate_references(data.definition,db,user,environment)}

@router.post("/mapping/preview")
def mapping_preview(data:MappingRequest,environment:str="development",db:Session=Depends(get_db),user=Depends(RequirePermission("power_apps_view"))):
    validate_environment(db,user,environment)
    try:
        bounded(data.context)
        context={**data.context,"env":{"name":environment}}
        value=map_value(data.mapping.model_dump(),context)
        if data.node_type or data.field:
            definition=NODES.get(data.node_type,{})
            field=next((item for item in definition.get("fields",[]) if item["key"]==data.field),None)
            if not field:raise ValueError("Mapping destination must be a registered field")
            from app.apps.power_apps.node_registry import configuration_errors
            if field["kind"] not in {"dynamic","expression"}:
                errors=configuration_errors(data.node_type,{data.field:value})
                if errors:raise ValueError("; ".join(errors))
        return {"value":value,"design_time_only":True}
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError) as exc:raise HTTPException(422,str(exc)[:300])

@router.post("/portable/prepare")
def prepare(data:GraphRequest,environment:str="development",db:Session=Depends(get_db),user=Depends(RequirePermission("power_apps_view"))):
    validate_environment(db,user,environment)
    result=portable(data.definition.model_dump())
    return {"definition":result,"validation":validate_references(VisualWorkflowDefinition.model_validate(result),db,user,environment),"warnings":["Credential references and tenant-bound sub-workflow/block links stripped. IDs remapped. Draft only."]}

@router.post("/ai/propose")
def ai_propose(data:AIRequest,request:Request,environment:str="development",db:Session=Depends(get_db),user=Depends(RequirePermission("power_apps_create"))):
    validate_environment(db,user,environment)
    from app.ai_agents.api import _require_ai_access, _require_ai_rate_limit
    from app.ai_agents.services.advanced_security import AiSecuritySettingsService,AiUsageService,AiDataRedactionService
    from app.ai_operator.models import OperatorProvider
    from app.ai_operator.providers import generate_json
    from copy import copy
    from app.access.service import check_background_access, effective_objects
    from app.apps.business_os.services.module_service import assert_module_enabled
    check_background_access(db,user,"ai","view")
    ai_user=copy(user)
    if getattr(user,"_suite_grants",None) is not None:ai_user._suite_permission_objects=effective_objects(db,user._suite_grants,"ai")
    _require_ai_access(ai_user)
    assert_module_enabled(db,"ai",organization(user))
    AiSecuritySettingsService(db).ensure_enabled(user=user,module="CROSS")
    AiUsageService(db).check_limits(user=user,agent=None,module="CROSS")
    _require_ai_rate_limit(db,request,user,bucket="power_apps_authoring")
    scope=f"company:{organization(user)}"
    config=db.query(OperatorProvider).filter_by(scope_key=scope,provider=data.provider,enabled=True,data_sharing_allowed=True).first()
    if not config:raise HTTPException(503,"Authorized AI gateway unavailable: configure an enabled company provider with data-sharing approval. No fallback generated.")
    definition=data.definition.model_dump()
    for node in definition["nodes"]:node["credential_reference"]=None
    outbound=AiDataRedactionService().redact_for_ai(user,"CROSS",{"request":data.prompt,"mode":data.mode,"definition":definition,"catalog":list(NODES.values())})
    AiUsageService(db).record_event(user=user,agent_id=None,module="CROSS",event_type="power_apps_design")
    try:
        result=generate_json(db,user,config,prompt=json.dumps(outbound),schema=Proposal.model_json_schema(),output_type=Proposal,purpose="power_apps_design",usage_scope=scope,module="POWER_APPS")
        proposal=Proposal.model_validate(result)
        bounded(proposal.model_dump())
        if proposal.definition:
            bounded(proposal.definition.model_dump())
            for node in proposal.definition.nodes:
                if node.credential_reference:raise ValueError("AI may not bind credentials")
            validation=validate_references(proposal.definition,db,user,environment)
        else:validation=None
        db.commit()
        return {**proposal.model_dump(),"validation":validation,"requires_approval":True,"execution_enabled":False}
    except (ValidationError,ValueError,TypeError):
        db.commit();raise HTTPException(502,"AI proposal rejected: invalid or unsafe workflow definition")
    except HTTPException:
        db.commit();raise

class BlockWrite(GraphRequest):
    name: str = Field(min_length=1,max_length=180)
    description: str = Field(default="",max_length=2000)
    expected_version: int = Field(default=0,ge=0)

def block(db,user,environment,id):
    validate_environment(db,user,environment)
    row=scoped(db,PowerResource,user,environment).filter_by(id=id,application_id="reusable-blocks").first()
    if not row:raise HTTPException(404,"Block not found")
    return row

def dependencies(db,user,environment,definition,ancestors=None,depth=0,budget=None):
    budget=budget if budget is not None else [0]
    budget[0]+=1
    if budget[0]>1000:raise HTTPException(422,"Block dependency complexity exceeds 1000")
    if depth>12:raise HTTPException(422,"Block dependency depth exceeds 12")
    for ref in definition.get("block_references",[]):
        if ref["resource_id"] in (ancestors or set()):raise HTTPException(422,"Circular reusable-block dependency")
        row=block(db,user,environment,ref["resource_id"])
        if row.archived_at:raise HTTPException(422,"Archived block versions cannot be inserted into a new definition")
        snapshot=db.query(PowerVersion).filter_by(resource_id=row.id,version=ref["version"],organization_id=organization(user)).first()
        if not snapshot:raise HTTPException(422,"Referenced block version unavailable")
        dependencies(db,user,environment,snapshot.snapshot["definition"],(ancestors or set())|{row.id},depth+1,budget)

def usages(db,user,environment,id):
    rows=scoped(db,PowerResource,user,environment).all()
    return [{"id":row.id,"name":row.name,"version":row.version} for row in rows if any(ref.get("resource_id")==id for ref in row.definition.get("block_references",[]))]

@router.get("/blocks")
def list_blocks(environment:str="development",db:Session=Depends(get_db),user=Depends(RequirePermission("power_apps_view"))):
    validate_environment(db,user,environment)
    return {"items":[serialize(row) for row in scoped(db,PowerResource,user,environment).filter_by(application_id="reusable-blocks",archived_at=None).order_by(PowerResource.id.desc()).limit(100)]}

@router.post("/blocks",status_code=201)
def create_block(data:BlockWrite,environment:str="development",db:Session=Depends(get_db),user=Depends(RequirePermission("power_apps_create"))):
    validate_environment(db,user,environment);definition=data.definition.model_dump();dependencies(db,user,environment,definition)
    if not definition["nodes"] or any(NODES[n["type"]]["trigger"] for n in definition["nodes"]):raise HTTPException(422,"Select a nonempty block without a trigger")
    row=PowerResource(organization_id=organization(user),environment=environment,application_id="reusable-blocks",name=data.name,description=data.description,owner_user_id=user.id,status="draft",version=1,definition=definition)
    db.add(row);db.flush();record_change(db,user,row,"block_created");db.commit();db.refresh(row);return serialize(row)

@router.put("/blocks/{id}")
def update_block(id:int,data:BlockWrite,environment:str="development",db:Session=Depends(get_db),user=Depends(RequirePermission("power_apps_edit"))):
    row=block(db,user,environment,id)
    if row.archived_at:raise HTTPException(409,"Archived blocks are immutable")
    definition=data.definition.model_dump();dependencies(db,user,environment,definition,{id})
    if not definition["nodes"] or any(NODES[n["type"]]["trigger"] for n in definition["nodes"]):raise HTTPException(422,"Blocks cannot contain triggers")
    changed=scoped(db,PowerResource,user,environment).filter_by(id=id,version=data.expected_version).update({PowerResource.definition:definition,PowerResource.name:data.name,PowerResource.description:data.description,PowerResource.version:PowerResource.version+1,PowerResource.updated_at:func.now()},synchronize_session=False)
    if not changed:raise HTTPException(409,"Block changed; reload before saving")
    db.refresh(row);record_change(db,user,row,"block_updated");db.commit();return serialize(row)

@router.get("/blocks/{id}/versions")
def block_versions(id:int,environment:str="development",db:Session=Depends(get_db),user=Depends(RequirePermission("power_apps_view"))):
    row=block(db,user,environment,id)
    return {"items":[serialize(v) for v in db.query(PowerVersion).filter_by(resource_id=row.id,organization_id=organization(user)).order_by(PowerVersion.version.desc()).limit(100)]}

@router.get("/blocks/{id}/usage")
def block_usage(id:int,environment:str="development",db:Session=Depends(get_db),user=Depends(RequirePermission("power_apps_view"))):
    block(db,user,environment,id);return {"items":usages(db,user,environment,id)}

@router.post("/blocks/{id}/archive")
def archive_block(id:int,data:VersionRequest,environment:str="development",db:Session=Depends(get_db),user=Depends(RequirePermission("power_apps_edit"))):
    row=block(db,user,environment,id)
    # Check all tenant resources, including scopes invisible to the caller, without revealing them.
    referenced=any(any(ref.get("resource_id")==id for ref in resource.definition.get("block_references",[])) for resource in db.query(PowerResource).filter_by(organization_id=organization(user),environment=environment))
    if referenced:raise HTTPException(409,"Referenced block versions cannot be archived or deleted")
    changed=scoped(db,PowerResource,user,environment).filter_by(id=id,version=data.expected_version).update({PowerResource.archived_at:datetime.now(timezone.utc),PowerResource.version:PowerResource.version+1},synchronize_session=False)
    if not changed:raise HTTPException(409,"Block changed; reload")
    db.refresh(row);record_change(db,user,row,"block_archived");db.commit();return serialize(row)
