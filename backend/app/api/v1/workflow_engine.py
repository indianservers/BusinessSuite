from datetime import datetime, timedelta, timezone
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.core.deps import RequirePermission, get_current_user, get_db
from app.models.attendance import AttendanceRegularization
from app.models.employee import Employee
from app.models.expense import ExpenseClaim
from app.models.leave import LeaveRequest
from app.models.payroll import PayrollRun, Reimbursement
from app.models.user import User
from app.models.workflow_engine import (
    WorkflowAuditEvent,
    WorkflowDefinition,
    WorkflowDelegation,
    WorkflowInstance,
    WorkflowStepDefinition,
    WorkflowTask,
)
from app.schemas.workflow_engine import (
    WorkflowDefinitionCreate, WorkflowDefinitionSchema, WorkflowInstanceCreate,
    WorkflowAuditEventSchema, WorkflowDelegationCreate, WorkflowDelegationSchema,
    WorkflowInstanceSchema, WorkflowTaskDecision, WorkflowTaskSchema,
)

router = APIRouter(prefix="/workflow-engine", tags=["Workflow Engine"])

ALLOWED_CONDITION_FIELDS = {
    "amount",
    "days_count",
    "leave_days",
    "department",
    "department_id",
    "role",
    "employee_type",
    "location",
    "work_location",
    "requires_hr",
    "employee.department",
    "employee.department_id",
    "employee.role",
    "employee.employee_type",
    "employee.location",
    "employee.work_location",
    "request.amount",
    "request.days_count",
    "request.leave_days",
    "request.department",
    "request.role",
    "request.employee_type",
    "request.location",
    "payroll.amount",
    "leave.days_count",
    "leave.leave_days",
}

ACTION_TARGETS = {
    "leave": (LeaveRequest, {"status", "review_remarks"}),
    "attendance": (AttendanceRegularization, {"status", "manager_remarks", "hr_remarks"}),
    "expense": (ExpenseClaim, {"status", "approval_notes", "finance_notes"}),
    "payroll": (PayrollRun, {"status", "approval_status", "remarks"}),
    "reimbursement": (Reimbursement, {"status", "approval_status", "payment_status", "remarks"}),
    "employee": (Employee, {"status", "probation_status", "work_location", "background_verification_status"}),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _audit(
    db: Session,
    instance: WorkflowInstance,
    event_type: str,
    *,
    task: WorkflowTask | None = None,
    step: WorkflowStepDefinition | None = None,
    actor_user_id: int | None = None,
    before_status: str | None = None,
    after_status: str | None = None,
    reason: str | None = None,
    details: dict | None = None,
) -> None:
    db.add(WorkflowAuditEvent(
        instance_id=instance.id,
        task_id=task.id if task else None,
        step_definition_id=(step.id if step else task.step_definition_id if task else None),
        event_type=event_type,
        actor_user_id=actor_user_id,
        before_status=before_status,
        after_status=after_status,
        reason=reason,
        details_json=details or {},
    ))


def _literal(value: str):
    raw = value.strip()
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    if (raw.startswith("'") and raw.endswith("'")) or (raw.startswith('"') and raw.endswith('"')):
        return raw[1:-1]
    try:
        return float(raw) if "." in raw else int(raw)
    except ValueError:
        return raw


def _coerce_comparable(value):
    if isinstance(value, str):
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered in {"null", "none"}:
            return None
    return value


def _parse_datetime(value):
    if not value or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _lookup_context(context: dict, key: str):
    if key not in ALLOWED_CONDITION_FIELDS:
        raise ValueError(f"Condition field '{key}' is not allowed")
    actual = context
    for part in key.split("."):
        actual = actual.get(part) if isinstance(actual, dict) else None
    return actual


def _condition_matches(expression: str | None, context: dict | None) -> bool:
    if not expression:
        return True
    context = context or {}
    or_groups = re.split(r"\s+or\s+", expression, flags=re.IGNORECASE)
    return any(all(_single_condition_matches(part, context) for part in re.split(r"\s+and\s+", group, flags=re.IGNORECASE)) for group in or_groups)


def _single_condition_matches(expression: str, context: dict) -> bool:
    match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_.]*)\s*(not\s+in|in|==|!=|>=|<=|>|<)\s*(.+?)\s*$", expression, re.IGNORECASE)
    if not match:
        raise HTTPException(status_code=400, detail=f"Invalid workflow condition: {expression.strip()}")
    key, operator, expected_raw = match.groups()
    actual_value = _coerce_comparable(_lookup_context(context, key))
    expected_value = _literal(expected_raw)
    operator = operator.lower()
    if operator in {"in", "not in"}:
        if isinstance(expected_value, str):
            expected_values = [item.strip() for item in expected_value.split(",")]
        elif isinstance(expected_value, (list, tuple, set)):
            expected_values = list(expected_value)
        else:
            expected_values = [expected_value]
        result = actual_value in expected_values
        return not result if operator == "not in" else result
    try:
        comparable_actual = float(actual_value)
        comparable_expected = float(expected_value)
    except (TypeError, ValueError):
        comparable_actual = "" if actual_value is None else str(actual_value)
        comparable_expected = "" if expected_value is None else str(expected_value)
    if operator == "==":
        return comparable_actual == comparable_expected
    if operator == "!=":
        return comparable_actual != comparable_expected
    if operator == ">=":
        return comparable_actual >= comparable_expected
    if operator == "<=":
        return comparable_actual <= comparable_expected
    if operator == ">":
        return comparable_actual > comparable_expected
    if operator == "<":
        return comparable_actual < comparable_expected
    return False


