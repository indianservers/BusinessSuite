"""Workspace configuration over ServicePolicy; PMS keeps its original entities.

Only navigation/configuration is shared. All record reads, posting rules, HR
visibility, and module mutations remain in their original domain endpoints.
"""
from copy import deepcopy
import json
from datetime import datetime, timezone
from uuid import uuid4
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, false
from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.models.audit import AuditLog
from app.shared.models import ServicePolicy
from app.branches.service import access, company_administrator
from app.apps.srm.services.commercial import tenant
from app.core.tenant_boundary import company_ids
from sqlalchemy.exc import IntegrityError
from .domains import DOMAINS

COLORS = ("#7632ff", "#1671ff", "#168354", "#bd6500", "#c82f79", "#008596")
ICONS = ("layers", "folder", "team", "sales", "customers", "finance", "operations", "technology", "documents", "analytics")
KIND = "module_workspace"

class Member(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(gt=0)
    role: Literal["Admin", "Member", "Guest"] = "Member"

class WorkspaceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=2000)
    icon: Literal["layers", "folder", "team", "sales", "customers", "finance", "operations", "technology", "documents", "analytics"] = "layers"
    color: Literal["#7632ff", "#1671ff", "#168354", "#bd6500", "#c82f79", "#008596"] = "#7632ff"
    visibility: Literal["private", "organization"] = "private"
    views: list[str] = Field(default_factory=list, max_length=12)
    members: list[Member] = Field(default_factory=list, max_length=100)
    expected_version: int | None = Field(default=None, ge=0)
    expected_status: Literal["Active", "Archived"] | None = None
    status: Literal["Active", "Archived"] = "Active"

    @model_validator(mode="after")
    def distinct(self):
        if len(set(self.views)) != len(self.views) or len({m.user_id for m in self.members}) != len(self.members):
            raise ValueError("Choose distinct views and members")
        return self


def context(db, actor, write=False):
    company, branch = tenant(actor), getattr(actor, "_suite_branch_id", None)
    if branch is None:
        raise HTTPException(422, "Select a branch to manage workspaces")
    allowed, writable, all_access, _ = access(db, actor, company)
    if branch == "all":
        if write:
            raise HTTPException(422, "Select a branch to manage workspaces")
        if not all_access:
            raise HTTPException(403, "All-branches access is required")
        return company, None
    if int(branch) not in (writable if write else allowed):
        raise HTTPException(403, "Branch access is required")
    return company, int(branch)


def prefix(domain, company, branch):
    return f"workspace:{domain.module}:{company}:{branch}:"


def policies(db, domain, company, branch):
    if branch is None:
        branches = db.info.get("branch_context")
        allowed = branches.allowed if branches else ()
        return db.query(ServicePolicy).filter(ServicePolicy.organization_id == company, ServicePolicy.module_key == domain.permission_module,
            ServicePolicy.kind == KIND, or_(false(), *(ServicePolicy.scope_key.like(prefix(domain, company, ident) + "%") for ident in allowed)))
    return db.query(ServicePolicy).filter(ServicePolicy.organization_id == company, ServicePolicy.module_key == domain.permission_module,
        ServicePolicy.kind == KIND, ServicePolicy.scope_key.like(prefix(domain, company, branch) + "%"))


def role_for(data, actor):
    if data.get("owner_id") == actor.id:
        return "Owner"
    return next((m["role"] for m in data.get("members", []) if m["user_id"] == actor.id), None)


def pms_access(db, actor, wid, manage=False, archived=False):
    from app.apps.project_management.workspace_directory import workspace_access
    return workspace_access(db, actor, wid, manage)


def visible(domain, actor, data, company_admin=False):
    return data.get("visibility") == "organization" or role_for(data, actor) is not None or domain.administrator(actor) or company_admin


def get_policy(db, domain, actor, ref, write=False):
    company, branch = context(db, actor, write)
    if len(ref) > 64: raise HTTPException(404, "Workspace not found")
    query = policies(db, domain, company, branch)
    row = query.filter(ServicePolicy.scope_key.endswith(":" + ref, autoescape=True) if branch is None else ServicePolicy.scope_key == prefix(domain, company, branch) + ref).with_for_update().first()
    if domain.module == "pms":
        if not ref.isdigit(): raise HTTPException(404, "Workspace not found")
        pms_access(db, actor, int(ref), write)
    elif row is None or not visible(domain, actor, row.values_json, company_administrator(db, actor, company)):
        raise HTTPException(404, "Workspace not found")
    if write and domain.module != "pms" and role_for(row.values_json, actor) not in {"Owner", "Admin"} and not domain.administrator(actor) and not company_administrator(db, actor, company):
        raise HTTPException(403, "Workspace management access is required")
    return row, company, branch


