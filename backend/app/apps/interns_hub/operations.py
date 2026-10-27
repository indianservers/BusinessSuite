"""Paged workforce directory, exceptions and resumable manager operations."""
import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import func, or_, case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.access.catalog import permission_objects
from app.core.deps import get_db, get_current_user
from app.models.employee import Employee
from app.models.user import User
from app.models.notification import Notification
from app.models.audit import AuditLog
from app.apps.srm.services.commercial import tenant
from app.apps.project_management.models import PMSTask, PMSTaskAssignee, PMSProject
from app.apps.project_management.access import accessible_project_query
from .management_access import require_admin, employee_query, get_employee
from .management_models import InternBatchMembership
from .operations_models import WorkforceJob, WorkforceMessage

router = APIRouter(prefix="/operations", tags=["People and work operations"])


@router.get("/managers")
def managers(user=Depends(require_admin), db: Session = Depends(get_db)):
    from .applications import reporting_managers
    choices = reporting_managers(user, db)
    permitted = {e[0] for e in employee_query(db, user, include_employees=True).with_entities(Employee.id)}
    return [choice for choice in choices if choice["id"] < 0 or choice["id"] in permitted]


def require_operator(user=Depends(require_admin)):
    permissions = {p.name for p in permission_objects(user)}
    if not user.is_superuser and not permissions.intersection({"employee_update", "intern_management_manage", "pms_manage_tasks", "pms_manage_projects", "pms_admin"}):
        raise HTTPException(403, "Workforce management permission required")
    return user


def directory(db, user, search="", kind="all", department_id=None, batch_id=None, manager_id=None, status="", account_status=""):
    q = employee_query(db, user, include_employees=True)
    if kind == "intern":
        q = q.filter(func.lower(Employee.employment_type) == "intern")
    elif kind == "employee":
        q = q.filter(func.lower(Employee.employment_type) != "intern")
    if search.strip():
        term = "%" + search.strip() + "%"
        q = q.filter(or_((Employee.first_name + " " + Employee.last_name).ilike(term), Employee.employee_id.ilike(term), Employee.work_email.ilike(term), Employee.personal_email.ilike(term)))
    if department_id:
        q = q.filter(Employee.department_id == department_id)
    if batch_id:
        q = q.filter(Employee.id.in_(db.query(InternBatchMembership.employee_id).filter_by(batch_id=batch_id, status="Active")))
    if manager_id:
        q = q.filter(Employee.reporting_manager_id == manager_id)
    if status:
        q = q.filter(Employee.status == status)
    if account_status == "active":
        q = q.filter(Employee.user_id.in_(db.query(User.id).filter(User.is_active.is_(True))))
    elif account_status == "missing":
        q = q.filter(or_(Employee.user_id.is_(None), Employee.user_id.in_(db.query(User.id).filter(User.is_active.is_(False)))))
    return q


def assignments(db, user, people):
    projects = accessible_project_query(db, user).with_entities(PMSProject.id)
    return db.query(PMSTaskAssignee).join(PMSTask, PMSTask.id == PMSTaskAssignee.task_id).filter(
        PMSTask.deleted_at.is_(None), PMSTask.project_id.in_(projects), PMSTaskAssignee.cancelled_at.is_(None),
        PMSTaskAssignee.user_id.in_(people.with_entities(Employee.user_id)))


def day():
    from .router import today
    return today()


