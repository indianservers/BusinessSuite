"""Permission-aware, paginated public people workspace. No HR documents are exposed."""

import csv
import io
import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_, exists, select, func, cast, String, case
from sqlalchemy.orm import Session, joinedload
from app.core.deps import get_db, get_current_user
from app.models.user import User, Role
from app.models.employee import Employee
from app.models.company import Branch, Department, Company
from app.models.audit import AuditLog
from app.common.models import CommonPerson, CommonProfile
from app.access.models import AccessMembership
from .models import (
    PMSWorkspace,
    PMSWorkspaceMember,
    PMSProject,
    PMSProjectMember,
    PMSWorkspaceTeam,
    PMSWorkspaceTeamMember,
    PMSTask,
    PMSTaskAssignee,
    PMSWorkSubmission,
    PMSWorkReview,
    PMSActivity,
    PMSSavedFilter,
)
from .access import (
    organization_id_for,
    accessible_project_query,
    can_access_project,
    has_any_permission,
)
from .people_management import organization_admin, scoped_workspace, public_person
from .directory import can_explore_directory
from .schemas import PMSTaskCreate

router = APIRouter(prefix="/people-workspace", tags=["PMS People Workspace"])


class Filters(BaseModel):
    q: str = Field("", max_length=150)
    status: str = ""
    role: str = ""
    workspace_id: int | None = None
    team_id: int | None = None
    batch_id: int | None = None
    department_id: int | None = None
    skill: str = Field("", max_length=80)
    kind: Literal["all", "interns", "employees", "team_members", "batched"] = "all"
    membership: Literal["", "member", "unassigned"] = ""
    registered_from: date | None = None
    registered_to: date | None = None
    sort: Literal["name", "email", "newest", "oldest", "status"] = "name"


def filters(
    q: str = Query("", max_length=150),
    status: str = "",
    role: str = "",
    workspace_id: int | None = None,
    team_id: int | None = None,
    batch_id: int | None = None,
    department_id: int | None = None,
    skill: str = Query("", max_length=80),
    kind: Literal["all", "interns", "employees", "team_members", "batched"] = "all",
    membership: Literal["", "member", "unassigned"] = "",
    registered_from: date | None = None,
    registered_to: date | None = None,
    sort: Literal["name", "email", "newest", "oldest", "status"] = "name",
):
    return Filters(**locals())


def workspace_query(db, user):
    from .workspace_lifecycle import archived_ids

    q = db.query(PMSWorkspace).filter(
        PMSWorkspace.organization_id == organization_id_for(user),
        PMSWorkspace.id.notin_(archived_ids()),
    )
    if not organization_admin(user):
        q = q.filter(
            PMSWorkspace.id.in_(
                db.query(PMSWorkspaceMember.workspace_id).filter_by(user_id=user.id)
            )
        )
    return q


def scope(db, user):
    from app.services.metrics.queries import registered_users
    q=(db.query(User).outerjoin(CommonPerson,CommonPerson.user_id==User.id).outerjoin(Employee,Employee.user_id==User.id).outerjoin(Branch,Branch.id==Employee.branch_id).outerjoin(Role,Role.id==User.role_id).outerjoin(CommonProfile,CommonProfile.person_id==CommonPerson.id).filter(User.id.in_(registered_users(db,user).with_entities(User.id))))
    grants = getattr(user, "_suite_grants", None)
    grant = (grants or {}).get("project_management", {})
    level = grant.get("scope", "")
    if grants is not None and level in {"own", "self"}:
        return q.filter(User.id == user.id)
    if grants is not None and level in {"department", "branch"}:
        employee = getattr(user, "employee", None)
        column = Employee.department_id if level == "department" else Employee.branch_id
        identity = getattr(employee, level + "_id", None)
        return q.filter(
            or_(
                User.id == user.id,
                column == identity if identity else User.id == user.id,
            )
        )
    if organization_admin(user) or (
        can_explore_directory(user)
        and (grants is None or level in {"all", "company", "organization"})
    ):
        return q
    workspaces = workspace_query(db, user).with_entities(PMSWorkspace.id)
    projects = accessible_project_query(db, user).with_entities(PMSProject.id)
    collaborators = db.query(PMSWorkspaceMember.user_id).filter(
        PMSWorkspaceMember.workspace_id.in_(workspaces)
    )
    project_people = db.query(PMSProjectMember.user_id).filter(
        PMSProjectMember.project_id.in_(projects)
    )
    return q.filter(
        or_(User.id == user.id, User.id.in_(collaborators), User.id.in_(project_people))
    )


def teams_query(db, user):
    q = db.query(PMSWorkspaceTeam).filter(
        PMSWorkspaceTeam.workspace_id.in_(
            workspace_query(db, user).with_entities(PMSWorkspace.id)
        )
    )
    if not organization_admin(user):
        own = db.query(PMSWorkspaceTeamMember.team_id).filter_by(user_id=user.id)
        managed = db.query(PMSWorkspaceMember.workspace_id).filter(
            PMSWorkspaceMember.user_id == user.id,
            PMSWorkspaceMember.role.in_(["Owner", "Admin"]),
        )
        q = q.filter(
            or_(
                PMSWorkspaceTeam.visibility == "workspace",
                PMSWorkspaceTeam.lead_user_id == user.id,
                PMSWorkspaceTeam.id.in_(own),
                PMSWorkspaceTeam.workspace_id.in_(managed),
            )
        )
    return q


