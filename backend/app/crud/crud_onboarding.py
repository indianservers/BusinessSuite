from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from app.models.employee import Employee
from app.models.onboarding import (
    EmployeeOnboarding,
    EmployeeOnboardingTask,
    OnboardingTemplate,
    OnboardingTemplateTask,
)


def normalize_employment_type(value: str | None) -> str:
    normalized = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"fulltime", "full_time", "full"}:
        return "full_time"
    if normalized in {"parttime", "part_time", "part"}:
        return "part_time"
    if normalized in {"intern", "internship"}:
        return "intern"
    if normalized in {"contract", "contractor"}:
        return "contract"
    return normalized or "all"


def find_default_template(db: Session, employee: Employee) -> OnboardingTemplate | None:
    applicable_for = normalize_employment_type(employee.employment_type)
    return (
        db.query(OnboardingTemplate)
        .filter(
            OnboardingTemplate.is_active.is_(True),
            OnboardingTemplate.applicable_for.in_(["all", applicable_for]),
        )
        .order_by(
            (OnboardingTemplate.applicable_for == applicable_for).desc(),
            OnboardingTemplate.created_at.asc(),
            OnboardingTemplate.id.asc(),
        )
        .first()
    )


def assign_task_user_id(db: Session, employee: Employee, assigned_to_role: str | None) -> int | None:
    role = (assigned_to_role or "employee").strip().lower()
    if role == "employee":
        return employee.user_id
    if role == "manager" and employee.reporting_manager_id:
        manager = db.get(Employee, employee.reporting_manager_id)
        return manager.user_id if manager else None
    return None


def refresh_onboarding_progress(onboarding: EmployeeOnboarding) -> None:
    total = len(onboarding.tasks or [])
    completed = len([task for task in onboarding.tasks if task.status in {"completed", "skipped"}])
    onboarding.completion_percentage = int(round((completed / total) * 100)) if total else 0
    if total and completed == total:
        onboarding.status = "completed"
    elif onboarding.tasks and any(task.due_date and task.due_date < date.today() and task.status not in {"completed", "skipped"} for task in onboarding.tasks):
        onboarding.status = "overdue"
    elif onboarding.tasks and any(task.status != "pending" for task in onboarding.tasks):
        onboarding.status = "in_progress"
    else:
        onboarding.status = "not_started"


def create_employee_onboarding(
    db: Session,
    *,
    employee: Employee,
    template: OnboardingTemplate,
    start_date: date | None = None,
    created_by: int | None = None,
    commit: bool = True,
) -> EmployeeOnboarding:
    start = start_date or employee.date_of_joining or date.today()
    existing = (
        db.query(EmployeeOnboarding)
        .filter(
            EmployeeOnboarding.employee_id == employee.id,
            EmployeeOnboarding.template_id == template.id,
        )
        .first()
    )
    if existing:
        return existing

    template_tasks = sorted(template.tasks or [], key=lambda item: (item.order_index or 0, item.id or 0))
    def due_delta(offset: int | None) -> int:
        return max((offset or 1) - 1, 0)

    max_offset = max((due_delta(task.due_day_offset) for task in template_tasks), default=0)
    onboarding = EmployeeOnboarding(
        employee_id=employee.id,
        template_id=template.id,
        start_date=start,
        target_completion_date=start + timedelta(days=max_offset),
        status="not_started",
        completion_percentage=0,
        created_by=created_by,
    )
    db.add(onboarding)
    db.flush()

    for template_task in template_tasks:
        db.add(
            EmployeeOnboardingTask(
                employee_onboarding_id=onboarding.id,
                template_task_id=template_task.id,
                task_name=template_task.task_name,
                category=template_task.category,
                due_date=start + timedelta(days=due_delta(template_task.due_day_offset)),
                assigned_to_user_id=assign_task_user_id(db, employee, template_task.assigned_to_role),
                status="pending",
            )
        )

    db.flush()
    db.refresh(onboarding)
    refresh_onboarding_progress(onboarding)
    if commit:
        db.commit()
        db.refresh(onboarding)
    return onboarding


def auto_start_onboarding_for_employee(db: Session, employee: Employee, created_by: int | None = None) -> EmployeeOnboarding | None:
    template = find_default_template(db, employee)
    if not template:
        return None
    return create_employee_onboarding(
        db,
        employee=employee,
        template=template,
        start_date=employee.date_of_joining,
        created_by=created_by,
        commit=False,
    )


def get_employee_onboarding(db: Session, employee_id: int) -> EmployeeOnboarding | None:
    return (
        db.query(EmployeeOnboarding)
        .options(joinedload(EmployeeOnboarding.tasks), joinedload(EmployeeOnboarding.template))
        .filter(EmployeeOnboarding.employee_id == employee_id)
        .order_by(EmployeeOnboarding.created_at.desc(), EmployeeOnboarding.id.desc())
        .first()
    )


def mark_task(
    db: Session,
    *,
    task: EmployeeOnboardingTask,
    status: str,
    user_id: int,
    notes: str | None = None,
) -> EmployeeOnboardingTask:
    task.status = status
    task.notes = notes
    if status == "completed":
        task.completed_at = datetime.now(timezone.utc)
        task.completed_by = user_id
    onboarding = task.employee_onboarding
    refresh_onboarding_progress(onboarding)
    db.commit()
    db.refresh(task)
    return task