def encoded(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


@router.get("/people")
def people(search: str = Query("", max_length=150), kind: Literal["all", "intern", "employee"] = "all",
           department_id: int | None = None, batch_id: int | None = None, manager_id: int | None = None,
           status: str = "", account_status: Literal["", "active", "missing"] = "", exception: Literal["", "overdue", "review", "unassigned", "warnings"] = "",
           page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=100),
           user=Depends(require_admin), db: Session = Depends(get_db)):
    q = directory(db, user, search, kind, department_id, batch_id, manager_id, status, account_status)
    work = assignments(db, user, q)
    due = func.coalesce(PMSTaskAssignee.due_date, PMSTask.due_date)
    outstanding = PMSTaskAssignee.execution_status != "Done"
    if exception == "overdue":
        q = q.filter(Employee.user_id.in_(work.filter(due < day(), outstanding).with_entities(PMSTaskAssignee.user_id)))
    elif exception == "review":
        q = q.filter(Employee.user_id.in_(work.filter(PMSTaskAssignee.execution_status == "In Review").with_entities(PMSTaskAssignee.user_id)))
    elif exception == "unassigned":
        q = q.filter(Employee.reporting_manager_id.is_(None))
    elif exception == "warnings":
        q = q.filter(Employee.id.in_(db.query(WorkforceMessage.employee_id).filter_by(organization_id=tenant(user), kind="warning", resolved_at=None)))
    total = q.count()
    rows = q.options(joinedload(Employee.department), joinedload(Employee.reporting_manager), joinedload(Employee.user)).order_by(Employee.id).offset((page - 1) * per_page).limit(per_page).all()
    ids = [e.id for e in rows]
    uids = [e.user_id for e in rows if e.user_id]
    stats = {r.user_id: r for r in work.filter(PMSTaskAssignee.user_id.in_(uids)).with_entities(
        PMSTaskAssignee.user_id, func.count().label("assigned"),
        func.sum(case((PMSTaskAssignee.execution_status == "Done", 1), else_=0)).label("done"),
        func.sum(case(((due < day()) & outstanding, 1), else_=0)).label("overdue"),
        func.sum(case((PMSTaskAssignee.execution_status == "In Review", 1), else_=0)).label("review")
    ).group_by(PMSTaskAssignee.user_id)} if uids else {}
    warnings = dict(db.query(WorkforceMessage.employee_id, func.count()).filter(WorkforceMessage.organization_id == tenant(user), WorkforceMessage.employee_id.in_(ids), WorkforceMessage.kind == "warning", WorkforceMessage.resolved_at.is_(None)).group_by(WorkforceMessage.employee_id)) if ids else {}
    return {"items": [{"id": e.id, "user_id": e.user_id, "name": f"{e.first_name} {e.last_name}".strip(),
        "employee_id": e.employee_id, "email": e.work_email or e.personal_email,
        "employment_type": e.employment_type, "department": e.department.name if e.department else None,
        "department_id": e.department_id, "status": e.status, "joining_date": e.date_of_joining,
        "manager_id": e.reporting_manager_id,
        "manager": f"{e.reporting_manager.first_name} {e.reporting_manager.last_name}".strip() if e.reporting_manager else None,
        "account_active": bool(e.user and e.user.is_active),
        **{k: int(getattr(stats[e.user_id], k) or 0) if e.user_id in stats else 0 for k in ["assigned", "done", "overdue", "review"]},
        "warnings": warnings.get(e.id, 0)} for e in rows], "total": total, "page": page, "per_page": per_page}


@router.get("/summary")
def summary(kind: Literal["all", "intern", "employee"] = "all", user=Depends(require_admin), db: Session = Depends(get_db)):
    q = directory(db, user, kind=kind)
    work = assignments(db, user, q)
    return {"people": q.count(), "active": q.filter(Employee.status.in_(["Active", "Probation"])).count(),
        "unassigned": q.filter(Employee.reporting_manager_id.is_(None)).count(),
        "overdue": work.filter(func.coalesce(PMSTaskAssignee.due_date, PMSTask.due_date) < day(), PMSTaskAssignee.execution_status != "Done").count(),
        "review": work.filter(PMSTaskAssignee.execution_status == "In Review").count(),
        "warnings": db.query(WorkforceMessage).filter(WorkforceMessage.organization_id == tenant(user), WorkforceMessage.employee_id.in_(q.with_entities(Employee.id)), WorkforceMessage.kind == "warning", WorkforceMessage.resolved_at.is_(None)).count()}


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_ids: list[int] = Field(default_factory=list, max_length=20000)
    all_filtered: bool = False
    search: str = Field("", max_length=150)
    kind: Literal["all", "intern", "employee"] = "all"
    department_id: int | None = None
    batch_id: int | None = None
    manager_id: int | None = None
    status: str = Field("", max_length=30)
    account_status: Literal["", "active", "missing"] = ""


