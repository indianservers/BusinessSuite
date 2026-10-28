"""Reusable PMS task packs and audited per-assignee bulk deadline changes."""
from datetime import date, timedelta
import hashlib
import json
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.models.employee import Employee
from app.models.user import User
from app.models.notification import Notification
from app.apps.srm.services.commercial import tenant
from app.apps.project_management.models import (PMSTask, PMSTaskAssignee, PMSInternTaskPack,
    PMSInternPackRun, PMSInternAssignmentPlan, PMSBulkDeadlineChange, PMSProject)
from app.apps.project_management.schemas import PMSTaskCreate
from app.apps.project_management.access import get_project_for_action, can_access_project
from app.apps.project_management.work import activity
from .management_access import require_admin, get_batch, employee_query, organization_admin
from .management_models import InternBatchMembership

router = APIRouter(prefix="/learning", tags=["Intern Task Programs"])
LEVELS = ("beginner", "intermediate", "advanced")


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Criterion(StrictInput):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    label: str = Field(min_length=1, max_length=120)
    points: int = Field(ge=1, le=1000)
    description: str = Field(default="", max_length=1000)


class Variant(StrictInput):
    title: str = Field(min_length=1, max_length=180)
    instructions: str = Field(min_length=1, max_length=5000)
    deliverables: str = Field(min_length=1, max_length=3000)
    rubric: list[Criterion] = Field(min_length=1, max_length=15)

    @model_validator(mode="after")
    def valid_rubric(self):
        if len({c.key for c in self.rubric}) != len(self.rubric) or sum(c.points for c in self.rubric) > 1000:
            raise ValueError("Use unique rubric keys and a total score of at most 1,000")
        return self


class PackStep(StrictInput):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    week: int = Field(ge=1, le=52)
    due_day: int = Field(default=4, ge=0, le=6)
    depends_on: list[str] = Field(default_factory=list, max_length=20)
    variants: dict[Literal["beginner", "intermediate", "advanced"], Variant]

    @model_validator(mode="after")
    def all_levels(self):
        if set(self.variants) != set(LEVELS):
            raise ValueError("Define beginner, intermediate and advanced variants for each step")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError("Dependencies must be unique")
        return self


class PackInput(StrictInput):
    project_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    steps: list[PackStep] = Field(min_length=1, max_length=20)
    is_active: bool = True
    version: int | None = None

    @model_validator(mode="after")
    def dependency_order(self):
        seen = {}
        for step in self.steps:
            if step.key in seen:
                raise ValueError("Step keys must be unique")
            for key in step.depends_on:
                if key not in seen:
                    raise ValueError("Dependencies must refer to an earlier step; cycles are not allowed")
                if (seen[key].week, seen[key].due_day) > (step.week, step.due_day):
                    raise ValueError("A prerequisite cannot be due after its dependent step")
            seen[step.key] = step
        return self


class PackPublish(StrictInput):
    batch_id: int = Field(gt=0)
    pack_version: int = Field(gt=0)
    start_date: date
    reviewer_user_id: int = Field(gt=0)
    levels: dict[Literal["beginner", "intermediate", "advanced"], list[int]]
    request_key: str = Field(min_length=8, max_length=100)

    @model_validator(mode="after")
    def unique_people(self):
        ids = [identity for values in self.levels.values() for identity in values]
        if not ids or len(ids) > 500 or any(identity <= 0 for identity in ids) or len(ids) != len(set(ids)):
            raise ValueError("Select 1–500 interns, with each intern assigned exactly one skill level")
        return self


class AssignmentRef(StrictInput):
    task_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    expected_due_date: date


class DeadlineInput(StrictInput):
    project_id: int = Field(gt=0)
    assignments: list[AssignmentRef] = Field(min_length=1, max_length=500)
    due_date: date
    reason: str = Field(min_length=5, max_length=2000)
    request_key: str = Field(min_length=8, max_length=100)

    @model_validator(mode="after")
    def unique_assignments(self):
        if len({(a.task_id, a.user_id) for a in self.assignments}) != len(self.assignments):
            raise ValueError("Select each assignment only once")
        return self