def batches_query(db, user):
    from app.apps.interns_hub.management_access import require_admin, batch_query
    from app.apps.interns_hub.management_models import InternBatch

    try:
        require_admin(user)
    except HTTPException:
        return db.query(InternBatch).filter(InternBatch.id == -1)
    q = batch_query(db, user)
    grants = getattr(user, "_suite_grants", None)
    if grants is not None and not organization_admin(user):
        e = getattr(user, "employee", None)
        scope = (grants.get("project_management") or {}).get("scope", "")
        own = or_(
            InternBatch.manager_user_id == user.id,
            InternBatch.mentor_user_id == user.id,
            InternBatch.coordinator_user_id == user.id,
        )
        if scope == "department" and e and e.department_id:
            q = q.filter(or_(own, InternBatch.department_id == e.department_id))
        else:
            q = q.filter(own)
    return q


def batch_users(db, user, batch_id=None):
    from app.apps.interns_hub.management_models import (
        InternBatch,
        InternBatchMembership,
    )

    ids = batches_query(db, user).with_entities(InternBatch.id)
    q = (
        db.query(Employee.user_id)
        .join(InternBatchMembership, InternBatchMembership.employee_id == Employee.id)
        .filter(
            InternBatchMembership.batch_id.in_(ids),
            InternBatchMembership.status == "Active",
            Employee.deleted_at.is_(None),
        )
    )
    if batch_id:
        q = q.filter(InternBatchMembership.batch_id == batch_id)
    return q


def query_people(db, user, f):
    q = scope(db, user)
    wids = workspace_query(db, user).with_entities(PMSWorkspace.id)
    tids = teams_query(db, user).with_entities(PMSWorkspaceTeam.id)
    if f.workspace_id:
        if (
            not workspace_query(db, user)
            .filter(PMSWorkspace.id == f.workspace_id)
            .first()
        ):
            raise HTTPException(404, "Workspace is outside your accessible scope")
        q = q.filter(
            User.id.in_(
                db.query(PMSWorkspaceMember.user_id).filter_by(
                    workspace_id=f.workspace_id
                )
            )
        )
    if f.team_id:
        if not teams_query(db, user).filter(PMSWorkspaceTeam.id == f.team_id).first():
            raise HTTPException(404, "Team is outside your accessible scope")
        q = q.filter(
            User.id.in_(
                db.query(PMSWorkspaceTeamMember.user_id).filter_by(team_id=f.team_id)
            )
        )
    if f.batch_id:
        from app.apps.interns_hub.management_models import InternBatch

        if not batches_query(db, user).filter(InternBatch.id == f.batch_id).first():
            raise HTTPException(404, "Batch is outside your management scope")
        q = q.filter(User.id.in_(batch_users(db, user, f.batch_id)))
    if f.status == "active":
        q = q.filter(User.is_active.is_(True))
    elif f.status == "inactive":
        q = q.filter(User.is_active.is_(False))
    elif f.status in {"suspended", "terminated"}:
        q = q.filter(User.is_active.is_(False), CommonPerson.status == f.status)
    elif f.status:
        raise HTTPException(422, "Unknown people status")
    if f.role == "superuser":
        q = q.filter(User.is_superuser.is_(True))
    elif f.role:
        q = q.filter(Role.name == f.role)
    if f.department_id:
        q = q.filter(Employee.department_id == f.department_id)
    public = or_(CommonProfile.directory_visibility == "public", User.id == user.id)
    if f.skill:
        q = q.filter(
            public, cast(CommonProfile.skills_json, String).ilike("%" + f.skill + "%")
        )
    intern = or_(
        func.lower(Employee.employment_type) == "intern",
        func.lower(Role.name) == "intern",
    )
    if f.kind == "interns":
        q = q.filter(intern)
    if f.kind == "employees":
        q = q.filter(
            Employee.id.isnot(None), func.lower(Employee.employment_type) != "intern"
        )
    if f.kind == "team_members":
        q = q.filter(
            User.id.in_(
                db.query(PMSWorkspaceTeamMember.user_id).filter(
                    PMSWorkspaceTeamMember.team_id.in_(tids)
                )
            )
        )
    if f.kind == "batched":
        q = q.filter(User.id.in_(batch_users(db, user)))
    memberships = db.query(PMSWorkspaceMember.user_id).filter(
        PMSWorkspaceMember.workspace_id.in_(wids)
    )
    if f.membership == "member":
        q = q.filter(User.id.in_(memberships))
    elif f.membership == "unassigned":
        q = q.filter(User.id.notin_(memberships))
    if f.registered_from:
        q = q.filter(User.created_at >= datetime.combine(f.registered_from, time.min))
    if f.registered_to:
        q = q.filter(
            User.created_at
            < datetime.combine(f.registered_to + timedelta(days=1), time.min)
        )
    if f.q.strip():
        term = "%" + f.q.strip() + "%"
        matching_teams = (
            teams_query(db, user)
            .filter(
                or_(
                    PMSWorkspaceTeam.name.ilike(term),
                    PMSWorkspaceTeam.alias.ilike(term),
                )
            )
            .with_entities(PMSWorkspaceTeam.id)
        )
        matching_workspaces = (
            workspace_query(db, user)
            .filter(PMSWorkspace.name.ilike(term))
            .with_entities(PMSWorkspace.id)
        )
        from app.apps.interns_hub.management_models import InternBatch

        matching_batches = (
            batches_query(db, user)
            .filter(InternBatch.name.ilike(term))
            .with_entities(InternBatch.id)
        )
        from app.apps.interns_hub.management_models import InternBatchMembership

        batch_matches = (
            db.query(Employee.user_id)
            .join(
                InternBatchMembership, InternBatchMembership.employee_id == Employee.id
            )
            .filter(
                InternBatchMembership.batch_id.in_(matching_batches),
                InternBatchMembership.status == "Active",
            )
        )
        dept = db.query(Department.id).filter(Department.name.ilike(term))
        q = q.filter(
            or_(
                User.email.ilike(term),
                CommonPerson.display_name.ilike(term),
                Employee.employee_id.ilike(term),
                Employee.first_name.ilike(term),
                Employee.last_name.ilike(term),
                Role.name.ilike(term),
                Employee.department_id.in_(dept),
                and_(public, cast(CommonProfile.skills_json, String).ilike(term)),
                User.id.in_(
                    db.query(PMSWorkspaceTeamMember.user_id).filter(
                        PMSWorkspaceTeamMember.team_id.in_(matching_teams)
                    )
                ),
                User.id.in_(batch_matches),
                User.id.in_(
                    db.query(PMSWorkspaceMember.user_id).filter(
                        PMSWorkspaceMember.workspace_id.in_(matching_workspaces)
                    )
                ),
            )
        )
    return q


