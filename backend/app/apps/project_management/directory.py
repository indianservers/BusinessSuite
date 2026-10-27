"""Shared account directory, independent of employee and workspace enrollment."""
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from app.core.deps import get_current_user, get_db
from app.models.user import User
from .models import PMSWorkspace, PMSWorkspaceMember, PMSWorkspaceTeam

router = APIRouter()
DIRECTORY_ROLES = {"super_admin", "admin", "hr", "hr_admin", "hr_manager", "hr_company_admin", "hr_workflow_admin", "hr_custom_field_admin", "manager", "team_lead", "department_head", "ceo", "founder", "director", "executive", "pms_org_admin"}


def can_explore_directory(user):
    role = (getattr(getattr(user, "role", None), "name", "") or "").lower().replace(" ", "_")
    return bool(user.is_superuser or role in DIRECTORY_ROLES)


@router.get("/people-directory")
def people_directory(db: Session = Depends(get_db), user: User = Depends(get_current_user),
                     page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=200)):
    if not can_explore_directory(user):
        raise HTTPException(403, "Organization directory requires an administrator, HR or executive role")
    # The authenticated session's company boundary applies to every ORM query.
    # Superusers retain their existing installation-wide visibility.
    query = db.query(User).options(joinedload(User.role), joinedload(User.person)).order_by(User.email, User.id)
    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()
    ids = [item.id for item in users]
    memberships = db.query(PMSWorkspaceMember).filter(PMSWorkspaceMember.user_id.in_(ids)).all() if ids else []
    workspaces = db.query(PMSWorkspace).order_by(PMSWorkspace.name).all()
    workspace_ids = {item.id for item in workspaces}
    teams = db.query(PMSWorkspaceTeam).filter(PMSWorkspaceTeam.workspace_id.in_(workspace_ids)).order_by(PMSWorkspaceTeam.name).all() if workspace_ids else []
    eligible = {(item.workspace_id, item.user_id) for item in db.query(PMSWorkspaceMember).filter(PMSWorkspaceMember.workspace_id.in_(workspace_ids)).all() if item.role != "Guest"} if workspace_ids else set()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [{"id": item.id, "email": item.email,
                       "name": item.person.display_name if item.person else item.email.split("@")[0],
                       "role": "Super Admin" if item.is_superuser else item.role.name if item.role else "User",
                       "is_active": item.is_active,
                       "workspace_ids": [m.workspace_id for m in memberships if m.user_id == item.id and m.workspace_id in workspace_ids]}
                      for item in users],
            "workspaces": [{"id": item.id, "name": item.name} for item in workspaces],
            "teams": [{"id": item.id, "name": item.name, "workspace_id": item.workspace_id,
                       "member_ids": [uid for uid in json.loads(item.member_ids_json) if (item.workspace_id, uid) in eligible]} for item in teams]}
