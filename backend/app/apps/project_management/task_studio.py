"""Task composer with scoped, audited snapshots of people and group selections."""
import json
import hashlib
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.user import User
from .models import PMSTask, PMSActivity, PMSWorkspaceTeam
from .schemas import PMSTaskCreate, PMSTaskUpdate, PMSTaskResponse
from .access import get_project_for_action, get_task_project_for_action, can_access_project, accessible_project_query
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

class CreateInput(BaseModel):
    task: PMSTaskCreate
    assignment: Selection = Field(default_factory=Selection)

class UpdateInput(BaseModel):
    task: PMSTaskUpdate
    assignment: Selection
    version: str


def choices(db, project, user):
    from .api.router import _project_user_query
    candidates = [u for u in _project_user_query(db, project).all() if same_company(db, user, u) and (not u.person or u.person.status == "active") and (not getattr(u, "employee", None) or u.employee.status not in {"Terminated", "Inactive", "Suspended"})]
    ids = {u.id for u in candidates}
    def group(identity, name, members):
        unique = set(members)
        return {"id": identity, "name": name, "member_ids": sorted(unique & ids), "excluded_count": len(unique - ids)}
    teams = [group(t.id, t.name, json.loads(t.member_ids_json or "[]")) for t in db.query(PMSWorkspaceTeam).filter_by(workspace_id=project.workspace_id).order_by(PMSWorkspaceTeam.name)] if project.workspace_id else []
    batches, batch_reason = [], "Intern batch assignment requires an authorized intern manager within the batch scope."
    from app.module_registry import is_app_enabled
    if is_app_enabled("hrms"):
        from app.apps.interns_hub.management_access import require_admin, batch_query, employee_query
        from app.apps.interns_hub.management_models import InternBatchMembership
        from app.models.employee import Employee
        try:
            require_admin(user)
        except HTTPException:
            pass
        else:
            allowed_employees = employee_query(db, user, include_employees=True).with_entities(Employee.id)
            for batch in batch_query(db, user).filter_by(status="Active").all():
                if project.id != batch.project_id and project.id not in (batch.project_ids or []):
                    continue
                members = db.query(Employee).join(InternBatchMembership, InternBatchMembership.employee_id == Employee.id).filter(InternBatchMembership.batch_id == batch.id, InternBatchMembership.status == "Active").all()
                scoped = {row[0] for row in allowed_employees.all()}
                eligible = [e.user_id for e in members if e.id in scoped and e.user_id in ids and e.deleted_at is None and e.status not in {"Terminated", "Inactive", "Suspended"}]
                batches.append({"id": batch.id, "name": batch.name, "member_ids": sorted(set(eligible)), "excluded_count": len(members) - len(set(eligible))})
            batch_reason = "Only active batches linked to this project and within your management scope are listed."
    return {"people": [public_person(db, u) for u in candidates], "teams": teams, "batches": batches,
            "reviewers": [u.id for u in candidates if can_access_project(db, project, u, "approve")],
            "batch_reason": batch_reason, "workspace_id": project.workspace_id,
            "can_edit": can_access_project(db, project, user, "manage_tasks"),
            "can_add_existing": can_access_project(db, project, user, "manage_members")}