def digest(data):
    return hashlib.sha256(json.dumps(data.model_dump(mode="json", exclude={"request_key"}), sort_keys=True).encode()).hexdigest()


def existing_request(db, model, org, key, request_hash):
    row = db.query(model).filter(model.organization_id == org, model.request_key == key).first()
    if row and row.request_hash != request_hash:
        raise HTTPException(409, "Request key already used with different values")
    return row


def program_project(db, user, project_id, action="manage_tasks"):
    project = get_project_for_action(db, project_id, user, action)
    if (project.organization_id or 1) != tenant(user):
        raise HTTPException(404, "Project not found in your company")
    return project


def pack_row(db, user, identity, action="manage_tasks"):
    row = db.query(PMSInternTaskPack).filter(PMSInternTaskPack.id == identity, PMSInternTaskPack.organization_id == tenant(user)).first()
    if not row:
        raise HTTPException(404, "Task pack not found")
    program_project(db, user, row.project_id, action)
    return row


def pack_out(row):
    return {key: getattr(row, key) for key in ("id", "project_id", "name", "description", "steps", "version", "is_active")}


@router.get("/packs")
def packs(project_id: int, db: Session = Depends(get_db), user=Depends(require_admin)):
    program_project(db, user, project_id)
    return [pack_out(row) for row in db.query(PMSInternTaskPack).filter(PMSInternTaskPack.organization_id == tenant(user), PMSInternTaskPack.project_id == project_id).order_by(PMSInternTaskPack.name)]


@router.post("/packs", status_code=201)
def create_pack(data: PackInput, db: Session = Depends(get_db), user=Depends(require_admin)):
    if program_project(db, user, data.project_id).is_archived:
        raise HTTPException(409, "Project is archived")
    row = PMSInternTaskPack(**data.model_dump(exclude={"version"}), organization_id=tenant(user), created_by=user.id)
    db.add(row); db.commit()
    return pack_out(row)


@router.put("/packs/{identity}")
def edit_pack(identity: int, data: PackInput, db: Session = Depends(get_db), user=Depends(require_admin)):
    row = pack_row(db, user, identity)
    if program_project(db, user, row.project_id).is_archived:
        raise HTTPException(409, "Project is archived")
    if data.project_id != row.project_id:
        raise HTTPException(422, "Duplicate the pack to use another project")
    count = db.query(PMSInternTaskPack).filter(PMSInternTaskPack.id == identity, PMSInternTaskPack.organization_id == tenant(user), PMSInternTaskPack.version == data.version).update({**data.model_dump(exclude={"version"}), "version": PMSInternTaskPack.version+1}, synchronize_session=False)
    if not count:
        raise HTTPException(409, "Task pack changed. Reload before saving.")
    db.commit(); db.refresh(row)
    return pack_out(row)


def batch_people(db, user, batch_id):
    get_batch(db, user, batch_id)
    members = db.query(InternBatchMembership.employee_id).filter(InternBatchMembership.batch_id == batch_id, InternBatchMembership.status == "Active")
    return employee_query(db, user).join(User, User.id == Employee.user_id).filter(Employee.id.in_(members), Employee.status.in_(["Active", "Probation"]), User.is_active.is_(True))


@router.get("/batches/{identity}/recipients")
def roster(identity: int, db: Session = Depends(get_db), user=Depends(require_admin)):
    query = batch_people(db, user, identity)
    return {"total": query.count(), "items": [{"id": e.id, "name": f"{e.first_name} {e.last_name}", "code": e.employee_id} for e in query.order_by(Employee.first_name, Employee.id).limit(501)]}