class OperationInput(Selection):
    operation: Literal["notice", "warning", "reassign"]
    title: str = Field("", max_length=200)
    message: str = Field("", max_length=3000)
    severity: Literal["normal", "important", "urgent"] = "normal"
    reporting_manager_id: int | None = None
    request_key: str = Field(min_length=8, max_length=100)
    expected_total: int | None = Field(default=None, ge=1, le=20000)


def selected(db, user, data):
    q = directory(db, user, **data.model_dump(include={"search", "kind", "department_id", "batch_id", "manager_id", "status", "account_status"}))
    if not data.all_filtered:
        q = q.filter(Employee.id.in_(data.employee_ids))
        if q.count() != len(set(data.employee_ids)):
            raise HTTPException(403, "Some selected people are outside your scope or filters")
    return q


@router.post("/preview")
def preview(data: Selection, user=Depends(require_operator), db: Session = Depends(get_db)):
    q = selected(db, user, data)
    return {"total": q.count(), "without_account": q.filter(Employee.user_id.is_(None)).count(),
        "sample": [{"id": e.id, "name": f"{e.first_name} {e.last_name}".strip()} for e in q.order_by(Employee.id).limit(10)]}


def manager_for(db, user, value):
    if not value:
        raise HTTPException(422, "Select a reporting manager")
    if value > 0:
        manager = get_employee(db, user, value)
    else:
        account = db.query(User).filter_by(id=-value, is_active=True, is_superuser=True).with_for_update().first()
        if not account or tenant(account) != tenant(user):
            raise HTTPException(422, "Select an active superadmin in this organization")
        manager = db.query(Employee).filter_by(user_id=account.id).first()
        if manager is None:
            # A linked profile is needed by HRMS's employee reporting relationship.
            from app.models.company import Branch
            branch = db.query(Branch).filter_by(company_id=tenant(user)).order_by(Branch.id).first()
            if not branch:
                raise HTTPException(422, "Create an organization branch first")
            manager = Employee(employee_id="SUP-" + uuid4().hex[:16].upper(), user_id=account.id,
                first_name=account.email.split("@")[0], last_name="", work_email=account.email,
                branch_id=branch.id, date_of_joining=day(), employment_type="Full-time", status="Active")
            db.add(manager); db.flush()
    if manager.deleted_at or manager.status not in {"Active", "Probation"} or (manager.employment_type or "").lower() == "intern":
        raise HTTPException(422, "Select an active non-intern supervisor")
    return manager


def job_result(job):
    return {k: getattr(job, k) for k in ["id", "operation", "status", "cursor", "attempts", "error", "created_at", "result"]} | {"total": len(job.recipients)}


@router.post("/jobs", status_code=201)
def create_job(data: OperationInput, user=Depends(require_operator), db: Session = Depends(get_db)):
    payload = data.model_dump(mode="json")
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    existing = db.query(WorkforceJob).filter_by(organization_id=tenant(user), request_key=data.request_key).first()
    if existing:
        if existing.created_by != user.id or existing.payload_hash != digest:
            raise HTTPException(409, "Request key belongs to a different operation")
        return job_result(existing)
    ids = [e[0] for e in selected(db, user, data).with_entities(Employee.id).order_by(Employee.id).limit(20001)]
    if not ids or len(ids) > 20000:
        raise HTTPException(422, "Select between 1 and 20,000 people")
    if data.expected_total is not None and len(ids) != data.expected_total:
        raise HTTPException(409, "The selection changed. Close this preview and review the recipients again")
    if data.operation in {"warning", "notice"}:
        if not data.title.strip() or not data.message.strip():
            raise HTTPException(422, "A title and message are required")
        unavailable = employee_query(db, user, include_employees=True).outerjoin(User, Employee.user_id == User.id).filter(Employee.id.in_(ids), or_(User.id.is_(None), User.is_active.is_(False))).count()
        if unavailable:
            raise HTTPException(422, f"{unavailable} selected people have no active account; adjust the selection")
    else:
        manager = manager_for(db, user, data.reporting_manager_id)
        if manager.id in ids:
            raise HTTPException(422, "A supervisor cannot report to themselves")
        # Reject a cycle before saving the job; repeat this check at execution time.
        validate_hierarchy(db, manager, set(ids))
        payload["resolved_manager_id"] = manager.id
    job = WorkforceJob(organization_id=tenant(user), created_by=user.id, request_key=data.request_key,
        payload_hash=digest, operation=data.operation, payload=payload, recipients=ids)
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Operation is being created; retry using the same request key")
    process_job(db, job.id)
    return job_result(db.get(WorkforceJob, job.id))