def audit(db, domain, actor, row, action, before=None):
    db.add(AuditLog(organization_id=tenant(actor), user_id=actor.id, actor_email=actor.email, actor_authenticated=True,
        method="POST", module=domain.permission_module, entity_type="module_workspace", entity_id=row.id,
        action=action, old_values=json.dumps(before) if before else None, new_values=json.dumps({**row.values_json, "version": row.version}), description=f"{action.replace('_', ' ').capitalize()}: {row.values_json['name']}", status_code=200))


def validate_members(db, actor, members, company, branch):
    for member in members:
        target = db.query(User).filter_by(id=member.user_id, is_active=True).first()
        if target is None or company not in company_ids(db, target) or branch not in access(db, target, company)[0]:
            raise HTTPException(422, "Members must be active users of this company and branch")


def output(domain, actor, row, base=None, company_admin=False):
    data = deepcopy(row.values_json) if row else {}
    result = {**(base or {}), **data, "id": row.scope_key.rsplit(":", 1)[1] if row else str(base["id"]),
        "version": row.version if row else 0, "updated_at": row.updated_at if row else (base or {}).get("created_at"),
        "can_manage": (base or {}).get("role") in {"Owner", "Admin"} if domain.module == "pms" else role_for(data, actor) in {"Owner", "Admin"} or domain.administrator(actor),
        "can_archive": domain.administrator(actor) if domain.module == "pms" else role_for(data, actor) in {"Owner", "Admin"} or domain.administrator(actor)}
    result.setdefault("status", "Active")
    if company_admin:
        result["can_manage"] = result["can_archive"] = True
    result.setdefault("description", "")
    result.setdefault("icon", "layers")
    result.setdefault("color", COLORS[0])
    result.setdefault("views", list(domain.views))
    result.setdefault("visibility", "private")
    if domain.module == "pms" and base:
        result["name"] = base["name"]
        result["status"] = base.get("status", "Active")
        result["owner_id"] = base.get("owner_id")
    if domain.module != "pms":
        result["role"] = role_for(data, actor) or ("Admin" if domain.administrator(actor) else "Guest")
        result["member_count"] = len(data.get("members", [])) + 1
    for field in ("created_at", "updated_at"):
        value = result.get(field)
        if isinstance(value, datetime): result[field] = (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).isoformat()
    return result


def listing(db, domain, actor):
    domain.authorize(actor)
    company, branch = context(db, actor)
    company_admin = company_administrator(db, actor, company)
    rows = policies(db, domain, company, branch).all()
    metadata = {r.scope_key.rsplit(":", 1)[1]: r for r in rows}
    if domain.module != "pms":
        items = [output(domain, actor, r, company_admin=company_admin) for r in rows if visible(domain, actor, r.values_json, company_admin)]
    else:
        from app.apps.project_management.workspace_directory import base_workspaces
        items = [output(domain, actor, metadata.get(str(base["id"])), base) for base in base_workspaces(db, actor)]
    refs = {item["id"] for item in items}
    row_ids = [r.id for r in rows if r.scope_key.rsplit(":", 1)[1] in refs]
    counts = dict(db.query(AuditLog.entity_id, func.count(AuditLog.id)).filter(AuditLog.organization_id == company, AuditLog.module == domain.permission_module, AuditLog.entity_type == "module_workspace", AuditLog.entity_id.in_(row_ids)).group_by(AuditLog.entity_id).all()) if row_ids else {}
    owner_ids = {item.get("owner_id") for item in items if item.get("owner_id")}
    owner_ids.update(member["user_id"] for item in items for member in item.get("members", []))
    emails = dict(db.query(User.id, User.email).filter(User.id.in_(owner_ids)).all()) if owner_ids else {}
    for item in items:
        item["activity_count"] = counts.get(metadata[item["id"]].id, 0) if item["id"] in metadata else 0
        item["member_details"] = [{**member, "email": emails.get(member["user_id"])} for member in item.get("members", [])]
        if not item.get("owners") and item.get("owner_id") in emails: item["owners"] = [emails[item["owner_id"]]]
    try: domain.authorize(actor, True); can_create = True
    except HTTPException: can_create = False
    writable = branch in access(db, actor, company)[1]
    can_create = can_create and writable
    for item in items:
        item["can_manage"] = item["can_manage"] and writable
        item["can_archive"] = item["can_archive"] and writable
    from app.models.company import Branch
    branch_name = db.query(Branch.name).filter_by(id=branch, company_id=company).scalar() if branch is not None else "All branches"
    return {"items": items, "can_create": can_create, "views": list(domain.views), "module": domain.module, "branch_id": branch, "branch_name": branch_name}