@router.get("/projects")
def projects(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from .models import PMSProject
    return [{"id":p.id,"name":p.name,"project_key":p.project_key,"workspace_id":p.workspace_id,
             "can_manage_tasks":can_access_project(db,p,user,"manage_tasks")}
            for p in accessible_project_query(db,user).order_by(PMSProject.name).all()]


@router.get("/options")
def options(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return choices(db, get_project_for_action(db, project_id, user, "browse"), user)


def resolve(db, project, user, selection, preserved_ids=frozenset()):
    options = choices(db, project, user)
    eligible = {p["id"] for p in options["people"]}
    ids = set(selection.people)
    if not ids.issubset(eligible | set(preserved_ids)):
        raise HTTPException(422, "Choose active people with access to the selected project. Add existing people to its workspace first.")
    snapshots = []
    for kind, values in [("teams", selection.teams), ("batches", selection.batches)]:
        indexed = {g["id"]: g for g in options[kind]}
        for identity in set(values):
            item = indexed.get(identity)
            if not item:
                raise HTTPException(422, "A selected group is unavailable in this project or outside your management scope")
            if not item["member_ids"]:
                raise HTTPException(422, "A selected group has no eligible members")
            if item["excluded_count"] and not selection.allow_partial_groups:
                raise HTTPException(422, "Some group members cannot receive this task. Review exclusions and explicitly choose eligible members only.")
            ids.update(item["member_ids"])
            snapshots.append({"kind": kind, **item})
    if len(ids) > 100:
        raise HTTPException(422, "Choose at most 100 unique task assignees")
    if selection.owner and selection.owner not in eligible:
        raise HTTPException(422, "Owner must be an active project collaborator")
    if selection.reviewer and selection.reviewer not in options["reviewers"]:
        raise HTTPException(422, "Reviewer must have approval permission in this project")
    return sorted(ids), {**selection.model_dump(), "groups": snapshots, "resolved_ids": sorted(ids)}


def version(db, task):
    latest = db.query(PMSActivity.id).filter(PMSActivity.task_id == task.id, PMSActivity.action.in_(["task.created", "task.updated", "task.assignment_selection", "task.deleted", "task.restored", "task.moved"])).order_by(PMSActivity.id.desc()).first()
    return (task.updated_at or task.created_at).isoformat() + ":" + str(latest[0] if latest else 0)


def detail(db, task, project, user):
    event = db.query(PMSActivity).filter_by(task_id=task.id, action="task.assignment_selection").order_by(PMSActivity.id.desc()).first()
    selection = json.loads(event.metadata_json) if event else {"people": task.assignee_user_ids, "teams": [], "batches": [], "reviewer": None, "owner": None}
    # Changes made from another PMS surface remain visible as individual selections.
    if event and set(selection.get("resolved_ids", [])) != set(task.assignee_user_ids):
        selection = {**selection, "people": task.assignee_user_ids, "teams": [], "batches": []}
    return {"task": PMSTaskResponse.model_validate(task).model_dump(), "assignment": {key: selection.get(key, default) for key, default in Selection().model_dump().items()},
            "version": version(db, task), "can_edit": can_access_project(db, project, user, "manage_tasks"),
            "protected_ids": [a.user_id for a in task.assignments if a.source_key],
            "retained_people": [public_person(db, account) for account in db.query(User).filter(User.id.in_([a.user_id for a in task.assignments if a.source_key])).all()]}


@router.get("/tasks/{task_id}")
def get(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task, project = get_task_project_for_action(db, task_id, user, "browse")
    return detail(db, task, project, user)


def record(db, task, user, selection):
    from .api.router import _record_activity
    for row in task.assignments:
        if not row.source_key:
            row.reviewer_user_id = selection["reviewer"]
    _record_activity(db, task.project_id, user, "task.assignment_selection", "task", task.id,
                     f"Updated assignment selections for {task.task_key}", task_id=task.id, metadata=selection)


@router.post("/projects/{project_id}/tasks", status_code=201)
def create(project_id: int, data: CreateInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from .api.router import create_task_operation
    project = get_project_for_action(db, project_id, user, "manage_tasks")
    data.task.task_key = data.task.task_key.strip().upper()
    if not data.task.task_key:
        raise HTTPException(422, "Enter a task key")
    ids, selection = resolve(db, project, user, data.assignment)
    fingerprint = hashlib.sha256(json.dumps(data.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
    existing = db.query(PMSTask).filter_by(project_id=project_id, task_key=data.task.task_key.upper()).first()
    if existing:
        event = db.query(PMSActivity).filter_by(task_id=existing.id, action="task.assignment_selection", actor_user_id=user.id).order_by(PMSActivity.id.desc()).first()
        if not existing.deleted_at and event and json.loads(event.metadata_json).get("request_hash") == fingerprint:
            return detail(db, existing, project, user)
        raise HTTPException(409, "This task key is already used. Reload or start a new draft.")
    selection["request_hash"] = fingerprint
    try:
        task = create_task_operation(project_id, data.task.model_copy(update={"assignee_user_ids": ids}), db, user, commit=False)
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
    _broadcast_realtime(user, kind, project_id=task.project_id, task_id=task.id,
                        message=f"Saved task {task.task_key}", entity={"id":task.id,"taskKey":task.task_key,"title":task.title,"status":task.status})


@router.put("/tasks/{task_id}")
def update(task_id: int, data: UpdateInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from .api.router import update_task_operation
    task, project = get_task_project_for_action(db, task_id, user, "manage_tasks")
    if project.workspace_id:
        from .models import PMSWorkspace
        db.query(PMSWorkspace).filter_by(id=project.workspace_id).with_for_update().one()
    db.query(PMSTask).filter_by(id=task.id).with_for_update().one()
    db.refresh(task)
    if version(db, task) != data.version:
        raise HTTPException(409, "This task changed since you opened it. Reload the latest version before saving; your draft is kept.")
    protected = {a.user_id for a in task.assignments if a.source_key}
    ids, selection = resolve(db, project, user, data.assignment, protected)
    if not protected.issubset(ids):
        raise HTTPException(409, "Batch-controlled assignments must be removed from Batch controls. Their work history is protected.")
    active_ids = {p["id"] for p in choices(db, project, user)["people"]}
    editable_ids = [identity for identity in ids if identity in active_ids]
    try:
        task = update_task_operation(task_id, data.task.model_copy(update={"assignee_user_ids": editable_ids}), db, user, commit=False)
        record(db, task, user, selection)
        db.commit()
        db.refresh(task)
    except Exception:
        db.rollback()
        raise
    publish(user, task, "task.updated")
    return detail(db, task, project, user)