def _validate_step(step: WorkflowStepDefinition) -> None:
    for expression in [step.condition_expression, step.skip_if_condition]:
        if expression:
            try:
                _condition_matches(expression, {})
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
    if (step.step_type or "").lower() == "action":
        config = step.action_config or {}
        fields = config.get("fields") or {}
        if step.action_type != "field_update" or not isinstance(fields, dict):
            raise HTTPException(status_code=400, detail="Action steps require action_type=field_update and fields")
        _, allowed_fields = _action_target(step, None)
        unsafe = set(fields) - allowed_fields
        if unsafe:
            raise HTTPException(status_code=400, detail=f"Unsafe workflow action fields: {', '.join(sorted(unsafe))}")


def _action_target(step: WorkflowStepDefinition, instance: WorkflowInstance | None):
    config = step.action_config or {}
    module_key = config.get("target_module") or (instance.module if instance else None)
    target = ACTION_TARGETS.get(str(module_key or "").lower())
    if not target:
        raise HTTPException(status_code=400, detail=f"Workflow field updates are not supported for module '{module_key}'")
    return target


def _resolve_assignment(db: Session, instance: WorkflowInstance, step: WorkflowStepDefinition) -> dict:
    assignment = {
        "assigned_role": step.approver_value if step.approver_type == "Role" else None,
        "assigned_to_user_id": int(step.approver_value) if step.approver_type == "User" and str(step.approver_value or "").isdigit() else None,
    }
    now = _now()
    delegated = None
    if step.delegation_type and step.delegation_value:
        starts_at = _aware(step.delegation_starts_at)
        ends_at = _aware(step.delegation_ends_at)
        starts_ok = starts_at is None or starts_at <= now
        ends_ok = ends_at is None or ends_at >= now
        if starts_ok and ends_ok:
            delegated = {
                "type": step.delegation_type,
                "value": step.delegation_value,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "reason": "Step-level delegation",
            }
    if not delegated:
        filters = [
            WorkflowDelegation.is_active.is_(True),
            WorkflowDelegation.starts_at <= now,
            WorkflowDelegation.ends_at >= now,
            or_(WorkflowDelegation.module.is_(None), WorkflowDelegation.module == instance.module),
        ]
        if assignment["assigned_to_user_id"]:
            filters.append(WorkflowDelegation.delegator_user_id == assignment["assigned_to_user_id"])
        elif assignment["assigned_role"]:
            filters.append(WorkflowDelegation.delegator_role == assignment["assigned_role"])
        else:
            filters.append(WorkflowDelegation.id == -1)
        record = db.query(WorkflowDelegation).filter(*filters).order_by(WorkflowDelegation.created_at.desc()).first()
        if record:
            delegated = {
                "type": "User" if record.delegate_to_user_id else "Role",
                "value": str(record.delegate_to_user_id or record.delegate_to_role),
                "starts_at": record.starts_at,
                "ends_at": record.ends_at,
                "reason": record.reason or "Delegation rule",
            }
    if delegated:
        assignment["original_assigned_to_user_id"] = assignment["assigned_to_user_id"]
        assignment["original_assigned_role"] = assignment["assigned_role"]
        assignment["delegation_reason"] = delegated["reason"]
        assignment["delegation_started_at"] = delegated["starts_at"]
        assignment["delegation_ends_at"] = delegated["ends_at"]
        if delegated["type"] == "User":
            assignment["delegated_to_user_id"] = int(delegated["value"])
            assignment["assigned_to_user_id"] = int(delegated["value"])
            assignment["assigned_role"] = None
        else:
            assignment["delegated_role"] = delegated["value"]
            assignment["assigned_role"] = delegated["value"]
            assignment["assigned_to_user_id"] = None
    return assignment


