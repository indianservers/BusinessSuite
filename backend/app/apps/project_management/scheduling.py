"""Opt-in project-calendar scheduling, immutable baselines and variance reports."""
import bisect
import hashlib
import json
import uuid
from collections import defaultdict, deque
import csv
from io import StringIO
from typing import Literal
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from .access import get_project_for_action, revalidate_project_actor
from .models import PMSWorkspaceEntry, PMSProject, PMSTask, PMSTaskDependency

router = APIRouter()


class CalendarSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4], min_length=1, max_length=7)
    holidays: list[date] = Field(default_factory=list, max_length=365)

    @model_validator(mode="after")
    def valid_days(self):
        if len(set(self.weekdays)) != len(self.weekdays) or any(d < 0 or d > 6 for d in self.weekdays):
            raise ValueError("Weekdays must be unique numbers from Monday=0 to Sunday=6")
        return self


class PlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level_resources: bool = False
    calendar: CalendarSpec | None = None
    task_id: int | None = Field(default=None, gt=0)
    start_date: date | None = None
    due_date: date | None = None
    expected_revision: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def valid_dates(self):
        if self.task_id is not None and (not self.start_date or not self.due_date or self.due_date < self.start_date):
            raise ValueError("A moved task requires a start date and a due date on or after it")
        if self.task_id is None and (self.start_date or self.due_date):
            raise ValueError("Choose the task being moved")
        return self


class BaselineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    expected_revision: str = Field(min_length=64, max_length=64)


def _state(db, project):
    row = db.query(PMSWorkspaceEntry).filter_by(workspace_id=project.workspace_id, kind=f"sc{project.id:x}").populate_existing().first() if project.workspace_id else None
    return row, json.loads(row.body) if row else {"calendar": CalendarSpec().model_dump(mode="json"), "baselines": []}


def _save(db, project, user, row, state):
    if not project.workspace_id:
        raise HTTPException(422, "Move the project into a workspace before saving its schedule plan")
    if row:
        row.body = json.dumps(state)
    else:
        db.add(PMSWorkspaceEntry(workspace_id=project.workspace_id, author_id=user.id, kind=f"sc{project.id:x}", body=json.dumps(state)))


def _graph(db, project, state):
    tasks = db.query(PMSTask).filter(PMSTask.project_id == project.id, PMSTask.deleted_at.is_(None)).populate_existing().order_by(PMSTask.id).limit(1001).all()
    if len(tasks) > 1000:
        raise HTTPException(422, "Advanced scheduling currently supports up to 1,000 tasks per project")
    ids = [t.id for t in tasks]
    deps = db.query(PMSTaskDependency).filter(or_(PMSTaskDependency.task_id.in_(ids), PMSTaskDependency.depends_on_task_id.in_(ids))).order_by(PMSTaskDependency.id).all() if ids else []
    # A dependency outside the project is never silently ignored or exposed.
    if any(d.task_id not in ids or d.depends_on_task_id not in ids for d in deps):
        raise HTTPException(409, "Resolve dependencies outside this project's active task set before advanced planning")
    fingerprint = {"project": [project.id, project.workspace_id, project.organization_id, project.is_archived], "calendar": state["calendar"], "tasks": [[t.id, str(t.start_date), str(t.due_date), t.status, str(t.updated_at)] for t in tasks],
                   "dependencies": [[d.id, d.task_id, d.depends_on_task_id, d.dependency_type, d.lag_days] for d in deps]}
    revision = hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()
    return tasks, deps, revision


