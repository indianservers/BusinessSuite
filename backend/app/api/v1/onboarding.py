from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import RequirePermission, get_current_user, get_db
from app.crud.crud_onboarding import create_employee_onboarding, get_employee_onboarding, mark_task
from app.models.employee import Employee
from app.models.onboarding import (
    EmployeeOnboarding,
    EmployeeOnboardingTask,
    OnboardingTemplate,
    OnboardingTemplateTask,
    PolicyAcknowledgement,
)
from app.models.user import User
from app.schemas.onboarding import (
    EmployeeOnboardingResponse,
    EmployeeOnboardingStart,
    EmployeeOnboardingTaskResponse,
    OnboardingTaskAction,
    OnboardingTemplateCreate,
    OnboardingTemplateResponse,
    OnboardingTemplateTaskCreate,
    OnboardingTemplateTaskResponse,
    PolicyAcknowledgementCreate,
    PolicyAcknowledgementSchema,
)

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


def _permissions(user: User) -> set[str]:
    return {permission.name for permission in (user.role.permissions if user.role else [])}


def _role_name(user: User) -> str:
    return (user.role.name if user.role else "").lower().replace(" ", "_")


def _is_hr_admin(user: User) -> bool:
    return user.is_superuser or "hr_admin" in _permissions(user) or _role_name(user) in {
        "admin",
        "super_admin",
        "hr",
        "hr_admin",
        "hr_manager",
    }


def _ensure_hr_admin(user: User) -> None:
    if not _is_hr_admin(user):
        raise HTTPException(status_code=403, detail="HR admin access required")


def _employee_or_404(db: Session, employee_id: int) -> Employee:
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.deleted_at.is_(None)).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