def _assign_task_from_step(db: Session, instance: WorkflowInstance, step: WorkflowStepDefinition) -> WorkflowTask:
    assignment = _resolve_assignment(db, instance, step)
    task = WorkflowTask(
        instance_id=instance.id,
        step_definition_id=step.id,
        due_at=datetime.now(timezone.utc) + timedelta(hours=step.timeout_hours) if step.timeout_hours else None,
        **assignment,
    )
    return task


def _apply_field_update(db: Session, instance: WorkflowInstance, step: WorkflowStepDefinition) -> dict:
    model, allowed_fields = _action_target(step, instance)
    config = step.action_config or {}
    fields = config.get("fields") or {}
    unsafe = set(fields) - allowed_fields
    if unsafe:
        raise HTTPException(status_code=400, detail=f"Unsafe workflow action fields: {', '.join(sorted(unsafe))}")
    target_id = int(config.get("target_id") or instance.entity_id)
    target = db.query(model).filter(model.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Workflow action target not found")
    before = {field: getattr(target, field, None) for field in fields}
    for field, value in fields.items():
        setattr(target, field, value)
    after = {field: getattr(target, field, None) for field in fields}
    return {"target_module": config.get("target_module") or instance.module, "target_id": target_id, "before": before, "after": after}


def _run_automatic_step(db: Session, instance: WorkflowInstance, step: WorkflowStepDefinition) -> None:
    step_kind = (step.step_type or "approval").lower()
    if step_kind == "action":
        details = _apply_field_update(db, instance, step)
        _audit(db, instance, "action_applied", step=step, before_status=instance.status, after_status=instance.status, details=details)
    elif step_kind in {"notification", "condition"}:
        _audit(db, instance, "step_skipped", step=step, reason=f"{step_kind} step recorded without human task", details={"step_type": step_kind})


def _create_next_pending_task(db: Session, instance: WorkflowInstance, after_step_order: int = 0) -> bool:
    if not instance.workflow_id:
        return False
    steps = db.query(WorkflowStepDefinition).filter(
        WorkflowStepDefinition.workflow_id == instance.workflow_id,
        WorkflowStepDefinition.step_order > after_step_order,
    ).order_by(WorkflowStepDefinition.step_order).all()
    grouped: dict[int, list[WorkflowStepDefinition]] = {}
    for step in steps:
        grouped.setdefault(step.step_order, []).append(step)
    for step_order in sorted(grouped):
        created_tasks = []
        automatic_only = False
        for step in grouped[step_order]:
            if not step.is_required:
                _audit(db, instance, "step_skipped", step=step, reason="Step is inactive")
                continue
            try:
                skip_matched = bool(step.skip_if_condition and _condition_matches(step.skip_if_condition, instance.context_json))
                condition_matched = _condition_matches(step.condition_expression, instance.context_json)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            if skip_matched:
                _audit(db, instance, "step_skipped", step=step, reason="skip_if_condition matched", details={"condition": step.skip_if_condition})
                continue
            if not condition_matched:
                _audit(db, instance, "step_skipped", step=step, reason="condition_expression did not match", details={"condition": step.condition_expression})
                continue
            step_kind = (step.step_type or "approval").lower()
            if step_kind in {"action", "notification", "condition"}:
                _run_automatic_step(db, instance, step)
                automatic_only = True
                continue
            task = _assign_task_from_step(db, instance, step)
            db.add(task)
            db.flush()
            created_tasks.append(task)
        if created_tasks:
            instance.current_step_order = step_order
            instance.status = "Pending"
            for task in created_tasks:
                _audit(db, instance, "task_created", task=task, before_status=instance.status, after_status="Pending")
            return True
        if automatic_only:
            instance.current_step_order = step_order
            continue
    return False


def _step_to_designer_dict(step: WorkflowStepDefinition) -> dict:
    assignee_type = (step.approver_type or "Role").lower()
    metadata = step.metadata_json or {}
    return {
        "id": step.id,
        "definition_id": step.workflow_id,
        "workflow_id": step.workflow_id,
        "step_order": step.step_order,
        "name": metadata.get("name") or step.step_type or f"Step {step.step_order}",
        "step_type": (step.step_type or "approval").lower(),
        "assignee_type": "role" if assignee_type == "role" else "user" if assignee_type == "user" else assignee_type,
        "assignee_role": step.approver_value if assignee_type == "role" else None,
        "assignee_user_id": int(step.approver_value) if assignee_type == "user" and str(step.approver_value or "").isdigit() else None,
        "timeout_hours": step.timeout_hours,
        "timeout_action": step.timeout_action or "escalate",
        "condition_expression": step.condition_expression,
        "skip_if_condition": step.skip_if_condition,
        "reminder_hours": step.reminder_hours,
        "escalation_user_id": step.escalation_user_id,
        "escalation_role": step.escalation_role,
        "action_type": step.action_type,
        "action_config": step.action_config,
        "delegation_type": step.delegation_type,
        "delegation_value": step.delegation_value,
        "delegation_starts_at": step.delegation_starts_at,
        "delegation_ends_at": step.delegation_ends_at,
        "is_active": step.is_required,
        "description": metadata.get("description"),
        "metadata_json": metadata,
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
    step.step_type = payload.get("step_type") or step.step_type
    metadata = dict(step.metadata_json or {})
    if "name" in payload:
        metadata["name"] = payload.get("name")
    if "description" in payload:
        metadata["description"] = payload.get("description")
    step.metadata_json = metadata
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
    step.skip_if_condition = payload.get("skip_if_condition")
    step.timeout_hours = payload.get("timeout_hours")
    step.reminder_hours = payload.get("reminder_hours")
    step.timeout_action = payload.get("timeout_action") or "escalate"
    step.escalation_user_id = payload.get("escalation_user_id")
    step.escalation_role = payload.get("escalation_role")
    step.action_type = payload.get("action_type")
    step.action_config = payload.get("action_config")
    step.delegation_type = payload.get("delegation_type")
    step.delegation_value = payload.get("delegation_value")
    step.delegation_starts_at = _parse_datetime(payload.get("delegation_starts_at"))
    step.delegation_ends_at = _parse_datetime(payload.get("delegation_ends_at"))
    step.is_required = bool(payload.get("is_active", payload.get("is_required", True)))
    _validate_step(step)


@router.post("/definitions", response_model=WorkflowDefinitionSchema, status_code=201)
def create_definition(data: WorkflowDefinitionCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    definition = WorkflowDefinition(**data.model_dump(exclude={"steps"}), created_by=current_user.id)
    db.add(definition)
    db.flush()
    for step in data.steps:
        step_model = WorkflowStepDefinition(workflow_id=definition.id, **step.model_dump())
        _validate_step(step_model)
        db.add(step_model)
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
    if not definition.is_active:
        for step in definition.steps:
            _validate_step(step)
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
    definition = db.query(WorkflowDefinition).filter(WorkflowDefinition.id == data.workflow_id, WorkflowDefinition.is_active.is_(True)).first() if data.workflow_id else None
    instance = WorkflowInstance(**data.model_dump(), requester_user_id=current_user.id)
    db.add(instance)
    db.flush()
    _audit(db, instance, "instance_started", actor_user_id=current_user.id, after_status=instance.status)
    if definition and not _create_next_pending_task(db, instance):
        instance.status = "Approved"
        instance.completed_at = _now()
        _audit(db, instance, "instance_completed", actor_user_id=current_user.id, before_status="Pending", after_status="Approved", reason="No matching approval steps")
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
    if task.status != "Pending":
        raise HTTPException(status_code=400, detail="Workflow task is not pending")
    role_name = current_user.role.name if current_user.role else None
    if task.assigned_to_user_id != current_user.id and task.assigned_role != role_name:
        raise HTTPException(status_code=403, detail="Workflow task is not assigned to the current user")
    before_task_status = task.status
    task.status = "Completed"
    task.decision = data.decision
    task.decision_reason = data.reason
    task.decided_by = current_user.id
    task.decided_at = _now()
    db.flush()
    instance = db.query(WorkflowInstance).filter(WorkflowInstance.id == task.instance_id).first()
    if instance:
        before_instance_status = instance.status
        if data.decision.lower() == "approve":
            step = db.query(WorkflowStepDefinition).filter(WorkflowStepDefinition.id == task.step_definition_id).first()
            step_order = step.step_order if step else instance.current_step_order
            open_parallel_tasks = db.query(WorkflowTask).join(
                WorkflowStepDefinition,
                WorkflowTask.step_definition_id == WorkflowStepDefinition.id,
            ).filter(
                WorkflowTask.instance_id == instance.id,
                WorkflowTask.status == "Pending",
                WorkflowStepDefinition.step_order == step_order,
            ).count()
            _audit(db, instance, "task_approved", task=task, step=step, actor_user_id=current_user.id, before_status=before_task_status, after_status=task.status, reason=data.reason)
            if open_parallel_tasks:
                db.commit()
                db.refresh(task)
                return task
            if not _create_next_pending_task(db, instance, after_step_order=step_order):
                instance.status = "Approved"
                instance.completed_at = _now()
                _audit(db, instance, "instance_completed", actor_user_id=current_user.id, before_status=before_instance_status, after_status="Approved")
        else:
            instance.status = "Rejected"
            instance.completed_at = _now()
            _audit(db, instance, "task_rejected", task=task, actor_user_id=current_user.id, before_status=before_task_status, after_status=task.status, reason=data.reason)
            _audit(db, instance, "instance_completed", actor_user_id=current_user.id, before_status=before_instance_status, after_status="Rejected", reason=data.reason)
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
    now = _now()
    tasks = db.query(WorkflowTask).join(
        WorkflowStepDefinition,
        WorkflowTask.step_definition_id == WorkflowStepDefinition.id,
    ).filter(
        WorkflowTask.status == "Pending",
        WorkflowTask.due_at.isnot(None),
        WorkflowTask.due_at <= now,
        WorkflowTask.escalated_at.is_(None),
    ).all()
    for task in tasks:
        step = db.query(WorkflowStepDefinition).filter(WorkflowStepDefinition.id == task.step_definition_id).first()
        if not step:
            continue
        if (step.timeout_action or "escalate") == "auto_approve":
            task.status = "Completed"
            task.decision = "approve"
            task.decision_reason = "Auto-approved after timeout"
            task.decided_by = current_user.id
            task.decided_at = now
            instance = db.query(WorkflowInstance).filter(WorkflowInstance.id == task.instance_id).first()
            if instance:
                _audit(db, instance, "task_auto_approved", task=task, step=step, actor_user_id=current_user.id, before_status="Pending", after_status="Completed")
                if not _create_next_pending_task(db, instance, after_step_order=step.step_order):
                    instance.status = "Approved"
                    instance.completed_at = now
            continue
        if (step.timeout_action or "escalate") == "auto_reject":
            task.status = "Completed"
            task.decision = "reject"
            task.decision_reason = "Auto-rejected after timeout"
            task.decided_by = current_user.id
            task.decided_at = now
            instance = db.query(WorkflowInstance).filter(WorkflowInstance.id == task.instance_id).first()
            if instance:
                instance.status = "Rejected"
                instance.completed_at = now
                _audit(db, instance, "task_auto_rejected", task=task, step=step, actor_user_id=current_user.id, before_status="Pending", after_status="Completed")
            continue
        if not step.escalation_user_id and not step.escalation_role:
            continue
        task.escalated_at = now
        task.escalated_to_user_id = step.escalation_user_id
        task.assigned_to_user_id = step.escalation_user_id
        task.assigned_role = None if step.escalation_user_id else step.escalation_role
        instance = db.query(WorkflowInstance).filter(WorkflowInstance.id == task.instance_id).first()
        if instance:
            _audit(db, instance, "task_escalated", task=task, step=step, actor_user_id=current_user.id, before_status="Pending", after_status="Pending", details={"escalated_to_user_id": step.escalation_user_id, "escalation_role": step.escalation_role})
    db.commit()
    return tasks


@router.post("/tasks/send-reminders", response_model=list[WorkflowTaskSchema])
def mark_due_reminders(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    now = _now()
    tasks = db.query(WorkflowTask).join(
        WorkflowStepDefinition,
        WorkflowTask.step_definition_id == WorkflowStepDefinition.id,
    ).filter(
        WorkflowTask.status == "Pending",
        WorkflowTask.due_at.isnot(None),
        WorkflowTask.reminder_sent_at.is_(None),
    ).all()
    due_tasks = []
    for task in tasks:
        step = db.query(WorkflowStepDefinition).filter(WorkflowStepDefinition.id == task.step_definition_id).first()
        reminder_hours = step.reminder_hours if step else None
        due_at = _aware(task.due_at)
        if not due_at:
            continue
        reminder_at = due_at - timedelta(hours=reminder_hours or 0)
        if reminder_at > now:
            continue
        task.reminder_sent_at = now
        due_tasks.append(task)
        instance = db.query(WorkflowInstance).filter(WorkflowInstance.id == task.instance_id).first()
        if instance:
            _audit(db, instance, "reminder_sent", task=task, step=step, actor_user_id=current_user.id, details={"reminder_hours": reminder_hours})
    db.commit()
    return due_tasks


@router.post("/delegations", response_model=WorkflowDelegationSchema, status_code=201)
def create_delegation(data: WorkflowDelegationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if data.ends_at <= data.starts_at:
        raise HTTPException(status_code=400, detail="Delegation end must be after start")
    if not data.delegator_user_id and not data.delegator_role:
        raise HTTPException(status_code=400, detail="Delegation requires a delegator user or role")
    if not data.delegate_to_user_id and not data.delegate_to_role:
        raise HTTPException(status_code=400, detail="Delegation requires a delegate user or role")
    if data.delegator_user_id and data.delegator_user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Cannot create delegation for another user")
    delegation = WorkflowDelegation(**data.model_dump(), created_by=current_user.id)
    db.add(delegation)
    db.commit()
    db.refresh(delegation)
    return delegation


@router.get("/delegations", response_model=list[WorkflowDelegationSchema])
def list_delegations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.is_superuser:
        return db.query(WorkflowDelegation).order_by(WorkflowDelegation.created_at.desc()).limit(200).all()
    role_name = current_user.role.name if current_user.role else None
    return db.query(WorkflowDelegation).filter(
        or_(
            WorkflowDelegation.delegator_user_id == current_user.id,
            WorkflowDelegation.delegate_to_user_id == current_user.id,
            WorkflowDelegation.delegator_role == role_name,
            WorkflowDelegation.delegate_to_role == role_name,
        )
    ).order_by(WorkflowDelegation.created_at.desc()).limit(200).all()


@router.put("/delegations/{delegation_id}/deactivate", response_model=WorkflowDelegationSchema)
def deactivate_delegation(delegation_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    delegation = db.query(WorkflowDelegation).filter(WorkflowDelegation.id == delegation_id).first()
    if not delegation:
        raise HTTPException(status_code=404, detail="Workflow delegation not found")
    if delegation.created_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Cannot deactivate this delegation")
    delegation.is_active = False
    db.commit()
    db.refresh(delegation)
    return delegation


@router.get("/instances/{instance_id}/audit", response_model=list[WorkflowAuditEventSchema])
def instance_audit(instance_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = db.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Workflow instance not found")
    if instance.requester_user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Cannot view this workflow audit")
    return db.query(WorkflowAuditEvent).filter(WorkflowAuditEvent.instance_id == instance_id).order_by(WorkflowAuditEvent.created_at, WorkflowAuditEvent.id).all()