def calculate(tasks, deps, calendar, moved=None):
    """Generalized precedence over inclusive task dates; FS zero lag starts next workday.

    Existing start dates are lower bounds. Cascade moves successors later only;
    it never silently pulls a customer commitment forward.
    """
    schedules = {t.id: (t.start_date, t.due_date) for t in tasks}
    if moved and moved.task_id:
        if moved.task_id not in schedules:
            raise HTTPException(404, "Task not found in this project")
        schedules[moved.task_id] = (moved.start_date, moved.due_date)
    included = {tid: dates for tid, dates in schedules.items() if all(dates)}
    excluded = [t.id for t in tasks if t.id not in included]
    if not included:
        return {"tasks": [], "changes": [], "critical_task_ids": [], "excluded_task_ids": excluded, "complete": False, "finish_date": None}
    if any(end < start for start, end in included.values()):
        raise HTTPException(422, "Fix inverted task dates before planning")
    if any(start.year < 1900 or end.year > 2200 for start, end in included.values()):
        raise HTTPException(422, "Advanced planning supports task dates from 1900 through 2200")
    anchor = min(start for start, _ in included.values())
    if max(end for _, end in included.values()) > anchor + timedelta(days=7300):
        raise HTTPException(422, "The planning horizon is limited to 20 years")
    holidays = set(calendar.holidays)
    days = [anchor + timedelta(days=i) for i in range(7301) if (anchor + timedelta(days=i)).weekday() in calendar.weekdays and anchor + timedelta(days=i) not in holidays]
    starts = {tid: bisect.bisect_left(days, dates[0]) for tid, dates in included.items()}
    durations = {tid: max(1, bisect.bisect_right(days, dates[1]) - starts[tid]) for tid, dates in included.items()}
    incoming, outgoing = defaultdict(list), defaultdict(list)
    degree = dict.fromkeys(included, 0)
    incomplete_links = False
    for dep in deps:
        a, b = dep.depends_on_task_id, dep.task_id
        if a not in included or b not in included:
            incomplete_links = True
            continue
        lag = dep.lag_days or 0
        offsets = {"Finish To Start": durations[a] + lag, "Start To Start": lag,
                   "Finish To Finish": durations[a] - durations[b] + lag, "Start To Finish": 1 - durations[b] + lag}
        if dep.dependency_type not in offsets:
            raise HTTPException(422, "Unsupported dependency type; fix it before planning")
        weight = offsets[dep.dependency_type]
        incoming[b].append((a, weight)); outgoing[a].append((b, weight)); degree[b] += 1
    queue = deque(tid for tid, n in degree.items() if n == 0)
    order = []
    while queue:
        tid = queue.popleft(); order.append(tid)
        for target, _ in outgoing[tid]:
            degree[target] -= 1
            if not degree[target]: queue.append(target)
    if len(order) != len(included):
        raise HTTPException(409, "Dependency cycle detected; no schedule changes were applied")
    for tid in order:
        starts[tid] = max([starts[tid], *[starts[a] + weight for a, weight in incoming[tid]]])
    finish = max(starts[tid] + durations[tid] for tid in order)
    if finish > len(days):
        raise HTTPException(422, "The computed schedule exceeds the 20-year planning horizon")
    if days[finish-1].year > 2200:
        raise HTTPException(422, "The computed schedule exceeds the supported year 2200")
    latest = {tid: finish - durations[tid] for tid in order}
    for tid in reversed(order):
        if outgoing[tid]: latest[tid] = min(latest[tid], *[latest[b] - weight for b, weight in outgoing[tid]])
    rows, changes = [], []
    for task in tasks:
        if task.id not in included: continue
        tid = task.id
        start, end = days[starts[tid]], days[starts[tid] + durations[tid] - 1]
        row = {"id": tid, "task_key": task.task_key, "title": task.title, "start_date": start.isoformat(), "due_date": end.isoformat(), "duration_workdays": durations[tid], "slack_workdays": latest[tid] - starts[tid]}
        rows.append(row)
        if (start, end) != (task.start_date, task.due_date):
            changes.append({**row, "old_start_date": str(task.start_date) if task.start_date else None, "old_due_date": str(task.due_date) if task.due_date else None})
    return {"tasks": rows, "changes": changes, "critical_task_ids": [r["id"] for r in rows if r["slack_workdays"] == 0], "excluded_task_ids": excluded,
            "complete": not excluded and not incomplete_links, "finish_date": days[finish - 1].isoformat(), "basis": "Project working days; existing starts are lower bounds; no resource leveling"}


def _plan(db, project, tasks, deps, calendar, data, revision, user):
    plan = calculate(tasks, deps, calendar, data)
    if data.level_resources:
        from .resource_leveling import resource_inputs, level
        capacities, resource_revision = resource_inputs(db, project, tasks, calendar, data, user)
        revision = hashlib.sha256((revision + resource_revision).encode()).hexdigest()
        plan = level(tasks, deps, calendar, data, capacities, plan)
    return plan, revision


def _load(db, project_id, user, write=False):
    project = get_project_for_action(db, project_id, user, "manage_tasks" if write else "browse")
    if write:
        project = db.query(PMSProject).filter_by(id=project.id).with_for_update().populate_existing().one()
        if project.deleted_at: raise HTTPException(404, "Project not found")
        if project.is_archived: raise HTTPException(409, "Archived projects cannot be rescheduled or receive new baselines")
        revalidate_project_actor(db, project, user, "manage_tasks")
    row, state = _state(db, project)
    tasks, deps, revision = _graph(db, project, state)
    return project, row, state, tasks, deps, revision


