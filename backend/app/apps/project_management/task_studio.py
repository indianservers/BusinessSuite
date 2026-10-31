"""Task composer with scoped, audited snapshots of people and group selections."""

import json
import hashlib
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session, joinedload
from app.core.deps import get_db, get_current_user
from app.models.user import User
from .models import PMSTask, PMSActivity, PMSWorkspaceTeam
from .schemas import PMSTaskCreate, PMSTaskUpdate, PMSTaskResponse
from .access import (
    get_project_for_action,
    get_task_project_for_action,
    can_access_project,
    accessible_project_query,
)
from .people_management import same_company, public_person

router = APIRouter(prefix="/task-studio", tags=["PMS Task Studio"])


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    people: list[int] = Field(default_factory=list, max_length=100)
    teams: list[int] = Field(default_factory=list, max_length=50)
    batches: list[int] = Field(default_factory=list, max_length=50)
    reviewer: int | None = None
    owner: int | None = None
    allow_partial_groups: bool = False
    preserve_managed: bool = False


class CreateInput(BaseModel):
    task: PMSTaskCreate
    assignment: Selection = Field(default_factory=Selection)


class UpdateInput(BaseModel):
    task: PMSTaskUpdate
    assignment: Selection
    version: str


def choices(db, project, user, compact=False):
    from .api.router import _project_user_query
    from .people_workspace import load_users, scope, batches_query

    candidates = [
        u
        for u in load_users(
            _project_user_query(db, project).filter(
                User.id.in_(scope(db, user).with_entities(User.id))
            )
        ).all()
        if same_company(db, user, u)
        and (not u.person or u.person.status == "active")
        and (
            not getattr(u, "employee", None)
            or u.employee.status not in {"Terminated", "Inactive", "Suspended"}
        )
    ]
    ids = {u.id for u in candidates}

    def group(identity, name, members):
        unique = set(members)
        return {
            "id": identity,
            "name": name,
            "member_ids": sorted(unique & ids),
            "excluded_count": len(unique - ids),
        }

    from .people_workspace import teams_query

    teams = (
        [
            group(t.id, t.name, json.loads(t.member_ids_json or "[]"))
            for t in teams_query(db, user)
            .filter_by(workspace_id=project.workspace_id)
            .order_by(PMSWorkspaceTeam.name)
        ]
        if project.workspace_id
        else []
    )
    batches, batch_reason = (
        [],
        "Intern batch assignment requires an authorized intern manager within the batch scope.",
    )
    from app.module_registry import is_app_enabled

    if is_app_enabled("hrms"):
        from app.apps.interns_hub.management_access import (
            require_admin,
            batch_query,
            employee_query,
        )
        from app.apps.interns_hub.management_models import InternBatchMembership
        from app.models.employee import Employee

        try:
            require_admin(user)
        except HTTPException:
            pass
        else:
            allowed_employees = employee_query(
                db, user, include_employees=True
            ).with_entities(Employee.id)
            scoped = {row[0] for row in allowed_employees.all()}
            for batch in batches_query(db, user).filter_by(status="Active").all():
                if project.id != batch.project_id and project.id not in (
                    batch.project_ids or []
                ):
                    continue
                members = (
                    db.query(Employee)
                    .join(
                        InternBatchMembership,
                        InternBatchMembership.employee_id == Employee.id,
                    )
                    .filter(
                        InternBatchMembership.batch_id == batch.id,
                        InternBatchMembership.status == "Active",
                    )
                    .all()
                )
                eligible = [
                    e.user_id
                    for e in members
                    if e.id in scoped
                    and e.user_id in ids
                    and e.deleted_at is None
                    and e.status not in {"Terminated", "Inactive", "Suspended"}
                ]
                batches.append(
                    {
                        "id": batch.id,
                        "name": batch.name,
                        "member_ids": sorted(set(eligible)),
                        "excluded_count": len(members) - len(set(eligible)),
                        "population_count": len(members),
                    }
                )
            batch_reason = "Only active batches linked to this project and within your management scope are listed."
    # Approval candidates are narrowed in one query before applying the canonical policy.
    approval_candidates = candidates
    if project.workspace_id:
        from .models import PMSWorkspaceMember
        from .people_management import ADMIN_ROLES

        owners = {
            row[0]
            for row in db.query(PMSWorkspaceMember.user_id).filter(
                PMSWorkspaceMember.workspace_id == project.workspace_id,
                PMSWorkspaceMember.role.in_(["Owner", "Admin"]),
            )
        }
        approval_candidates = [
            u
            for u in candidates
            if u.id in owners
            or u.is_superuser
            or (u.role and u.role.name.lower().replace(" ", "_") in ADMIN_ROLES)
        ]
    reviewers = [
        u.id
        for u in approval_candidates
        if can_access_project(db, project, u, "approve")
    ]
    shown = (
        candidates
        if not compact
        else list(
            {
                u.id: u
                for u in candidates[:40]
                + [u for u in candidates if u.id in reviewers][:40]
            }.values()
        )
    )
    if compact:
        for item in teams + batches:
            item["member_count"] = len(item["member_ids"])
            item["member_ids"] = item["member_ids"][:100]
    return {
        "people": [public_person(db, u) for u in shown],
        "teams": teams,
        "batches": batches,
        "reviewers": reviewers,
        "batch_reason": batch_reason,
        "workspace_id": project.workspace_id,
        "can_edit": can_access_project(db, project, user, "manage_tasks"),
        "can_add_existing": can_access_project(db, project, user, "manage_members"),
    }


