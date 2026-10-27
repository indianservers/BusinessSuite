from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from typing import Literal
from app.core.deps import get_db, RequirePermission
from app.access.catalog import permission_names
from app.apps.power_apps.contracts import DraftCreate, DraftUpdate, EnvironmentUpdate
from app.apps.power_apps.models import PowerResource, PowerEnvironment, PowerExecution, PowerActivity, PowerVersion
from app.apps.power_apps.registry import APPLICATIONS, COMPONENTS, TEMPLATES, ENVIRONMENTS, PERMISSIONS
from app.apps.power_apps.service import organization, scoped, serialize, validate_environment, record_change
from app.apps.power_apps.templates import TEMPLATES as AUTOMATION_TEMPLATES

router = APIRouter(prefix="/power-apps", tags=["Power Apps"])
# Write permission alone never grants access to the module.
router.dependencies.append(Depends(RequirePermission("power_apps_view")))

@router.get("/catalog")
def catalog(user=Depends(RequirePermission("power_apps_view"))):
    names = set(PERMISSIONS) if user.is_superuser else permission_names(user)
    return {"applications": [app.payload() for app in APPLICATIONS if set(app.required_permissions) <= names],
        "permissions": sorted(names.intersection(PERMISSIONS)), "execution_enabled": True,
        "components": COMPONENTS, "templates": list(TEMPLATES.values()) + [{**item, "application_id": "automations"} for item in AUTOMATION_TEMPLATES]}

@router.get("/environments")
def environments(db: Session = Depends(get_db), user=Depends(RequirePermission("power_apps_view"))):
    items = db.query(PowerEnvironment).filter_by(organization_id=organization(user)).all()
    return {"items": [{"key": item.key, "enabled": item.enabled} for item in items]}

@router.put("/environments/{key}")
def configure_environment(key: str, data: EnvironmentUpdate, db: Session = Depends(get_db), user=Depends(RequirePermission("power_apps_manage_environment"))):
    if key not in ENVIRONMENTS:
        raise HTTPException(422, "Unknown environment")
    row = db.query(PowerEnvironment).filter_by(organization_id=organization(user), key=key).with_for_update().first()
    if row is None:
        row = PowerEnvironment(organization_id=organization(user), key=key)
        db.add(row)
    row.enabled = data.enabled
    db.add(PowerActivity(organization_id=organization(user), environment=key, owner_user_id=user.id,
        actor_user_id=user.id, action="environment_enabled" if data.enabled else "environment_disabled", resource_name=key))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Environment changed concurrently; reload and retry")
    return {"key": key, "enabled": row.enabled}

@router.get("/overview")
def overview(environment: str = "development", db: Session = Depends(get_db), user=Depends(RequirePermission("power_apps_view"))):
    validate_environment(db, user, environment)
    resources = scoped(db, PowerResource, user, environment).filter(PowerResource.archived_at.is_(None))
    runs = scoped(db, PowerExecution, user, environment)
    # There are no submissions or approvals writers in Phase 1; never read other modules.
    from app.apps.power_apps.runtime_models import AutomationDeployment
    active = resources.join(AutomationDeployment, AutomationDeployment.resource_id == PowerResource.id).filter(AutomationDeployment.status == "active").count()
    from app.apps.power_apps.approvals.service import visible_ids
    from app.models.approval_os import ApprovalRequest
    pending_approvals=db.query(ApprovalRequest).filter(ApprovalRequest.organization_id==organization(user),ApprovalRequest.source_module=='power_apps',ApprovalRequest.id.in_(visible_ids(db,user,environment)),ApprovalRequest.status.in_(['Pending','Changes Requested','Resolution Required'])).count()
    counts = {"total_apps": resources.filter(PowerResource.application_id == "app-builder").count(),
        "active_automations": active, "pending_approvals": pending_approvals, "form_submissions": 0,
        "workflow_executions": runs.count(), "failed_runs": runs.filter(PowerExecution.status == "failed").count()}
    return {"counts": counts, "recent": [serialize(row) for row in resources.order_by(PowerResource.updated_at.desc(), PowerResource.id.desc()).limit(8)],
        "unsupported_metrics": ["form_submissions"], "execution_enabled": True}

@router.get("/activity")
def activity(environment: str = "development", limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db), user=Depends(RequirePermission("power_apps_activity_view"))):
    validate_environment(db, user, environment)
    return {"items": [serialize(row) for row in scoped(db, PowerActivity, user, environment).order_by(PowerActivity.id.desc()).limit(limit)]}

@router.get("/automations")
def drafts(environment: str = "development", view: Literal["all", "mine", "shared", "drafts", "published", "disabled"] = "all", search: str = Query("", max_length=180), offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), user=Depends(RequirePermission("power_apps_view"))):
    validate_environment(db, user, environment)
    query = scoped(db, PowerResource, user, environment).filter(PowerResource.application_id == "automations")
    from app.apps.power_apps.approvals.models import ApprovalPolicy
    generated=db.query(ApprovalPolicy.runtime_resource_id).filter(ApprovalPolicy.organization_id==organization(user),ApprovalPolicy.environment==environment,ApprovalPolicy.runtime_resource_id.is_not(None))
    query=query.filter(PowerResource.id.notin_(generated))
    if view == "disabled":
        query = query.filter(PowerResource.archived_at.is_not(None))
    else:
        query = query.filter(PowerResource.archived_at.is_(None))
    if view == "mine": query = query.filter(PowerResource.owner_user_id == user.id)
    if view == "shared": query = query.filter(PowerResource.owner_user_id != user.id)
    if view == "published":
        from app.apps.power_apps.runtime_models import AutomationDeployment
        query = query.join(AutomationDeployment, AutomationDeployment.resource_id == PowerResource.id).filter(AutomationDeployment.version_id.is_not(None), AutomationDeployment.status.in_(["published", "active", "paused"]))
    if view == "drafts": query = query.filter(PowerResource.status == "draft")
    if search:
        query = query.filter(PowerResource.name.ilike("%" + search.replace("%", "\\%").replace("_", "\\_") + "%", escape="\\"))
    return {"items": [serialize(row) for row in query.order_by(PowerResource.updated_at.desc(), PowerResource.id.desc()).offset(offset).limit(limit)], "total": query.count()}

