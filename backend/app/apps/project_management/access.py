"""Access helpers for KaryaFlow project permissions."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.apps.project_management.models import PMSProject, PMSProjectMember, PMSTask
from app.models.user import User


PMS_GLOBAL_VIEW = {"pms_view", "pms_manage_projects", "pms_manage_tasks", "pms_time_manage", "pms_admin"}
PMS_GLOBAL_MANAGE_PROJECTS = {"pms_manage_projects", "pms_admin"}
PMS_GLOBAL_MANAGE_TASKS = {"pms_manage_tasks", "pms_manage_projects", "pms_admin"}
PMS_GLOBAL_TIME = {"pms_time_manage", "pms_manage_projects", "pms_admin"}
PMS_GLOBAL_CLIENT = {"pms_client_portal", "pms_manage_projects", "pms_admin"}

ROLE_PERMISSIONS = {
    "Admin": {"browse", "edit_project", "administer", "manage_members", "manage_tasks", "comment", "upload", "log_time", "approve"},
    "Project Admin": {"browse", "edit_project", "administer", "manage_members", "manage_tasks", "comment", "upload", "log_time", "approve"},
    "Manager": {"browse", "edit_project", "manage_members", "manage_tasks", "comment", "upload", "log_time", "approve"},
    "Project Manager": {"browse", "edit_project", "manage_members", "manage_tasks", "comment", "upload", "log_time", "approve"},
    "Lead": {"browse", "manage_tasks", "comment", "upload", "log_time", "approve"},
    "Member": {"browse", "manage_tasks", "comment", "upload", "log_time"},
    "Team Member": {"browse", "manage_tasks", "comment", "upload", "log_time"},
    "Viewer": {"browse"},
    "Client Viewer": {"browse_client", "comment_client", "approve"},
    "Client": {"browse_client", "comment_client", "approve"},
}

ACTION_GLOBAL_PERMISSIONS = {
    "browse": PMS_GLOBAL_VIEW,
    "create_project": PMS_GLOBAL_MANAGE_PROJECTS,
    "edit_project": PMS_GLOBAL_MANAGE_PROJECTS,
    "manage_members": PMS_GLOBAL_MANAGE_PROJECTS,
    "manage_tasks": PMS_GLOBAL_MANAGE_TASKS,
    "comment": PMS_GLOBAL_MANAGE_TASKS,
    "upload": PMS_GLOBAL_MANAGE_TASKS,
    "log_time": PMS_GLOBAL_TIME,
    "approve": PMS_GLOBAL_CLIENT,
}


def organization_id_for(user: User) -> int | None:
    return getattr(user, "organization_id", None)


def user_permission_names(user: User) -> set[str]:
    if user.is_superuser:
        return {"*"}
    return {permission.name for permission in (user.role.permissions if user.role else [])}


def has_any_permission(user: User, permissions: set[str]) -> bool:
    names = user_permission_names(user)
    return "*" in names or bool(names.intersection(permissions))


def same_organization(project: PMSProject, user: User) -> bool:
    user_org_id = organization_id_for(user)
    return project.organization_id == user_org_id


def project_member(db: Session, project_id: int, user_id: int) -> PMSProjectMember | None:
    return db.query(PMSProjectMember).filter(
        PMSProjectMember.project_id == project_id,
        PMSProjectMember.user_id == user_id,
    ).first()


def can_access_project(db: Session, project: PMSProject, user: User, action: str = "browse") -> bool:
    if user.is_superuser:
        return True

    global_permissions = ACTION_GLOBAL_PERMISSIONS.get(action, PMS_GLOBAL_VIEW)
    if same_organization(project, user) and has_any_permission(user, global_permissions):
        return True

    if project.manager_user_id == user.id and action != "browse_client":
        return True

    employee = getattr(user, "employee", None)
    if action == "browse" and employee:
        if project.department_id and project.department_id == getattr(employee, "department_id", None):
            return True
        if project.branch_id and project.branch_id == getattr(employee, "branch_id", None):
            return True

    member = project_member(db, project.id, user.id)
    if not member:
        return False

    allowed = ROLE_PERMISSIONS.get(member.role, set())
    if action in allowed:
        return True

    if action == "browse" and "browse_client" in allowed and project.is_client_visible:
        return True
    if action == "comment" and "comment_client" in allowed and project.is_client_visible:
        return True
    return False


def accessible_project_query(db: Session, user: User):
    query = db.query(PMSProject).filter(PMSProject.deleted_at == None)
    if user.is_superuser:
        return query

    if has_any_permission(user, PMS_GLOBAL_VIEW):
        return query.filter(PMSProject.organization_id == organization_id_for(user))

    member_project_ids = db.query(PMSProjectMember.project_id).filter(PMSProjectMember.user_id == user.id)
    visibility_filter = (PMSProject.manager_user_id == user.id) | (PMSProject.owner_user_id == user.id) | (PMSProject.id.in_(member_project_ids))
    employee = getattr(user, "employee", None)
    if employee:
        if getattr(employee, "department_id", None):
            visibility_filter = visibility_filter | (PMSProject.department_id == employee.department_id)
        if getattr(employee, "branch_id", None):
            visibility_filter = visibility_filter | (PMSProject.branch_id == employee.branch_id)
    return query.filter(visibility_filter)


def get_project_for_action(db: Session, project_id: int, user: User, action: str = "browse") -> PMSProject:
    project = db.query(PMSProject).filter(
        PMSProject.id == project_id,
        PMSProject.deleted_at == None,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not can_access_project(db, project, user, action):
        raise HTTPException(status_code=403, detail="Project access denied")
    return project


def get_task_project_for_action(db: Session, task_id: int, user: User, action: str = "browse") -> tuple[PMSTask, PMSProject]:
    task = db.query(PMSTask).filter(PMSTask.id == task_id, PMSTask.deleted_at == None).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    project = get_project_for_action(db, task.project_id, user, action)
    return task, project