def _save(db, domain, actor, data, ref=None):
    creating = ref is None
    domain.authorize(actor, creating)
    company, branch = context(db, actor, True)
    if any(view not in domain.views for view in data.views):
        raise HTTPException(422, "A selected view does not belong to this module")
    if ref is None and data.status != "Active": raise HTTPException(422, "New workspaces must be active")
    row = None
    if ref is not None:
        row, _, _ = get_policy(db, domain, actor, ref, True)
        if data.expected_version != (row.version if row else 0):
            raise HTTPException(409, "Workspace changed. Reload its settings before saving.")
    elif data.expected_version is not None:
        raise HTTPException(422, "Creation does not accept a version")
    before = deepcopy(row.values_json) if row else {}
    if domain.module != "pms" and role_for(before, actor) == "Admin" and not domain.administrator(actor):
        old_admins = {member["user_id"] for member in before.get("members", []) if member["role"] == "Admin"}
        new_admins = {member.user_id for member in data.members if member.role == "Admin"}
        if old_admins != new_admins:
            raise HTTPException(403, "Only the workspace owner or module administrator can change administrator roles")
    previous_status = before.get("status", "Active")
    if ref is not None and domain.module != "pms" and data.expected_status is not None and data.expected_status != previous_status:
        raise HTTPException(409, "Workspace archive state changed. Reload its settings.")
    validate_members(db, actor, data.members, company, branch)
    now = datetime.now(timezone.utc).isoformat()
    pms_created = None
    if domain.module == "pms":
        from app.apps.project_management.workspace_directory import persist
        ref, owner_id, previous_status, pms_created = persist(db, actor, data, ref)
    else:
        ref = ref or uuid4().hex
        owner_id = before.get("owner_id", actor.id)
        if any(m.user_id == owner_id for m in data.members): raise HTTPException(422, "The owner is already a member")
    if row is None:
        row = ServicePolicy(scope_key=prefix(domain, company, branch) + ref, organization_id=company, module_key=domain.permission_module, kind=KIND, updated_by=actor.id, values_json={})
        db.add(row)
    else: row.version += 1
    row.values_json = {**data.model_dump(exclude={"expected_version", "expected_status"}), "owner_id": owner_id,
        "created_at": before.get("created_at") or pms_created or now, "updated_at": now, "branch_id": branch}
    row.updated_by = actor.id
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Workspace changed. Reload before saving.") from exc
    action = "workspace_created" if creating else "workspace_archived" if previous_status != data.status and data.status == "Archived" else "workspace_restored" if previous_status == "Archived" and data.status == "Active" else "workspace_updated"
    audit(db, domain, actor, row, action, before)
    db.commit()
    return next(item for item in listing(db, domain, actor)["items"] if item["id"] == ref)


def save(db, domain, actor, data, ref=None):
    try:
        return _save(db, domain, actor, data, ref)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Workspace changed. Reload before saving.") from exc
    except HTTPException:
        db.rollback()
        raise


def ordered_activity(events):
    for event in events:
        value = event.get("created_at")
        if isinstance(value, datetime): event["created_at"] = (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).isoformat()
    return sorted(events, key=lambda event: event.get("created_at") or "", reverse=True)[:30]