def validate_hierarchy(db, manager, recipient_ids):
    seen = set()
    current = manager
    while current:
        if current.id in recipient_ids or current.id in seen:
            raise HTTPException(422, "This reassignment would create a reporting cycle")
        seen.add(current.id)
        current = db.get(Employee, current.reporting_manager_id) if current.reporting_manager_id else None


def process_job(db, job_id, chunk_size=250):
    job = db.query(WorkforceJob).filter_by(id=job_id).with_for_update().first()
    if not job or job.status == "Completed":
        return job
    if job.operation == "onboard":
        from .onboarding import process_onboarding
        return process_onboarding(db, job)
    savepoint = db.begin_nested()
    try:
        user = db.get(User, job.created_by)
        require_operator(require_admin(user))
        if tenant(user) != job.organization_id:
            raise HTTPException(403, "Operator organization changed")
        ids = job.recipients[job.cursor:job.cursor + chunk_size]
        rows = employee_query(db, user, include_employees=True).options(joinedload(Employee.user)).filter(Employee.id.in_(ids)).all()
        if {e.id for e in rows} != set(ids):
            raise HTTPException(403, "Recipient access changed; review the operation")
        payload = job.payload
        if job.operation == "reassign":
            from app.models.company import Company
            db.query(Company).filter_by(id=job.organization_id).with_for_update().first()
            manager = manager_for(db, user, payload["resolved_manager_id"])
            validate_hierarchy(db, manager, set(job.recipients))
            for employee in rows:
                db.add(AuditLog(organization_id=job.organization_id, user_id=user.id, method="POST", module="hrms",
                    entity_type="employee", entity_id=employee.id, action="UPDATE", status_code=200,
                    description="Bulk supervisor reassignment", old_values=json.dumps({"reporting_manager_id": employee.reporting_manager_id}),
                    new_values=json.dumps({"reporting_manager_id": manager.id, "job_id": job.id})))
                employee.reporting_manager_id = manager.id
        else:
            if any(not e.user or not e.user.is_active for e in rows):
                raise HTTPException(409, "A recipient account is inactive; review the operation")
            for employee in rows:
                message = WorkforceMessage(organization_id=job.organization_id, job_id=job.id, employee_id=employee.id,
                    user_id=employee.user_id, created_by=user.id, kind=job.operation, title=payload["title"].strip(),
                    message=payload["message"].strip(), severity=payload["severity"])
                db.add(message)
                db.add(Notification(company_id=job.organization_id, user_id=employee.user_id, title=message.title,
                    message=message.message, module="hrms", event_type="workforce_" + job.operation,
                    priority=payload["severity"], related_entity_type="workforce_job", related_entity_id=job.id,
                    action_url="/notifications" if (employee.employment_type or "").lower() == "intern" else "/pms/my-notices",
                    channels=["in_app"], is_read=False))
        job.cursor += len(ids)
        job.attempts += 1
        job.status = "Completed" if job.cursor >= len(job.recipients) else "Pending"
        job.error = None
        savepoint.commit()
        db.commit()
    except Exception as exc:
        savepoint.rollback()
        job = db.get(WorkforceJob, job_id)
        if job is None:
            raise
        job.status = "Failed"
        job.attempts += 1
        job.error = str(getattr(exc, "detail", type(exc).__name__))[:500]
        db.commit()
    return job


def visible_jobs(db, user):
    q = db.query(WorkforceJob).filter_by(organization_id=tenant(user)).filter(WorkforceJob.operation != "onboard")
    from .management_access import organization_admin
    if not organization_admin(user):
        q = q.filter_by(created_by=user.id)
    return q


@router.get("/jobs")
def jobs(page: int = Query(1, ge=1), user=Depends(require_admin), db: Session = Depends(get_db)):
    q = visible_jobs(db, user)
    return {"items": [job_result(j) for j in q.order_by(WorkforceJob.id.desc()).offset((page-1)*25).limit(25)], "total": q.count()}


