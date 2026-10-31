"""Management views share the same object permissions and mutation services as PMS."""
from datetime import date, timedelta
from uuid import uuid4
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from app.core.deps import get_db, get_current_user
from app.models.user import User
from .models import (PMSProject, PMSTask, PMSWorkspace, PMSMilestone, PMSChecklistItem,
    PMSTaskExecution, PMSFileAsset, PMSTaskDependency, PMSTaskAssignee, PMSNoteTaskLink,
    PMSUserCapacity, PMSPlannerPreference, PMSClientApproval, PMSProjectMember, PMSTimeLog, PMSComment, PMSMention, PMSDevLink)
from .access import accessible_project_query, get_project_for_action, get_task_project_for_action, can_access_project, organization_id_for
from .people_management import public_person, scoped_person, organization_admin

router = APIRouter(prefix="/management", tags=["PMS management"])
CLOSED = {"Done", "Completed", "Closed", "Cancelled", "Canceled", "Resolved"}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def completion(db, task):
    checks = db.query(PMSChecklistItem).filter_by(task_id=task.id).order_by(PMSChecklistItem.position).all()
    children = db.query(PMSTask).filter_by(parent_task_id=task.id, deleted_at=None).all()
    execution = db.get(PMSTaskExecution, task.id)
    blockers = ["Complete all checklist items"] if any(not c.is_completed for c in checks) else []
    if any(c.status not in CLOSED for c in children): blockers.append("Complete open subtasks")
    if execution and execution.evidence_required and not (execution.evidence or "").strip(): blockers.append("Provide required completion evidence")
    if db.query(PMSTaskAssignee).filter(PMSTaskAssignee.task_id == task.id, PMSTaskAssignee.source_key.isnot(None), PMSTaskAssignee.execution_status != "Done").first(): blockers.append("Approve each work submission")
    return {"checklist": [{"id": c.id, "title": c.title, "done": c.is_completed} for c in checks],
        "subtasks": [{"id": c.id, "title": c.title, "done": c.status in CLOSED} for c in children], "blockers": blockers}


def guard_transition(db, task, status):
    if status in {"Done", "Completed", "Closed", "Resolved", "In Review"}:
        from .models import PMSTaskUpdateEntry
        if db.query(PMSTaskUpdateEntry).filter_by(task_id=task.id, kind="blocker", resolved=False, deleted_at=None).first():
            raise HTTPException(409, "Resolve open task blockers before submitting or completing work")
    if status in {"Done", "Completed", "Closed", "Resolved"}:
        blockers = completion(db, task)["blockers"]
        if blockers: raise HTTPException(409, "; ".join(blockers))
    if status == "Blocked":
        execution = db.get(PMSTaskExecution, task.id)
        if not execution or not (execution.blocked_reason or "").strip() or not execution.responsible_user_id or not execution.review_date:
            raise HTTPException(409, "Set a blocked reason, responsible person, and next review date in task execution details first")


def task_row(db, task, execution_map=None):
    execution = execution_map.get(task.id) if execution_map is not None else db.get(PMSTaskExecution, task.id)
    return {"id": task.id, "project_id": task.project_id, "title": task.title, "task_key": task.task_key,
        "status": task.status, "priority": task.priority, "due_date": task.due_date,
        "assignee_user_ids": task.assignee_user_ids, "estimated_hours": float(task.estimated_hours or 0),
        "blocked_reason": execution.blocked_reason if execution else None,
        "responsible_user_id": execution.responsible_user_id if execution else None,
        "review_date": execution.review_date if execution else None}


