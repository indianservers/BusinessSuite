import hashlib
import json
from datetime import datetime, timezone

from fastapi import HTTPException
from app.ai_agents.models import AiActionApproval, AiAgent, AiAgentSetting
from app.ai_agents.services.advanced_security import AiAgentPermissionService, AiSecuritySettingsService, AiUsageService, company_id_for
from app.ai_operator.models import OperatorRun
from app.ai_operator.schemas import TaskPlan
from app.apps.project_management.access import get_project_for_action, get_task_project_for_action
from app.apps.project_management.models import PMSChecklistItem, PMSSprint, PMSTask, PMSTaskDependency


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def scope_key(db, user, workspace_id=None, *, manage=False):
    if workspace_id is not None:
        from app.apps.project_management.workspaces import workspace_member
        workspace_member(db, workspace_id, user, manage)
        return f"workspace:{workspace_id}"
    company = company_id_for(user)
    # Never share an unscoped/global provider credential between unrelated users.
    return f"company:{company}" if company is not None else f"user:{user.id}"


def require_enabled(db, user):
    from app.apps.business_os.services.module_service import assert_module_enabled
    assert_module_enabled(db, "ai", company_id_for(user) or 1)
    AiSecuritySettingsService(db).ensure_enabled(user=user, module="PMS")
    AiUsageService(db).check_limits(user=user, agent=None, module="PMS")


def task_snapshot(db, task):
    dependencies = db.query(PMSTaskDependency).filter((PMSTaskDependency.task_id == task.id) | (PMSTaskDependency.depends_on_task_id == task.id)).order_by(PMSTaskDependency.id).all()
    neighbor_ids = {d.depends_on_task_id for d in dependencies} | {d.task_id for d in dependencies}
    neighbors = db.query(PMSTask).filter(PMSTask.id.in_(neighbor_ids), PMSTask.project_id == task.project_id).order_by(PMSTask.id).all() if neighbor_ids else []
    return {"id": task.id, "project_id": task.project_id, "title": task.title,
        "description": task.description, "estimated_hours": float(task.estimated_hours) if task.estimated_hours is not None else None, "story_points": task.story_points,
        "status": task.status, "priority": task.priority, "assignee_user_ids": task.assignee_user_ids,
        "sprint_id": task.sprint_id, "updated_at": str(task.updated_at),
        "recurrence_rule": task.recurrence_rule, "recurrence_interval": task.recurrence_interval,
        "recurrence_until": str(task.recurrence_until), "due_date": str(task.due_date), "start_date": str(task.start_date),
        "dependencies": [{"id": d.id, "source": d.depends_on_task_id, "target": d.task_id, "type": d.dependency_type, "lag": d.lag_days}
            for d in dependencies],
        "dependency_dates": [{"id": n.id, "start_date": str(n.start_date), "due_date": str(n.due_date), "deleted_at": str(n.deleted_at)} for n in neighbors],
        "checklist": [{"id": c.id, "title": c.title, "is_completed": c.is_completed, "position": c.position}
                      for c in db.query(PMSChecklistItem).filter_by(task_id=task.id).order_by(PMSChecklistItem.id).all()]}


def context_for(db, user, project_id, ids):
    project = get_project_for_action(db, project_id, user, "manage_tasks")
    tasks = []
    for task_id in sorted(set(ids)):
        task, _ = get_task_project_for_action(db, task_id, user, "manage_tasks")
        if task.project_id != project.id:
            raise HTTPException(422, "All selected tasks must belong to the selected project")
        tasks.append(task)
    from app.apps.project_management.api.router import _project_user_query
    users = _project_user_query(db, project).order_by("id").limit(101).all()
    sprints = db.query(PMSSprint).filter(PMSSprint.project_id == project.id, PMSSprint.status != "Completed").order_by(PMSSprint.id).limit(101).all()
    return project, tasks, {"project": {"id": project.id, "name": project.name},
        "tasks": [task_snapshot(db, t) for t in tasks],
        "collaborators": [{"id": u.id, "email": u.email} for u in users[:100]],
        "collaborators_complete": len(users) <= 100,
        "sprints": [{"id": s.id, "name": s.name, "status": s.status, "start_date": str(s.start_date), "end_date": str(s.end_date)} for s in sprints[:100]],
        "sprints_complete": len(sprints) <= 100,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "supported_tools": ["update_task (status, priority, replace assignee_user_ids, title, description, estimated_hours, story_points)", "add_checklist (title)", "move_to_sprint (sprint_id)",
            "update_checklist (item_id, is_completed)", "remove_checklist (item_id)", "add_comment (body; internal plain text)",
            "schedule_task (start_date, due_date; ISO dates)", "add_dependency (source_task_id blocks task_id; both must be selected)",
            "remove_dependency (dependency_id from task snapshot; both endpoints must be selected)"]}