@router.get("/projects/{project_id}/schedule-analysis")
def analysis(project_id: int, baseline_id: str | None = Query(None), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project, _, state, tasks, deps, revision = _load(db, project_id, user)
    plan = calculate(tasks, deps, CalendarSpec.model_validate(state["calendar"]))
    selected = next((b for b in state["baselines"] if b["id"] == baseline_id), None) if baseline_id else (state["baselines"][-1] if state["baselines"] else None)
    if baseline_id and not selected: raise HTTPException(404, "Baseline not found in this project")
    snapshots = {t["id"]: t for t in selected["tasks"]} if selected else {}
    variance = [{"id": t.id, "task_key": t.task_key, "title": t.title, "start_date": str(t.start_date) if t.start_date else None,
                 "due_date": str(t.due_date) if t.due_date else None, "baseline_due_date": snapshots.get(t.id, {}).get("due_date"),
                 "due_variance_days": (t.due_date - date.fromisoformat(snapshots[t.id]["due_date"])).days if t.due_date and snapshots.get(t.id, {}).get("due_date") else None,
                 "in_baseline": t.id in snapshots} for t in tasks]
    return {**plan, "revision": revision, "calendar": state["calendar"], "baselines": [{k: v for k, v in b.items() if k != "tasks"} for b in state["baselines"]],
            "selected_baseline_id": selected["id"] if selected else None, "variance": variance,
            "removed_baseline_task_count": len(set(snapshots) - {t.id for t in tasks})}


@router.post("/projects/{project_id}/schedule-preview")
def preview(project_id: int, data: PlanInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project, _, state, tasks, deps, revision = _load(db, project_id, user, True)
    calendar = data.calendar or CalendarSpec.model_validate(state["calendar"])
    plan, revision = _plan(db, project, tasks, deps, calendar, data, revision, user)
    return {**plan, "revision": revision, "calendar": calendar.model_dump(mode="json")}


@router.post("/projects/{project_id}/schedule-apply")
def apply(project_id: int, data: PlanInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project, row, state, tasks, deps, revision = _load(db, project_id, user, True)
    calendar = data.calendar or CalendarSpec.model_validate(state["calendar"])
    plan, revision = _plan(db, project, tasks, deps, calendar, data, revision, user)
    if data.expected_revision != revision:
        raise HTTPException(409, "Schedule or resource capacity changed. Preview again before applying")
    if not plan["complete"]:
        raise HTTPException(409, "Date every active task before applying a complete dependency plan")
    lookup = {t.id: t for t in tasks}
    if any(lookup[c["id"]].status in {"Done", "Completed", "Cancelled", "Canceled", "Closed"} for c in plan["changes"]):
        raise HTTPException(409, "The plan would move a completed/cancelled task. Resolve its dates or dependencies first")
    from .api.router import _record_activity, _broadcast_realtime
    for change in plan["changes"]:
        task = lookup[change["id"]]
        task.start_date = date.fromisoformat(change["start_date"]); task.due_date = date.fromisoformat(change["due_date"])
        _record_activity(db, project.id, user, "schedule.changed", "task", task.id, f"Applied {'resource' if data.level_resources else 'dependency'} plan to {task.task_key}", task_id=task.id, metadata=change)
    state["calendar"] = calendar.model_dump(mode="json")
    _save(db, project, user, row, state)
    db.commit()
    _broadcast_realtime(user, "task.updated", project_id=project.id, message="Project resource plan applied" if data.level_resources else "Project dependency plan applied")
    return {"updated": len(plan["changes"]), "finish_date": plan["finish_date"]}


@router.post("/projects/{project_id}/schedule-baselines", status_code=201)
def capture_baseline(project_id: int, data: BaselineInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project, row, state, tasks, _, revision = _load(db, project_id, user, True)
    if revision != data.expected_revision: raise HTTPException(409, "Schedule changed. Reload before capturing a baseline")
    if not data.name.strip(): raise HTTPException(422, "Enter a baseline name")
    if len(state["baselines"]) >= 20: raise HTTPException(422, "This project already has 20 retained baselines")
    baseline = {"id": str(uuid.uuid4()), "name": data.name.strip(), "created_at": datetime.now(timezone.utc).isoformat(), "author_id": user.id,
                "tasks": [{"id": t.id, "start_date": str(t.start_date) if t.start_date else None, "due_date": str(t.due_date) if t.due_date else None} for t in tasks]}
    state["baselines"].append(baseline)
    _save(db, project, user, row, state)
    from .api.router import _record_activity
    _record_activity(db, project.id, user, "schedule.baseline", "project", project.id, f"Captured schedule baseline: {data.name.strip()}", metadata={"baseline_id": baseline["id"], "task_count": len(tasks)})
    db.commit()
    return {k: v for k, v in baseline.items() if k != "tasks"}


@router.get("/projects/{project_id}/schedule-variance/export")
def export_variance(project_id: int, baseline_id: str | None = None, file_format: Literal["csv", "xlsx"] = Query("csv", alias="format"),
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = analysis(project_id, baseline_id, db, user)
    if not result["selected_baseline_id"]: raise HTTPException(422, "Capture a baseline before exporting schedule variance")
    baseline = next(b for b in result["baselines"] if b["id"] == result["selected_baseline_id"])
    headers = ["Baseline", "Captured at", "Task", "Title", "Baseline due", "Current due", "Variance calendar days", "In baseline"]
    rows = [[baseline["name"],baseline["created_at"],r["task_key"],r["title"],r["baseline_due_date"],r["due_date"],r["due_variance_days"],r["in_baseline"]] for r in result["variance"]]
    if file_format == "xlsx":
        from .report_files import xlsx_bytes
        content = xlsx_bytes(headers, rows, sheet_name="Schedule variance"); media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        output = StringIO(); writer = csv.writer(output); writer.writerow(headers)
        for row in rows: writer.writerow(["'"+v if isinstance(v,str) and v.lstrip().startswith(("=","+","-","@","\t","\r")) else v for v in row])
        content = output.getvalue().encode("utf-8-sig"); media = "text/csv; charset=utf-8"
    return Response(content,media_type=media,headers={"Content-Disposition":f'attachment; filename="schedule-variance.{file_format}"',"Cache-Control":"private, no-store"})