def load_users(q):
    return q.options(
        joinedload(User.role),
        joinedload(User.person).joinedload(CommonPerson.profile),
        joinedload(User.employee).joinedload(Employee.department),
    )


def serialize(db, user, accounts):
    ids = [u.id for u in accounts]
    if not ids:
        return []
    team_rows = (
        db.query(
            PMSWorkspaceTeamMember.user_id,
            PMSWorkspaceTeam.id,
            PMSWorkspaceTeam.name,
            PMSWorkspaceTeam.workspace_id,
        )
        .join(PMSWorkspaceTeam, PMSWorkspaceTeam.id == PMSWorkspaceTeamMember.team_id)
        .filter(
            PMSWorkspaceTeamMember.user_id.in_(ids),
            PMSWorkspaceTeam.id.in_(
                teams_query(db, user).with_entities(PMSWorkspaceTeam.id)
            ),
        )
        .all()
    )
    from app.apps.interns_hub.management_models import (
        InternBatch,
        InternBatchMembership,
    )

    batch_rows = (
        db.query(Employee.user_id, InternBatch.id, InternBatch.name)
        .join(InternBatchMembership, InternBatchMembership.employee_id == Employee.id)
        .join(InternBatch, InternBatch.id == InternBatchMembership.batch_id)
        .filter(
            Employee.user_id.in_(ids),
            InternBatch.id.in_(batches_query(db, user).with_entities(InternBatch.id)),
            InternBatchMembership.status == "Active",
        )
        .all()
    )
    managed_workspaces = db.query(PMSWorkspaceMember.workspace_id).filter(
        PMSWorkspaceMember.user_id == user.id,
        PMSWorkspaceMember.role.in_(["Owner", "Admin"]),
    )
    manageable = {
        row[0]
        for row in db.query(PMSWorkspaceMember.user_id).filter(
            PMSWorkspaceMember.user_id.in_(ids),
            PMSWorkspaceMember.workspace_id.in_(managed_workspaces),
        )
    }
    org_admin = organization_admin(user)
    rows = []
    for account in accounts:
        person = account.person
        profile = person.profile if person else None
        e = getattr(account, "employee", None)
        public = profile and (
            profile.directory_visibility == "public" or account.id == user.id
        )
        skills = (
            profile.skills_json
            if public and isinstance(profile.skills_json, list)
            else []
        )
        skills = [
            value if isinstance(value, str) else value.get("name", "")
            for value in skills
            if isinstance(value, (str, dict))
        ]
        classification = (
            "Intern"
            if (e and (e.employment_type or "").lower() == "intern")
            or (account.role and account.role.name.lower() == "intern")
            else (
                "Employee"
                if e
                else (
                    "Super Admin"
                    if account.is_superuser
                    else (
                        account.role.name.replace("_", " ").title()
                        if account.role
                        else "User"
                    )
                )
            )
        )
        rows.append(
            {
                "can_manage": org_admin or account.id in manageable,
                "id": account.id,
                "name": (
                    person.display_name
                    if person
                    else (e.full_name if e else account.email.split("@")[0])
                ),
                "email": account.email,
                "role": (
                    "Super Admin"
                    if account.is_superuser
                    else account.role.name if account.role else "User"
                ),
                "classification": classification,
                "status": (
                    "active"
                    if account.is_active
                    else (
                        person.status
                        if person and person.status in {"suspended", "terminated"}
                        else "inactive"
                    )
                ),
                "photo_url": profile.profile_photo_url if public else None,
                "employee_code": e.employee_id if e else None,
                "department": e.department.name if e and e.department else None,
                "skills": skills[:12],
                "teams": [
                    {"id": r.id, "name": r.name, "workspace_id": r.workspace_id}
                    for r in team_rows
                    if r.user_id == account.id
                ],
                "batches": [
                    {"id": r.id, "name": r.name}
                    for r in batch_rows
                    if r.user_id == account.id
                ],
                "registered_at": account.created_at,
            }
        )
    return rows


def stats(db, user):
    q = scope(db, user)
    total, active = q.with_entities(
        func.count(User.id),
        func.sum(case((User.is_active.is_(True), 1), else_=0)),
    ).first()
    return {
        "total": total,
        "active": int(active or 0),
        "inactive": total - int(active or 0),
        "teams": teams_query(db, user).count(),
        "batches": batches_query(db, user).count(),
    }


def can_export(user):
    grant = (getattr(user, "_suite_grants", None) or {}).get("project_management", {})
    return (
        user.is_superuser
        or "export" in grant.get("actions", [])
        or has_any_permission(user, {"pms_export", "pms_admin", "employee_export"})
    )


