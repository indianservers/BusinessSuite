"""PMS transition adapter for the shared workflow definitions, tasks and decisions."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.models.workflow_engine import WorkflowDefinition, WorkflowStepDefinition, WorkflowInstance, WorkflowTask, WorkflowAuditEvent
from .access import get_task_project_for_action, can_access_project, organization_id_for, revalidate_project_actor
from .models import PMSWorkspace, PMSTask, PMSProject
from .workflow_schemes import current_scheme, transition_for, guard_scheme, Status
from .recovery import task_state, digest, ready

router = APIRouter()
MODULE = "project_management"
ENTITY = "pms_transition"


def is_transition(instance):
    return bool(instance and instance.module == MODULE and instance.entity_type == ENTITY)


def binding(task, scheme, rule):
    return digest({"task": task_state(task), "revision": scheme.revision, "rule": rule.model_dump()})


def instances(db, task):
    return db.query(WorkflowInstance).filter_by(module=MODULE, entity_type=ENTITY,
        entity_id=task.id, organization_id=db.get(PMSProject, task.project_id).organization_id)


def route_for(db, task, target):
    scheme = current_scheme(db, task)
    rule = transition_for(scheme, task, target) if scheme.enabled else None
    if not rule or not rule.approval_user_ids:
        raise HTTPException(409, "This transition has no active approval route")
    return scheme, rule


def matches(db, instance, task):
    context = instance.context_json or {}
    try:
        scheme, rule = route_for(db, task, context.get("target"))
    except HTTPException:
        return False
    return context.get("binding") == binding(task, scheme, rule)


def may_decide(db, instance, workflow_task, user, task):
    project = db.get(PMSProject, task.project_id)
    role = user.role.name if user.role else None
    assigned = workflow_task.assigned_to_user_id == user.id or bool(role and workflow_task.assigned_role == role)
    return bool(project and not project.deleted_at and not project.is_archived and not task.deleted_at
                and assigned and user.is_active and instance.requester_user_id != user.id
                and can_access_project(db, project, user, "manage_tasks"))


def validate_assignment(db, instance, review):
    task = db.get(PMSTask, instance.entity_id)
    if review.assigned_to_user_id:
        candidates = db.query(User).filter_by(id=review.assigned_to_user_id).all()
    else:
        from app.models.user import Role
        candidates = db.query(User).join(Role).filter(Role.name == review.assigned_role).all() if review.assigned_role else []
    if not any(may_decide(db, instance, review, user, task) for user in candidates):
        raise HTTPException(409, "The resolved reviewer needs active project access and must differ from the requester")


def validate_engine_decision(db, instance, workflow_task, user):
    """Called by every shared-engine decision endpoint, including its aliases."""
    task, project = get_task_project_for_action(db, instance.entity_id, user, "manage_tasks")
    if instance.organization_id != project.organization_id:
        raise HTTPException(404, "Approval not found in this organization")
    db.query(PMSWorkspace).filter_by(id=project.workspace_id).with_for_update().one()
    # The task and actor were loaded before acquiring the project/workspace
    # locks. READ COMMITTED does not refresh SQLAlchemy's identity map for us.
    db.refresh(task)
    revalidate_project_actor(db, project, user, "manage_tasks")
    db.refresh(instance)
    db.refresh(workflow_task)
    if instance.status != "Pending" or workflow_task.status != "Pending" or not matches(db, instance, task):
        raise HTTPException(409, "Approval is no longer current. Request approval again")
    if not may_decide(db, instance, workflow_task, user, task):
        raise HTTPException(403, "An active assigned project reviewer other than the requester must decide")


def completed_route(db, instance, rule):
    tasks = db.query(WorkflowTask).filter_by(instance_id=instance.id).all()
    if len(tasks) != len(rule.approval_user_ids):
        return False
    orders = set()
    for approval in tasks:
        step = db.get(WorkflowStepDefinition, approval.step_definition_id) if approval.step_definition_id else None
        if not step or step.workflow_id != instance.workflow_id or not 1 <= step.step_order <= len(rule.approval_user_ids):
            return False
        if (step.approver_type != "User" or step.approver_value != str(rule.approval_user_ids[step.step_order-1])
            or approval.status != "Completed" or approval.decision != "approve"
            or not approval.decided_by or approval.decided_by == instance.requester_user_id):
            return False
        reviewer = db.get(User, approval.decided_by)
        item = db.get(PMSTask, instance.entity_id)
        if not reviewer or not may_decide(db, instance, approval, reviewer, item):
            return False
        if not db.query(WorkflowAuditEvent.id).filter_by(instance_id=instance.id, task_id=approval.id, event_type="task_approved").first():
            return False
        orders.add(step.step_order)
    return len(orders) == len(tasks)


def consume_approval(db, task, target, scheme, rule, changes):
    # Approval covers the saved task; editing and applying together must not change reviewed data.
    state = task_state(task)
    for key, value in (changes or {}).items():
        if key != "status" and (key in state and ready(value) != state[key] or key not in state and key not in {"status"}):
            raise HTTPException(409, "Save task changes before requesting and applying approval")
    candidates = instances(db, task).filter_by(status="Approved").order_by(WorkflowInstance.id.desc()).with_for_update().populate_existing().all()
    for instance in candidates:
        if (instance.context_json or {}).get("binding") == binding(task, scheme, rule) and completed_route(db, instance, rule):
            instance.status = "Applied"
            from app.api.v1.workflow_engine import _audit
            _audit(db, instance, "transition_applied", before_status="Approved", after_status="Applied",
                   details={"source": task.status, "target": target})
            return
    raise HTTPException(409, "Request transition approval and complete every review before changing status")


def payload(db, instance, user, task):
    current = matches(db, instance, task)
    approvals = db.query(WorkflowTask).filter_by(instance_id=instance.id).order_by(WorkflowTask.id).all()
    return {"id": instance.id, "status": instance.status, "current": current,
            "target": (instance.context_json or {}).get("target"),
            "requester_user_id": instance.requester_user_id,
            "steps": [{"id": t.id, "assigned_to_user_id": t.assigned_to_user_id,
                       "reviewer": (db.get(User, t.assigned_to_user_id).email if t.assigned_to_user_id and db.get(User, t.assigned_to_user_id) else t.assigned_role or "Unassigned reviewer"),
                       "status": t.status, "decision": t.decision, "reason": t.decision_reason,
                       "can_decide": current and instance.status == "Pending" and t.status == "Pending"
                                     and may_decide(db, instance, t, user, task)} for t in approvals]}


@router.get("/tasks/{task_id}/transition-approvals")
def list_approvals(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task, project = get_task_project_for_action(db, task_id, user)
    scheme = current_scheme(db, task)
    rules = scheme.work_type_transitions.get(task.work_type, scheme.transitions) if scheme.enabled else []
    return {"can_request": can_access_project(db, project, user, "manage_tasks"),
            "transitions": [{"target": r.target, "approval_required": bool(r.approval_user_ids)}
                            for r in rules if r.source == task.status],
            "requests": [payload(db, i, user, task) for i in instances(db, task).order_by(WorkflowInstance.id.desc()).limit(30)]}


@router.get("/transition-approvals/inbox")
def approval_inbox(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assigned = WorkflowTask.assigned_to_user_id == user.id
    if user.role and user.role.name:
        assigned = assigned | (WorkflowTask.assigned_role == user.role.name)
    rows = db.query(WorkflowTask, WorkflowInstance).join(WorkflowInstance).filter(
        assigned, WorkflowTask.status == "Pending", WorkflowInstance.status == "Pending",
        WorkflowInstance.organization_id == organization_id_for(user),
        WorkflowInstance.module == MODULE, WorkflowInstance.entity_type == ENTITY,
    ).order_by(WorkflowTask.id.desc()).limit(200).all()
    result = []
    for review, instance in rows:
        task = db.get(PMSTask, instance.entity_id)
        if task and not task.deleted_at and may_decide(db, instance, review, user, task):
            result.append({"id": review.id, "task_id": task.id, "title": task.title,
                           "target": (instance.context_json or {}).get("target"),
                           "current": matches(db, instance, task)})
    return result


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: Status


@router.post("/tasks/{task_id}/transition-approvals", status_code=201)
def request_approval(task_id: int, data: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task, project = get_task_project_for_action(db, task_id, user, "manage_tasks")
    if not project.workspace_id or project.is_archived:
        raise HTTPException(409, "An active workspace project is required")
    db.query(PMSWorkspace).filter_by(id=project.workspace_id).with_for_update().one()
    db.refresh(task)
    scheme, rule = route_for(db, task, data.target)
    revalidate_project_actor(db, project, user, "manage_tasks")
    guard_scheme(db, task, data.target, check_approval=False)
    from .automations import _eligible_assignee
    if user.id in rule.approval_user_ids:
        raise HTTPException(422, "The requester cannot be an approver for this transition")
    for uid in rule.approval_user_ids:
        reviewer = db.get(User, uid)
        if not _eligible_assignee(db, project.workspace_id, uid) or not can_access_project(db, project, reviewer, "manage_tasks"):
            raise HTTPException(409, "An approver no longer has active project access. Update the route")
    fingerprint = binding(task, scheme, rule)
    from app.api.v1.workflow_engine import _audit, _create_next_pending_task
    for old in instances(db, task).filter(WorkflowInstance.status.in_(["Pending", "Approved"])).all():
        if (old.context_json or {}).get("binding") == fingerprint:
            return payload(db, old, user, task)
        old.status = "Cancelled"
        for review in db.query(WorkflowTask).filter_by(instance_id=old.id, status="Pending"):
            review.status = "Cancelled"
        _audit(db, old, "instance_cancelled", actor_user_id=user.id, after_status="Cancelled", reason="Superseded by a new task or policy revision")
    definition = WorkflowDefinition(organization_id=project.organization_id, name=f"{task.task_key}: {task.status} to {data.target}"[:160],
        module=MODULE, trigger_event="pms.transition", created_by=user.id,
        steps=[WorkflowStepDefinition(step_order=n, step_type="Approval", approver_type="User", approver_value=str(uid), is_required=True)
               for n, uid in enumerate(rule.approval_user_ids, 1)])
    db.add(definition); db.flush()
    instance = WorkflowInstance(organization_id=project.organization_id, workflow_id=definition.id,
        module=MODULE, entity_type=ENTITY, entity_id=task.id, requester_user_id=user.id,
        context_json={"binding": fingerprint, "target": data.target, "project_id": project.id,
                      "work_type": task.work_type, "scheme_revision": scheme.revision})
    db.add(instance); db.flush()
    _audit(db, instance, "instance_started", actor_user_id=user.id, after_status="Pending")
    if not _create_next_pending_task(db, instance):
        raise HTTPException(409, "No approval step was created")
    from .api.router import _record_activity
    _record_activity(db, project.id, user, "workflow.approval_requested", "task", task.id,
                     f"Requested approval to move {task.task_key} to {data.target}", task_id=task.id,
                     metadata={"instance_id": instance.id})
    db.commit()
    return payload(db, instance, user, task)
