"""Permission-checked, optimistic assignment editing for the My Work workspace."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.user import User
from .access import get_task_project_for_action, organization_id_for
from .models import PMSTask, PMSTaskGroupTarget
from . import task_studio

router = APIRouter(prefix="/my-work", tags=["PMS My Work"])


class TaskArrangeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group_by: str = Field(pattern="^(status|sprint)$")
    status: str | None = None
    sprint_id: int | None = None
    before_id: int | None = None
    version: str


@router.post("/tasks/{task_id}/arrange")
def arrange_task(task_id: int, data: TaskArrangeInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Move and rank in a single transaction; preserve hidden siblings in filtered lists."""
    from .api.router import update_task_operation, move_task_to_sprint_operation, _record_activity, TaskSprintMoveRequest
    from .schemas import PMSTaskUpdate
    from .models import PMSProject, PMSSprint
    task, project = get_task_project_for_action(db, task_id, user, "manage_tasks")
    db.query(PMSProject).filter_by(id=project.id).with_for_update().one()
    db.refresh(task)
    if task_studio.version(db, task) != data.version:
        raise HTTPException(409, "This task changed. Refresh before moving it.")
    before = None
    if data.before_id:
        before, _ = get_task_project_for_action(db, data.before_id, user, "manage_tasks")
        if before.id == task.id or before.project_id != project.id:
            raise HTTPException(422, "Reorder tasks within the same project.")
    try:
        if data.group_by == "status":
            target = data.status or task.status
            if before and before.status != target:
                raise HTTPException(409, "The destination task moved. Refresh and try again.")
            update_task_operation(task.id, PMSTaskUpdate(status=target), db, user, commit=False)
            siblings = db.query(PMSTask).filter(PMSTask.project_id == project.id, PMSTask.status == target, PMSTask.deleted_at.is_(None), PMSTask.id != task.id).order_by(PMSTask.position, PMSTask.id).all()
            field = "position"
        else:
            old_sprint_id = task.sprint_id
            if old_sprint_id and db.query(PMSSprint).filter_by(id=old_sprint_id, status="Completed").first():
                raise HTTPException(409, "Completed sprint history cannot be rearranged.")
            if before and before.sprint_id != data.sprint_id:
                raise HTTPException(409, "The destination task moved. Refresh and try again.")
            if data.sprint_id:
                move_task_to_sprint_operation(task.id, TaskSprintMoveRequest(sprint_id=data.sprint_id), db, user, commit=False)
            else:
                task.sprint_id = None
                if old_sprint_id:
                    old = db.query(PMSSprint).filter_by(id=old_sprint_id).first()
                    if old and old.status == "Active": old.scope_change_count = (old.scope_change_count or 0) + 1
            siblings = db.query(PMSTask).filter(PMSTask.project_id == project.id, PMSTask.sprint_id == data.sprint_id, PMSTask.deleted_at.is_(None), PMSTask.id != task.id).order_by(PMSTask.rank.is_(None), PMSTask.rank, PMSTask.id).all()
            field = "rank"
        index = next((i for i, item in enumerate(siblings) if before and item.id == before.id), len(siblings))
        siblings.insert(index, task)
        for index, item in enumerate(siblings): setattr(item, field, index + (1 if field == "rank" else 0))
        _record_activity(db, project.id, user, "task.reordered", "task", task.id, f"Rearranged {task.task_key}", task_id=task.id, metadata={"group_by": data.group_by, "status": task.status, "sprint_id": task.sprint_id, "before_id": data.before_id})
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"id": task.id, "version": task_studio.version(db, task)}


class AssignmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    people: list[int] = Field(default_factory=list, max_length=100)
    teams: list[int] = Field(default_factory=list, max_length=50)
    batches: list[int] = Field(default_factory=list, max_length=50)
    version: str
    note: str = Field("", max_length=2000)
    notify: bool = True


def targets(db, task_id):
    return [{"id": g.target_id, "kind": g.kind, "name": g.name, "member_count": g.member_count}
            for g in db.query(PMSTaskGroupTarget).filter_by(task_id=task_id)]


@router.get("/tasks/{task_id}/assignment")
def assignment(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task, project = get_task_project_for_action(db, task_id, user, "browse")
    return {**task_studio.detail(db, task, project, user), "group_targets": targets(db, task.id)}


@router.put("/tasks/{task_id}/assignment")
def save_assignment(task_id: int, data: AssignmentInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from .api.router import update_task_operation, _record_activity
    from .schemas import PMSTaskUpdate
    from app.models.notification import Notification
    task, project = get_task_project_for_action(db, task_id, user, "manage_tasks")
    if project.workspace_id:
        from .models import PMSWorkspace
        db.query(PMSWorkspace).filter_by(id=project.workspace_id).with_for_update().one()
    db.query(PMSTask).filter_by(id=task.id).with_for_update().one()
    db.refresh(task)
    if task_studio.version(db, task) != data.version:
        raise HTTPException(409, "This task changed. Reopen assignment to load the latest version.")
    protected = {a.user_id for a in task.assignments if a.source_key}
    previous = task_studio.detail(db, task, project, user)["assignment"]
    ids, selection = task_studio.resolve(db, project, user, task_studio.Selection(people=data.people, owner=previous.get("owner"), reviewer=previous.get("reviewer")), protected)
    if not protected.issubset(ids):
        raise HTTPException(409, "Batch-controlled work must be removed from Batch controls; its history is protected.")
    options = task_studio.choices(db, project, user, compact=True)
    groups = []
    for kind, chosen in (("teams", data.teams), ("batches", data.batches)):
        available = {g["id"]: g for g in options[kind]}
        for identity in set(chosen):
            group = available.get(identity)
            if not group:
                raise HTTPException(422, "A selected group is unavailable in this project's scope.")
            groups.append((kind, group))
    try:
        update_task_operation(task.id, PMSTaskUpdate(assignee_user_ids=ids), db, user, commit=False)
        db.query(PMSTaskGroupTarget).filter_by(task_id=task.id).delete(synchronize_session=False)
        for kind, group in groups:
            db.add(PMSTaskGroupTarget(task_id=task.id, kind=kind, target_id=group["id"], name=group["name"],
                member_count=group.get("member_count", len(group["member_ids"])), assigned_by=user.id))
        task_studio.record(db, task, user, selection)
        _record_activity(db, project.id, user, "task.group_assignment", "task", task.id,
            f"Updated responsibility for {task.task_key}", task_id=task.id,
            metadata={"people": ids, "groups": [{"kind": kind, "id": g["id"], "name": g["name"]} for kind, g in groups], "note": data.note})
        if data.notify:
            # Group responsibility does not enroll every member in individual execution.
            for identity in set(ids) - {user.id}:
                db.add(Notification(company_id=organization_id_for(user), user_id=identity, title="Task assignment updated",
                    message=f"{task.title}" + (f" — {data.note}" if data.note else ""), module="project_management",
                    event_type="task.assigned", action_url=f"/pms/tasks/{task.id}"))
        db.commit()
    except Exception:
        db.rollback()
        raise
    task_studio.publish(user, task, "task.updated")
    return assignment(task.id, db, user)
