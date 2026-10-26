"""Bounded project bootstrapping, discovery and recurring local goal checks.

Model output is a draft. Canonical PMS operations execute only after approval.
"""
import json
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.ai_agents.api import _require_ai_access, _require_ai_admin, _require_ai_rate_limit
from app.ai_agents.models import AiActionApproval
from app.ai_agents.services.advanced_security import AiDataRedactionService
from app.ai_agents.services.approval_executor import AiApprovalExecutorService
from app.ai_agents.services.audit import AiAuditService
from app.ai_operator.models import OperatorProposal, OperatorProvider, OperatorMonitor, OperatorApiLog
from app.ai_operator.planner import planning_agent
from app.ai_operator.providers import generate_json
from app.ai_operator.provider_scope import resolve_provider
from app.ai_operator.schemas import Provider, ApproveInput
from app.ai_operator.service import digest, scope_key, require_enabled
from app.apps.project_management.access import get_project_for_action, can_access_project, organization_id_for, has_any_permission, PMS_GLOBAL_MANAGE_PROJECTS
from app.apps.project_management.models import PMSProject, PMSTask, PMSTaskDependency, PMSUserCapacity

router = APIRouter()


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SetupTask(Strict):
    key: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=220)
    description: str | None = Field(default=None, max_length=8000)
    estimated_hours: float | None = Field(default=None, ge=0, le=10000, allow_inf_nan=False)
    start_date: date | None = None
    due_date: date | None = None
    # References are local draft keys, never provider-invented database IDs.
    parent_key: str | None = None
    milestone_key: str | None = None
    blocked_by: list[str] = Field(default_factory=list, max_length=50)
    existing_parent_task_id: int | None = Field(default=None, gt=0)
    assignee_user_ids: list[int] = Field(default_factory=list, max_length=25)


class SetupMilestone(Strict):
    key: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=180)
    due_date: date | None = None


class SetupPlan(Strict):
    summary: str = Field(min_length=1, max_length=1000)
    clarification: str | None = Field(default=None, max_length=1500)
    name: str = Field(min_length=1, max_length=180)
    project_key: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    description: str | None = Field(default=None, max_length=12000)
    milestones: list[SetupMilestone] = Field(default_factory=list, max_length=20)
    tasks: list[SetupTask] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def valid_graph(self):
        seen, milestones = set(), {m.key for m in self.milestones}
        if len(milestones) != len(self.milestones):
            raise ValueError("Duplicate milestone key")
        for t in self.tasks:
            if t.parent_key and t.existing_parent_task_id:
                raise ValueError("Use either a draft parent or an existing parent")
            if t.key in seen or (t.parent_key and t.parent_key not in seen) or any(k not in seen for k in t.blocked_by):
                raise ValueError("Task keys must be unique; references must point to earlier tasks")
            if t.milestone_key and t.milestone_key not in milestones:
                raise ValueError("Unknown milestone reference")
            if t.start_date and t.due_date and t.start_date > t.due_date:
                raise ValueError("Invalid task dates")
            seen.add(t.key)
        if self.clarification and (self.tasks or self.milestones):
            raise ValueError("Clarification cannot contain actions")
        return self


class SetupInput(Strict):
    brief: str = Field(min_length=3, max_length=20000)
    provider: Provider
    request_key: str = Field(min_length=8, max_length=100)
    workspace_id: int | None = Field(default=None, gt=0)
    project_id: int | None = Field(default=None, gt=0)
    template_id: int | None = Field(default=None, gt=0)
    local_plan: SetupPlan | None = None


def setup_access(db, user, workspace_id, project_id):
    if project_id:
        project = get_project_for_action(db, project_id, user, "manage_tasks")
        if project.workspace_id != workspace_id:
            raise HTTPException(422, "Project and workspace must match")
    elif workspace_id:
        scope_key(db, user, workspace_id, manage=True)
    elif not has_any_permission(user, PMS_GLOBAL_MANAGE_PROJECTS):
        raise HTTPException(403, "Project creation permission required")
    return scope_key(db, user, workspace_id)