def prepare_pack(db, user, identity, data):
    row = pack_row(db, user, identity)
    if program_project(db, user, row.project_id).is_archived:
        raise HTTPException(409, "Project is archived")
    if row.version != data.pack_version:
        raise HTTPException(409, "Task pack changed. Reload and preview again.")
    if not row.is_active:
        raise HTTPException(409, "This task pack is archived")
    batch = get_batch(db, user, data.batch_id)
    if batch.status not in {"Upcoming", "Active", "Evaluation"}:
        raise HTTPException(409, "Choose a live batch")
    if row.project_id not in {batch.project_id, *(batch.project_ids or [])}:
        raise HTTPException(422, "Pack project must be linked to the selected batch")
    from .router import today
    if data.start_date < today():
        raise HTTPException(422, "Pack start date cannot be in the past")
    reviewer = db.get(User, data.reviewer_user_id)
    if not reviewer or not reviewer.is_active or tenant(reviewer) != tenant(user):
        raise HTTPException(403, "Choose an authorized reviewer in your company")
    require_admin(reviewer)
    if not can_access_project(db, program_project(db, user, row.project_id), reviewer, "approve"):
        raise HTTPException(403, "Reviewer requires PMS approval permission")
    selected = {i for ids in data.levels.values() for i in ids}
    people = {e.id: e for e in batch_people(db, user, data.batch_id).filter(Employee.id.in_(selected))}
    if set(people) != selected:
        raise HTTPException(403, "One or more interns are outside this batch, inactive, or outside your scope")
    if len(people)*len(row.steps) > 5000:
        raise HTTPException(422, "Publish at most 5,000 individual assignments per run; split the selection")
    schedule = []
    try:
        for step in row.steps:
            for level in LEVELS:
                if data.levels.get(level):
                    schedule.append({"step_key": step["key"], "level": level, "title": step["variants"][level]["title"],
                        "week": step["week"], "due_date": str(data.start_date+timedelta(days=(step["week"]-1)*7+step["due_day"])),
                        "recipients": len(data.levels[level]), "depends_on": step["depends_on"]})
    except OverflowError:
        raise HTTPException(422, "Pack dates exceed the supported calendar") from None
    return row, people, schedule


@router.post("/packs/{identity}/preview")
def preview_pack(identity: int, data: PackPublish, db: Session = Depends(get_db), user=Depends(require_admin)):
    row, people, schedule = prepare_pack(db, user, identity, data)
    return {"pack_version": row.version, "interns": len(people), "tasks": len(schedule), "assignments": len(people)*len(row.steps), "schedule": schedule}


@router.post("/packs/{identity}/publish", status_code=201)
def publish_pack(identity: int, data: PackPublish, db: Session = Depends(get_db), user=Depends(require_admin)):
    pack_row(db, user, identity)
    request_hash = hashlib.sha256((str(identity)+digest(data)).encode()).hexdigest()
    previous = existing_request(db, PMSInternPackRun, tenant(user), data.request_key, request_hash)
    if previous:
        return previous.result
    row, people, schedule = prepare_pack(db, user, identity, data)
    run = PMSInternPackRun(organization_id=tenant(user), project_id=row.project_id, pack_id=row.id, pack_version=row.version,
        snapshot={"pack": pack_out(row), "selection": data.model_dump(mode="json"), "schedule": schedule}, result={},
        request_key=data.request_key, request_hash=request_hash, created_by=user.id)
    db.add(run)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        previous = existing_request(db, PMSInternPackRun, tenant(user), data.request_key, request_hash)
        if previous:
            return previous.result
        raise
    from app.apps.project_management.api.router import create_task_operation
    task_ids = {}
    for entry in schedule:
        step = next(s for s in row.steps if s["key"] == entry["step_key"])
        variant = step["variants"][entry["level"]]
        rubric = variant["rubric"]
        description = variant["instructions"] + "\n\nDeliverables:\n" + variant["deliverables"]
        description += "\n\nEvaluation rubric:\n" + "\n".join(f'{c["label"]}: {c["points"]} points — {c["description"]}' for c in rubric)
        task = create_task_operation(row.project_id, PMSTaskCreate(title=variant["title"], description=description,
            task_key="PK-"+uuid4().hex[:20].upper(), start_date=data.start_date+timedelta(days=(step["week"]-1)*7),
            due_date=date.fromisoformat(entry["due_date"])), db, user, commit=False)
        task_ids[(step["key"], entry["level"])] = task.id
        for employee_id in data.levels[entry["level"]]:
            person = people[employee_id]
            db.add(PMSTaskAssignee(task_id=task.id, user_id=person.user_id, due_date=task.due_date,
                reviewer_user_id=data.reviewer_user_id, maximum_score=sum(c["points"] for c in rubric), source_key=f"intern-pack:{run.id}"))
            db.add(PMSInternAssignmentPlan(task_id=task.id, user_id=person.user_id, run_id=run.id, step_key=step["key"],
                skill_level=entry["level"], prerequisites=[task_ids[(key, entry["level"])] for key in step["depends_on"]], rubric=rubric))
        activity(db, task, user, "task_pack.published", metadata={"run_id": run.id, "pack_id": row.id, "pack_version": row.version, "skill_level": entry["level"]})
    for person in people.values():
        db.add(Notification(user_id=person.user_id, company_id=tenant(user), title="New internship task pack",
            message=f"{row.name}: {len(row.steps)} assignments starting {data.start_date}. Open My Tasks for your instructions and deadlines.",
            module="hrms", event_type="intern_task_pack", channels=["in_app"], is_read=False))
    run.result = {"run_id": run.id, "pack_version": row.version, "interns": len(people), "assignments": len(people)*len(row.steps), "tasks": len(task_ids), "task_ids": list(task_ids.values())}
    db.commit()
    return run.result


