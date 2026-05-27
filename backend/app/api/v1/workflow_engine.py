from datetime import datetime, timedelta, timezone
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.deps import RequirePermission, get_current_user, get_db
from app.models.user import User
from app.models.workflow_engine import WorkflowDefinition, WorkflowInstance, WorkflowStepDefinition, WorkflowTask
from app.schemas.workflow_engine import (
    WorkflowDefinitionCreate, WorkflowDefinitionSchema, WorkflowInstanceCreate,
    WorkflowInstanceSchema, WorkflowTaskDecision, WorkflowTaskSchema,
)

router = APIRouter(prefix="/workflow-engine", tags=["Workflow Engine"])


def _condition_matches(expression: str | None, context: dict | None) -> bool:
    if not expression:
        return True
    context = context or {}
    match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_.]*)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*$", expression)
    if not match:
        return False
    key, operator, expected_raw = match.groups()
    actual = context
    for part in key.split("."):
        actual = actual.get(part) if isinstance(actual, dict) else None
    expected_raw = expected_raw.strip().strip("\"'")
    try:
        actual_value = float(actual)
        expected_value = float(expected_raw)
    except (TypeError, ValueError):
        actual_value = "" if actual is None else str(actual)
        expected_value = expected_raw
    if operator == "==":
        return actual_value == expected_value
    if operator == "!=":
        return actual_value != expected_value
    if operator == ">=":
        return actual_value >= expected_value
    if operator == "<=":
        return actual_value <= expected_value
    if operator == ">":
        return actual_value > expected_value
    if operator == "<":
        return actual_value < expected_value
    return False


def _assign_task_from_step(instance: WorkflowInstance, step: WorkflowStepDefinition) -> WorkflowTask:
    return WorkflowTask(
        instance_id=instance.id,
        step_definition_id=step.id,
        assigned_role=step.approver_value if step.approver_type == "Role" else None,
        assigned_to_user_id=int(step.approver_value) if step.approver_type == "User" and step.approver_value else None,
        due_at=datetime.now(timezone.utc) + timedelta(hours=step.timeout_hours) if step.timeout_hours else None,
    )


def _create_next_pending_task(db: Session, instance: WorkflowInstance, after_step_order: int = 0) -> bool:
    if not instance.workflow_id:
        return False
    steps = db.query(WorkflowStepDefinition).filter(
        WorkflowStepDefinition.workflow_id == instance.workflow_id,
        WorkflowStepDefinition.step_order > after_step_order,
    ).order_by(WorkflowStepDefinition.step_order).all()
    for step in steps:
        if not _condition_matches(step.condition_expression, instance.context_json):
            continue
        db.add(_assign_task_from_step(instance, step))
        instance.current_step_order = step.step_order
        instance.status = "Pending"
        return True
    return False


def _step_to_designer_dict(step: WorkflowStepDefinition) -> dict:
    assignee_type = (step.approver_type or "Role").lower()
    return {
        "id": step.id,
        "definition_id": step.workflow_id,
        "workflow_id": step.workflow_id,
        "step_order": step.step_order,
        "name": step.step_type or f"Step {step.step_order}",
        "step_type": (step.step_type or "approval").lower(),
        "assignee_type": "role" if assignee_type == "role" else "user" if assignee_type == "user" else assignee_type,
        "assignee_role": step.approver_value if assignee_type == "role" else None,
        "assignee_user_id": int(step.approver_value) if assignee_type == "user" and str(step.approver_value or "").isdigit() else None,
        "timeout_hours": step.timeout_hours,
        "timeout_action": "escalate",
        "condition_expression": step.condition_expression,
        "skip_if_condition": None,
        "reminder_hours": None,
        "is_active": step.is_required,
        "description": None,
    }


def _definition_to_designer_dict(definition: WorkflowDefinition) -> dict:
    return {
        "id": definition.id,
        "name": definition.name,
        "module": definition.module,
        "trigger_event": definition.trigger_event,
        "description": definition.description,
        "is_active": definition.is_active,
        "version": 1,
        "created_by": definition.created_by,
        "created_at": definition.created_at,
        "steps": [_step_to_designer_dict(step) for step in sorted(definition.steps, key=lambda item: item.step_order)],
    }