def proposal_public(row):
    return {k: getattr(row, k) for k in ("id", "kind", "payload", "plan_hash", "approval_id", "status", "result", "created_at")}


@router.post("/setup/preview")
def setup_preview(payload: SetupInput, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    agent = planning_agent(db, user)
    scope = setup_access(db, user, payload.workspace_id, payload.project_id)
    fingerprint = digest(payload.model_dump(exclude={"request_key"}))
    old = db.query(OperatorProposal).filter_by(user_id=user.id, request_key=payload.request_key).first()
    if old:
        from app.ai_agents.security import verify
        verify(db,user,old.security_context,history=True)
        if old.scope_key != scope or old.request_hash != fingerprint:
            raise HTTPException(409, "Idempotency key already used")
        return proposal_public(old)
    _require_ai_rate_limit(db, request, user, bucket="operator_setup")
    config = resolve_provider(db, user, payload.provider, payload.workspace_id)
    if config and (not config.enabled or not config.data_sharing_allowed):
        config = None
    if not config and not payload.local_plan:
        raise HTTPException(409, "Provider unavailable for this scope")
    template = None
    if payload.template_id:
        source = get_project_for_action(db, payload.template_id, user, "manage_tasks")
        if not source.is_template or scope_key(db, user, source.workspace_id) != scope:
            raise HTTPException(422, "Select an accessible template in this scope")
        template = {"name": source.name, "description": source.description,
            "tasks": [{"title": t.title, "description": t.description, "estimated_hours": str(t.estimated_hours)}
                for t in db.query(PMSTask).filter_by(project_id=source.id, deleted_at=None).order_by(PMSTask.id).limit(50).all()]}
    outbound = AiDataRedactionService().redact_for_ai(user, "PMS", {"brief": payload.brief, "template": template,
        "instructions": "Extract a delivery work breakdown from this brief, meeting notes or document text. Preserve explicit dates only. Order parents and blockers before children. Use short unique local keys. Do not assign people or claim actions completed. Ask clarification if needed."})
    try:
        if payload.local_plan:
            if payload.template_id:
                raise HTTPException(422, "Local setup cannot apply a template implicitly")
            plan = payload.local_plan
        else:
            output = generate_json(db, user, config, prompt=json.dumps(outbound), schema=SetupPlan.model_json_schema(), purpose="setup", output_type=SetupPlan, usage_scope=scope)
            plan = SetupPlan.model_validate(output)
    except HTTPException:
        db.commit()  # Retain sanitized API usage even on failure.
        raise
    from app.ai_operator.service import task_snapshot
    from app.apps.project_management.access import get_task_project_for_action
    from app.apps.project_management.api.router import _sync_task_planning_links
    parents = {}
    if not payload.project_id and db.query(PMSProject).filter_by(organization_id=organization_id_for(user), project_key=plan.project_key.upper()).first():
        raise HTTPException(422, "Project key already exists. Choose a different key.")
    seen_keys = set()
    for item in plan.tasks:
        key = item.key.upper()
        if key in seen_keys or (payload.project_id and db.query(PMSTask).filter_by(project_id=payload.project_id, task_key=key).first()):
            raise HTTPException(422, "Task key already exists. Choose a different key.")
        seen_keys.add(key)
        if item.existing_parent_task_id:
            parent, parent_project = get_task_project_for_action(db, item.existing_parent_task_id, user, "manage_tasks")
            if parent_project.id != payload.project_id:
                raise HTTPException(422, "Parent must belong to the destination project")
            parents[str(parent.id)] = digest(task_snapshot(db, parent))
        if item.assignee_user_ids:
            if not payload.project_id:
                raise HTTPException(422, "Create the project before assigning collaborators")
            _sync_task_planning_links(db, payload.project_id, {"assignee_user_ids": item.assignee_user_ids})
    body = {"project_id": payload.project_id, "workspace_id": payload.workspace_id, "plan": plan.model_dump(mode="json"),
        "parent_snapshots": parents, "planning_source": "local" if payload.local_plan else "provider"}
    row = OperatorProposal(user_id=user.id, scope_key=scope, workspace_id=payload.workspace_id, kind="project_setup",
        request_key=payload.request_key, request_hash=fingerprint, payload=body, plan_hash=digest(body),
        status="needs_clarification" if plan.clarification else "awaiting_approval")
    db.add(row)
    db.flush()
    if not plan.clarification:
        approval = AiActionApproval(user_id=user.id, agent_id=agent.id, module="PMS", action_type="EXECUTE_PMS_OPERATOR_SETUP",
            related_entity_type="operator_proposal", related_entity_id=str(row.id), status="pending", execution_status="pending",
            proposed_action_json={"input": {"proposal_id": row.id, "plan_hash": row.plan_hash}, "preview": body},
            idempotency_key=f"operator-setup:{row.id}:{row.plan_hash}")
        db.add(approval)
        db.flush()
        row.approval_id = approval.id
    AiAuditService(db).log(user=user, agent_id=agent.id, module="PMS", action="operator.setup.preview",
        input_json={"proposal_id": row.id, "planning_source": body["planning_source"]},
        output_json={"status": row.status, "task_count": len(plan.tasks)}, status="success")
    db.commit()
    return proposal_public(row)


def owned_proposal(db, user, proposal_id):
    row = db.query(OperatorProposal).filter_by(id=proposal_id, user_id=user.id).first()
    if not row:
        raise HTTPException(404, "Proposal not found")
    from app.ai_agents.security import verify
    verify(db,user,row.security_context,history=True)
    if setup_access(db, user, row.workspace_id, row.payload.get("project_id")) != row.scope_key:
        raise HTTPException(403, "Proposal scope changed")
    return row


@router.get("/proposals/{proposal_id}")
def proposal_detail(proposal_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    return proposal_public(owned_proposal(db, user, proposal_id))


@router.post("/proposals/{proposal_id}/approve")
def proposal_approve(proposal_id: int, payload: ApproveInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    row = owned_proposal(db, user, proposal_id)
    if payload.plan_hash != row.plan_hash or not row.approval_id:
        raise HTTPException(409, "Preview changed or cannot execute")
    AiApprovalExecutorService(db).execute_approved_action(user=user, approval_id=row.approval_id)
    db.commit()
    db.refresh(row)
    return proposal_public(row)


def execute_setup(db, user, proposal):
    from app.apps.project_management.api.router import (create_project_operation, create_task_operation, create_milestone_operation,
        create_task_dependency_operation, TaskDependencyCreateRequest)
    from app.apps.project_management.schemas import PMSProjectCreate, PMSTaskCreate, PMSMilestoneCreate
    data = proposal["input"]
    row = db.query(OperatorProposal).filter_by(id=data["proposal_id"], user_id=user.id).with_for_update().first()
    if not row:
        raise HTTPException(404, "Proposal not found")
    owned_proposal(db, user, row.id)
    planning_agent(db, user)
    if row.plan_hash != data["plan_hash"] or digest(row.payload) != row.plan_hash or digest(proposal.get("preview")) != row.plan_hash:
        raise HTTPException(409, "Preview changed")
    from app.ai_agents.security import verify
    verify(db,user,row.security_context)
    if row.status == "succeeded":
        return row.result
    if row.status != "awaiting_approval":
        raise HTTPException(409, "Proposal no longer executable")
    plan = SetupPlan.model_validate(row.payload["plan"])
    with db.begin_nested():
        from app.ai_operator.service import task_snapshot
        from app.apps.project_management.access import get_task_project_for_action
        for parent_id, snapshot in row.payload.get("parent_snapshots", {}).items():
            parent = db.query(PMSTask).filter_by(id=int(parent_id)).populate_existing().with_for_update().one_or_none()
            if not parent:
                raise HTTPException(409, "Parent task changed. Create a new preview.")
            get_task_project_for_action(db, parent.id, user, "manage_tasks")
            if digest(task_snapshot(db, parent)) != snapshot:
                raise HTTPException(409, "Parent task changed. Create a new preview.")
        project_id = row.payload.get("project_id")
        if not project_id:
            project_id = create_project_operation(PMSProjectCreate(name=plan.name, project_key=plan.project_key,
                description=plan.description, workspace_id=row.workspace_id), db, user, commit=False).id
        milestones, tasks, receipts = {}, {}, []
        for item in plan.milestones:
            record = create_milestone_operation(project_id, PMSMilestoneCreate(name=item.name, due_date=item.due_date), db, user, commit=False)
            milestones[item.key] = record.id
            receipts.append({"tool": "create_milestone", "record_id": record.id, "key": item.key})
        for item in plan.tasks:
            record = create_task_operation(project_id, PMSTaskCreate(title=item.title, task_key=item.key,
                description=item.description, estimated_hours=item.estimated_hours, start_date=item.start_date, due_date=item.due_date,
                parent_task_id=item.existing_parent_task_id or tasks.get(item.parent_key), milestone_id=milestones.get(item.milestone_key),
                assignee_user_ids=item.assignee_user_ids), db, user, commit=False)
            tasks[item.key] = record.id
            receipts.append({"tool": "create_task", "record_id": record.id, "key": item.key})
            for blocker in item.blocked_by:
                dep = create_task_dependency_operation(TaskDependencyCreateRequest(source_task_id=tasks[blocker], target_task_id=record.id), db, user, commit=False)
                receipts.append({"tool": "add_dependency", "record_id": dep["id"]})
        row.status, row.result = "succeeded", {"success": True, "project_id": project_id, "receipts": receipts}
        db.flush()
    return row.result


@router.get("/local-context")
def local_context(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    require_enabled(db, user)
    project = get_project_for_action(db, project_id, user, "manage_tasks")
    from app.apps.project_management.api.router import _project_user_query
    from app.ai_operator.service import task_snapshot
    people = _project_user_query(db, project).order_by(User.id).limit(101).all()
    tasks = db.query(PMSTask).filter_by(project_id=project_id, deleted_at=None).order_by(PMSTask.id).limit(501).all()
    from app.apps.project_management.models import PMSSprint
    sprints = db.query(PMSSprint).filter(PMSSprint.project_id == project_id, PMSSprint.status != "Completed").order_by(PMSSprint.id).limit(101).all()
    return {"project": {"id": project.id, "name": project.name, "project_key": project.project_key, "workspace_id": project.workspace_id},
        "tasks": [task_snapshot(db, t) | {"task_key": t.task_key} for t in tasks[:500]], "tasks_complete": len(tasks) <= 500,
        "collaborators": [{"id": p.id, "email": p.email, "name": p.person.display_name if p.person else p.email.split("@")[0]} for p in people[:100]],
        "collaborators_complete": len(people) <= 100,
        "sprints": [{"id": s.id, "name": s.name, "status": s.status} for s in sprints[:100]], "sprints_complete": len(sprints) <= 100}


@router.get("/resolve")
def resolve(project_id: int, q: str = Query(min_length=1, max_length=180), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    project = get_project_for_action(db, project_id, user, "manage_tasks")
    from app.apps.project_management.api.router import _project_user_query
    # Literal matching avoids treating user-entered %/_ as wildcard expansion.
    pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    tasks = db.query(PMSTask).filter_by(project_id=project.id, deleted_at=None).filter(or_(
        PMSTask.title.ilike(pattern, escape="\\"), PMSTask.task_key.ilike(pattern, escape="\\"))).order_by(PMSTask.id).limit(21).all()
    people = _project_user_query(db, project).filter(User.email.ilike(pattern, escape="\\")).order_by(User.id).limit(21).all()
    items = [{"type": "task", "id": t.id, "label": f"{t.task_key}: {t.title}"} for t in tasks[:20]] + [
        {"type": "user", "id": u.id, "label": u.email} for u in people[:20]]
    return {"items": items, "ambiguous": len(items) != 1, "truncated": len(tasks) > 20 or len(people) > 20,
        "requires_selection": True}


def goal_findings(db, project_id, today):
    tasks = db.query(PMSTask).filter_by(project_id=project_id, deleted_at=None).filter(PMSTask.status.notin_(["Done", "Completed", "Cancelled"])).order_by(PMSTask.id).all()
    return [{"task_id": t.id, "task_key": t.task_key, "title": t.title,
        "reasons": (["overdue"] if t.due_date and t.due_date < today else []) + (["blocked"] if t.status == "Blocked" else []) +
            (["unassigned"] if not t.assignee_user_ids and not t.assignee_user_id else [])}
        for t in tasks if (t.due_date and t.due_date < today) or t.status == "Blocked" or (not t.assignee_user_ids and not t.assignee_user_id)]


class MonitorInput(Strict):
    project_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=180)
    interval_minutes: int = Field(default=60, ge=15, le=10080)
    enabled: bool = True


def monitor_public(row):
    return {k: getattr(row, k) for k in ("id", "project_id", "name", "enabled", "interval_minutes", "findings", "checked_at", "next_check_at", "error_code")}


@router.post("/monitors")
def create_monitor(payload: MonitorInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    planning_agent(db, user)
    project = get_project_for_action(db, payload.project_id, user, "manage_tasks")
    if db.query(OperatorMonitor).filter_by(user_id=user.id).count() >= 50:
        raise HTTPException(409, "Monitor limit reached")
    row = OperatorMonitor(user_id=user.id, scope_key=scope_key(db, user, project.workspace_id), next_check_at=datetime.now(timezone.utc), **payload.model_dump())
    db.add(row)
    db.commit()
    return monitor_public(row)


@router.get("/monitors")
def monitors(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    get_project_for_action(db, project_id, user, "manage_tasks")
    return {"items": [monitor_public(r) for r in db.query(OperatorMonitor).filter_by(user_id=user.id, project_id=project_id).order_by(OperatorMonitor.id).all()]}


@router.put("/monitors/{monitor_id}")
def update_monitor(monitor_id: int, payload: MonitorInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    row = db.query(OperatorMonitor).filter_by(id=monitor_id, user_id=user.id).with_for_update().first()
    if not row:
        raise HTTPException(404, "Monitor not found")
    project = get_project_for_action(db, row.project_id, user, "manage_tasks")
    if payload.project_id != row.project_id or scope_key(db, user, project.workspace_id) != row.scope_key:
        raise HTTPException(409, "Monitor scope cannot change")
    if payload.enabled:
        planning_agent(db, user)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    row.next_check_at = datetime.now(timezone.utc)
    db.commit()
    return monitor_public(row)


def check_monitors(db, limit=20):
    now, changed = datetime.now(timezone.utc), 0
    rows = db.query(OperatorMonitor).filter(OperatorMonitor.enabled.is_(True), OperatorMonitor.next_check_at <= now).order_by(OperatorMonitor.id).with_for_update(skip_locked=True).limit(limit).all()
    for row in rows:
        try:
            user = db.get(User, row.user_id)
            if not user or not user.is_active:
                raise HTTPException(403, "User unavailable")
            planning_agent(db, user)
            project = get_project_for_action(db, row.project_id, user, "manage_tasks")
            if scope_key(db, user, project.workspace_id) != row.scope_key:
                raise HTTPException(403, "Scope changed")
            findings = goal_findings(db, row.project_id, now.date())
            signature = digest(findings)
            if signature != row.finding_hash:
                row.findings, row.finding_hash = findings, signature
                changed += 1
                AiAuditService(db).log(user=user, agent_id=None, module="PMS", action="operator.monitor.changed",
                    input_json={"monitor_id": row.id}, output_json={"finding_count": len(findings)}, status="success")
            row.error_code = None
        except HTTPException:
            row.enabled, row.error_code = False, "MONITOR_ACCESS_REVOKED"
            row.findings = None
        row.checked_at, row.next_check_at = now, now + timedelta(minutes=row.interval_minutes)
    db.commit()
    return {"checked": len(rows), "changed": changed}


@router.get("/portfolio")
def portfolio(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    require_enabled(db, user)
    rows = []
    for p in db.query(PMSProject).filter_by(deleted_at=None, is_archived=False).order_by(PMSProject.id):
        if can_access_project(db, p, user, "manage_tasks"):
            findings = goal_findings(db, p.id, datetime.now(timezone.utc).date())
            rows.append({"project_id": p.id, "name": p.name, "health": p.health, "billing_status": p.billing_status,
                "budget_amount": p.budget_amount, "actual_cost": p.actual_cost, "findings": findings})
        if len(rows) == 100:
            break
    return {"items": rows, "limit": 100}


@router.get("/capacity")
def capacity(project_id: int, week_start: date, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    project = get_project_for_action(db, project_id, user, "manage_tasks")
    require_enabled(db, user)
    from app.apps.project_management.api.router import _project_user_query
    start = week_start - timedelta(days=week_start.weekday())
    end = start + timedelta(days=6)
    people = _project_user_query(db, project).order_by(User.id).limit(100).all()
    # Count only authorized projects; disclose the incomplete workload explicitly.
    visible = [p.id for p in db.query(PMSProject).filter_by(deleted_at=None, organization_id=project.organization_id)
        if can_access_project(db, p, user, "manage_tasks")]
    tasks = db.query(PMSTask).filter(PMSTask.project_id.in_(visible), PMSTask.deleted_at.is_(None),
        PMSTask.status.notin_(["Done", "Completed", "Cancelled"])).all()
    result = []
    for person in people:
        override = db.query(PMSUserCapacity).filter_by(organization_id=project.organization_id, user_id=person.id, week_start_date=start).first()
        assigned, missing = 0.0, 0
        for task in tasks:
            ids = task.assignee_user_ids or ([task.assignee_user_id] if task.assignee_user_id else [])
            if person.id not in ids:
                continue
            if not task.start_date or not task.due_date or task.estimated_hours is None:
                missing += 1
                continue
            working = [task.start_date + timedelta(days=i) for i in range((task.due_date-task.start_date).days+1)
                if (task.start_date+timedelta(days=i)).weekday() < 5]
            if working:
                assigned += float(task.estimated_hours) / len(set(ids)) * sum(start <= d <= end for d in working) / len(working)
        available = float(override.capacity_hours) if override else 40.0
        result.append({"user_id": person.id, "email": person.email, "capacity_hours": available,
            "allocated_hours": round(assigned, 2), "overload_hours": round(max(0, assigned-available), 2), "unscheduled_tasks": missing})
    return {"week_start": start, "items": result,
        "assumptions": "Monday–Friday; estimates spread equally across working days and assignees. Authorized projects only. Weekly PMS capacity overrides default 40h. Leave/holiday calendars are not yet deducted."}


class RetentionInput(Strict):
    days: int = Field(ge=30, le=3650)
    workspace_id: int | None = Field(default=None, gt=0)
    execute: bool = False


@router.post("/retention")
def retention(payload: RetentionInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_admin(user)
    scope = scope_key(db, user, payload.workspace_id, manage=True)
    cutoff = datetime.now(timezone.utc)-timedelta(days=payload.days)
    logs = db.query(OperatorApiLog).filter(OperatorApiLog.scope_key == scope, OperatorApiLog.created_at < cutoff)
    count = logs.count()
    if payload.execute:
        logs.delete(synchronize_session=False)
        AiAuditService(db).log(user=user, agent_id=None, module="PMS", action="operator.retention.purge",
            input_json={"days": payload.days, "scope": scope}, output_json={"api_logs_deleted": count}, status="success")
        db.commit()
    return {"api_logs": count, "executed": payload.execute, "cutoff": cutoff,
        "preserved": "Run history, approvals and execution receipts remain for replay protection."}
