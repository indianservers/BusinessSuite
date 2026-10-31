"""Scoped, audited people management and transactional assignment handovers."""
from datetime import date, datetime, timezone
import hashlib
import json
from types import SimpleNamespace
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import or_, select, func, inspect
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.models.audit import AuditLog
from app.models.employee import Employee
from app.models.notification import Notification
from app.common.models import CommonPerson
from .models import PMSWorkspace, PMSWorkspaceMember, PMSProject, PMSProjectMember, PMSTask, PMSWorkspaceInvitation, PMSClientApproval
from .access import organization_id_for
from .workspace_lifecycle import is_archived

router = APIRouter(prefix="/people-management", tags=["PMS people management"])
ADMIN_ROLES = {"admin", "super_admin", "hr", "hr_admin", "hr_company_admin", "pms_super_admin", "pms_org_admin"}
CLOSED = {"done", "completed", "closed", "resolved", "cancelled", "canceled", "rejected", "approved"}


def organization_admin(actor):
    """A company role is not authority over a different company or a narrowed grant."""
    if actor.is_superuser:
        return True
    role = actor.role.name.lower().replace(" ", "_") if actor.role else ""
    grants = getattr(actor, "_suite_grants", None)
    if grants is not None:
        grant = grants.get("project_management", {})
        if not grant.get("enabled") or grant.get("scope") not in {"all", "company", "organization"}:
            return False
        if not set(grant.get("actions", [])).intersection({"assign", "configure"}):
            return False
    return role in ADMIN_ROLES or bool(grants is not None and grant.get("role") in {"admin", "pms_org_admin", "pms_super_admin"} and "configure" in grant.get("actions", []))


def same_company(db, actor, target):
    from app.core.tenant_boundary import company_ids
    if target.person and target.person.organization_id == organization_id_for(actor):
        return True
    ids = company_ids(db, target) or {organization_id_for(target)}
    return organization_id_for(actor) in ids


def scoped_workspace(db, wid, actor, manage=True):
    workspace = db.get(PMSWorkspace, wid)
    if not workspace or is_archived(db, wid):
        raise HTTPException(404, "Workspace not found in your scope")
    member = db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, user_id=actor.id).first()
    if member and (not manage or member.role in {"Owner", "Admin"}):
        return workspace, member
    if organization_admin(actor) and workspace.organization_id == organization_id_for(actor):
        return workspace, SimpleNamespace(role="Admin", user_id=actor.id, source="organization role")
    raise HTTPException(403 if member else 404, "Workspace owner, admin, or authorized organization Admin/HR access is required")


def scoped_person(db, actor, uid, manage=False):
    target = db.query(User).filter_by(id=uid).first()
    if not target or not same_company(db, actor, target):
        raise HTTPException(404, "Person not found in your organization scope")
    if organization_admin(actor):
        return target
    actor_workspaces = db.query(PMSWorkspaceMember.workspace_id).filter_by(user_id=actor.id)
    shared = db.query(PMSWorkspaceMember).filter(PMSWorkspaceMember.user_id == uid, PMSWorkspaceMember.workspace_id.in_(actor_workspaces)).all()
    if manage:
        if not shared or not any(db.query(PMSWorkspaceMember).filter(PMSWorkspaceMember.workspace_id == m.workspace_id, PMSWorkspaceMember.user_id == actor.id, PMSWorkspaceMember.role.in_(["Owner", "Admin"])).first() for m in shared):
            raise HTTPException(403, "Managing this person requires a scoped workspace administrator")
    elif actor.id != uid and not shared:
        from .directory import can_explore_directory
        if not can_explore_directory(actor):
            raise HTTPException(403, "This person is outside your workspace scope")
    return target


def record(db, actor, target, action, reason, before=None, after=None, workspace_id=None, project_id=None):
    db.add(AuditLog(organization_id=organization_id_for(actor), user_id=actor.id, actor_email=actor.email,
        actor_authenticated=True, method="POST", module="project_management", entity_type="user", entity_id=target,
        action=action, description=reason, old_values=json.dumps(before, default=str) if before else None,
        new_values=json.dumps(after, default=str) if after else None, workspace_id=workspace_id, project_id=project_id, status_code=200))


def person_status(db, user):
    if user.is_active:
        return "active"
    latest = db.query(AuditLog).filter(AuditLog.entity_type == "user", AuditLog.entity_id == user.id,
        AuditLog.action.in_(["ACCOUNT_SUSPEND", "ACCOUNT_TERMINATE", "ACCOUNT_ACTIVATE"])).order_by(AuditLog.id.desc()).first()
    return "terminated" if (latest and latest.action == "ACCOUNT_TERMINATE") or (user.person and user.person.status == "terminated") else "suspended"


def scoped_reactivation(db, actor, target):
    if actor.is_superuser:
        return True
    latest = db.query(AuditLog).filter(AuditLog.entity_type == "user", AuditLog.entity_id == target.id,
        AuditLog.action.in_(["ACCOUNT_SUSPEND", "ACCOUNT_TERMINATE", "ACCOUNT_ACTIVATE"])).order_by(AuditLog.id.desc()).first()
    return bool(latest and latest.action == "ACCOUNT_SUSPEND" and latest.module == "project_management" and latest.organization_id == organization_id_for(actor))