def _template_or_404(db: Session, template_id: int) -> OnboardingTemplate:
    template = (
        db.query(OnboardingTemplate)
        .options(joinedload(OnboardingTemplate.tasks))
        .filter(OnboardingTemplate.id == template_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Onboarding template not found")
    return template


def _can_view_employee_onboarding(user: User, employee: Employee) -> bool:
    if _is_hr_admin(user):
        return True
    if user.employee and user.employee.id == employee.id:
        return True
    if user.employee and employee.reporting_manager_id == user.employee.id:
        return True
    return False


def _can_update_task(user: User, task: EmployeeOnboardingTask) -> bool:
    onboarding = task.employee_onboarding
    employee = onboarding.employee if onboarding else None
    if _is_hr_admin(user):
        return True
    if task.assigned_to_user_id and task.assigned_to_user_id == user.id:
        return True
    if user.employee and employee:
        return employee.id == user.employee.id or employee.reporting_manager_id == user.employee.id
    return False


@router.get("/templates", response_model=list[OnboardingTemplateResponse])
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_hr_admin(current_user)
    return (
        db.query(OnboardingTemplate)
        .options(joinedload(OnboardingTemplate.tasks))
        .order_by(OnboardingTemplate.created_at.desc(), OnboardingTemplate.id.desc())
        .all()
    )


@router.post("/templates", response_model=OnboardingTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(
    data: OnboardingTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_hr_admin(current_user)
    template = OnboardingTemplate(**data.model_dump(), created_by=current_user.id)
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.post(
    "/templates/{template_id}/tasks",
    response_model=OnboardingTemplateTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_template_task(
    template_id: int,
    data: OnboardingTemplateTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_hr_admin(current_user)
    _template_or_404(db, template_id)
    task = OnboardingTemplateTask(template_id=template_id, **data.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.post("/start", response_model=EmployeeOnboardingResponse, status_code=status.HTTP_201_CREATED)
def start_onboarding(
    data: EmployeeOnboardingStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_hr_admin(current_user)
    employee = _employee_or_404(db, data.employee_id)
    template = _template_or_404(db, data.template_id)
    onboarding = create_employee_onboarding(
        db,
        employee=employee,
        template=template,
        start_date=data.start_date,
        created_by=current_user.id,
    )
    return onboarding


@router.get("/my", response_model=EmployeeOnboardingResponse)
def my_onboarding(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=404, detail="Employee profile not linked")
    onboarding = get_employee_onboarding(db, current_user.employee.id)
    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding record not found")
    return onboarding


@router.put("/tasks/{task_id}/complete", response_model=EmployeeOnboardingTaskResponse)
def complete_task(
    task_id: int,
    data: OnboardingTaskAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = (
        db.query(EmployeeOnboardingTask)
        .options(joinedload(EmployeeOnboardingTask.employee_onboarding).joinedload(EmployeeOnboarding.employee))
        .filter(EmployeeOnboardingTask.id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Onboarding task not found")
    if not _can_update_task(current_user, task):
        raise HTTPException(status_code=403, detail="Not allowed to update this onboarding task")
    return mark_task(db, task=task, status="completed", user_id=current_user.id, notes=data.notes)


@router.put("/tasks/{task_id}/skip", response_model=EmployeeOnboardingTaskResponse)
def skip_task(
    task_id: int,
    data: OnboardingTaskAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = (
        db.query(EmployeeOnboardingTask)
        .options(joinedload(EmployeeOnboardingTask.employee_onboarding).joinedload(EmployeeOnboarding.employee))
        .filter(EmployeeOnboardingTask.id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Onboarding task not found")
    if not _can_update_task(current_user, task):
        raise HTTPException(status_code=403, detail="Not allowed to update this onboarding task")
    notes = data.reason or data.notes
    if not notes:
        raise HTTPException(status_code=422, detail="Reason is required to skip a task")
    return mark_task(db, task=task, status="skipped", user_id=current_user.id, notes=notes)


@router.get("/employees", response_model=list[EmployeeOnboardingResponse])
def list_employee_onboarding(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_view")),
):
    if _is_hr_admin(current_user):
        query = db.query(EmployeeOnboarding)
    elif current_user.employee:
        query = db.query(EmployeeOnboarding).join(Employee).filter(Employee.reporting_manager_id == current_user.employee.id)
    else:
        raise HTTPException(status_code=403, detail="Employee profile is required")
    return (
        query.options(joinedload(EmployeeOnboarding.tasks))
        .order_by(EmployeeOnboarding.created_at.desc(), EmployeeOnboarding.id.desc())
        .limit(200)
        .all()
    )


@router.post("/employees", response_model=EmployeeOnboardingResponse, status_code=status.HTTP_201_CREATED)
def start_employee_onboarding_legacy(
    data: EmployeeOnboardingStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return start_onboarding(data, db, current_user)


@router.put("/employees/{onboarding_id}/complete", response_model=EmployeeOnboardingResponse)
def complete_onboarding_legacy(
    onboarding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_hr_admin(current_user)
    onboarding = (
        db.query(EmployeeOnboarding)
        .options(joinedload(EmployeeOnboarding.tasks))
        .filter(EmployeeOnboarding.id == onboarding_id)
        .first()
    )
    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding record not found")
    onboarding.status = "completed"
    onboarding.completion_percentage = 100
    for task in onboarding.tasks:
        if task.status not in {"completed", "skipped"}:
            task.status = "completed"
            task.completed_at = datetime.now(timezone.utc)
            task.completed_by = current_user.id
    db.commit()
    db.refresh(onboarding)
    return onboarding


@router.post("/policy-acknowledgements", response_model=PolicyAcknowledgementSchema, status_code=status.HTTP_201_CREATED)
def acknowledge_policy(
    data: PolicyAcknowledgementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_hr_admin(current_user):
        if not current_user.employee or current_user.employee.id != data.employee_id:
            raise HTTPException(status_code=403, detail="Not allowed to acknowledge policy for this employee")
    acknowledgement = PolicyAcknowledgement(**data.model_dump(), acknowledged_at=datetime.now(timezone.utc))
    db.add(acknowledgement)
    db.commit()
    db.refresh(acknowledgement)
    return acknowledgement


@router.get("/{employee_id}", response_model=EmployeeOnboardingResponse)
def get_onboarding_for_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = _employee_or_404(db, employee_id)
    if not _can_view_employee_onboarding(current_user, employee):
        raise HTTPException(status_code=403, detail="Not allowed to view this onboarding record")
    onboarding = get_employee_onboarding(db, employee_id)
    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding record not found")
    return onboarding