def router_for(domain):
    child = APIRouter(prefix=f"/{domain.api}/workspace-directory", tags=[f"{domain.module.upper()} workspaces"])
    @child.get("")
    def list_items(db: Session = Depends(get_db), actor=Depends(get_current_user)):
        return listing(db, domain, actor)
    @child.post("", status_code=201)
    def create_item(data: WorkspaceInput, db: Session = Depends(get_db), actor=Depends(get_current_user)):
        return save(db, domain, actor, data)
    @child.put("/{ref}")
    def update_item(ref: str, data: WorkspaceInput, db: Session = Depends(get_db), actor=Depends(get_current_user)):
        return save(db, domain, actor, data, ref)
    @child.get("/eligible-people")
    def eligible(db: Session = Depends(get_db), actor=Depends(get_current_user), q: str = Query("", max_length=100), ref: str | None = None):
        domain.authorize(actor, ref is None)
        if ref is not None: get_policy(db, domain, actor, ref, True)
        company, branch = context(db, actor)
        from app.branches.models import BranchGrant, BranchPolicy
        from app.models.employee import Employee
        candidates = {uid for uid, in db.query(BranchGrant.user_id).filter_by(company_id=company, branch_id=branch).all()}
        candidates.update(uid for uid, in db.query(BranchPolicy.user_id).filter_by(company_id=company, all_branches=True).all())
        no_home = {uid for uid, in db.query(BranchPolicy.user_id).filter_by(company_id=company, use_home_branch=False).all()}
        candidates.update(uid for uid, in db.query(Employee.user_id).filter(Employee.branch_id == branch, Employee.deleted_at.is_(None), Employee.user_id.is_not(None)).all() if uid not in no_home)
        candidates.update(uid for uid, in db.query(User.id).filter(User.is_superuser.is_(True)).all())
        users = db.query(User).filter(User.is_active.is_(True), User.id.in_(candidates))
        if q.strip(): users = users.filter(User.email.icontains(q.strip(), autoescape=True))
        return [{"user_id": u.id, "email": u.email} for u in users.order_by(User.email).all() if company in company_ids(db, u)]
    @child.get("/activity")
    def recent_activity(db: Session = Depends(get_db), actor=Depends(get_current_user)):
        visible_items = listing(db, domain, actor)["items"]
        allowed = {item["id"] for item in visible_items}
        company, branch = context(db, actor)
        ids = [r.id for r in policies(db, domain, company, branch).all() if r.scope_key.rsplit(":", 1)[1] in allowed]
        rows = db.query(AuditLog).filter(AuditLog.organization_id == company, AuditLog.module == domain.permission_module, AuditLog.entity_type == "module_workspace", AuditLog.entity_id.in_(ids)).order_by(AuditLog.id.desc()).limit(20).all() if ids else []
        events = [{"id": f"config:{r.id}", "summary": r.description, "actor": r.actor_email, "created_at": r.created_at} for r in rows]
        if domain.module == "pms":
            from app.apps.project_management.workspace_directory import native_activity
            events += native_activity(db, actor, allowed)
        return ordered_activity(events)
    @child.get("/{ref}/activity")
    def activity(ref: str, db: Session = Depends(get_db), actor=Depends(get_current_user)):
        domain.authorize(actor)
        row, company, _ = get_policy(db, domain, actor, ref)
        rows = db.query(AuditLog).filter_by(organization_id=company, module=domain.permission_module, entity_type="module_workspace", entity_id=row.id if row else -1).order_by(AuditLog.id.desc()).limit(30).all()
        events = [{"id": f"config:{r.id}", "summary": r.description, "actor": r.actor_email, "created_at": r.created_at} for r in rows]
        if domain.module == "pms":
            from app.apps.project_management.workspace_directory import native_activity
            events += native_activity(db, actor, {ref})
        return ordered_activity(events)
    @child.get("/{ref}")
    def detail(ref: str, db: Session = Depends(get_db), actor=Depends(get_current_user)):
        domain.authorize(actor)
        get_policy(db, domain, actor, ref)
        result = next((item for item in listing(db, domain, actor)["items"] if item["id"] == ref), None)
        if result is None: raise HTTPException(404, "Workspace not found")
        return result
    return child

router = APIRouter()
for domain in DOMAINS.values():
    from app.access.catalog import register_routes
    child = router_for(domain)
    register_routes(child, f"app.apps.{domain.permission_module}.workspace_management", domain.permission_module)
    router.include_router(child)