@router.get("/people")
def directory(
    f: Filters = Depends(filters),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = query_people(db, user, f)
    total = q.count()
    name = func.lower(func.coalesce(CommonPerson.display_name, User.email))
    order = {
        "name": name.asc(),
        "email": User.email.asc(),
        "newest": User.created_at.desc(),
        "oldest": User.created_at.asc(),
        "status": User.is_active.desc(),
    }[f.sort]
    users = (
        load_users(q)
        .order_by(order, User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": serialize(db, user, users),
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.get("/reference")
def reference(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.apps.interns_hub.management_access import require_admin

    batch_access = True
    try:
        require_admin(user)
    except HTTPException:
        batch_access = False
    q = scope(db, user)
    workspaces = workspace_query(db, user).order_by(PMSWorkspace.name).all()
    roles = [
        r[0]
        for r in q.with_entities(Role.name)
        .filter(Role.name.isnot(None))
        .distinct()
        .order_by(Role.name)
        .all()
    ]
    departments = (
        db.query(Department.id, Department.name)
        .filter(Department.id.in_(q.with_entities(Employee.department_id)))
        .order_by(Department.name)
        .all()
    )
    company = db.get(Company, organization_id_for(user))
    managed = {
        m.workspace_id
        for m in db.query(PMSWorkspaceMember).filter(
            PMSWorkspaceMember.user_id == user.id,
            PMSWorkspaceMember.role.in_(["Owner", "Admin"]),
        )
    }
    org_admin = organization_admin(user)
    return {
        "stats": stats(db, user),
        "roles": roles,
        "departments": [{"id": r.id, "name": r.name} for r in departments],
        "workspaces": [
            {"id": w.id, "name": w.name, "can_manage": org_admin or w.id in managed}
            for w in workspaces
        ],
        "organizations": [{"id": company.id, "name": company.name}] if company else [],
        "can_create_user": bool(user.is_superuser),
        "can_export": bool(can_export(user)),
        "can_manage_batches": batch_access,
        "can_manage_people": org_admin or bool(managed),
    }


def _manage_workspace(db, user, wid):
    if organization_admin(user):
        return True
    return bool(
        db.query(PMSWorkspaceMember.id)
        .filter_by(workspace_id=wid, user_id=user.id)
        .filter(PMSWorkspaceMember.role.in_(["Owner", "Admin"]))
        .first()
    )


@router.get("/groups")
def groups(
    kind: Literal["teams", "batches"] = "teams",
    q: str = Query("", max_length=150),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.apps.interns_hub.management_models import (
        InternBatch,
        InternBatchMembership,
    )

    visible = scope(db, user).with_entities(User.id)
    if kind == "teams":
        query = teams_query(db, user)
        if q:
            query = query.filter(PMSWorkspaceTeam.name.ilike("%" + q + "%"))
        total = query.count()
        items = (
            query.order_by(PMSWorkspaceTeam.name, PMSWorkspaceTeam.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        ids = [g.id for g in items]
        member_query = db.query(
            PMSWorkspaceTeamMember.team_id, PMSWorkspaceTeamMember.user_id
        ).filter(
            PMSWorkspaceTeamMember.team_id.in_(ids),
            PMSWorkspaceTeamMember.user_id.in_(visible),
        )
        counts = (
            dict(
                member_query.with_entities(
                    PMSWorkspaceTeamMember.team_id, func.count()
                ).group_by(PMSWorkspaceTeamMember.team_id)
            )
            if ids
            else {}
        )
        ranked = member_query.with_entities(
            PMSWorkspaceTeamMember.team_id.label("team_id"),
            PMSWorkspaceTeamMember.user_id.label("user_id"),
            func.row_number()
            .over(
                partition_by=PMSWorkspaceTeamMember.team_id,
                order_by=PMSWorkspaceTeamMember.user_id,
            )
            .label("rank"),
        ).subquery()
        preview_rows = (
            db.query(ranked.c.team_id, ranked.c.user_id)
            .filter(ranked.c.rank <= 3)
            .all()
            if ids
            else []
        )
        previews = {identity: [] for identity in ids}
        for row in preview_rows:
            previews[row.team_id].append(row.user_id)
        preview_ids = {identity for values in previews.values() for identity in values}
        people = (
            {
                u.id: u
                for u in load_users(
                    scope(db, user).filter(User.id.in_(preview_ids))
                ).all()
            }
            if preview_ids
            else {}
        )
        public = {p["id"]: p for p in serialize(db, user, list(people.values()))}
        managed = {
            m.workspace_id
            for m in db.query(PMSWorkspaceMember).filter(
                PMSWorkspaceMember.user_id == user.id,
                PMSWorkspaceMember.role.in_(["Owner", "Admin"]),
            )
        }
        org_admin = organization_admin(user)
        return {
            "items": [
                {
                    "id": t.id,
                    "name": t.name,
                    "workspace_id": t.workspace_id,
                    "members": counts.get(t.id, 0),
                    "avatars": [
                        public[identity]
                        for identity in previews[t.id]
                        if identity in public
                    ],
                    "can_manage": org_admin or t.workspace_id in managed,
                }
                for t in items
            ],
            "total": total,
            "page": page,
            "pages": (total + page_size - 1) // page_size,
        }
    query = batches_query(db, user)
    if q:
        query = query.filter(InternBatch.name.ilike("%" + q + "%"))
    total = query.count()
    items = (
        query.order_by(InternBatch.start_date.desc(), InternBatch.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    ids = [b.id for b in items]
    counts = (
        dict(
            db.query(InternBatchMembership.batch_id, func.count())
            .join(Employee, Employee.id == InternBatchMembership.employee_id)
            .filter(
                InternBatchMembership.batch_id.in_(ids),
                InternBatchMembership.status == "Active",
                Employee.user_id.in_(visible),
            )
            .group_by(InternBatchMembership.batch_id)
        )
        if ids
        else {}
    )
    return {
        "items": [
            {
                "id": b.id,
                "name": b.name,
                "project_id": b.project_id,
                "start_date": b.start_date,
                "end_date": b.end_date,
                "members": counts.get(b.id, 0),
                "status": b.status,
            }
            for b in items
        ],
        "total": total,
        "page": page,
        "pages": (total + page_size - 1) // page_size,
    }


@router.get("/export")
def export(
    f: Filters = Depends(filters),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not can_export(user):
        raise HTTPException(403, "Export requires scoped export permission")
    q = load_users(query_people(db, user, f)).order_by(User.id)

    def safe(value):
        text = str(value or "")
        return "'" + text if text[:1] in {"=", "+", "-", "@", "\t", "\r"} else text

    def stream():
        yield "\ufeff"
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "Name",
                "Email",
                "Classification",
                "Status",
                "Employee ID",
                "Department",
                "Role",
            ]
        )
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        for account in q.yield_per(500):
            person = account.person
            e = getattr(account, "employee", None)
            writer.writerow(
                [
                    safe(person.display_name if person else account.email),
                    safe(account.email),
                    (
                        "Intern"
                        if e and (e.employment_type or "").lower() == "intern"
                        else "Employee" if e else "User"
                    ),
                    "Active" if account.is_active else "Inactive",
                    safe(e.employee_id if e else ""),
                    safe(e.department.name if e and e.department else ""),
                    safe(account.role.name if account.role else "User"),
                ]
            )
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    return StreamingResponse(
        stream(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="people-directory.csv"'},
    )


class ViewInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    filters: dict = Field(default_factory=dict)


@router.get("/views")
def views(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from .api.router import _saved_view_payload

    return [
        _saved_view_payload(v)
        for v in db.query(PMSSavedFilter)
        .filter_by(
            user_id=user.id,
            organization_id=organization_id_for(user),
            entity_type="people",
        )
        .order_by(PMSSavedFilter.name)
    ]


@router.post("/views", status_code=201)
def save_view(
    data: ViewInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from .api.router import create_saved_view
    from .schemas import PMSSavedFilterCreate

    Filters.model_validate(
        {
            key: value
            for key, value in data.filters.items()
            if key in Filters.model_fields
        }
    )
    return create_saved_view(
        PMSSavedFilterCreate(
            name=data.name,
            entity_type="people",
            view_type="people_directory",
            filters=data.filters,
            visibility="private",
            is_shared=False,
        ),
        db,
        user,
    )


@router.delete("/views/{view_id}")
def remove_view(
    view_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    row = (
        db.query(PMSSavedFilter)
        .filter_by(
            id=view_id,
            user_id=user.id,
            organization_id=organization_id_for(user),
            entity_type="people",
        )
        .first()
    )
    if not row:
        raise HTTPException(404, "Personal view not found")
    db.delete(row)
    db.commit()
    return {"deleted": True}


def task_stats(db, user, member_ids):
    projects = accessible_project_query(db, user).with_entities(PMSProject.id)
    assigned = db.query(PMSTaskAssignee.task_id).filter(
        PMSTaskAssignee.user_id.in_(member_ids), PMSTaskAssignee.cancelled_at.is_(None)
    )
    q = db.query(PMSTask).filter(
        PMSTask.project_id.in_(projects),
        PMSTask.deleted_at.is_(None),
        or_(PMSTask.assignee_user_id.in_(member_ids), PMSTask.id.in_(assigned)),
    )
    from app.services.metrics.queries import COMPLETED,TERMINAL,business_day
    complete = PMSTask.status.in_(COMPLETED)
    closed = PMSTask.status.in_(TERMINAL)
    total, completed, pending, overdue = q.with_entities(
        func.count(),
        func.sum(case((complete, 1), else_=0)),
        func.sum(case((~closed, 1), else_=0)),
        func.sum(case((and_(~closed, PMSTask.due_date < business_day(db,user)), 1), else_=0)),
    ).first()
    submissions = (
        db.query(PMSWorkSubmission.status, func.count())
        .filter(
            PMSWorkSubmission.task_id.in_(q.with_entities(PMSTask.id)),
            PMSWorkSubmission.user_id.in_(member_ids),
            PMSWorkSubmission.status != "Draft",
        )
        .group_by(PMSWorkSubmission.status)
        .all()
    )
    return q, {
        "total": total,
        "completed": int(completed or 0),
        "pending": int(pending or 0),
        "overdue": int(overdue or 0),
        "submissions": dict(submissions),
    }


def tasks_page(query, page=1, page_size=20):
    total = query.count()
    return {
        "items": [
            {
                "id": t.id,
                "title": t.title,
                "task_key": t.task_key,
                "project_id": t.project_id,
                "status": t.status,
                "priority": t.priority,
                "due_date": t.due_date,
            }
            for t in query.order_by(PMSTask.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ],
        "total": total,
        "page": page,
        "pages": (total + page_size - 1) // page_size,
    }


@router.get("/groups/{kind}/{group_id}")
def group_detail(
    kind: Literal["teams", "batches"],
    group_id: int,
    section: Literal["overview", "members", "tasks"] = "overview",
    q: str = Query("", max_length=150),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.apps.interns_hub.management_models import InternBatch

    if kind == "teams":
        group = teams_query(db, user).filter(PMSWorkspaceTeam.id == group_id).first()
        if not group:
            raise HTTPException(404, "Team not found in your accessible scope")
        ids = db.query(PMSWorkspaceTeamMember.user_id).filter_by(team_id=group_id)
        info = {
            "id": group.id,
            "name": group.name,
            "alias": group.alias,
            "description": group.description,
            "lead_user_id": group.lead_user_id,
            "workspace_id": group.workspace_id,
            "visibility": group.visibility,
            "can_manage": _manage_workspace(db, user, group.workspace_id),
        }
    else:
        group = batches_query(db, user).filter(InternBatch.id == group_id).first()
        if not group:
            raise HTTPException(404, "Batch not found in your management scope")
        ids = batch_users(db, user, group_id)
        info = {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "project_id": group.project_id,
            "status": group.status,
            "start_date": group.start_date,
            "end_date": group.end_date,
            "manager_user_id": group.manager_user_id,
            "mentor_user_id": group.mentor_user_id,
            "coordinator_user_id": group.coordinator_user_id,
            "can_manage": True,
        }
    ids = scope(db, user).filter(User.id.in_(ids)).with_entities(User.id)
    leaders = {
        info.get(key)
        for key in [
            "lead_user_id",
            "manager_user_id",
            "mentor_user_id",
            "coordinator_user_id",
        ]
        if info.get(key)
    }
    leader_names = (
        {
            u.id: (u.person.display_name if u.person else u.email)
            for u in load_users(scope(db, user).filter(User.id.in_(leaders))).all()
        }
        if leaders
        else {}
    )
    info["responsible_people"] = [
        {
            "role": key.replace("_user_id", "").replace("_", " ").title(),
            "id": info[key],
            "name": leader_names[info[key]],
        }
        for key in [
            "lead_user_id",
            "manager_user_id",
            "mentor_user_id",
            "coordinator_user_id",
        ]
        if info.get(key) in leader_names
    ]
    people = scope(db, user).filter(User.id.in_(ids))
    if q:
        people = people.filter(
            or_(
                User.email.ilike("%" + q + "%"),
                CommonPerson.display_name.ilike("%" + q + "%"),
                Employee.employee_id.ilike("%" + q + "%"),
            )
        )
    total = people.count()
    query, summary = task_stats(db, user, ids)
    result = {
        "group": info,
        "members": total,
        "stats": summary,
        "workload_scope": "Work for current visible members in projects you can access",
    }
    if section == "members":
        result["items"] = serialize(
            db,
            user,
            load_users(people)
            .order_by(User.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all(),
        )
        result.update(page=page, pages=(total + page_size - 1) // page_size)
    if section == "tasks":
        result.update(tasks_page(query, page, page_size))
    if section == "overview":
        projects = (
            db.query(PMSProject.id, PMSProject.name)
            .filter(PMSProject.id.in_(query.with_entities(PMSTask.project_id)))
            .order_by(PMSProject.name)
            .limit(20)
            .all()
        )
        result["projects"] = [{"id": p.id, "name": p.name} for p in projects]
        review = (
            db.query(func.avg(PMSWorkReview.score))
            .join(
                PMSWorkSubmission, PMSWorkSubmission.id == PMSWorkReview.submission_id
            )
            .filter(
                PMSWorkSubmission.user_id.in_(ids),
                PMSWorkSubmission.task_id.in_(query.with_entities(PMSTask.id)),
            )
            .scalar()
        )
        result["stats"]["average_review_score"] = (
            float(review) if review is not None else None
        )
        reviewers = (
            db.query(PMSTaskAssignee.reviewer_user_id, func.count())
            .filter(
                PMSTaskAssignee.user_id.in_(ids),
                PMSTaskAssignee.task_id.in_(query.with_entities(PMSTask.id)),
            )
            .group_by(PMSTaskAssignee.reviewer_user_id)
            .all()
        )
        result["stats"]["with_reviewer"] = sum(
            count for identity, count in reviewers if identity
        )
        result["stats"]["without_reviewer"] = sum(
            count for identity, count in reviewers if not identity
        )
    return result


@router.get("/workspaces/{workspace_id}/people")
def workspace_people(
    workspace_id: int,
    q: str = Query("", max_length=150),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    scoped_workspace(db, workspace_id, user, True)
    ids = (
        db.query(PMSWorkspaceMember.user_id)
        .filter_by(workspace_id=workspace_id)
        .filter(PMSWorkspaceMember.role != "Guest")
    )
    query = scope(db, user).filter(User.id.in_(ids))
    if q:
        query = query.filter(
            or_(
                CommonPerson.display_name.ilike("%" + q + "%"),
                User.email.ilike("%" + q + "%"),
            )
        )
    total = query.count()
    return {
        "items": serialize(
            db,
            user,
            load_users(query)
            .order_by(User.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all(),
        ),
        "total": total,
        "page": page,
        "pages": (total + page_size - 1) // page_size,
    }


@router.get("/people/{person_id}")
def person_detail(
    person_id: int,
    section: Literal[
        "overview", "teams", "batches", "projects", "tasks", "activity"
    ] = "overview",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    person = load_users(scope(db, user).filter(User.id == person_id)).first()
    if not person:
        raise HTTPException(404, "Person not found in your accessible scope")
    identity = serialize(db, user, [person])[0]
    can_manage = organization_admin(user) or bool(
        db.query(PMSWorkspaceMember.id)
        .filter(
            PMSWorkspaceMember.user_id == person_id,
            PMSWorkspaceMember.workspace_id.in_(
                workspace_query(db, user).with_entities(PMSWorkspace.id)
            ),
        )
        .filter(
            PMSWorkspaceMember.workspace_id.in_(
                db.query(PMSWorkspaceMember.workspace_id).filter(
                    PMSWorkspaceMember.user_id == user.id,
                    PMSWorkspaceMember.role.in_(["Owner", "Admin"]),
                )
            )
        )
        .first()
    )
    result = {"person": identity, "can_manage": can_manage}
    if section == "overview":
        _, summary = task_stats(db, user, [person_id])
        result["stats"] = summary
        result["employment_status"] = (
            person.employee.status if person.employee else None
        )
    if section == "teams":
        result["items"] = identity["teams"]
    if section == "batches":
        result["items"] = identity["batches"]
    if section == "projects":
        workspace_ids = db.query(PMSWorkspaceMember.workspace_id).filter_by(
            user_id=person_id
        )
        project_ids = db.query(PMSProjectMember.project_id).filter_by(user_id=person_id)
        query = accessible_project_query(db, user).filter(
            or_(
                PMSProject.workspace_id.in_(workspace_ids),
                PMSProject.id.in_(project_ids),
                PMSProject.manager_user_id == person_id,
            )
        )
        total = query.count()
        result.update(
            items=[
                {"id": p.id, "name": p.name, "status": p.status}
                for p in query.order_by(PMSProject.name)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ],
            total=total,
            page=page,
            pages=(total + page_size - 1) // page_size,
        )
    if section == "tasks":
        result.update(tasks_page(task_stats(db, user, [person_id])[0], page, page_size))
    if section == "activity":
        if not can_manage and user.id != person_id:
            result["items"] = []
            result["restricted_reason"] = (
                "Membership change history requires permission to manage this person."
            )
        else:
            logs = db.query(AuditLog).filter(
                AuditLog.organization_id == organization_id_for(user),
                AuditLog.entity_type == "user",
                AuditLog.entity_id == person_id,
                AuditLog.module == "project_management",
            )
            total = logs.count()
            result.update(
                items=[
                    {
                        "id": row.id,
                        "action": row.action,
                        "description": row.description,
                        "created_at": row.created_at,
                        "actor": row.actor_email,
                    }
                    for row in logs.order_by(AuditLog.id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                ],
                total=total,
                page=page,
                pages=(total + page_size - 1) // page_size,
            )
    return result


class IndividualInput(BaseModel):
    task: PMSTaskCreate
    batches: list[int] = Field(default_factory=list, max_length=500)
    people: list[int] = Field(default_factory=list, max_length=20000)
    reviewer_user_id: int
    request_key: str = Field(min_length=8, max_length=100)


def job_output(job):
    return {
        "id": job.id,
        "task_id": job.task_id,
        "status": job.status,
        "total": len(job.recipients),
        "processed": job.cursor,
        "attempts": job.attempts,
        "error": job.error,
        "batch_ids": job.batch_ids,
    }


@router.post("/individual-tasks/{project_id}", status_code=201)
def individual_tasks(
    project_id: int,
    data: IndividualInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.apps.interns_hub.management_access import require_admin, get_batch
    from app.apps.interns_hub.distribution import recipients, publish
    from app.apps.interns_hub.management_models import InternDistribution
    from .access import get_project_for_action

    require_admin(user)
    project = get_project_for_action(db, project_id, user, "manage_tasks")
    if not data.task.due_date:
        raise HTTPException(422, "Individual assignments require a due date")
    if not data.batches and not data.people:
        raise HTTPException(422, "Select at least one batch or intern")
    if data.batches and data.people:
        raise HTTPException(422, "Choose whole batches or selected interns, not both")
    for identity in data.batches:
        batch = get_batch(db, user, identity)
        if not batches_query(db, user).filter_by(id=identity).first() or (
            project_id != batch.project_id
            and project_id not in (batch.project_ids or [])
        ):
            raise HTTPException(
                403, "Batch must be within your scope and linked to this project"
            )
    employee_ids = []
    if data.people:
        scoped = scope(db, user).filter(User.id.in_(data.people)).with_entities(User.id)
        employees = (
            db.query(Employee)
            .filter(
                Employee.user_id.in_(scoped),
                func.lower(Employee.employment_type) == "intern",
                Employee.deleted_at.is_(None),
            )
            .all()
        )
        if {e.user_id for e in employees} != set(data.people):
            raise HTTPException(
                422,
                "Individual assignments require authorized linked intern identities",
            )
        employee_ids = sorted(e.id for e in employees)
    payload = {
        "project_id": project_id,
        "title": data.task.title,
        "description": data.task.description or "",
        "priority": data.task.priority,
        "due_date": data.task.due_date,
        "start_date": data.task.start_date,
        "reviewer_user_id": data.reviewer_user_id,
        "maximum_score": 100,
        "target_type": "batches" if data.batches else "interns",
        "batch_ids": sorted(set(data.batches)),
        "employee_ids": employee_ids,
        "idempotency_key": data.request_key,
        "source_payload": data.task.model_dump(mode="json"),
    }
    # Authorization and recipient preview occur before creating the parent task.
    if recipients(db, user, payload).count() == 0:
        raise HTTPException(422, "No authorized active interns match this selection")
    previous = (
        db.query(InternDistribution)
        .filter_by(
            organization_id=organization_id_for(user), idempotency_key=data.request_key
        )
        .first()
    )
    if previous:
        payload["task_id"] = previous.task_id
    else:
        from .api.router import create_task_operation

        reviewer = db.get(User, data.reviewer_user_id)
        if (
            not reviewer
            or not reviewer.is_active
            or not can_access_project(db, project, reviewer, "approve")
        ):
            raise HTTPException(403, "Reviewer lacks project approval permission")
        parent = create_task_operation(
            project_id,
            data.task.model_copy(
                update={"assignee_user_ids": [], "assignee_user_id": None}
            ),
            db,
            user,
            commit=False,
        )
        payload["task_id"] = parent.id
    job = publish(db, user, payload, process=True)
    return job_output(job)


@router.get("/assignment-jobs/{job_id}")
def assignment_job(
    job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    from app.apps.interns_hub.management_access import require_admin
    from app.apps.interns_hub.management_models import InternDistribution
    from .access import get_task_project_for_action

    require_admin(user)
    job = (
        db.query(InternDistribution)
        .filter_by(id=job_id, organization_id=organization_id_for(user))
        .first()
    )
    if not job or (not organization_admin(user) and job.created_by != user.id):
        raise HTTPException(404, "Assignment job not found in your scope")
    get_task_project_for_action(db, job.task_id, user, "manage_tasks")
    return job_output(job)


@router.post("/assignment-jobs/{job_id}/continue")
def continue_job(
    job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    assignment_job(job_id, db, user)
    from app.apps.interns_hub.distribution import process_job

    return job_output(process_job(db, job_id))


@router.get("/assignment-context")
def assignment_context(
    kind: Literal["people", "teams", "batches"],
    ids: str = Query(..., max_length=2000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        selected = sorted({int(value) for value in ids.split(",") if value})
    except ValueError:
        raise HTTPException(422, "Select valid identities")
    if not selected or len(selected) > 100 or min(selected) <= 0:
        raise HTTPException(422, "Select 1–100 identities")
    query = accessible_project_query(db, user)
    if kind == "teams":
        groups = teams_query(db, user).filter(PMSWorkspaceTeam.id.in_(selected)).all()
        if len(groups) != len(selected):
            raise HTTPException(404, "A team is outside your scope")
        query = query.filter(
            PMSProject.workspace_id.in_({team.workspace_id for team in groups})
        )
    elif kind == "batches":
        from app.apps.interns_hub.management_models import InternBatch

        groups = batches_query(db, user).filter(InternBatch.id.in_(selected)).all()
        if len(groups) != len(selected):
            raise HTTPException(404, "A batch is outside your management scope")
        linked = set.intersection(
            *[{batch.project_id, *list(batch.project_ids or [])} for batch in groups]
        )
        query = query.filter(PMSProject.id.in_(linked))
    else:
        permitted = (
            scope(db, user)
            .filter(User.id.in_(selected), User.is_active.is_(True))
            .with_entities(User.id)
            .all()
        )
        if {row[0] for row in permitted} != set(selected):
            raise HTTPException(422, "Choose active people in your accessible scope")
    output = []
    for project in query.order_by(PMSProject.name).all():
        if not can_access_project(db, project, user, "manage_tasks"):
            continue
        missing = []
        if kind == "people":
            from .api.router import _project_user_query

            eligible = {
                row[0]
                for row in _project_user_query(db, project)
                .filter(User.id.in_(selected))
                .with_entities(User.id)
            }
            missing = sorted(set(selected) - eligible)
            if missing and not can_access_project(db, project, user, "manage_members"):
                continue
        output.append(
            {
                "id": project.id,
                "name": project.name,
                "workspace_id": project.workspace_id,
                "missing_user_ids": missing,
            }
        )
    return {"projects": output, "kind": kind, "ids": selected}


class TeamChange(BaseModel):
    user_ids: list[int] = Field(min_length=1, max_length=100)
    action: Literal["add", "remove"] = "add"
    add_workspace_members: bool = False
    reason: str = Field(min_length=3, max_length=1000)


def team_change_preview(db, user, team_id, data):
    team = teams_query(db, user).filter(PMSWorkspaceTeam.id == team_id).first()
    if not team:
        raise HTTPException(404, "Team not found in your scope")
    workspace, _ = scoped_workspace(db, team.workspace_id, user, True)
    selected = set(data.user_ids)
    permitted = {
        row[0]
        for row in scope(db, user)
        .filter(User.id.in_(selected), User.is_active.is_(True))
        .with_entities(User.id)
    }
    if permitted != selected:
        raise HTTPException(422, "Choose active people within your authorized scope")
    members = {
        row.user_id: row.role
        for row in db.query(PMSWorkspaceMember).filter(
            PMSWorkspaceMember.workspace_id == team.workspace_id,
            PMSWorkspaceMember.user_id.in_(selected),
        )
    }
    if any(role == "Guest" for role in members.values()):
        raise HTTPException(
            422,
            "Guests cannot join teams. A workspace owner must change their role first.",
        )
    current = {member.user_id for member in team.members}
    return team, {
        "workspace_id": workspace.id,
        "workspace_name": workspace.name,
        "selected": len(selected),
        "missing_user_ids": (
            sorted(selected - set(members)) if data.action == "add" else []
        ),
        "changed": (
            len(selected - current) if data.action == "add" else len(selected & current)
        ),
        "role": "Member",
    }


@router.post("/teams/{team_id}/members/preview")
def preview_team_change(
    team_id: int,
    data: TeamChange,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return team_change_preview(db, user, team_id, data)[1]


@router.post("/teams/{team_id}/members")
def change_team(
    team_id: int,
    data: TeamChange,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    team, preview = team_change_preview(db, user, team_id, data)
    if preview["missing_user_ids"]:
        if not data.add_workspace_members:
            raise HTTPException(
                409,
                "Confirm the Member workspace access shown in the preview before adding these people",
            )
        from .people_management import BulkAdd, bulk_add

        bulk_add(
            BulkAdd(
                user_ids=preview["missing_user_ids"],
                workspace_ids=[team.workspace_id],
                role="Member",
                reason=data.reason,
            ),
            db,
            user,
        )
    from .teams import persist_team, TeamInput

    current = {member.user_id for member in team.members}
    final = (
        current | set(data.user_ids)
        if data.action == "add"
        else current - set(data.user_ids)
    )
    result = persist_team(
        db,
        team.workspace_id,
        TeamInput(name=team.name, alias=team.alias, member_ids=sorted(final)),
        team,
        actor=user,
    )
    return {
        "team": result,
        "changed": preview["changed"],
        "workspace_access_added": len(preview["missing_user_ids"]),
    }