def validate_plan(db, user, run, plan):
    from app.apps.project_management.api.router import _sync_task_planning_links
    from app.apps.project_management.schemas import PMSTaskUpdate
    if plan.clarification:
        if plan.steps:
            raise HTTPException(422, "Clarification plans must not contain executable steps")
        return
    if not plan.steps:
        raise HTTPException(422, "Plan has no actions")
    from types import SimpleNamespace
    from app.apps.project_management.api.router import _dependency_conflict
    project_tasks = {t.id: SimpleNamespace(id=t.id, task_key=t.task_key, start_date=t.start_date, due_date=t.due_date)
        for t in db.query(PMSTask).filter_by(project_id=run.project_id, deleted_at=None).all()}
    edges = [(d.depends_on_task_id, d.task_id, d.dependency_type, d.lag_days or 0)
        for d in db.query(PMSTaskDependency).filter(PMSTaskDependency.task_id.in_(list(project_tasks))).all()]
    for step in plan.steps:
        if step.task_id not in run.selection:
            raise HTTPException(422, "Plan targets a task outside the frozen selection")
        task, project = get_task_project_for_action(db, step.task_id, user, "manage_tasks")
        if project.id != run.project_id:
            raise HTTPException(422, "Plan project mismatch")
        if step.tool == "update_task":
            data = step.changes.model_dump(exclude_none=True)
            PMSTaskUpdate(**data)
            _sync_task_planning_links(db, project.id, data)
        if step.tool == "move_to_sprint":
            sprint = db.query(PMSSprint).filter_by(id=step.sprint_id, project_id=project.id).first()
            if not sprint or sprint.status == "Completed":
                raise HTTPException(422, "Target sprint is unavailable or completed")
        if step.tool in {"update_checklist", "remove_checklist"}:
            if not db.query(PMSChecklistItem).filter_by(id=step.item_id, task_id=task.id).first():
                raise HTTPException(422, "Checklist item must belong to the selected task")
        if step.tool == "schedule_task":
            target = project_tasks[step.task_id]
            target.start_date = step.start_date or target.start_date
            target.due_date = step.due_date or target.due_date
            if target.start_date and target.due_date and target.start_date > target.due_date:
                raise HTTPException(422, "Schedule has an invalid date range")
        if step.tool == "add_dependency":
            if step.source_task_id not in run.selection or step.source_task_id not in project_tasks:
                raise HTTPException(422, "Dependency source must be in the frozen selection")
            if any(s == step.source_task_id and t == step.task_id for s, t, _, _ in edges):
                raise HTTPException(422, "Dependency already exists")
            edges.append((step.source_task_id, step.task_id, step.dependency_type or "Finish To Start", step.lag_days))
        if step.tool == "remove_dependency":
            dep = db.get(PMSTaskDependency, step.dependency_id)
            if not dep or dep.task_id != step.task_id or dep.depends_on_task_id not in run.selection:
                raise HTTPException(422, "Dependency endpoints must be in the frozen selection")
            edge = (dep.depends_on_task_id, dep.task_id, dep.dependency_type, dep.lag_days or 0)
            if edge not in edges:
                raise HTTPException(422, "Dependency was already removed in this plan")
            edges.remove(edge)
    graph = {}
    for source, target, _, _ in edges:
        graph.setdefault(source, []).append(target)
    from collections import deque
    nodes = set(graph) | {child for children in graph.values() for child in children}
    incoming = dict.fromkeys(nodes, 0)
    for children in graph.values():
        for child in children:
            incoming[child] += 1
    ready, visited = deque(n for n in nodes if incoming[n] == 0), 0
    while ready:
        node = ready.popleft()
        visited += 1
        for child in graph.get(node, []):
            incoming[child] -= 1
            if incoming[child] == 0:
                ready.append(child)
    if visited != len(nodes):
        raise HTTPException(422, "Dependency graph contains a cycle")
    if any(s.tool in {"schedule_task", "add_dependency"} for s in plan.steps):
        for source, target, kind, lag in edges:
            if source in project_tasks and target in project_tasks and (source in run.selection or target in run.selection):
                if _dependency_conflict(SimpleNamespace(dependency_type=kind, lag_days=lag), project_tasks[source], project_tasks[target]):
                    raise HTTPException(422, "Plan conflicts with task dependency dates")