def find_draft(db, user, environment, resource_id):
    validate_environment(db, user, environment)
    row = scoped(db, PowerResource, user, environment).filter(PowerResource.id == resource_id, PowerResource.application_id == "automations").first()
    if row is None:
        raise HTTPException(404, "Draft not found")
    from app.apps.power_apps.approvals.models import ApprovalPolicy
    if not db.info.get('power_approval_domain') and db.query(ApprovalPolicy).filter_by(runtime_resource_id=row.id,organization_id=row.organization_id).first():
        raise HTTPException(409,'This execution definition is governed by its approval policy; use the Approval Designer')
    return row

@router.post("/automations", status_code=201)
def create_draft(data: DraftCreate, environment: str = "development", db: Session = Depends(get_db), user=Depends(RequirePermission("power_apps_create"))):
    validate_environment(db, user, environment)
    if getattr(data.definition,"block_references",None):
        from app.apps.power_apps.intelligence_api import dependencies
        dependencies(db,user,environment,data.definition.model_dump())
    row = PowerResource(organization_id=organization(user), environment=environment, application_id="automations",
        name=data.name, description=data.description, owner_user_id=user.id, status="draft", version=1, definition=data.definition.model_dump())
    db.add(row)
    db.flush()
    record_change(db, user, row, "draft_created")
    db.commit()
    db.refresh(row)
    return serialize(row)

@router.get("/automations/{resource_id}")
def read_draft(resource_id: int, environment: str = "development", db: Session = Depends(get_db), user=Depends(RequirePermission("power_apps_view"))):
    return serialize(find_draft(db, user, environment, resource_id))

@router.put("/automations/{resource_id}")
def update_draft(resource_id: int, data: DraftUpdate, environment: str = "development", db: Session = Depends(get_db), user=Depends(RequirePermission("power_apps_edit"))):
    row = find_draft(db, user, environment, resource_id)
    if row.status != "draft" or row.archived_at is not None:
        raise HTTPException(409, "Only active drafts can be edited; unarchive this draft first")
    if getattr(data.definition,"block_references",None):
        from app.apps.power_apps.intelligence_api import dependencies
        dependencies(db,user,environment,data.definition.model_dump())
    previous_refs = {node.get("id"): node.get("credential_reference") for node in row.definition.get("nodes", []) if isinstance(node, dict)}
    changed = scoped(db, PowerResource, user, environment).filter(PowerResource.id == row.id,
        PowerResource.version == data.expected_version).update({PowerResource.name: data.name, PowerResource.description: data.description,
        PowerResource.definition: data.definition.model_dump(), PowerResource.version: PowerResource.version + 1,
        PowerResource.updated_at: func.now()}, synchronize_session=False)
    if not changed:
        raise HTTPException(409, "Draft changed since you opened it; reload before saving")
    db.refresh(row)
    record_change(db, user, row, "draft_updated")
    current_refs = {node.get("id"): node.get("credential_reference") for node in row.definition.get("nodes", []) if isinstance(node, dict)}
    if previous_refs != current_refs and any(value for value in [*previous_refs.values(), *current_refs.values()]):
        record_change(db, user, row, "credential_reference_changed", snapshot=False)
    db.commit()
    return serialize(row)

@router.get("/automations/{resource_id}/versions")
def versions(resource_id: int, environment: str = "development", db: Session = Depends(get_db), user=Depends(RequirePermission("power_apps_view"))):
    row = find_draft(db, user, environment, resource_id)
    return {"items": [serialize(item) for item in db.query(PowerVersion).filter_by(organization_id=row.organization_id, resource_id=row.id).order_by(PowerVersion.version.desc()).limit(100)]}

@router.delete("/automations/{resource_id}", status_code=204)
def delete_draft(resource_id: int, expected_version: int = Query(ge=1), environment: str = "development", db: Session = Depends(get_db), user=Depends(RequirePermission("power_apps_delete"))):
    row = find_draft(db, user, environment, resource_id)
    if row.status != "draft":
        raise HTTPException(409, "Only drafts can be deleted in Phase 2")
    # Lock plus optimistic version protects deletion against concurrent saves.
    row = scoped(db, PowerResource, user, environment).filter(PowerResource.id == row.id).with_for_update().populate_existing().first()
    if not row or row.version != expected_version:
        raise HTTPException(409, "Draft changed; reload before deleting")
    from app.apps.power_apps.runtime_models import AutomationDeployment, AutomationRun
    if db.query(AutomationDeployment).filter_by(resource_id=row.id).filter(AutomationDeployment.version_id.is_not(None)).first() or db.query(PowerExecution).filter_by(resource_id=row.id).first():
        raise HTTPException(409, "Published workflows and execution histories must be retained; archive instead")
    db.query(AutomationDeployment).filter_by(resource_id=row.id).delete()
    record_change(db, user, row, "draft_deleted", snapshot=False)
    db.query(PowerVersion).filter_by(organization_id=row.organization_id, resource_id=row.id).delete()
    db.delete(row)
    db.commit()