@router.get("/home")
def home(workspace_id: int | None = None, project_id: int | None = None, mine: bool = False,
         db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = accessible_project_query(db, user)
    if workspace_id: query = query.filter(PMSProject.workspace_id == workspace_id)
    if project_id: query = query.filter(PMSProject.id == project_id)
    projects = query.order_by(PMSProject.name).all()
    ids = [p.id for p in projects]
    tasks = db.query(PMSTask).filter(PMSTask.project_id.in_(ids), PMSTask.deleted_at.is_(None)).order_by(PMSTask.id).all() if ids else []
    people_ids = {u for t in tasks for u in t.assignee_user_ids} | {p.owner_user_id for p in projects if p.owner_user_id} | {user.id}
    teams = db.query(PMSProjectMember).filter(PMSProjectMember.project_id.in_(ids)).all() if ids else []
    people_ids |= {m.user_id for m in teams}
    from .models import PMSWorkspaceMember
    wsids = {p.workspace_id for p in projects if p.workspace_id}
    if wsids: people_ids |= {m.user_id for m in db.query(PMSWorkspaceMember).filter(PMSWorkspaceMember.workspace_id.in_(wsids))}
    from app.common.models import CommonPerson
    people = db.query(User).options(joinedload(User.person).joinedload(CommonPerson.profile), joinedload(User.role), joinedload(User.employee)).filter(User.id.in_(people_ids)).all()
    today = date.today()
    rows = []
    milestones = db.query(PMSMilestone).filter(PMSMilestone.project_id.in_(ids)).all() if ids else []
    for p in projects:
        pt = [t for t in tasks if t.project_id == p.id]
        upcoming = sorted([m for m in milestones if m.project_id == p.id and m.status not in CLOSED], key=lambda m: m.due_date or date.max)
        rows.append({"is_task_collection": p.is_task_collection, "id": p.id, "name": p.name, "project_key": p.project_key, "workspace_id": p.workspace_id,
            "owner_user_id": p.owner_user_id, "status": p.status, "health": p.health, "due_date": p.due_date,
            "is_archived": p.is_archived, "progress": round(100 * sum(t.status in CLOSED for t in pt) / len(pt)) if pt else p.progress_percent or 0,
            "overdue": sum(bool(t.due_date and t.due_date < today and t.status not in CLOSED) for t in pt),
            "next_milestone": {"name": upcoming[0].name, "due_date": upcoming[0].due_date} if upcoming else None,
            "can_edit": can_access_project(db, p, user, "edit_project"), "can_manage_tasks": can_access_project(db, p, user, "manage_tasks"),
            "can_manage_members": can_access_project(db, p, user, "manage_members")})
    if mine: tasks = [t for t in tasks if user.id in t.assignee_user_ids or t.status == "In Review" and (t.reporter_user_id == user.id or can_access_project(db, next(p for p in projects if p.id == t.project_id), user, "approve"))]
    execution_map = {row.task_id:row for row in db.query(PMSTaskExecution).filter(PMSTaskExecution.task_id.in_([t.id for t in tasks]))} if tasks else {}
    taskrows = [{**task_row(db, t, execution_map), "review_for_me": t.status == "In Review" and (t.reporter_user_id == user.id or can_access_project(db, next(p for p in projects if p.id == t.project_id), user, "approve"))} for t in tasks]
    approvals = db.query(PMSClientApproval).filter(PMSClientApproval.project_id.in_(ids), PMSClientApproval.client_user_id == user.id, PMSClientApproval.status == "Pending").all() if ids else []
    from app.models.approval_os import ApprovalRequest
    own_approvals = db.query(ApprovalRequest).filter_by(organization_id=organization_id_for(user), assigned_to_user_id=user.id, status="Pending").all()
    return {"organization_id": organization_id_for(user), "workspace_id": workspace_id, "project_id": project_id,
        "projects": rows, "tasks": taskrows, "people": [public_person(db, p) for p in people],
        "workspaces": [{"id": w.id, "name": w.name} for w in db.query(PMSWorkspace).filter(PMSWorkspace.id.in_(wsids))],
        "approvals": [{"id": a.id, "title": a.title, "kind": "Approval", "href": "/pms/reviews"} for a in own_approvals] + [{"id": a.id, "title": f"Project #{a.project_id} client approval", "kind": "Client approval", "href": "/pms/client-portal"} for a in approvals],
        "can_manage": organization_admin(user) or any(r["can_edit"] for r in rows)}


class QuickTask(Strict):
    title: str = Field(min_length=1, max_length=220)
    project_id: int
    assignee_user_id: int | None = None
    due_date: date | None = None


@router.post("/quick-task", status_code=201)
def quick_task(data: QuickTask, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from .api.router import create_task_operation, _project_user_query
    from .schemas import PMSTaskCreate
    project = get_project_for_action(db, data.project_id, user, "manage_tasks")
    owner = data.assignee_user_id or (user.id if _project_user_query(db, project).filter(User.id == user.id).first() else None)
    if not data.title.strip(): raise HTTPException(422, "Enter a task title")
    task = create_task_operation(project.id, PMSTaskCreate(title=data.title.strip(), task_key=f"T-{uuid4().hex[:12]}", assignee_user_id=owner, due_date=data.due_date), db, user)
    return task_row(db, task)


class Execution(Strict):
    revision: int = Field(ge=0)
    blocked_reason: str = Field(default="", max_length=4000)
    responsible_user_id: int | None = None
    review_date: date | None = None
    evidence_required: bool = False
    evidence: str = Field(default="", max_length=10000)


@router.get("/tasks/{task_id}")
def details(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task, project = get_task_project_for_action(db, task_id, user)
    row = db.get(PMSTaskExecution, task.id)
    execution = {f: getattr(row, f) for f in Execution.model_fields} if row else Execution(revision=0).model_dump()
    from .note_actions import linked_note_source_payload
    return {**task_row(db, task), "execution": execution, "completion": completion(db, task), "can_edit": can_access_project(db, project, user, "manage_tasks"), "note_sources": linked_note_source_payload(db, task.id, user)}


@router.put("/tasks/{task_id}/execution")
def save_execution(task_id: int, data: Execution, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task, project = get_task_project_for_action(db, task_id, user, "manage_tasks")
    db.query(PMSTask).filter_by(id=task.id).with_for_update().one()
    row = db.get(PMSTaskExecution, task.id)
    if (row.revision if row else 0) != data.revision: raise HTTPException(409, "Execution details changed. Reload before saving")
    if data.responsible_user_id:
        from .api.router import _project_user_query
        if not _project_user_query(db, project).filter_by(id=data.responsible_user_id).first(): raise HTTPException(422, "Responsible person needs active project access")
    if task.status == "Blocked" and not (data.blocked_reason.strip() and data.responsible_user_id and data.review_date): raise HTTPException(422, "Blocked work needs a reason, responsible person and next review date")
    if task.status in CLOSED and data.evidence_required and not data.evidence.strip(): raise HTTPException(409, "Completed work requires its evidence")
    if not row: row = PMSTaskExecution(task_id=task.id); db.add(row)
    for key, value in data.model_dump(exclude={"revision"}).items(): setattr(row, key, value)
    row.revision = data.revision + 1
    from .api.router import _record_activity
    _record_activity(db, project.id, user, "task.execution_updated", "task", task.id, "Updated blocking and completion details", task_id=task.id)
    db.commit()
    return details(task_id, db, user)


class TaskChange(Strict):
    title: str | None = Field(default=None, min_length=1, max_length=220)
    status: Literal["Backlog", "To Do", "In Progress", "In Review", "Blocked", "Done"] | None = None
    priority: Literal["Low", "Medium", "High", "Urgent"] | None = None
    assignee_user_id: int | None = None
    due_date: date | None = None
    project_id: int | None = None


@router.patch("/tasks/{task_id}")
def change_task(task_id: int, data: TaskChange, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from .api.router import update_task_operation, _sync_task_planning_links, _record_activity
    from .schemas import PMSTaskUpdate
    task, project = get_task_project_for_action(db, task_id, user, "manage_tasks")
    values = data.model_dump(exclude_unset=True)
    destination = values.pop("project_id", None)
    if destination and destination != task.project_id:
        from .models import PMSTaskGroupTarget
        if db.query(PMSTaskGroupTarget).filter_by(task_id=task.id).first():
            raise HTTPException(409, "Remove team and batch responsibility before moving this task to another project")
        target = get_project_for_action(db, destination, user, "manage_tasks")
        if target.organization_id != project.organization_id: raise HTTPException(403, "Task moves must stay within the same organization")
        if target.is_archived: raise HTTPException(409, "Destination project is archived")
        if task.parent_task_id or db.query(PMSTask).filter_by(parent_task_id=task.id, deleted_at=None).first(): raise HTTPException(409, "Move parent and subtasks through the project workflow together")
        if db.query(PMSTaskAssignee).filter(PMSTaskAssignee.task_id == task.id, PMSTaskAssignee.source_key.isnot(None)).first(): raise HTTPException(409, "Source-managed task must be moved through its source workflow")
        if db.query(PMSTaskDependency).filter(or_(PMSTaskDependency.task_id == task.id, PMSTaskDependency.depends_on_task_id == task.id)).first(): raise HTTPException(409, "Resolve dependency links before moving this task")
        if db.query(PMSTimeLog).filter_by(task_id=task.id).first(): raise HTTPException(409, "Task has time or billing history; use its original project to preserve accounting")
        ids = [values["assignee_user_id"]] if values.get("assignee_user_id") else [] if "assignee_user_id" in values else task.assignee_user_ids
        _sync_task_planning_links(db, target.id, {"assignee_user_ids": ids})
        if db.query(PMSTask).filter_by(project_id=target.id, task_key=task.task_key).first(): raise HTTPException(409, "Task key already exists in destination")
        task.project_id = target.id
        for field in ("board_id", "column_id", "milestone_id", "sprint_id", "epic_id", "component_id", "release_id", "epic_key", "component", "release_name", "fix_version"): setattr(task, field, None)
        for model in (PMSFileAsset, PMSComment, PMSMention):
            for linked in db.query(model).filter_by(task_id=task.id): linked.project_id = target.id
        _record_activity(db, project.id, user, "task.moved", "task", task.id, f"Moved task to {target.project_key}", task_id=task.id, metadata={"destination_project_id": target.id})
        _record_activity(db, target.id, user, "task.moved", "task", task.id, f"Moved task from {project.project_key}", task_id=task.id)
        db.flush()
    if values.get("status"): guard_transition(db, task, values["status"])
    if values.get("title") is not None and not values["title"].strip(): raise HTTPException(422, "Enter a task title")
    warnings = assignment_warnings(task.project_id, values["assignee_user_id"], values.get("due_date") or task.due_date, db, user)["warnings"] if values.get("assignee_user_id") else []
    task = update_task_operation(task.id, PMSTaskUpdate(**values), db, user)
    return {**task_row(db, task), "warnings":warnings}


class ProjectChange(Strict):
    owner_user_id: int | None = None
    status: Literal["Draft", "Planned", "Active", "On Hold", "Completed", "Cancelled"] | None = None
    is_archived: bool | None = None
    member_user_ids: list[int] | None = Field(default=None, max_length=100)


@router.patch("/projects/{project_id}")
def change_project(project_id: int, data: ProjectChange, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = get_project_for_action(db, project_id, user, "edit_project")
    values = data.model_dump(exclude_unset=True)
    ids = values.pop("member_user_ids", None)
    if ids is not None:
        get_project_for_action(db, project_id, user, "manage_members")
        from .people_management import BulkAdd, bulk_add
        if not project.workspace_id: raise HTTPException(409, "Use the project team panel for legacy projects without a workspace")
        # Validate the whole item before invoking the transactional membership service.
        if any(k in values for k in ("owner_user_id", "status", "is_archived")): raise HTTPException(422, "Apply membership and project field changes separately")
        return bulk_add(BulkAdd(user_ids=ids, project_ids=[project.id], reason="Management home bulk project staffing"), db, user)
    if values.get("owner_user_id"):
        from .api.router import _project_user_query
        if not _project_user_query(db, project).filter(User.id == values["owner_user_id"]).first(): raise HTTPException(422, "Owner needs active project access; add the person first")
    from .api.router import update_project
    from .schemas import PMSProjectUpdate
    result = update_project(project.id, PMSProjectUpdate(**values), db, user)
    return {"id": result.id, "status": result.status, "is_archived": result.is_archived}


@router.get("/assignment-warnings")
def assignment_warnings(project_id: int, user_id: int, on: date | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = get_project_for_action(db, project_id, user, "manage_tasks")
    target = db.get(User, user_id)
    from .people_management import same_company
    from .models import PMSWorkspaceMember
    linked = db.query(PMSWorkspaceMember.id).filter_by(workspace_id=project.workspace_id, user_id=user_id).first() if project.workspace_id else db.query(PMSProjectMember.id).filter_by(project_id=project.id, user_id=user_id).first()
    if not target or not same_company(db,user,target) or not (linked or user_id in {project.owner_user_id,project.manager_user_id} or organization_admin(user)):
        raise HTTPException(404, "Person not found in this project scope")
    from .api.router import _project_user_query
    warnings = []
    if not target.is_active: warnings.append("This account is suspended or inactive")
    if not _project_user_query(db, project).filter(User.id == target.id).first(): warnings.append("Missing active project/workspace access; add the person first")
    from app.access.service import policy_for, resolved_grants
    policy=policy_for(db,target,organization_id_for(user))
    if policy and (policy.status != "active" or not resolved_grants(db,policy).get("project_management",{}).get("enabled")):
        warnings.append("Organization access policy currently blocks PMS access; an access administrator must enable it")
    on = on or date.today()
    capacity = effective_capacity(db, target, on, on, organization_id_for(user))
    if capacity["unavailable_days"]: warnings.append("Approved leave, holiday, or non-working day on this date")
    taskids = accessible_project_query(db, user).with_entities(PMSProject.id)
    active = db.query(PMSTask).filter(PMSTask.project_id.in_(taskids), PMSTask.deleted_at.is_(None), PMSTask.status.notin_(CLOSED)).all()
    own = [t for t in active if target.id in t.assignee_user_ids]
    week = on - timedelta(days=on.weekday())
    available = effective_capacity(db, target, week, week+timedelta(days=6), organization_id_for(user))["capacity_hours"]
    planned = sum(float(t.estimated_hours or 0) / max(1, len(t.assignee_user_ids)) for t in own if t.due_date and week <= t.due_date <= week+timedelta(days=6))
    if planned > available: warnings.append(f"Visible workload {planned:g}h exceeds {available:g}h available capacity this week")
    return {"warnings": warnings, "visible_open_tasks": len(own), "planned_hours": planned, "capacity_hours": available}


def effective_capacity(db, person, start, end, organization_id=None):
    from app.models.leave import LeaveRequest
    from app.models.attendance import Holiday
    employee = getattr(person, "employee", None)
    pref = db.get(PMSPlannerPreference, person.id)
    workdays = (pref.payload or {}).get("workdays", []) if pref else []
    schedule = {d["day"]: d for d in workdays}
    leaves = db.query(LeaveRequest).filter(LeaveRequest.employee_id == employee.id, LeaveRequest.status == "Approved", LeaveRequest.deleted_at.is_(None), LeaveRequest.from_date <= end, LeaveRequest.to_date >= start).all() if employee else []
    holidays = db.query(Holiday).filter(Holiday.is_active.is_(True), Holiday.holiday_date.between(start, end)).all()
    holidays = {h.holiday_date for h in holidays if not h.applicable_branches or employee and str(employee.branch_id) in [v.strip() for v in h.applicable_branches.split(",")]}
    overrides = {c.week_start_date: float(c.capacity_hours) for c in db.query(PMSUserCapacity).filter(PMSUserCapacity.organization_id == (organization_id or organization_id_for(person)), PMSUserCapacity.user_id == person.id, PMSUserCapacity.week_start_date.between(start-timedelta(days=6), end))}
    days=[]
    for offset in range((end-start).days+1):
        day = start+timedelta(days=offset); spec=schedule.get(day.weekday(), {"enabled": day.weekday()<5, "start":"09:00", "end":"17:00"})
        def minutes(value):
            h,m=value.split(":"); return int(h)*60+int(m)
        hours = max(0, (minutes(spec["end"])-minutes(spec["start"]))/60) if spec.get("enabled") else 0
        week=day-timedelta(days=day.weekday())
        if week in overrides and hours:
            weekly=sum(max(0,(minutes(schedule.get(d,{"start":"09:00","end":"17:00"})["end"])-minutes(schedule.get(d,{"start":"09:00","end":"17:00"})["start"]))/60) for d in range(7) if schedule.get(d,{"enabled":d<5}).get("enabled"))
            hours = overrides[week]*hours/weekly if weekly else 0
        reason = "Non-working day" if not hours else "Holiday" if day in holidays else None
        leave = next((l for l in leaves if l.from_date <= day <= l.to_date), None)
        if leave: hours *= 0.5 if leave.is_half_day else 0; reason="Approved leave"
        if day in holidays or not person.is_active: hours=0
        days.append({"date":day,"hours":round(hours,2),"reason":reason})
    return {"capacity_hours":round(sum(d["hours"] for d in days),2),"unavailable_days":sum(bool(d["reason"]) for d in days),"days":days,"basis":"Working hours, dated weekly capacity, applicable holidays and approved leave"}


@router.get("/capacity")
def capacity(user_id: int, start: date, end: date, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if end < start or (end-start).days>90: raise HTTPException(422,"Choose a date range of at most 90 days")
    target=scoped_person(db,user,user_id)
    return effective_capacity(db,target,start,end,organization_id_for(user))


class CapacitySave(Strict):
    user_id: int
    week_start_date: date
    capacity_hours: float = Field(ge=0,le=168)


@router.put("/capacity")
def save_capacity(data: CapacitySave, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    target=scoped_person(db,user,data.user_id,manage=True)
    if not organization_admin(user): raise HTTPException(403,"Organization Admin or HR authority is required to change working capacity")
    if data.week_start_date.weekday()!=0: raise HTTPException(422,"Choose the Monday of the capacity week")
    row=db.query(PMSUserCapacity).filter_by(organization_id=organization_id_for(user),user_id=target.id,week_start_date=data.week_start_date).with_for_update().first()
    if not row: row=PMSUserCapacity(organization_id=organization_id_for(user),user_id=target.id,week_start_date=data.week_start_date);db.add(row)
    row.capacity_hours=data.capacity_hours
    from .people_management import record
    record(db,user,target.id,"PMS_CAPACITY_UPDATED","Updated dated capacity",after=data.model_dump())
    db.commit()
    return {"message":"Dated capacity saved"}