def _apply_step_payload(step: WorkflowStepDefinition, payload: dict) -> None:
    step.step_order = int(payload.get("step_order", step.step_order))
    step.step_type = payload.get("name") or payload.get("step_type") or step.step_type
    assignee_type = payload.get("assignee_type") or payload.get("approver_type") or step.approver_type
    step.approver_type = str(assignee_type).replace("assignee_", "").title()
    if step.approver_type == "Role":
        step.approver_value = payload.get("assignee_role") or payload.get("approver_value")
    elif step.approver_type == "User":
        user_id = payload.get("assignee_user_id") or payload.get("approver_value")
        step.approver_value = str(user_id) if user_id else None
    else:
        step.approver_value = payload.get("approver_value")
    step.condition_expression = payload.get("condition_expression")
    step.timeout_hours = payload.get("timeout_hours")
    step.escalation_user_id = payload.get("escalation_user_id")
    step.is_required = bool(payload.get("is_active", payload.get("is_required", True)))


@router.post("/definitions", response_model=WorkflowDefinitionSchema, status_code=201)
def create_definition(data: WorkflowDefinitionCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    definition = WorkflowDefinition(**data.model_dump(exclude={"steps"}), created_by=current_user.id)
    db.add(definition)
    db.flush()
    for step in data.steps:
        db.add(WorkflowStepDefinition(workflow_id=definition.id, **step.model_dump()))
    db.commit()
    db.refresh(definition)
    return definition


@router.get("/definitions")
def list_definitions(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    definitions = db.query(WorkflowDefinition).order_by(WorkflowDefinition.module, WorkflowDefinition.name).all()
    return [_definition_to_designer_dict(definition) for definition in definitions]


@router.get("/definitions/{definition_id}")
def get_definition(definition_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    definition = db.query(WorkflowDefinition).filter(WorkflowDefinition.id == definition_id).first()
    if not definition:
        raise HTTPException(status_code=404, detail="Workflow definition not found")
    return _definition_to_designer_dict(definition)


@router.put("/definitions/{definition_id}")
def update_definition(definition_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    definition = db.query(WorkflowDefinition).filter(WorkflowDefinition.id == definition_id).first()
    if not definition:
        raise HTTPException(status_code=404, detail="Workflow definition not found")
    for field in ["name", "module", "trigger_event", "description"]:
        if field in data:
            setattr(definition, field, data[field])
    db.commit()
    db.refresh(definition)
    return _definition_to_designer_dict(definition)


@router.delete("/definitions/{definition_id}")
def delete_definition(definition_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    definition = db.query(WorkflowDefinition).filter(WorkflowDefinition.id == definition_id).first()
    if not definition:
        raise HTTPException(status_code=404, detail="Workflow definition not found")
    definition.is_active = False
    db.commit()
    return {"message": "Workflow definition deactivated"}


@router.put("/definitions/{definition_id}/toggle-active")
def toggle_definition(definition_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    definition = db.query(WorkflowDefinition).filter(WorkflowDefinition.id == definition_id).first()
    if not definition:
        raise HTTPException(status_code=404, detail="Workflow definition not found")
    definition.is_active = not bool(definition.is_active)
    db.commit()
    db.refresh(definition)
    return _definition_to_designer_dict(definition)


@router.get("/definitions/{definition_id}/steps")
def list_definition_steps(definition_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    steps = db.query(WorkflowStepDefinition).filter(WorkflowStepDefinition.workflow_id == definition_id).order_by(WorkflowStepDefinition.step_order).all()
    return [_step_to_designer_dict(step) for step in steps]


@router.post("/definitions/{definition_id}/steps", status_code=201)
def create_definition_step(definition_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    if not db.query(WorkflowDefinition).filter(WorkflowDefinition.id == definition_id).first():
        raise HTTPException(status_code=404, detail="Workflow definition not found")
    step = WorkflowStepDefinition(workflow_id=definition_id, step_order=int(data.get("step_order", 1)))
    _apply_step_payload(step, data)
    db.add(step)
    db.commit()
    db.refresh(step)
    return _step_to_designer_dict(step)


@router.put("/definitions/{definition_id}/steps/{step_id}")
def update_definition_step(definition_id: int, step_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    step = db.query(WorkflowStepDefinition).filter(WorkflowStepDefinition.workflow_id == definition_id, WorkflowStepDefinition.id == step_id).first()
    if not step:
        raise HTTPException(status_code=404, detail="Workflow step not found")
    _apply_step_payload(step, data)
    db.commit()
    db.refresh(step)
    return _step_to_designer_dict(step)


@router.delete("/definitions/{definition_id}/steps/{step_id}")
def delete_definition_step(definition_id: int, step_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    step = db.query(WorkflowStepDefinition).filter(WorkflowStepDefinition.workflow_id == definition_id, WorkflowStepDefinition.id == step_id).first()
    if not step:
        raise HTTPException(status_code=404, detail="Workflow step not found")
    db.delete(step)
    db.commit()
    return {"message": "Workflow step deleted"}


@router.put("/definitions/{definition_id}/steps/reorder")
def reorder_definition_steps(definition_id: int, data: list[dict], db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    order_map = {int(item["step_id"]): int(item["step_order"]) for item in data}
    steps = db.query(WorkflowStepDefinition).filter(WorkflowStepDefinition.workflow_id == definition_id, WorkflowStepDefinition.id.in_(order_map.keys())).all()
    for step in steps:
        step.step_order = order_map[step.id]
    db.commit()
    return [_step_to_designer_dict(step) for step in sorted(steps, key=lambda item: item.step_order)]


@router.post("/instances", response_model=WorkflowInstanceSchema, status_code=201)
def start_instance(data: WorkflowInstanceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    definition = db.query(WorkflowDefinition).filter(WorkflowDefinition.id == data.workflow_id).first() if data.workflow_id else None
    instance = WorkflowInstance(**data.model_dump(), requester_user_id=current_user.id)
    db.add(instance)
    db.flush()
    if definition and not _create_next_pending_task(db, instance):
        instance.status = "Approved"
        instance.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(instance)
    return instance


@router.post("/instances/start", response_model=WorkflowInstanceSchema, status_code=201)
def start_instance_alias(data: WorkflowInstanceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return start_instance(data, db, current_user)


@router.get("/tasks", response_model=list[WorkflowTaskSchema])
def my_tasks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(WorkflowTask).filter(WorkflowTask.status == "Pending")
    role_name = current_user.role.name if current_user.role else None
    return query.filter((WorkflowTask.assigned_to_user_id == current_user.id) | (WorkflowTask.assigned_role == role_name)).order_by(WorkflowTask.created_at).limit(200).all()


@router.get("/inbox", response_model=list[WorkflowTaskSchema])
def workflow_inbox(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return my_tasks(db, current_user)


@router.put("/tasks/{task_id}/decision", response_model=WorkflowTaskSchema)
def decide_task(task_id: int, data: WorkflowTaskDecision, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Workflow task not found")
    task.status = "Completed"
    task.decision = data.decision
    task.decision_reason = data.reason
    task.decided_by = current_user.id
    task.decided_at = datetime.now(timezone.utc)
    instance = db.query(WorkflowInstance).filter(WorkflowInstance.id == task.instance_id).first()
    if instance:
        if data.decision.lower() == "approve":
            step = db.query(WorkflowStepDefinition).filter(WorkflowStepDefinition.id == task.step_definition_id).first()
            step_order = step.step_order if step else instance.current_step_order
            if not _create_next_pending_task(db, instance, after_step_order=step_order):
                instance.status = "Approved"
                instance.completed_at = datetime.now(timezone.utc)
        else:
            instance.status = "Rejected"
            instance.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task


@router.put("/tasks/{task_id}/approve", response_model=WorkflowTaskSchema)
def approve_task(task_id: int, data: dict | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return decide_task(task_id, WorkflowTaskDecision(decision="approve", reason=(data or {}).get("reason")), db, current_user)


@router.put("/tasks/{task_id}/reject", response_model=WorkflowTaskSchema)
def reject_task(task_id: int, data: dict | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return decide_task(task_id, WorkflowTaskDecision(decision="reject", reason=(data or {}).get("reason")), db, current_user)


@router.post("/tasks/process-escalations", response_model=list[WorkflowTaskSchema])
def process_escalations(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    now = datetime.now(timezone.utc)
    tasks = db.query(WorkflowTask).join(
        WorkflowStepDefinition,
        WorkflowTask.step_definition_id == WorkflowStepDefinition.id,
    ).filter(
        WorkflowTask.status == "Pending",
        WorkflowTask.due_at.isnot(None),
        WorkflowTask.due_at <= now,
        WorkflowTask.escalated_at.is_(None),
        WorkflowStepDefinition.escalation_user_id.isnot(None),
    ).all()
    for task in tasks:
        step = db.query(WorkflowStepDefinition).filter(WorkflowStepDefinition.id == task.step_definition_id).first()
        task.escalated_at = now
        task.escalated_to_user_id = step.escalation_user_id
        task.assigned_to_user_id = step.escalation_user_id
        task.assigned_role = None
    db.commit()
    return tasks


@router.post("/tasks/send-reminders", response_model=list[WorkflowTaskSchema])
def mark_due_reminders(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    now = datetime.now(timezone.utc)
    tasks = db.query(WorkflowTask).filter(
        WorkflowTask.status == "Pending",
        WorkflowTask.due_at.isnot(None),
        WorkflowTask.due_at <= now,
        WorkflowTask.reminder_sent_at.is_(None),
    ).all()
    for task in tasks:
        task.reminder_sent_at = now
    db.commit()
    return tasks
