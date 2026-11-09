"""PMS adapter: preserve native workspace, membership, archive and activity rules."""
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import func
from app.core.deps import RequirePermission
from app.apps.srm.services.commercial import tenant
from .models import PMSWorkspace, PMSWorkspaceMember, PMSProject, PMSActivity
from .workspace_lifecycle import WorkspaceArchive, archived_ids
from .people_management import organization_admin


def workspace_access(db, actor, wid, manage=False):
    workspace = db.query(PMSWorkspace).filter_by(id=wid, organization_id=tenant(actor)).first()
    member = db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, user_id=actor.id).first()
    if not workspace or not (member or organization_admin(actor)):
        raise HTTPException(404, "Workspace not found")
    if manage and not (member and member.role in {"Owner", "Admin"} or organization_admin(actor)):
        raise HTTPException(403, "Workspace management access is required")
    return workspace, member.role if member else "Admin"


def base_workspaces(db, actor):
    from .workspaces import list_workspaces
    from app.models.user import User
    active = [{**item, "status": "Active"} for item in list_workspaces(db, actor)]
    memberships = {member.workspace_id: member.role for member in db.query(PMSWorkspaceMember).filter_by(user_id=actor.id).all()}
    archived = db.query(PMSWorkspace).filter(PMSWorkspace.organization_id == tenant(actor), PMSWorkspace.id.in_(archived_ids())).all()
    archived = [workspace for workspace in archived if workspace.id in memberships or organization_admin(actor)]
    ids = [workspace.id for workspace in archived]
    counts = dict(db.query(PMSWorkspaceMember.workspace_id, func.count(PMSWorkspaceMember.id)).filter(PMSWorkspaceMember.workspace_id.in_(ids)).group_by(PMSWorkspaceMember.workspace_id).all()) if ids else {}
    owners = {}
    for wid, email in (db.query(PMSWorkspaceMember.workspace_id, User.email).join(User, User.id == PMSWorkspaceMember.user_id).filter(PMSWorkspaceMember.workspace_id.in_(ids), PMSWorkspaceMember.role == "Owner").all() if ids else []):
        owners.setdefault(wid, []).append(email)
    result = active + [{"id": workspace.id, "name": workspace.name, "role": memberships.get(workspace.id, "Admin"), "owners": owners.get(workspace.id, []), "member_count": counts.get(workspace.id, 0), "created_at": workspace.created_at, "status": "Archived"} for workspace in archived]
    all_ids = [item["id"] for item in result]
    owner_ids = dict(db.query(PMSWorkspaceMember.workspace_id, PMSWorkspaceMember.user_id).filter(PMSWorkspaceMember.workspace_id.in_(all_ids), PMSWorkspaceMember.role == "Owner").all()) if all_ids else {}
    for item in result: item["owner_id"] = owner_ids.get(item["id"])
    return result


def persist(db, actor, data, ref):
    if data.visibility != "private":
        raise HTTPException(422, "PMS access is controlled by workspace membership")
    if data.members:
        raise HTTPException(422, "Use existing PMS member management")
    marker = db.get(WorkspaceArchive, int(ref)) if ref else None
    current_status = "Archived" if marker and marker.deleted_at else "Active"
    if data.expected_status is not None and data.expected_status != current_status:
        raise HTTPException(409, "Workspace archive state changed. Reload its settings.")
    if current_status != data.status:
        RequirePermission("pms_admin")(actor)
    if ref is None:
        workspace = PMSWorkspace(organization_id=tenant(actor), name=data.name)
        db.add(workspace); db.flush()
        ref = str(workspace.id)
        db.add(PMSWorkspaceMember(workspace_id=workspace.id, user_id=actor.id, role="Owner")); db.flush()
    else:
        workspace, _ = workspace_access(db, actor, int(ref), True)
        workspace.name = data.name
    if current_status != data.status:
        if marker is None:
            marker = WorkspaceArchive(workspace_id=int(ref), deleted_by=actor.id, batch_key=uuid4().hex)
            db.add(marker)
        marker.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None) if data.status == "Archived" else None
        marker.deleted_by = actor.id
        marker.restored_at = datetime.now(timezone.utc).replace(tzinfo=None) if data.status == "Active" else None
    owner = db.query(PMSWorkspaceMember).filter_by(workspace_id=int(ref), role="Owner").first()
    created = workspace.created_at.replace(tzinfo=timezone.utc).isoformat() if workspace.created_at else None
    return ref, owner.user_id if owner else actor.id, current_status, created


def native_activity(db, actor, refs):
    """Match native workspace activity's Owner/Admin requirement and ORM scope."""
    from app.models.user import User
    query = db.query(PMSWorkspace.id).filter(PMSWorkspace.organization_id == tenant(actor), PMSWorkspace.id.in_([int(ref) for ref in refs if str(ref).isdigit()]), PMSWorkspace.id.notin_(archived_ids()))
    if not organization_admin(actor):
        query = query.join(PMSWorkspaceMember, PMSWorkspaceMember.workspace_id == PMSWorkspace.id).filter(PMSWorkspaceMember.user_id == actor.id, PMSWorkspaceMember.role.in_(["Owner", "Admin"]))
    ids = [wid for wid, in query.all()]
    if not ids: return []
    rows = db.query(PMSActivity, User.email).join(PMSProject, PMSProject.id == PMSActivity.project_id).outerjoin(User, User.id == PMSActivity.actor_user_id).filter(PMSProject.workspace_id.in_(ids)).order_by(PMSActivity.id.desc()).limit(20).all()
    return [{"id": f"pms:{event.id}", "summary": event.summary, "actor": email or "System", "created_at": event.created_at} for event, email in rows]