@router.get("/runs")
def runs(project_id: int, page: int = Query(default=1, ge=1), db: Session = Depends(get_db), user=Depends(require_admin)):
    program_project(db, user, project_id)
    query = db.query(PMSInternPackRun).filter(PMSInternPackRun.organization_id == tenant(user), PMSInternPackRun.project_id == project_id)
    return {"total": query.count(), "items": [{"id": r.id, "name": r.snapshot["pack"]["name"], "pack_version": r.pack_version, "created_at": r.created_at, **r.result} for r in query.order_by(PMSInternPackRun.id.desc()).offset((page-1)*20).limit(20)]}


@router.get("/assignments")
def assignments(project_id: int, batch_id: int | None = None, page: int = Query(default=1, ge=1), db: Session = Depends(get_db), user=Depends(require_admin)):
    program_project(db, user, project_id)
    people = batch_people(db, user, batch_id) if batch_id else employee_query(db, user)
    query = db.query(PMSTaskAssignee, PMSTask, Employee).join(PMSTask, PMSTask.id == PMSTaskAssignee.task_id).join(Employee, Employee.user_id == PMSTaskAssignee.user_id).filter(
        PMSTask.project_id == project_id, PMSTask.deleted_at.is_(None), Employee.id.in_(people.with_entities(Employee.id)),
        PMSTaskAssignee.cancelled_at.is_(None), PMSTaskAssignee.execution_status != "Done")
    return {"total": query.count(), "items": [{"task_id": t.id, "user_id": a.user_id, "employee_id": e.id, "intern": f"{e.first_name} {e.last_name}",
        "task": t.title, "status": a.execution_status, "due_date": a.due_date or t.due_date} for a, t, e in query.order_by(PMSTask.id, PMSTaskAssignee.user_id).offset((page-1)*50).limit(50)]}


