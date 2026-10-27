"""Authorized design-time operations. This router has no runtime executors."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.apps.power_apps.contracts import Contract, DraftCreate
from app.apps.power_apps.graph import VisualWorkflowDefinition
from app.apps.power_apps.node_registry import NODES, CATALOG_VERSION
from app.apps.power_apps.studio import validate_graph, preview_graph
from app.apps.power_apps.templates import TEMPLATES, template_by_id
from app.apps.power_apps.models import PowerResource, PowerVersion
from app.apps.power_apps.router import find_draft, create_draft
from app.apps.power_apps.service import serialize, record_change, scoped, validate_environment, organization

router = APIRouter(prefix="/power-apps/automations", tags=["Automation Studio"], dependencies=[Depends(RequirePermission("power_apps_view"))])

class ValidationRequest(Contract):
    definition: VisualWorkflowDefinition

class PreviewRequest(ValidationRequest):
    test_input: dict = Field(default_factory=dict, max_length=100)
    synthetic_outputs: dict = Field(default_factory=dict, max_length=250)
    injected_errors: list[str] = Field(default_factory=list,max_length=250)

class VersionRequest(Contract):
    expected_version: int = Field(ge=1)

class DuplicateRequest(Contract):
    name: str | None = Field(default=None, min_length=1, max_length=180)

class RestoreRequest(DuplicateRequest):
    version: int = Field(ge=1)

def validate_references(graph, db, user, environment):
    result = validate_graph(graph)
    for node in graph.nodes:
        value = node.config.get("workflow_id") if node.type == "sub_workflow" else None
        if not value or "{{" in str(value):
            continue
        text = str(value)
        target_id = int(text) if text.isascii() and text.isdigit() and len(text) <= 10 and int(text) <= 2147483647 else -1
        target = scoped(db, PowerResource, user, environment).filter(
            PowerResource.id == target_id,
            PowerResource.application_id == "automations", PowerResource.archived_at.is_(None),
        ).first()
        if target is None:
            result["issues"].append({"code": "workflow_reference", "message": "Workflow reference is unavailable in this tenant and environment", "node_id": node.id, "field": "workflow_id", "severity": "error"})
            result["valid"] = False
    return result

@router.get("/node-catalog")
def node_catalog(user=Depends(RequirePermission("power_apps_view"))):
    from app.apps.power_apps.runtime_executors import EXECUTORS
    return {"version": CATALOG_VERSION, "nodes": [{**n, "executable": n["id"] in EXECUTORS} for n in NODES.values()], "execution_enabled": True}

@router.get("/templates")
def templates(user=Depends(RequirePermission("power_apps_view"))):
    return {"items": TEMPLATES}

@router.post("/templates/{template_id}/use", status_code=201)
def use_template(template_id: str, environment: str = "development", db: Session = Depends(get_db), user=Depends(RequirePermission("power_apps_create"))):
    template = template_by_id(template_id)
    if not template:
        raise HTTPException(404, "Template not found")
    payload = DraftCreate(name=template["name"], description=template["description"], definition=template["definition"])
    return create_draft(payload, environment, db, user)

@router.post("/validate")
def validate(data: ValidationRequest, environment: str = "development", db: Session = Depends(get_db), user=Depends(RequirePermission("power_apps_view"))):
    validate_environment(db, user, environment)
    return validate_references(data.definition, db, user, environment)

@router.post("/preview")
def preview(data: PreviewRequest, environment: str = "development", db: Session = Depends(get_db), user=Depends(RequirePermission("power_apps_view"))):
    validate_environment(db, user, environment)
    validation = validate_references(data.definition, db, user, environment)
    if not validation["valid"]:
        return {"design_time_only": True, "integration_execution": False, "validation": validation, "timeline": []}
    try:
        return preview_graph(data.definition, data.test_input, environment, data.synthetic_outputs, data.injected_errors)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

@router.post("/{resource_id}/duplicate", status_code=201)
def duplicate(resource_id: int, data: DuplicateRequest, environment: str = "development", db: Session = Depends(get_db), user=Depends(RequirePermission("power_apps_create"))):
    original = find_draft(db, user, environment, resource_id)
    payload = DraftCreate(name=data.name or (original.name[:170] + " (copy)"), description=original.description, definition=original.definition)
    return create_draft(payload, environment, db, user)

@router.post("/{resource_id}/restore", status_code=201)
def restore(resource_id: int, data: RestoreRequest, environment: str = "development", db: Session = Depends(get_db), user=Depends(RequirePermission("power_apps_create"))):
    original = find_draft(db, user, environment, resource_id)
    snapshot = db.query(PowerVersion).filter_by(organization_id=organization(user), resource_id=original.id, version=data.version).first()
    if snapshot is None:
        raise HTTPException(404, "Version not found")
    payload = DraftCreate(name=data.name or (snapshot.snapshot["name"][:150] + f" (restored v{data.version})"), description=snapshot.snapshot.get("description", ""), definition=snapshot.snapshot["definition"])
    # Restoring creates a new draft; it never mutates the source or its snapshots.
    return create_draft(payload, environment, db, user)


def lifecycle(db, user, environment, resource_id, data, archived):
    row = find_draft(db, user, environment, resource_id)
    if row.status != "draft":
        raise HTTPException(409, "Only drafts can change lifecycle in Phase 2")
    changed = scoped(db, PowerResource, user, environment).filter(PowerResource.id == row.id, PowerResource.version == data.expected_version).update({PowerResource.archived_at: datetime.now(timezone.utc) if archived else None, PowerResource.version: PowerResource.version + 1, PowerResource.updated_at: datetime.now(timezone.utc)}, synchronize_session=False)
    if not changed:
        raise HTTPException(409, "Draft changed; reload before changing its lifecycle")
    db.refresh(row)
    record_change(db, user, row, "draft_archived" if archived else "draft_unarchived")
    db.commit()
    return serialize(row)

@router.post("/{resource_id}/archive")
def archive(resource_id: int, data: VersionRequest, environment: str = "development", db: Session = Depends(get_db), user=Depends(RequirePermission("power_apps_edit"))):
    return lifecycle(db, user, environment, resource_id, data, True)

@router.post("/{resource_id}/unarchive")
def unarchive(resource_id: int, data: VersionRequest, environment: str = "development", db: Session = Depends(get_db), user=Depends(RequirePermission("power_apps_edit"))):
    return lifecycle(db, user, environment, resource_id, data, False)

