"""SQL equivalents of native project/task browse checks for bounded feeds.

Returned task pages are still checked by scoped_task; shared role constants and
parity tests keep aggregate counts consistent with the native authorizer.
"""
from sqlalchemy import and_, or_, false, select
from .models import PMSProject, PMSProjectMember, PMSWorkspaceMember, PMSTask, PMSTaskAssignee
from .access import (accessible_project_query, module_identity_allowed, organization_id_for,
                     has_any_permission, ACTION_GLOBAL_PERMISSIONS, PMS_GLOBAL_VIEW, ROLE_PERMISSIONS)


def project_action_query(db, user, action='browse'):
    query = accessible_project_query(db, user)
    if not module_identity_allowed(db, user, organization_id_for(user)):
        return query.filter(false())
    from .people_management import organization_admin
    workspace_roles = ['Owner', 'Admin', 'Member', 'Guest'] if action == 'browse' else ['Owner', 'Admin', 'Member'] if action == 'comment' else ['Owner', 'Admin']
    memberships = select(PMSWorkspaceMember.workspace_id).where(PMSWorkspaceMember.user_id == user.id, PMSWorkspaceMember.role.in_(workspace_roles))
    workspace = PMSProject.workspace_id.in_(memberships)
    if organization_admin(user):
        workspace = or_(workspace, PMSProject.organization_id == organization_id_for(user))
    if user.is_superuser or has_any_permission(user, ACTION_GLOBAL_PERMISSIONS.get(action, PMS_GLOBAL_VIEW)):
        legacy = True
    else:
        roles = [role for role, actions in ROLE_PERMISSIONS.items() if action in actions]
        member = PMSProject.id.in_(select(PMSProjectMember.project_id).where(PMSProjectMember.user_id == user.id, PMSProjectMember.role.in_(roles)))
        legacy = or_(PMSProject.manager_user_id == user.id, member)
        if action in ('browse', 'comment'):
            client_roles = [role for role, actions in ROLE_PERMISSIONS.items() if ('browse_client' if action == 'browse' else 'comment_client') in actions]
            legacy = or_(legacy, and_(PMSProject.is_client_visible.is_(True), PMSProject.id.in_(select(PMSProjectMember.project_id).where(PMSProjectMember.user_id == user.id, PMSProjectMember.role.in_(client_roles)))))
        employee = getattr(user, 'employee', None)
        if action == 'browse' and employee:
            if employee.department_id:
                legacy = or_(legacy, PMSProject.department_id == employee.department_id)
            if employee.branch_id:
                legacy = or_(legacy, PMSProject.branch_id == employee.branch_id)
    return query.filter(or_(and_(PMSProject.workspace_id.is_(None), legacy), and_(PMSProject.workspace_id.is_not(None), workspace)))


def visible_task_query(db, user):
    query = db.query(PMSTask).filter(PMSTask.deleted_at.is_(None), PMSTask.project_id.in_(project_action_query(db, user).with_entities(PMSProject.id)))
    employee = getattr(user, 'employee', None)
    intern = (user.role and user.role.name.lower() == 'intern') or (employee and (employee.employment_type or '').lower() == 'intern')
    if not intern:
        return query
    from .models import PMSTaskGroupTarget, PMSWorkspaceTeamMember
    from app.apps.interns_hub.management_models import InternBatchMembership
    from app.models.employee import Employee
    team_ids = select(PMSWorkspaceTeamMember.team_id).where(PMSWorkspaceTeamMember.user_id == user.id)
    team_tasks = select(PMSTaskGroupTarget.task_id).where(PMSTaskGroupTarget.kind == 'teams', PMSTaskGroupTarget.target_id.in_(team_ids))
    membership, person = InternBatchMembership.__table__, Employee.__table__
    batches = select(membership.c.batch_id).join(person, person.c.id == membership.c.employee_id).where(membership.c.status == 'Active', person.c.user_id == user.id, person.c.deleted_at.is_(None), person.c.status.notin_(['Inactive', 'Terminated', 'Suspended']))
    batch_tasks = select(PMSTaskGroupTarget.task_id).where(PMSTaskGroupTarget.kind == 'batches', PMSTaskGroupTarget.target_id.in_(batches))
    responsibility = or_(PMSTask.assignee_user_id == user.id,
        PMSTask.id.in_(select(PMSTaskAssignee.task_id).where(PMSTaskAssignee.user_id == user.id)),
        PMSTask.project_id.in_(select(PMSProject.id).where(or_(PMSProject.owner_user_id == user.id, PMSProject.manager_user_id == user.id))),
        PMSTask.project_id.in_(project_action_query(db, user, 'approve').with_entities(PMSProject.id)),
        PMSTask.id.in_(team_tasks), PMSTask.id.in_(batch_tasks))
    return query.filter(PMSTask.project_id.in_(project_action_query(db, user, 'comment').with_entities(PMSProject.id)), responsibility)
