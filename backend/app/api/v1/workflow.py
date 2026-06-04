from collections import Counter
from datetime import datetime, time, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.deps import RequirePermission, get_current_user, get_db
from app.core.masking import user_has_permission
from app.models.attendance import AttendanceRegularization
from app.models.employee import Employee
from app.models.leave import LeaveRequest
from app.models.payroll import PayrollRun, Reimbursement
from app.models.timesheet import Timesheet
from app.models.user import User
from app.models.workflow_engine import WorkflowDefinition, WorkflowStepDefinition
from app.schemas.workflow import WorkflowInboxItem, WorkflowInboxSummary

router = APIRouter(prefix="/workflow", tags=["Workflow Inbox"])


class WorkflowDefinitionPayload(BaseModel):
    name: str
    module: str
    trigger_event: str
    description: str | None = None


class WorkflowStepPayload(BaseModel):
    step_order: int | None = None
    step_type: str = "Approval"
    approver_type: str = "role"
    approver_value: str | None = None
    condition_expression: str | None = None
    skip_if_condition: str | None = None
    timeout_hours: int | None = None
    reminder_hours: int | None = None
    timeout_action: str | None = "escalate"
    escalation_user_id: int | None = None
    escalation_role: str | None = None
    action_type: str | None = None
    action_config: dict[str, Any] | None = None
    delegation_type: str | None = None
    delegation_value: str | None = None
    delegation_starts_at: datetime | None = None
    delegation_ends_at: datetime | None = None
    metadata_json: dict[str, Any] | None = None
    is_required: bool = True


class WorkflowStepOut(BaseModel):
    id: int
    workflow_id: int
    step_order: int
    step_type: str
    approver_type: str
    approver_value: str | None = None
    condition_expression: str | None = None
    skip_if_condition: str | None = None
    timeout_hours: int | None = None
    reminder_hours: int | None = None
    timeout_action: str | None = None
    escalation_user_id: int | None = None
    escalation_role: str | None = None
    action_type: str | None = None
    action_config: dict[str, Any] | None = None
    delegation_type: str | None = None
    delegation_value: str | None = None
    delegation_starts_at: datetime | None = None
    delegation_ends_at: datetime | None = None
    metadata_json: dict[str, Any] | None = None
    is_required: bool

    model_config = ConfigDict(from_attributes=True)


class WorkflowDefinitionOut(BaseModel):
    id: int
    name: str
    module: str
    trigger_event: str
    description: str | None = None
    is_active: bool
    created_by: int | None = None
    created_at: datetime | None = None
    steps: list[WorkflowStepOut] = []

    model_config = ConfigDict(from_attributes=True)


def _definition_or_404(db: Session, definition_id: int) -> WorkflowDefinition:
    definition = (
        db.query(WorkflowDefinition)
        .options(joinedload(WorkflowDefinition.steps))
        .filter(WorkflowDefinition.id == definition_id)
        .first()
    )
    if not definition:
        raise HTTPException(status_code=404, detail="Workflow definition not found")
    return definition


def _step_or_404(db: Session, definition_id: int, step_id: int) -> WorkflowStepDefinition:
    step = (
        db.query(WorkflowStepDefinition)
        .filter(
            WorkflowStepDefinition.workflow_id == definition_id,
            WorkflowStepDefinition.id == step_id,
        )
        .first()
    )
    if not step:
        raise HTTPException(status_code=404, detail="Workflow step not found")
    return step


def _renumber_steps(db: Session, definition_id: int) -> None:
    steps = (
        db.query(WorkflowStepDefinition)
        .filter(WorkflowStepDefinition.workflow_id == definition_id)
        .order_by(WorkflowStepDefinition.step_order, WorkflowStepDefinition.id)
        .all()
    )
    for index, step in enumerate(steps, start=1):
        step.step_order = index