def public_person(db, user):
    person = user.person
    profile = person.profile if person else None
    employee = getattr(user, "employee", None)
    data = (profile.profile_data_json or {}).get("profile", {}) if profile else {}
    return {"id": user.id, "user_id": user.id, "email": user.email,
        "name": person.display_name if person else user.email.split("@")[0],
        "photo_url": profile.profile_photo_url if profile and profile.directory_visibility == "public" else None,
        "role": "Super Admin" if user.is_superuser else user.role.name if user.role else "User",
        "status": person_status(db, user), "availability": "Unavailable" if not user.is_active else "On leave" if employee and (employee.status or "").lower() == "on leave" else "Available",
        "available_from": data.get("available_from"), "employment_status": employee.status if employee else None}


class Change(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("reason")
    @classmethod
    def reason_required(cls, value):
        if len(value.strip()) < 3:
            raise ValueError("Enter a meaningful reason")
        return value.strip()


class BulkAdd(Change):
    user_ids: list[int] = Field(min_length=1, max_length=100)
    workspace_ids: list[int] = Field(default_factory=list, max_length=30)
    project_ids: list[int] = Field(default_factory=list, max_length=100)
    role: Literal["Member", "Guest"] = "Member"


class PersonAction(Change):
    action: Literal["remove_project", "remove_workspace", "suspend", "reactivate", "offboard", "terminate"]
    workspace_id: int | None = Field(None, gt=0)
    project_id: int | None = Field(None, gt=0)
    replacement_user_id: int | None = Field(None, gt=0)
    end_at: datetime | None = None
    preview_version: str | None = Field(None, min_length=64, max_length=64)


class ProfileEdit(Change):
    values: dict = Field(default_factory=dict, max_length=12)
    version: str = Field(min_length=24, max_length=64)


PROFILE_FIELDS = {"first_name", "last_name", "preferred_display_name", "bio", "timezone", "phone_number", "phone_number_country_code"}


def safe_profile(db, actor, target):
    from app.common.services import profiles
    from app.apps.admin_security.services import field_rules, apply_field_security
    editable = profiles.authorized_user(db, actor, target.id, write=True)
    profile = profiles.serialize_profile(db, editable, actor)
    values = {k: v for k, v in profile["values"].items() if k in PROFILE_FIELDS}
    permissions = {k: {"can_view": True, "can_edit": bool(profile["canEdit"] and k not in profile["requiresApprovalFields"]), "reason": "Editable with your profile permission" if k not in profile["requiresApprovalFields"] else "This field requires HR approval; edit through the profile request flow"} for k in PROFILE_FIELDS}
    for module in ("employees", "hrms", "profiles"):
        values = apply_field_security(db, module, values, actor)
        for rule in field_rules(db, module, actor):
            if rule.field_name in permissions and (not rule.can_view or not rule.can_edit or rule.mask_value):
                permissions[rule.field_name] = {"can_view": bool(rule.can_view), "can_edit": False, "reason": "Restricted by field-level profile permissions"}
    return {"values": values, "version": profile["version"], "canEdit": profile["canEdit"], "field_permissions": permissions}


@router.patch("/{user_id}/profile")
def edit_profile(user_id: int, data: ProfileEdit, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    target = scoped_person(db, actor, user_id)
    profile = safe_profile(db, actor, target)
    if set(data.values) - PROFILE_FIELDS:
        raise HTTPException(403, "Use the appropriate account or HR flow for protected fields")
    if any(not profile["field_permissions"][field]["can_edit"] for field in data.values):
        raise HTTPException(403, "One or more fields are read-only with your current permissions")
    from app.common.services import profiles
    record(db, actor, target.id, "PMS_PROFILE_EDIT", data.reason, after={"fields": sorted(data.values)})
    profiles.update_profile(db, target, actor, data.values, data.version, data.reason)
    return {"message": "Authorized profile fields updated"}


@router.get("/options")
def options(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    workspaces = []
    for w in db.query(PMSWorkspace).filter_by(organization_id=organization_id_for(actor)).order_by(PMSWorkspace.name):
        try:
            _, member = scoped_workspace(db, w.id, actor)
            workspaces.append({"id": w.id, "name": w.name, "role": member.role, "can_appoint_admin": member.role == "Owner"})
        except HTTPException:
            continue
    ids = [w["id"] for w in workspaces]
    from .access import accessible_project_query, can_access_project
    projects = [{"id": p.id, "name": p.name, "project_key": p.project_key, "workspace_id": p.workspace_id} for p in accessible_project_query(db, actor).all()
                if p.workspace_id in ids or can_access_project(db, p, actor, "manage_members")]
    return {"workspaces": workspaces, "projects": projects, "organization_admin": organization_admin(actor)}


@router.get("/assignment-options")
def assignment_options(project_id: int, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    from .access import get_project_for_action, can_access_project
    project = get_project_for_action(db, project_id, actor)
    ids = db.query(PMSWorkspaceMember.user_id).filter(PMSWorkspaceMember.workspace_id == project.workspace_id, PMSWorkspaceMember.role != "Guest") if project.workspace_id else db.query(PMSProjectMember.user_id).filter_by(project_id=project.id)
    people = db.query(User).filter(User.is_active.is_(True), or_(User.id.in_(ids), User.id == project.manager_user_id)).order_by(User.email).all()
    return {"items": [public_person(db, user) for user in people], "workspace_id": project.workspace_id,
        "can_add_existing": can_access_project(db, project, actor, "manage_members"),
        "unavailable_reason": "Only a scoped organization Admin/HR or workspace/project administrator can add an existing person while assigning work"}


@router.get("/directory")
def directory(q: str = Query("", max_length=150), workspace_id: int | None = None, project_id: int | None = None,
              status: str = "", db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    allowed = organization_admin(actor)
    if workspace_id:
        scoped_workspace(db, workspace_id, actor, manage=False)
        allowed = True
    if project_id:
        from .access import get_project_for_action
        get_project_for_action(db, project_id, actor)
        allowed = True
    from .directory import can_explore_directory
    if not allowed and not can_explore_directory(actor):
        raise HTTPException(403, "Choose an accessible workspace or project to find people")
    items, counts = [], {key: 0 for key in ("active", "suspended", "terminated", "invited")}
    shared_ids = {m.user_id for m in db.query(PMSWorkspaceMember).filter_by(workspace_id=workspace_id)} if workspace_id and not organization_admin(actor) else None
    if workspace_id:
        try:
            scoped_workspace(db, workspace_id, actor, manage=True)
            shared_ids = None
        except HTTPException:
            pass
    if project_id and not organization_admin(actor):
        project = db.get(PMSProject, project_id)
        shared_ids = {m.user_id for m in db.query(PMSWorkspaceMember).filter_by(workspace_id=project.workspace_id)} if project.workspace_id else {m.user_id for m in db.query(PMSProjectMember).filter_by(project_id=project_id)}
        from .access import can_access_project
        if can_access_project(db, project, actor, "manage_members"):
            shared_ids = None
    users = db.query(User).options(joinedload(User.role), joinedload(User.person).joinedload(CommonPerson.profile))
    if hasattr(User, "employee"):
        users = users.options(joinedload(User.employee))
    for user in users.order_by(User.email):
        if not same_company(db, actor, user) or (shared_ids is not None and user.id not in shared_ids):
            continue
        item = public_person(db, user)
        counts[item["status"]] += 1
        if (not status or item["status"] == status) and (not q or q.casefold() in f'{item["name"]} {item["email"]} {item["role"]}'.casefold()):
            items.append(item)
    manageable = {w["id"] for w in options(db, actor)["workspaces"]}
    pending = db.query(PMSWorkspaceInvitation, PMSWorkspace.name).join(PMSWorkspace, PMSWorkspace.id == PMSWorkspaceInvitation.workspace_id).filter(
        PMSWorkspaceInvitation.workspace_id.in_(manageable), PMSWorkspaceInvitation.status == "pending", PMSWorkspaceInvitation.expires_at > datetime.utcnow())
    if workspace_id:
        pending = pending.filter(PMSWorkspaceInvitation.workspace_id == workspace_id)
    invitations = [{"id": i.id, "email": i.email, "name": i.email, "status": "invited", "role": i.role, "workspace": name, "workspace_id": i.workspace_id} for i, name in pending]
    counts["invited"] = len(invitations)
    if status == "invited":
        items = [i for i in invitations if not q or q.casefold() in i["email"].casefold()]
    return {"items": items, "counts": counts, "total": len(items)}


@router.post("/memberships/bulk")
def bulk_add(data: BulkAdd, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    if not data.workspace_ids and not data.project_ids:
        raise HTTPException(422, "Choose at least one workspace or project")
    if len(set(data.user_ids)) * (len(set(data.workspace_ids)) + len(set(data.project_ids))) > 500:
        raise HTTPException(422, "Select at most 500 person/destination combinations")
    workspaces = {wid: scoped_workspace(db, wid, actor)[0] for wid in sorted(set(data.workspace_ids))}
    from .access import get_project_for_action
    projects = [get_project_for_action(db, pid, actor, "manage_members") for pid in sorted(set(data.project_ids))]
    for p in projects:
        if p.organization_id != organization_id_for(actor):
            raise HTTPException(403, "All destinations must belong to the selected organization")
        if p.workspace_id and p.workspace_id not in workspaces:
            workspaces[p.workspace_id] = scoped_workspace(db, p.workspace_id, actor)[0]
    if data.role == "Guest" and projects:
        raise HTTPException(422, "Project collaborators need Member access to the workspace")
    users = []
    for uid in sorted(set(data.user_ids)):
        target = db.query(User).filter_by(id=uid).with_for_update().first()
        if not target or not target.is_active or not same_company(db, actor, target):
            raise HTTPException(404, "An eligible active person was not found in your assigned scope")
        # Scope-filtered user lookups and destination checks complete before any mutation.
        users.append(target)
    added, existing, membership_results = [], 0, []
    for target in users:
        for wid, workspace in workspaces.items():
            member = db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, user_id=target.id).first()
            membership_results.append({"user_id": target.id, "email": target.email, "destination_type": "workspace", "destination_name": workspace.name, "status": "already_present" if member else "added"})
            if member:
                if projects and member.role == "Guest" and any(p.workspace_id == wid for p in projects):
                    raise HTTPException(409, f"{target.email} is a guest in {workspace.name}. Review and upgrade their workspace role first.")
                existing += 1
            else:
                db.add(PMSWorkspaceMember(workspace_id=wid, user_id=target.id, role=data.role))
                db.query(PMSWorkspaceInvitation).filter_by(workspace_id=wid, email=target.email.lower(), status="pending").update({"status": "accepted"})
                record(db, actor, target.id, "PMS_WORKSPACE_ADDED", data.reason, after={"workspace": workspace.name, "role": data.role}, workspace_id=wid)
                added.append({"user_id": target.id, "workspace_id": wid})
        for project in projects:
            present = db.query(PMSProjectMember).filter_by(project_id=project.id, user_id=target.id).first()
            membership_results.append({"user_id": target.id, "email": target.email, "destination_type": "project", "destination_name": project.name, "status": "already_present" if present else "added"})
            if present:
                existing += 1
                continue
            db.add(PMSProjectMember(project_id=project.id, user_id=target.id, role="Member"))
            record(db, actor, target.id, "PMS_PROJECT_ADDED", data.reason, after={"project": project.name, "role": "Member"}, project_id=project.id, workspace_id=project.workspace_id)
            added.append({"user_id": target.id, "project_id": project.id})
        db.add(Notification(user_id=target.id, title="Team membership updated", message="You were added to workspaces or project teams. No invitation approval is needed.", module="project_management", event_type="people.membership_added", action_url="/pms/members"))
    from app.access.service import policy_for, resolved_grants
    warnings = []
    for target in users:
        policy = policy_for(db, target, organization_id_for(actor))
        if policy and (policy.status != "active" or not resolved_grants(db, policy).get("project_management", {}).get("enabled")):
            warnings.append(f"{target.email}: membership is saved, but the organization access policy does not currently enable PMS. An authorized access administrator must enable that module; this action does not override policy.")
    db.commit()
    return {"added": added, "already_present": existing, "warnings": warnings, "results": membership_results, "message": "People added directly; no invitation approval required"}


def _impact(db, actor, target, workspace_id=None, project_id=None):
    from .access import accessible_project_query, can_access_project
    query = accessible_project_query(db, actor)
    if db.info.get("security_write_request"):
        query = query.with_for_update(of=PMSProject)
    if workspace_id:
        scoped_workspace(db, workspace_id, actor)
        query = query.filter(PMSProject.workspace_id == workspace_id)
    if project_id:
        query = query.filter(PMSProject.id == project_id)
    projects = query.order_by(PMSProject.id).all()
    manageable = [p for p in projects if can_access_project(db, p, actor, "manage_members")]
    ids = [p.id for p in manageable]
    tasks = [t for t in db.query(PMSTask).options(selectinload(PMSTask.assignments)).filter(PMSTask.project_id.in_(ids), PMSTask.deleted_at.is_(None), or_(PMSTask.assignee_user_id == target.id, PMSTask.assignments.any(user_id=target.id))).order_by(PMSTask.id).all()
             if target.id in t.assignee_user_ids and (t.status or "").lower() not in CLOSED]
    owned = [p for p in manageable if target.id in {p.owner_user_id, p.manager_user_id}]
    from app.models.approval_os import ApprovalRequest
    from app.models.workflow_engine import WorkflowTask, WorkflowInstance
    approvals, workflows = [], []
    if organization_admin(actor) and not workspace_id and not project_id:
        approvals = db.query(ApprovalRequest).filter(ApprovalRequest.organization_id == organization_id_for(actor),
            or_(ApprovalRequest.assigned_to_user_id == target.id, ApprovalRequest.delegated_to_user_id == target.id)).order_by(ApprovalRequest.id).all()
        approvals = [a for a in approvals if (a.status or "").lower() not in CLOSED]
        workflows = db.query(WorkflowTask).join(WorkflowInstance, WorkflowInstance.id == WorkflowTask.instance_id).filter(WorkflowInstance.organization_id == organization_id_for(actor),
            or_(WorkflowTask.assigned_to_user_id == target.id, WorkflowTask.delegated_to_user_id == target.id)).order_by(WorkflowTask.id).all()
        workflows = [a for a in workflows if (a.status or "").lower() not in CLOSED]
    client_approvals = db.query(PMSClientApproval).filter(PMSClientApproval.project_id.in_(ids), PMSClientApproval.client_user_id == target.id, func.lower(PMSClientApproval.status).notin_(CLOSED)).order_by(PMSClientApproval.id).all()
    return tasks, owned, approvals, workflows, client_approvals


def preview_data(db, actor, target, workspace_id=None, project_id=None):
    tasks, owned, approvals, workflows, client_approvals = _impact(db, actor, target, workspace_id, project_id)
    memberships = db.query(PMSWorkspaceMember).filter_by(user_id=target.id).all()
    owner_workspaces = [m.workspace_id for m in memberships if m.role == "Owner" and (not workspace_id or m.workspace_id == workspace_id)] if not project_id else []
    values = {"user_id": target.id, "organization_id": organization_id_for(actor), "tasks": [{"id": t.id, "title": t.title, "project_id": t.project_id, "assignees": t.assignee_user_ids} for t in tasks],
        "projects": [{"id": p.id, "name": p.name, "owner_user_id": p.owner_user_id, "manager_user_id": p.manager_user_id} for p in owned],
        "approvals": [{"id": a.id, "title": a.title, "assigned_to_user_id": a.assigned_to_user_id, "delegated_to_user_id": a.delegated_to_user_id} for a in approvals] + [{"id": a.id, "title": f"Project client approval #{a.id}", "kind": "client_approval", "client_user_id": a.client_user_id} for a in client_approvals],
        "workflow_approvals": [{"id": w.id, "status": w.status, "assigned_to_user_id": w.assigned_to_user_id, "delegated_to_user_id": w.delegated_to_user_id} for w in workflows],
        "owned_workspace_ids": sorted(owner_workspaces), "account_active": target.is_active}
    values["blockers"] = [f"{t.task_key}: transfer its batch-controlled assignment in Batch controls first" for t in tasks if any(a.user_id == target.id and a.source_key for a in t.assignments)]
    if not workspace_id and not project_id and organization_admin(actor):
        # Only counts cross module boundaries: do not expose records the actor cannot read.
        from app.models.approval_os import ApprovalRequest
        table = ApprovalRequest.__table__
        expected = db.connection().execute(select(func.count()).select_from(table).where(table.c.organization_id == organization_id_for(actor),
            or_(table.c.assigned_to_user_id == target.id, table.c.delegated_to_user_id == target.id), func.lower(table.c.status).notin_(CLOSED))).scalar_one()
        if expected > len(approvals):
            values["blockers"].append("Pending approvals exist outside your assigned approval scope. An authorized approval administrator must transfer them first.")
        from app.apps.power_apps.approvals.models import Assignment
        if inspect(db.bind).has_table(Assignment.__tablename__):
            power = Assignment.__table__
            count = db.connection().execute(select(func.count()).select_from(power).where(power.c.user_id == target.id, power.c.status == "pending")).scalar_one()
            if count:
                values["blockers"].append(f"{count} policy-controlled Power Apps approval assignment(s) must be delegated in Approval OS first to preserve independent approval seats.")
        task_table, project_table = PMSTask.__table__, PMSProject.__table__
        from .models import PMSTaskAssignee
        assignments = PMSTaskAssignee.__table__
        other = db.connection().execute(select(func.count()).select_from(task_table.join(project_table, project_table.c.id == task_table.c.project_id)).where(
            project_table.c.organization_id != organization_id_for(actor), task_table.c.deleted_at.is_(None), func.lower(task_table.c.status).notin_(CLOSED),
            or_(task_table.c.assignee_user_id == target.id, task_table.c.id.in_(select(assignments.c.task_id).where(assignments.c.user_id == target.id))))).scalar_one()
        if other:
            values["blockers"].append("Open tasks exist in another organization. Complete that organization's handover before changing the account status.")
    values["version"] = hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()
    return values


@router.get("/{user_id}/preview")
def preview(user_id: int, workspace_id: int | None = None, project_id: int | None = None, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    target = scoped_person(db, actor, user_id, manage=True)
    return preview_data(db, actor, target, workspace_id, project_id)


@router.get("/{user_id}")
def person_detail(user_id: int, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    target = scoped_person(db, actor, user_id)
    destinations = options(db, actor)
    visible_workspaces = {w[0] for w in db.query(PMSWorkspace.id).filter_by(organization_id=organization_id_for(actor))} if organization_admin(actor) else {m[0] for m in db.query(PMSWorkspaceMember.workspace_id).filter_by(user_id=actor.id)}
    memberships = [{"id": m.id, "workspace_id": w.id, "name": w.name, "role": m.role, "source": "Workspace membership"}
        for m, w in db.query(PMSWorkspaceMember, PMSWorkspace).join(PMSWorkspace, PMSWorkspace.id == PMSWorkspaceMember.workspace_id).filter(PMSWorkspaceMember.user_id == target.id, PMSWorkspace.id.in_(visible_workspaces)).all()]
    from .access import accessible_project_query
    accessible = {p.id for p in accessible_project_query(db, actor).all()}
    project_memberships = [{"id": m.id, "project_id": p.id, "workspace_id": p.workspace_id, "name": p.name, "role": m.role, "source": "Project role"}
        for m, p in db.query(PMSProjectMember, PMSProject).join(PMSProject, PMSProject.id == PMSProjectMember.project_id).filter(PMSProjectMember.user_id == target.id, PMSProject.id.in_(accessible)).all()]
    admin = organization_admin(actor)
    lifecycle = admin and target.id != actor.id and not target.is_superuser
    from app.core.tenant_boundary import company_ids
    if not actor.is_superuser and len(company_ids(db, target)) > 1:
        lifecycle = False
    profile = None
    try:
        from app.common.services import profiles
        editable = profiles.authorized_user(db, actor, target.id, write=True)
        profile = safe_profile(db, actor, editable)
    except HTTPException:
        pass
    history = db.query(AuditLog).filter(AuditLog.entity_type == "user", AuditLog.entity_id == target.id,
        AuditLog.organization_id == organization_id_for(actor), or_(AuditLog.action.like("PMS_%"), AuditLog.action.like("ACCOUNT_%"), AuditLog.action.like("PROFILE_%"))).order_by(AuditLog.id.desc()).limit(100).all()
    if not admin:
        manageable_wids = {w["id"] for w in destinations["workspaces"]}
        history = [h for h in history if h.workspace_id in manageable_wids or h.project_id in accessible]
    can_members = bool(destinations["workspaces"] or destinations["projects"])
    by_workspace = {w["id"]: w for w in destinations["workspaces"]}
    for membership in memberships:
        destination = by_workspace.get(membership["workspace_id"])
        membership["can_remove"] = bool(destination and membership["role"] != "Owner" and (membership["role"] != "Admin" or destination["role"] == "Owner" or actor.is_superuser))
        membership["unavailable_reason"] = "Transfer workspace ownership first." if membership["role"] == "Owner" else "Only the workspace owner or a Super Admin can remove workspace administrators." if membership["role"] == "Admin" else "A scoped workspace administrator is required."
    from .access import can_access_project
    for membership in project_memberships:
        membership["can_remove"] = can_access_project(db, db.get(PMSProject, membership["project_id"]), actor, "manage_members")
        membership["unavailable_reason"] = "A scoped project or workspace administrator must manage this project team."
    metadata = (target.person.external_refs_json or {}).get("pms_suspension", {}) if target.person else {}
    from app.access.service import policy_for, resolved_grants
    policy = policy_for(db, target, organization_id_for(actor))
    grant = resolved_grants(db, policy).get("project_management", {}) if policy else {}
    organization_source = {"source": "Organization role", "role": "Super Admin" if target.is_superuser else target.role.name if target.role else "User",
        "explanation": "Organization permissions are limited by the assigned company and scope.",
        "scope": grant.get("scope", "organization role scope"), "policy_status": policy.status if policy else "Legacy role permissions", "module_enabled": grant.get("enabled") if policy else None,
        "capabilities": ["All organization permissions"] if target.is_superuser else grant.get("permissions", [p.name for p in target.role.permissions] if target.role else [])}
    for membership in memberships:
        membership["capabilities"] = ["View workspace projects"] + (["Create and update tasks", "Comment and upload files"] if membership["role"] != "Guest" else []) + (["Manage people and projects"] if membership["role"] in {"Admin", "Owner"} else []) + (["Appoint workspace admins"] if membership["role"] == "Owner" else [])
    from .access import ROLE_PERMISSIONS
    effective = target.is_active and (not policy or policy.status == "active" and grant.get("enabled"))
    workspace_roles = {m["workspace_id"]: m["role"] for m in memberships}
    all_actions = sorted(set().union(*ROLE_PERMISSIONS.values()))
    for membership in project_memberships:
        workspace_role = workspace_roles.get(membership["workspace_id"])
        capabilities = all_actions if workspace_role in {"Owner", "Admin"} else ["browse", "manage_tasks", "comment", "upload", "log_time"] if workspace_role == "Member" else ["browse"] if workspace_role == "Guest" else sorted(ROLE_PERMISSIONS.get(membership["role"], set())) if not membership["workspace_id"] else []
        membership["capabilities"] = capabilities if effective else []
        membership["explanation"] = "Workspace membership determines access to shared workspace projects; the project role records team responsibility." if membership["workspace_id"] else "Project-role permissions apply within the organization's assigned scope."
    if not effective:
        for membership in memberships:
            membership["capabilities"] = []
            membership["explanation"] = "Stored membership is retained, but the account or PMS organization policy currently blocks access."
    db.commit()
    return {**public_person(db, target), "workspaces": memberships, "projects": project_memberships,
        "access_sources": [organization_source] + memberships + project_memberships,
        "permissions": {"memberships": can_members, "profile": bool(profile and profile.get("canEdit")), "suspend": lifecycle, "reactivate": lifecycle and person_status(db, target) != "terminated" and scoped_reactivation(db, actor, target), "offboard": lifecycle, "terminate": lifecycle and bool(getattr(target, "employee", None))},
        "unavailable_reasons": {"memberships": "A scoped workspace or organization administrator is required.", "profile": "Profile fields require HR profile-edit permission within the person's assigned scope.", "reactivate": "A Super Admin must reactivate an account disabled outside this organization's scoped PMS lifecycle.", "terminate": "Employment termination requires an authorized Admin/HR role and a linked HR employee record.", "lifecycle": "Only authorized organization Admin/HR roles can change another non-Super-Admin account. Accounts spanning organizations require a Super Admin."},
        "profile": profile, "suspension": metadata if not target.is_active else None,
        "history": [{"id": h.id, "action": h.action, "reason": h.description, "actor": h.actor_email, "created_at": h.created_at, "workspace_id": h.workspace_id, "project_id": h.project_id} for h in history]}


@router.post("/{user_id}/actions")
def apply_action(user_id: int, data: PersonAction, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    target = scoped_person(db, actor, user_id, manage=True)
    target = db.query(User).filter_by(id=target.id).with_for_update().populate_existing().one()
    account_action = data.action in {"suspend", "reactivate", "offboard", "terminate"}
    if account_action:
        from app.core.tenant_boundary import company_ids
        if not organization_admin(actor) or target.id == actor.id or target.is_superuser:
            raise HTTPException(403, "A scoped organization Admin/HR must manage another non-Super-Admin account")
        if not actor.is_superuser and len(company_ids(db, target)) > 1:
            raise HTTPException(403, "This account spans organizations. A Super Admin must manage its account status.")
    if data.action == "reactivate":
        if not scoped_reactivation(db, actor, target):
            raise HTTPException(403, "A Super Admin must reactivate an account disabled outside this organization's scoped PMS lifecycle")
        if person_status(db, target) == "terminated":
            raise HTTPException(409, "Terminated employment requires a separate HR rehire process")
        target.is_active = True
        if target.person:
            target.person.status = "active"
            target.person.external_refs_json = {**(target.person.external_refs_json or {}), "pms_suspension": None}
        record(db, actor, target.id, "ACCOUNT_ACTIVATE", data.reason)
        db.commit()
        return {"message": "Account reactivated. The person can sign in again."}
    if data.action in {"suspend", "offboard"} and not target.is_active:
        raise HTTPException(409, "This account is already inactive. Review its existing suspension and use an authorized reactivation or employment-termination flow.")
    if data.action in {"remove_workspace", "remove_project"}:
        if data.action == "remove_workspace" and not data.workspace_id or data.action == "remove_project" and not data.project_id:
            raise HTTPException(422, "Choose the workspace or project to remove")
        if data.action == "remove_workspace":
            scoped_workspace(db, data.workspace_id, actor)
        else:
            from .access import get_project_for_action
            get_project_for_action(db, data.project_id, actor, "manage_members")
    workspace_id = data.workspace_id if data.action == "remove_workspace" else None
    project_id = data.project_id if data.action == "remove_project" else None
    current = preview_data(db, actor, target, workspace_id, project_id)
    if not data.preview_version or data.preview_version != current["version"]:
        raise HTTPException(409, "Assignments changed or no preview was reviewed. Refresh the affected-assignment preview before applying.")
    if current["blockers"]:
        raise HTTPException(409, "Resolve the batch-controlled assignments shown in the preview before applying this change")
    if current["owned_workspace_ids"] and data.action in {"remove_workspace", "offboard", "terminate"}:
        raise HTTPException(409, "Transfer workspace ownership with the workspace owner before removing or offboarding this person")
    tasks, projects, approvals, workflows, client_approvals = _impact(db, actor, target, workspace_id, project_id)
    needs_handover = bool(tasks or projects or approvals or workflows or client_approvals)
    replacement = None
    if data.replacement_user_id:
        replacement = scoped_person(db, actor, data.replacement_user_id)
        if not replacement.is_active or replacement.id == target.id:
            raise HTTPException(422, "Choose a different active person for handover")
    if needs_handover and not replacement:
        raise HTTPException(422, "Choose a replacement for open tasks, project ownership, and pending approvals")
    # Validate every replacement before changing any assignment.
    for pid in {t.project_id for t in tasks} | {p.id for p in projects} | {a.project_id for a in client_approvals}:
        project = db.get(PMSProject, pid)
        if project.workspace_id:
            member = db.query(PMSWorkspaceMember).filter_by(workspace_id=project.workspace_id, user_id=replacement.id).first()
            if not member or member.role == "Guest":
                raise HTTPException(422, f"Add the replacement to the workspace of {project.name} as a Member before handover")
        elif not db.query(PMSProjectMember).filter_by(project_id=pid, user_id=replacement.id).first():
            raise HTTPException(422, f"Add the replacement to {project.name} before handover")
    if replacement:
        from .access import can_access_project
        if any(not can_access_project(db, project, replacement, "manage_members") for project in projects):
            raise HTTPException(422, "Project ownership must transfer to an authorized workspace Admin or project manager")
        if (approvals or workflows) and not organization_admin(replacement):
            raise HTTPException(422, "Pending approvals must transfer to an authorized organization Admin/HR approver")
        if any(not can_access_project(db, db.get(PMSProject, approval.project_id), replacement, "approve") for approval in client_approvals):
            raise HTTPException(422, "Project client approvals must transfer to a person authorized to approve that project")
    from app.models.approval_os import ApprovalHistory
    from app.models.workflow_engine import WorkflowAuditEvent
    for task in tasks:
        new_assignees = list(dict.fromkeys(replacement.id if uid == target.id else uid for uid in task.assignee_user_ids))
        task.assignee_user_ids = new_assignees
        task.assignee_user_id = new_assignees[0] if new_assignees else None
    for project in projects:
        if project.owner_user_id == target.id:
            project.owner_user_id = replacement.id
        if project.manager_user_id == target.id:
            project.manager_user_id = replacement.id
    for approval in approvals:
        if approval.assigned_to_user_id == target.id:
            approval.assigned_to_user_id = replacement.id
        if approval.delegated_to_user_id == target.id:
            approval.delegated_to_user_id = replacement.id
        db.add(ApprovalHistory(request_id=approval.id, event_type="offboarding_transfer", actor_user_id=actor.id, reason=data.reason, details_json={"from_user_id":target.id,"to_user_id":replacement.id}))
    for workflow in workflows:
        if workflow.assigned_to_user_id == target.id:
            workflow.assigned_to_user_id = replacement.id
        if workflow.delegated_to_user_id == target.id:
            workflow.delegated_to_user_id = replacement.id
        db.add(WorkflowAuditEvent(instance_id=workflow.instance_id, task_id=workflow.id, event_type="offboarding_transfer", actor_user_id=actor.id, reason=data.reason, details_json={"from_user_id":target.id,"to_user_id":replacement.id}))
    for approval in client_approvals:
        approval.client_user_id = replacement.id
    if data.action == "remove_project":
        member = db.query(PMSProjectMember).filter_by(project_id=project_id, user_id=target.id).first()
        if not member:
            raise HTTPException(404, "Project membership not found")
        db.delete(member)
    if data.action == "remove_workspace":
        from .workspaces import editable_member
        member = db.query(PMSWorkspaceMember).filter_by(workspace_id=workspace_id, user_id=target.id).first()
        if not member:
            raise HTTPException(404, "Workspace membership not found")
        editable_member(db, workspace_id, member.id, actor)
        pids = [p[0] for p in db.query(PMSProject.id).filter_by(workspace_id=workspace_id)]
        db.query(PMSProjectMember).filter(PMSProjectMember.user_id == target.id, PMSProjectMember.project_id.in_(pids)).delete(synchronize_session=False)
        db.delete(member)
    if data.action in {"offboard", "terminate"}:
        scoped_workspaces = [w.id for w in db.query(PMSWorkspace).filter_by(organization_id=organization_id_for(actor))]
        db.query(PMSWorkspaceMember).filter(PMSWorkspaceMember.user_id == target.id, PMSWorkspaceMember.workspace_id.in_(scoped_workspaces)).delete(synchronize_session=False)
        scoped_projects = [p.id for p in db.query(PMSProject).filter_by(organization_id=organization_id_for(actor))]
        db.query(PMSProjectMember).filter(PMSProjectMember.user_id == target.id, PMSProjectMember.project_id.in_(scoped_projects)).delete(synchronize_session=False)
    if data.action in {"suspend", "offboard", "terminate"}:
        from app.common.services.identity import SharedIdentityService
        person = target.person or SharedIdentityService.ensure_person_for_user(db, target, organization_id=organization_id_for(actor))
        person.status = "terminated" if data.action == "terminate" else "suspended"
        until = data.end_at
        if until and (until.replace(tzinfo=timezone.utc) if until.tzinfo is None else until) <= datetime.now(timezone.utc):
            raise HTTPException(422, "The suspension end date must be in the future")
        if data.action != "suspend" and until:
            raise HTTPException(422, "Only temporary suspension has an end date")
        person.external_refs_json = {**(person.external_refs_json or {}), "pms_suspension": {"reason": data.reason, "end_at": until.isoformat() if until else None, "actor_id": actor.id}}
        target.is_active = False
        if data.action == "terminate":
            employee = getattr(target, "employee", None)
            if not employee:
                raise HTTPException(422, "This person has no employment record to terminate")
            employee.status = "Terminated"
            employee.date_of_exit = date.today()
        from app.api.v1.auth import _revoke_user_sessions
        _revoke_user_sessions(db, target.id)
        target.password_reset_token = None
        target.password_reset_expires = None
    result = {"action": data.action, "tasks_transferred": len(tasks), "projects_transferred": len(projects), "approvals_transferred": len(approvals) + len(workflows) + len(client_approvals), "replacement_user_id": replacement.id if replacement else None, "end_at": data.end_at.isoformat() if data.end_at else None}
    record(db, actor, target.id, "ACCOUNT_TERMINATE" if data.action == "terminate" else "ACCOUNT_SUSPEND" if data.action in {"suspend", "offboard"} else "PMS_" + data.action.upper(), data.reason, before=current, after=result, workspace_id=workspace_id, project_id=project_id)
    db.commit()
    # Existing sessions cannot retain cached project-room access after removal/offboarding.
    from .realtime import pms_realtime_manager
    import anyio
    affected = {p[0] for p in db.query(PMSProject.id).filter_by(organization_id=organization_id_for(actor))}
    anyio.from_thread.run(pms_realtime_manager.revoke_projects, target.id, affected)
    return {"message": "Change applied with assignment handover and audit history", **result}


def restore_due_suspension(db, user):
    """Lazy, clock-based reactivation at fresh authentication; revoked sessions stay revoked."""
    if user.is_active or not user.person or user.person.status != "suspended":
        return False
    user = db.query(User).filter_by(id=user.id).with_for_update().populate_existing().one()
    db.refresh(user.person)
    if user.is_active or user.person.status != "suspended":
        return False
    metadata = (user.person.external_refs_json or {}).get("pms_suspension") or {}
    if not metadata.get("end_at"):
        return False
    latest = db.query(AuditLog).filter(AuditLog.entity_type == "user", AuditLog.entity_id == user.id, AuditLog.action.in_(["ACCOUNT_SUSPEND", "ACCOUNT_TERMINATE", "ACCOUNT_ACTIVATE"])).order_by(AuditLog.id.desc()).first()
    if not latest or latest.action != "ACCOUNT_SUSPEND" or (json.loads(latest.new_values or "{}")).get("end_at") != metadata["end_at"]:
        return False
    until = datetime.fromisoformat(metadata["end_at"])
    until = until.replace(tzinfo=timezone.utc) if until.tzinfo is None else until
    if until > datetime.now(timezone.utc):
        return False
    user.is_active = True
    user.person.status = "active"
    user.person.external_refs_json = {**user.person.external_refs_json, "pms_suspension": None}
    db.add(AuditLog(organization_id=user.person.organization_id, method="POST", entity_type="user", entity_id=user.id, action="ACCOUNT_ACTIVATE", actor_email="System", description="Temporary suspension ended; reactivated during fresh sign-in", status_code=200))
    db.commit()
    return True