@router.post("/jobs/{job_id}/continue")
def continue_job(job_id: int, user=Depends(require_operator), db: Session = Depends(get_db)):
    job = visible_jobs(db, user).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(404, "Operation not found")
    return job_result(process_job(db, job.id))


@router.get("/people/{employee_id}/history")
def history(employee_id: int, page: int = Query(1, ge=1), user=Depends(require_admin), db: Session = Depends(get_db)):
    get_employee(db, user, employee_id)
    q = db.query(WorkforceMessage).filter_by(organization_id=tenant(user), employee_id=employee_id)
    return {"items": [encoded(m) for m in q.order_by(WorkforceMessage.id.desc()).offset((page-1)*25).limit(25)], "total": q.count()}


@router.get("/people/{employee_id}/work")
def person_work(employee_id: int, page: int = Query(1, ge=1), user=Depends(require_admin), db: Session = Depends(get_db)):
    get_employee(db, user, employee_id)
    q = assignments(db, user, employee_query(db, user, include_employees=True).filter(Employee.id == employee_id))
    total = q.count()
    rows = q.with_entities(PMSTaskAssignee, PMSTask).order_by(PMSTaskAssignee.due_date, PMSTask.id).offset((page-1)*20).limit(20).all()
    return {"items": [{"id": task.id, "title": task.title, "project_id": task.project_id,
        "status": assignment.execution_status, "progress": assignment.progress_percent,
        "due_date": assignment.due_date or task.due_date, "reviewer_user_id": assignment.reviewer_user_id,
        "overdue": bool((assignment.due_date or task.due_date) and (assignment.due_date or task.due_date) < day() and assignment.execution_status != "Done")}
        for assignment, task in rows], "total": total}


class Resolution(BaseModel):
    note: str = Field(min_length=3, max_length=2000)


@router.post("/messages/{message_id}/resolve")
def resolve(message_id: int, data: Resolution, user=Depends(require_operator), db: Session = Depends(get_db)):
    message = db.query(WorkforceMessage).filter_by(id=message_id, organization_id=tenant(user)).with_for_update().first()
    if not message:
        raise HTTPException(404, "Message not found")
    get_employee(db, user, message.employee_id)
    if not data.note.strip():
        raise HTTPException(422, "Enter a resolution note")
    if message.resolved_at is None:
        message.resolved_at = datetime.now(timezone.utc)
        message.resolved_by = user.id
        message.resolution = data.note.strip()
        db.commit()
    return encoded(message)


@router.get("/inbox")
def inbox(page: int = Query(1, ge=1), user=Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(WorkforceMessage).filter_by(organization_id=tenant(user), user_id=user.id)
    return {"items": [encoded(m) for m in q.order_by(WorkforceMessage.id.desc()).offset((page-1)*25).limit(25)],
        "total": q.count(), "unacknowledged": q.filter(WorkforceMessage.acknowledged_at.is_(None)).count()}


@router.get("/inbox-count")
def inbox_count(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return {"unacknowledged": db.query(WorkforceMessage).filter_by(organization_id=tenant(user), user_id=user.id,
        acknowledged_at=None).count()}


@router.post("/inbox/{message_id}/acknowledge")
def acknowledge(message_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    message = db.query(WorkforceMessage).filter_by(id=message_id, organization_id=tenant(user), user_id=user.id).with_for_update().first()
    if not message:
        raise HTTPException(404, "Message not found")
    if message.acknowledged_at is None:
        message.acknowledged_at = datetime.now(timezone.utc)
        db.query(Notification).filter_by(company_id=tenant(user), user_id=user.id,
            related_entity_type="workforce_job", related_entity_id=message.job_id).update({"is_read": True, "read_at": message.acknowledged_at}, synchronize_session=False)
        db.commit()
    return encoded(message)


def scheduled_tick(db):
    ids = [j[0] for j in db.query(WorkforceJob.id).filter_by(status="Pending").order_by(WorkforceJob.id).limit(10)]
    for job_id in ids:
        process_job(db, job_id)
    return {"chunks": len(ids)}