@router.get("/definitions", response_model=list[WorkflowDefinitionOut])
def list_workflow_definitions(
    module: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    query = db.query(WorkflowDefinition).options(joinedload(WorkflowDefinition.steps))
    if module:
        query = query.filter(WorkflowDefinition.module == module)
    return query.order_by(WorkflowDefinition.module, WorkflowDefinition.name).all()


@router.post("/definitions", response_model=WorkflowDefinitionOut, status_code=201)
def create_workflow_definition(
    data: WorkflowDefinitionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    definition = WorkflowDefinition(**data.model_dump(), created_by=current_user.id)
    db.add(definition)
    db.commit()
    db.refresh(definition)
    return definition


@router.get("/definitions/{definition_id}", response_model=WorkflowDefinitionOut)
def get_workflow_definition(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    return _definition_or_404(db, definition_id)


@router.put("/definitions/{definition_id}", response_model=WorkflowDefinitionOut)
def update_workflow_definition(
    definition_id: int,
    data: WorkflowDefinitionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    definition = _definition_or_404(db, definition_id)
    for field, value in data.model_dump().items():
        setattr(definition, field, value)
    db.commit()
    db.refresh(definition)
    return definition


@router.delete("/definitions/{definition_id}", response_model=WorkflowDefinitionOut)
def delete_workflow_definition(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    definition = _definition_or_404(db, definition_id)
    definition.is_active = False
    db.commit()
    db.refresh(definition)
    return definition


@router.get("/definitions/{definition_id}/steps", response_model=list[WorkflowStepOut])
def list_workflow_steps(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    _definition_or_404(db, definition_id)
    return (
        db.query(WorkflowStepDefinition)
        .filter(WorkflowStepDefinition.workflow_id == definition_id)
        .order_by(WorkflowStepDefinition.step_order, WorkflowStepDefinition.id)
        .all()
    )


@router.post("/definitions/{definition_id}/steps", response_model=WorkflowStepOut, status_code=201)
def add_workflow_step(
    definition_id: int,
    data: WorkflowStepPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    _definition_or_404(db, definition_id)
    step_data = data.model_dump()
    if step_data["step_order"] is None:
        step_data["step_order"] = (
            db.query(func.coalesce(func.max(WorkflowStepDefinition.step_order), 0))
            .filter(WorkflowStepDefinition.workflow_id == definition_id)
            .scalar()
            + 1
        )
    step = WorkflowStepDefinition(workflow_id=definition_id, **step_data)
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


@router.put("/definitions/{definition_id}/steps/{step_id}", response_model=WorkflowStepOut)
def update_workflow_step(
    definition_id: int,
    step_id: int,
    data: WorkflowStepPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    step = _step_or_404(db, definition_id, step_id)
    for field, value in data.model_dump().items():
        setattr(step, field, value)
    db.commit()
    db.refresh(step)
    return step


@router.delete("/definitions/{definition_id}/steps/{step_id}", response_model=list[WorkflowStepOut])
def delete_workflow_step(
    definition_id: int,
    step_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    step = _step_or_404(db, definition_id, step_id)
    db.delete(step)
    db.flush()
    _renumber_steps(db, definition_id)
    db.commit()
    return list_workflow_steps(definition_id, db, current_user)


@router.post("/definitions/{definition_id}/activate", response_model=WorkflowDefinitionOut)
def activate_workflow_definition(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    definition = _definition_or_404(db, definition_id)
    definition.is_active = True
    db.commit()
    db.refresh(definition)
    return definition


@router.post("/definitions/{definition_id}/deactivate", response_model=WorkflowDefinitionOut)
def deactivate_workflow_definition(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    definition = _definition_or_404(db, definition_id)
    definition.is_active = False
    db.commit()
    db.refresh(definition)
    return definition


def _role_name(user: User) -> str:
    if user.is_superuser:
        return "admin"
    return user.role.name if user.role else "employee"


def _employee_name(employee: Employee | None) -> str | None:
    if not employee:
        return None
    return " ".join(part for part in [employee.first_name, employee.last_name] if part)


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min).replace(tzinfo=timezone.utc)


def _sort_datetime(value: datetime | None) -> datetime:
    if not value:
        return datetime.min
    if value.tzinfo:
        return value.replace(tzinfo=None)
    return value


def _add_item(
    items: list[WorkflowInboxItem],
    *,
    source: str,
    source_id: int,
    title: str,
    status: str,
    action_url: str,
    action_label: str,
    role_scope: str,
    employee: Employee | None = None,
    submitted_at: Any = None,
    priority: str = "Normal",
) -> None:
    items.append(
        WorkflowInboxItem(
            id=f"{source}:{source_id}",
            source=source,
            source_id=source_id,
            title=title,
            requester_employee_id=employee.id if employee else None,
            requester_name=_employee_name(employee),
            status=status,
            priority=priority,
            submitted_at=_as_datetime(submitted_at),
            action_url=action_url,
            action_label=action_label,
            role_scope=role_scope,
        )
    )


@router.get("/inbox", response_model=WorkflowInboxSummary)
def workflow_inbox(
    mine: bool = Query(False, description="Show items submitted by the logged-in employee"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items: list[WorkflowInboxItem] = []
    role = _role_name(current_user)
    employee = current_user.employee
    can_approve_leave = user_has_permission(current_user, "leave_approve")
    can_manage_attendance = user_has_permission(current_user, "attendance_manage")
    can_approve_timesheet = user_has_permission(current_user, "timesheet_approve")
    can_run_payroll = user_has_permission(current_user, "payroll_run")
    can_approve_payroll = user_has_permission(current_user, "payroll_approve")

    if mine and employee:
        leave_rows = (
            db.query(LeaveRequest)
            .filter(LeaveRequest.employee_id == employee.id)
            .order_by(LeaveRequest.applied_at.desc())
            .limit(50)
            .all()
        )
        for row in leave_rows:
            _add_item(
                items,
                source="leave",
                source_id=row.id,
                title=f"Leave request for {row.days_count} day(s)",
                status=row.status,
                employee=employee,
                submitted_at=row.applied_at,
                action_url="/leave",
                action_label="View leave",
                role_scope="employee",
            )

        timesheet_rows = (
            db.query(Timesheet)
            .filter(Timesheet.employee_id == employee.id)
            .order_by(Timesheet.created_at.desc())
            .limit(50)
            .all()
        )
        for row in timesheet_rows:
            _add_item(
                items,
                source="timesheet",
                source_id=row.id,
                title=f"Timesheet {row.period_start} to {row.period_end}",
                status=row.status,
                employee=employee,
                submitted_at=row.submitted_at or row.created_at,
                action_url="/timesheets",
                action_label="View timesheet",
                role_scope="employee",
            )

        reimbursement_rows = (
            db.query(Reimbursement)
            .filter(Reimbursement.employee_id == employee.id)
            .order_by(Reimbursement.created_at.desc())
            .limit(50)
            .all()
        )
        for row in reimbursement_rows:
            amount = f"{Decimal(row.amount or 0):,.2f}"
            _add_item(
                items,
                source="reimbursement",
                source_id=row.id,
                title=f"Reimbursement claim INR {amount}",
                status=row.status,
                employee=employee,
                submitted_at=row.created_at,
                action_url="/payroll",
                action_label="View claim",
                role_scope="employee",
            )

    else:
        if can_approve_leave:
            query = db.query(LeaveRequest).join(Employee, Employee.id == LeaveRequest.employee_id).filter(LeaveRequest.status == "Pending")
            if role == "manager" and employee:
                query = query.filter(Employee.reporting_manager_id == employee.id)
            for row in query.order_by(LeaveRequest.applied_at.asc()).limit(100).all():
                _add_item(
                    items,
                    source="leave",
                    source_id=row.id,
                    title=f"Leave approval for {row.days_count} day(s)",
                    status=row.status,
                    employee=row.employee,
                    submitted_at=row.applied_at,
                    action_url="/leave",
                    action_label="Review leave",
                    role_scope=role,
                )

        if can_approve_timesheet:
            query = db.query(Timesheet).join(Employee, Employee.id == Timesheet.employee_id).filter(Timesheet.status == "Submitted")
            if role == "manager" and employee:
                query = query.filter(Employee.reporting_manager_id == employee.id)
            for row in query.order_by(Timesheet.submitted_at.asc()).limit(100).all():
                _add_item(
                    items,
                    source="timesheet",
                    source_id=row.id,
                    title=f"Timesheet approval {row.period_start} to {row.period_end}",
                    status=row.status,
                    employee=db.query(Employee).filter(Employee.id == row.employee_id).first(),
                    submitted_at=row.submitted_at,
                    action_url="/timesheets",
                    action_label="Review timesheet",
                    role_scope=role,
                )

        if can_manage_attendance:
            query = (
                db.query(AttendanceRegularization)
                .join(Employee, Employee.id == AttendanceRegularization.employee_id)
                .filter(AttendanceRegularization.status == "Pending")
            )
            if role == "manager" and employee:
                query = query.filter(Employee.reporting_manager_id == employee.id)
            for row in query.order_by(AttendanceRegularization.created_at.asc()).limit(100).all():
                requester = db.query(Employee).filter(Employee.id == row.employee_id).first()
                _add_item(
                    items,
                    source="attendance",
                    source_id=row.id,
                    title="Attendance regularization",
                    status=row.status,
                    employee=requester,
                    submitted_at=row.created_at,
                    action_url="/attendance",
                    action_label="Review attendance",
                    role_scope=role,
                )

        if can_run_payroll:
            reimbursement_rows = db.query(Reimbursement).filter(Reimbursement.status == "Pending").order_by(Reimbursement.created_at.asc()).limit(100).all()
            for row in reimbursement_rows:
                requester = db.query(Employee).filter(Employee.id == row.employee_id).first()
                amount = f"{Decimal(row.amount or 0):,.2f}"
                _add_item(
                    items,
                    source="reimbursement",
                    source_id=row.id,
                    title=f"Reimbursement claim INR {amount}",
                    status=row.status,
                    employee=requester,
                    submitted_at=row.created_at,
                    action_url="/payroll",
                    action_label="Review claim",
                    role_scope=role,
                )

        if can_approve_payroll:
            payroll_rows = db.query(PayrollRun).filter(
                PayrollRun.status.in_(["calculated", "Completed"])
            ).order_by(PayrollRun.created_at.asc()).limit(50).all()
            for row in payroll_rows:
                _add_item(
                    items,
                    source="payroll",
                    source_id=row.id,
                    title=f"Payroll approval for {row.month:02d}/{row.year}",
                    status=row.status,
                    submitted_at=row.created_at,
                    action_url="/payroll",
                    action_label="Approve payroll",
                    role_scope=role,
                    priority="High",
                )

    items.sort(key=lambda item: _sort_datetime(item.submitted_at), reverse=True)
    by_source = dict(Counter(item.source for item in items))
    submitted_by_me = len([item for item in items if employee and item.requester_employee_id == employee.id])
    return WorkflowInboxSummary(
        total=len(items),
        pending_action=len([item for item in items if item.status in {"Pending", "Submitted", "Completed"}]),
        submitted_by_me=submitted_by_me,
        by_source=by_source,
        items=items[:200],
    )