def deadline_selection(db, user, data, lock=False):
    if program_project(db, user, data.project_id).is_archived:
        raise HTTPException(409, "Project is archived")
    from .router import today
    if data.due_date < today():
        raise HTTPException(422, "New deadline cannot be in the past")
    people = employee_query(db, user).with_entities(Employee.user_id)
    task_ids = {a.task_id for a in data.assignments}
    user_ids = {a.user_id for a in data.assignments}
    query = db.query(PMSTaskAssignee, PMSTask).join(PMSTask, PMSTask.id == PMSTaskAssignee.task_id).filter(PMSTask.project_id == data.project_id,
        PMSTask.deleted_at.is_(None), PMSTaskAssignee.user_id.in_(people), PMSTaskAssignee.task_id.in_(task_ids), PMSTaskAssignee.user_id.in_(user_ids)).order_by(PMSTaskAssignee.task_id, PMSTaskAssignee.user_id)
    if lock:
        query = query.with_for_update(of=PMSTaskAssignee)
    available = {(a.task_id, a.user_id): (a, t) for a, t in query}
    changes = []
    for ref in data.assignments:
        pair = available.get((ref.task_id, ref.user_id))
        if not pair:
            raise HTTPException(403, "One or more assignments are outside your authorized scope")
        assignment, task = pair
        old = assignment.due_date or task.due_date
        if assignment.cancelled_at or assignment.execution_status == "Done":
            raise HTTPException(409, "Completed or cancelled assignments cannot be extended")
        if old != ref.expected_due_date:
            raise HTTPException(409, "A deadline changed. Refresh your selection and preview again.")
        if data.due_date <= old:
            raise HTTPException(422, "New deadline must be later than every selected assignment's current deadline")
        changes.append({"task_id": task.id, "user_id": assignment.user_id, "title": task.title, "old_due_date": str(old), "new_due_date": str(data.due_date)})
    return available, changes


@router.post("/deadlines/preview")
def preview_deadlines(data: DeadlineInput, db: Session = Depends(get_db), user=Depends(require_admin)):
    _, changes = deadline_selection(db, user, data)
    return {"count": len(changes), "changes": changes}


@router.post("/deadlines/extend")
def extend_deadlines(data: DeadlineInput, db: Session = Depends(get_db), user=Depends(require_admin)):
    program_project(db, user, data.project_id)
    db.query(PMSProject.id).filter(PMSProject.id == data.project_id).with_for_update().one()
    request_hash = digest(data)
    previous = existing_request(db, PMSBulkDeadlineChange, tenant(user), data.request_key, request_hash)
    if previous:
        return {"id": previous.id, "count": len(previous.changes), "changes": previous.changes}
    available, changes = deadline_selection(db, user, data, lock=True)
    record = PMSBulkDeadlineChange(organization_id=tenant(user), project_id=data.project_id, reason=data.reason, changes=changes,
        request_key=data.request_key, request_hash=request_hash, created_by=user.id)
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        previous = existing_request(db, PMSBulkDeadlineChange, tenant(user), data.request_key, request_hash)
        if previous:
            return {"id": previous.id, "count": len(previous.changes), "changes": previous.changes}
        raise
    for change in changes:
        assignment, task = available[(change["task_id"], change["user_id"])]
        assignment.due_date = data.due_date
        activity(db, task, user, "assignment.deadline_extended", metadata={**change, "reason": data.reason, "bulk_change_id": record.id})
        db.add(Notification(user_id=assignment.user_id, company_id=tenant(user), title="Assignment deadline extended",
            message=f'{task.title}: {change["old_due_date"]} → {data.due_date}. Reason: {data.reason}', module="hrms",
            event_type="intern_deadline_extended", channels=["in_app"], is_read=False))
    db.commit()
    return {"id": record.id, "count": len(changes), "changes": changes}


@router.get("/deadlines/history")
def deadline_history(project_id: int, page: int = Query(default=1, ge=1), db: Session = Depends(get_db), user=Depends(require_admin)):
    program_project(db, user, project_id)
    query = db.query(PMSBulkDeadlineChange).filter(PMSBulkDeadlineChange.organization_id == tenant(user), PMSBulkDeadlineChange.project_id == project_id)
    if not organization_admin(user):
        query = query.filter(PMSBulkDeadlineChange.created_by == user.id)
    return {"total": query.count(), "items": [{"id": r.id, "reason": r.reason, "count": len(r.changes), "created_by": r.created_by, "created_at": r.created_at, "changes": r.changes} for r in query.order_by(PMSBulkDeadlineChange.id.desc()).offset((page-1)*20).limit(20)]}