def perform_step(db, user, step, position):
    from app.apps.project_management.api.router import (update_task_operation, create_task_checklist_operation,
        move_task_to_sprint_operation, TaskSprintMoveRequest, update_task_schedule_operation,
        TaskScheduleUpdateRequest, create_task_dependency_operation, TaskDependencyCreateRequest, delete_task_dependency_operation,
        update_task_checklist_item_operation, delete_checklist_entry_operation, add_comment_to_task_operation)
    from app.apps.project_management.schemas import PMSTaskUpdate, PMSChecklistItemCreate, PMSChecklistItemUpdate, PMSCommentCreate
    if step.tool == "update_task":
        record = update_task_operation(step.task_id, PMSTaskUpdate(**step.changes.model_dump(exclude_none=True)), db, user, commit=False)
    elif step.tool == "add_checklist":
        record = create_task_checklist_operation(step.task_id, PMSChecklistItemCreate(title=step.title), db, user, commit=False)
    elif step.tool == "move_to_sprint":
        record = move_task_to_sprint_operation(step.task_id, TaskSprintMoveRequest(sprint_id=step.sprint_id), db, user, commit=False)
    elif step.tool == "schedule_task":
        dates = {k: v for k, v in {"start_date": step.start_date, "due_date": step.due_date}.items() if v is not None}
        record = update_task_schedule_operation(step.task_id, TaskScheduleUpdateRequest(**dates), db, user, commit=False)["task"]
    elif step.tool == "remove_dependency":
        delete_task_dependency_operation(step.dependency_id, db, user, commit=False)
        record = {"id": step.dependency_id}
    elif step.tool == "update_checklist":
        record = update_task_checklist_item_operation(step.task_id, step.item_id, PMSChecklistItemUpdate(is_completed=step.is_completed), db, user, commit=False)
    elif step.tool == "remove_checklist":
        delete_checklist_entry_operation(step.item_id, db, user, commit=False)
        record = {"id": step.item_id}
    elif step.tool == "add_comment":
        record = add_comment_to_task_operation(step.task_id, PMSCommentCreate(body=step.body, body_format="plain"), db, user, commit=False)
    else:
        record = create_task_dependency_operation(TaskDependencyCreateRequest(source_task_id=step.source_task_id,
            target_task_id=step.task_id, dependency_type=step.dependency_type or "Finish To Start", lag_days=step.lag_days), db, user, commit=False)
    return {"step": position, "tool": step.tool, "task_id": step.task_id,
            "record_id": record["id"] if isinstance(record, dict) else record.id, "status": "succeeded"}


class OperatorExecutor:
    def __init__(self, db):
        self.db = db

    def execute_setup(self, user, proposal):
        from app.ai_operator.extensions import execute_setup
        return execute_setup(self.db, user, proposal)

    def execute_run(self, user, proposal):
        db = self.db
        data = proposal.get("input", proposal)
        run = db.query(OperatorRun).filter_by(id=data["run_id"], user_id=user.id).with_for_update().first()
        if not run:
            raise HTTPException(404, "Operator run not found")
        if run.status == "succeeded":
            return run.result
        if (run.status not in {"awaiting_approval", "queued", "executing"} or run.plan_hash != data["plan_hash"] or digest(run.plan) != run.plan_hash
                or digest(proposal.get("preview")) != run.plan_hash):
            raise HTTPException(409, "Plan is cancelled, changed or no longer executable")
        require_enabled(db, user)
        approval = db.get(AiActionApproval, run.approval_id)
        agent = db.get(AiAgent, approval.agent_id) if approval else None
        if not agent or not agent.is_active or not AiAgentPermissionService(db).can_use_agent(user, agent.id):
            raise HTTPException(403, "Task planning agent is no longer available")
        AiUsageService(db).check_limits(user=user, agent=agent, module="PMS")
        setting = db.query(AiAgentSetting).filter_by(agent_id=agent.id, company_id=company_id_for(user)).first()
        if setting and not setting.is_enabled:
            raise HTTPException(403, "Task planning agent is disabled")
        try:
            # All domain writes + receipts are in the same transaction/savepoint.
            # HTTP handlers keep their existing commit/broadcast behavior; tools do not commit.
            with db.begin_nested():
                tasks = db.query(PMSTask).filter(PMSTask.id.in_(run.selection)).order_by(PMSTask.id).populate_existing().with_for_update().all()
                if len(tasks) != len(run.selection):
                    raise HTTPException(409, "STALE_PLAN")
                for task in tasks:
                    get_task_project_for_action(db, task.id, user, "manage_tasks")
                    if task.deleted_at or digest(task_snapshot(db, task)) != run.snapshots.get(str(task.id)):
                        raise HTTPException(409, "STALE_PLAN")
                plan = TaskPlan.model_validate(run.plan)
                validate_plan(db, user, run, plan)
                run.status = "executing"
                receipts = []
                for index, step in enumerate(plan.steps):
                    receipts.append(perform_step(db, user, step, index + 1))
                run.status = "succeeded"
                run.result = {"success": True, "run_id": run.id, "receipts": receipts}
                AiUsageService(db).record_event(user=user, agent_id=None, module="PMS", event_type="operator_executed")
                db.flush()
            return run.result
        except Exception as exc:
            run.status = "failed"
            run.error_code = "STALE_PLAN" if isinstance(exc, HTTPException) and exc.status_code == 409 else "EXECUTION_FAILED"
            run.result = {"success": False, "error_code": run.error_code, "message": "No task changes were committed. Create a new preview."}
            db.flush()
            return run.result