@router.get("/projects")
def projects(
    people: str = "",
    teams: str = "",
    batches: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from .models import PMSProject

    context = None
    for kind, selected in [("people", people), ("teams", teams), ("batches", batches)]:
        if selected:
            from .people_workspace import assignment_context

            context = assignment_context(kind, selected, db, user)
            break
    allowed = {p["id"] for p in context["projects"]} if context else None
    return [
        {
            "id": p.id,
            "name": p.name,
            "project_key": p.project_key,
            "workspace_id": p.workspace_id,
            "can_manage_tasks": can_access_project(db, p, user, "manage_tasks"),
        }
        for p in accessible_project_query(db, user).order_by(PMSProject.name).all()
        if allowed is None or p.id in allowed
    ]


@router.get("/options")
def options(
    project_id: int,
    compact: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return choices(
        db, get_project_for_action(db, project_id, user, "browse"), user, compact
    )


@router.get("/people")
def picker_people(
    project_id: int,
    q: str = Query("", max_length=150),
    page: int = Query(1, ge=1),
    selected: str = Query("", max_length=2000),
    reviewers: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from .people_workspace import query_people, Filters, load_users
    from .api.router import _project_user_query

    project = get_project_for_action(db, project_id, user, "browse")
    query = query_people(db, user, Filters(q=q, status="active")).filter(
        User.id.in_(_project_user_query(db, project).with_entities(User.id))
    )
    if reviewers:
        allowed = choices(db, project, user, True)["reviewers"]
        query = query.filter(User.id.in_(allowed))
    total = query.count()
    rows = load_users(
        query.order_by(User.email, User.id).offset((page - 1) * 30).limit(30)
    ).all()
    try:
        ids = {int(v) for v in selected.split(",") if v}
    except ValueError:
        raise HTTPException(422, "Invalid selected identities")
    if len(ids) > 100:
        raise HTTPException(422, "Select at most 100 people")
    retained = (
        load_users(
            query_people(db, user, Filters(status="active")).filter(
                User.id.in_(ids),
                User.id.in_(_project_user_query(db, project).with_entities(User.id)),
            )
        ).all()
        if ids
        else []
    )
    return {
        "items": [public_person(db, u) for u in rows],
        "selected": [public_person(db, u) for u in retained],
        "total": total,
        "pages": (total + 29) // 30,
        "page": page,
    }


def resolve(db, project, user, selection, preserved_ids=frozenset()):
    options = choices(db, project, user)
    eligible = {p["id"] for p in options["people"]}
    ids = set(selection.people)
    if not ids.issubset(eligible | set(preserved_ids)):
        raise HTTPException(
            422,
            "Choose active people with access to the selected project. Add existing people to its workspace first.",
        )
    snapshots = []
    for kind, values in [("teams", selection.teams), ("batches", selection.batches)]:
        indexed = {g["id"]: g for g in options[kind]}
        for identity in set(values):
            item = indexed.get(identity)
            if not item:
                raise HTTPException(
                    422,
                    "A selected group is unavailable in this project or outside your management scope",
                )
            if not item["member_ids"]:
                raise HTTPException(422, "A selected group has no eligible members")
            if item["excluded_count"] and not selection.allow_partial_groups:
                raise HTTPException(
                    422,
                    "Some group members cannot receive this task. Review exclusions and explicitly choose eligible members only.",
                )
            ids.update(item["member_ids"])
            snapshots.append({"kind": kind, **item})
    if len(ids) > 100:
        raise HTTPException(422, "Choose at most 100 unique task assignees")
    if selection.owner and selection.owner not in eligible:
        raise HTTPException(422, "Owner must be an active project collaborator")
    if selection.reviewer and selection.reviewer not in options["reviewers"]:
        raise HTTPException(
            422, "Reviewer must have approval permission in this project"
        )
    return sorted(ids), {
        **selection.model_dump(),
        "groups": snapshots,
        "resolved_ids": sorted(ids),
    }


def version(db, task):
    latest = (
        db.query(PMSActivity.id)
        .filter(
            PMSActivity.task_id == task.id,
            PMSActivity.action.in_(
                [
                    "task.created",
                    "task.updated",
                    "task.assignment_selection",
                    "task.deleted",
                    "task.restored",
                    "task.moved",
                ]
            ),
        )
        .order_by(PMSActivity.id.desc())
        .first()
    )
    return (
        (task.updated_at or task.created_at).isoformat()
        + ":"
        + str(latest[0] if latest else 0)
    )


def detail(db, task, project, user):
    from .people_workspace import load_users

    event = (
        db.query(PMSActivity)
        .filter_by(task_id=task.id, action="task.assignment_selection")
        .order_by(PMSActivity.id.desc())
        .first()
    )
    selection = (
        json.loads(event.metadata_json)
        if event
        else {
            "people": task.assignee_user_ids,
            "teams": [],
            "batches": [],
            "reviewer": None,
            "owner": None,
        }
    )
    # Changes made from another PMS surface remain visible as individual selections.
    if event and set(selection.get("resolved_ids", [])) != set(task.assignee_user_ids):
        selection = {
            **selection,
            "people": task.assignee_user_ids,
            "teams": [],
            "batches": [],
        }
    protected = [a.user_id for a in task.assignments if a.source_key]
    protected_set = set(protected)
    if len(protected) > 100:
        selection = {
            **selection,
            "people": [
                uid for uid in selection.get("people", []) if uid not in protected_set
            ],
            "preserve_managed": True,
        }
    return {
        "task": PMSTaskResponse.model_validate(task).model_dump(),
        "protected_count": len(protected),
        "assignment": {
            key: selection.get(key, default)
            for key, default in Selection().model_dump().items()
        },
        "version": version(db, task),
        "can_edit": can_access_project(db, project, user, "manage_tasks"),
        "protected_ids": protected[:100],
        "retained_people": [
            public_person(db, account)
            for account in load_users(
                db.query(User).filter(User.id.in_(protected[:100]))
            ).all()
        ],
    }


@router.get("/tasks/{task_id}")
def get(
    task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    task, project = get_task_project_for_action(db, task_id, user, "browse")
    return detail(db, task, project, user)


def record(db, task, user, selection):
    from .api.router import _record_activity

    for row in task.assignments:
        if not row.source_key:
            row.reviewer_user_id = selection["reviewer"]
    _record_activity(
        db,
        task.project_id,
        user,
        "task.assignment_selection",
        "task",
        task.id,
        f"Updated assignment selections for {task.task_key}",
        task_id=task.id,
        metadata=selection,
    )


@router.post("/projects/{project_id}/tasks", status_code=201)
def create(
    project_id: int,
    data: CreateInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from .api.router import create_task_operation

    project = get_project_for_action(db, project_id, user, "manage_tasks")
    data.task.task_key = data.task.task_key.strip().upper()
    if not data.task.task_key:
        raise HTTPException(422, "Enter a task key")
    ids, selection = resolve(db, project, user, data.assignment)
    fingerprint = hashlib.sha256(
        json.dumps(data.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
    existing = (
        db.query(PMSTask)
        .filter_by(project_id=project_id, task_key=data.task.task_key.upper())
        .first()
    )
    if existing:
        event = (
            db.query(PMSActivity)
            .filter_by(
                task_id=existing.id,
                action="task.assignment_selection",
                actor_user_id=user.id,
            )
            .order_by(PMSActivity.id.desc())
            .first()
        )
        if (
            not existing.deleted_at
            and event
            and json.loads(event.metadata_json).get("request_hash") == fingerprint
        ):
            return detail(db, existing, project, user)
        raise HTTPException(
            409, "This task key is already used. Reload or start a new draft."
        )
    selection["request_hash"] = fingerprint
    try:
        task = create_task_operation(
            project_id,
            data.task.model_copy(update={"assignee_user_ids": ids}),
            db,
            user,
            commit=False,
        )
        record(db, task, user, selection)
        db.commit()
        db.refresh(task)
    except Exception:
        db.rollback()
        raise
    publish(user, task, "task.created")
    return detail(db, task, project, user)


def publish(user, task, kind):
    from .api.router import _broadcast_realtime

    _broadcast_realtime(
        user,
        kind,
        project_id=task.project_id,
        task_id=task.id,
        message=f"Saved task {task.task_key}",
        entity={
            "id": task.id,
            "taskKey": task.task_key,
            "title": task.title,
            "status": task.status,
        },
    )


@router.put("/tasks/{task_id}")
def update(
    task_id: int,
    data: UpdateInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from .api.router import update_task_operation

    task, project = get_task_project_for_action(db, task_id, user, "manage_tasks")
    if project.workspace_id:
        from .models import PMSWorkspace

        db.query(PMSWorkspace).filter_by(
            id=project.workspace_id
        ).with_for_update().one()
    db.query(PMSTask).filter_by(id=task.id).with_for_update().one()
    db.refresh(task)
    if version(db, task) != data.version:
        raise HTTPException(
            409,
            "This task changed since you opened it. Reload the latest version before saving; your draft is kept.",
        )
    protected = {a.user_id for a in task.assignments if a.source_key}
    ids, selection = resolve(db, project, user, data.assignment, protected)
    if data.assignment.preserve_managed:
        if set(task.assignee_user_ids) - protected != set(ids) - protected:
            raise HTTPException(
                409,
                "Manage individual batch assignments from Batch controls; save task details separately",
            )
        ids = sorted(set(ids) | protected)
    if not protected.issubset(ids):
        raise HTTPException(
            409,
            "Batch-controlled assignments must be removed from Batch controls. Their work history is protected.",
        )
    active_ids = {p["id"] for p in choices(db, project, user)["people"]}
    editable_ids = [identity for identity in ids if identity in active_ids]
    try:
        task = update_task_operation(
            task_id,
            (
                data.task.model_copy(update={"assignee_user_ids": None})
                if data.assignment.preserve_managed
                else data.task.model_copy(update={"assignee_user_ids": editable_ids})
            ),
            db,
            user,
            commit=False,
        )
        record(db, task, user, selection)
        db.commit()
        db.refresh(task)
    except Exception:
        db.rollback()
        raise
    publish(user, task, "task.updated")
    return detail(db, task, project, user)
