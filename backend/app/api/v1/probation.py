from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.services.notifications import create_notification
from app.core.config import settings
from app.core.deps import RequirePermission, get_current_user, get_db
from app.models.employee import Employee, ProbationAction, ProbationReview
from app.models.user import User
from app.schemas.notification import NotificationCreate

router = APIRouter(prefix="/hrms/probation", tags=["HRMS Probation"])


class ProbationReviewPayload(BaseModel):
    reviewDate: date | None = None
    performanceRating: int = Field(..., ge=1, le=5)
    conductRating: int = Field(..., ge=1, le=5)
    attendanceRating: int = Field(..., ge=1, le=5)
    recommendation: str
    comments: str | None = None


class ProbationActionPayload(BaseModel):
    effectiveDate: date | None = None
    extendedUntil: date | None = None
    remarks: str | None = None


def _org_id(user: User) -> int | None:
    return getattr(user, "organization_id", None) or getattr(user, "company_id", None)


def _has_permission(user: User, permission: str) -> bool:
    if user.is_superuser:
        return True
    return permission in {p.name for p in (user.role.permissions if user.role else [])}


def _can_hr(user: User) -> bool:
    role = (user.role.name if user.role else "").lower()
    return user.is_superuser or _has_permission(user, "employee_update") or role in {"hr", "hr_admin", "hr_manager", "super_admin", "admin"}


def _add_months(value: date, months: int) -> date:
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    day = min(value.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def _probation_start(employee: Employee) -> date:
    return employee.probation_start_date or employee.date_of_joining


def _probation_end(employee: Employee) -> date:
    return employee.probation_end_date or _add_months(_probation_start(employee), employee.probation_period_months or 6)


def _employee_name(employee: Employee) -> str:
    return " ".join(part for part in [employee.first_name, employee.last_name] if part).strip() or employee.employee_id


def _load_employee(db: Session, employee_id: int) -> Employee:
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.deleted_at.is_(None)).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


def _ensure_manager_or_hr(employee: Employee, current_user: User) -> None:
    if _can_hr(current_user):
        return
    if current_user.employee and employee.reporting_manager_id == current_user.employee.id:
        return
    raise HTTPException(status_code=403, detail="Manager can review direct reports only")


def _serialize_employee(db: Session, employee: Employee) -> dict[str, Any]:
    latest_review = (
        db.query(ProbationReview)
        .filter(ProbationReview.employee_id == employee.id)
        .order_by(ProbationReview.created_at.desc(), ProbationReview.id.desc())
        .first()
    )
    latest_action = (
        db.query(ProbationAction)
        .filter(ProbationAction.employee_id == employee.id)
        .order_by(ProbationAction.created_at.desc(), ProbationAction.id.desc())
        .first()
    )
    end_date = _probation_end(employee)
    return {
        "employeeId": employee.id,
        "employeeCode": employee.employee_id,
        "employeeName": _employee_name(employee),
        "managerId": employee.reporting_manager_id,
        "managerName": _employee_name(employee.reporting_manager) if employee.reporting_manager else None,
        "probationStartDate": _probation_start(employee),
        "probationEndDate": end_date,
        "probationStatus": employee.probation_status or ("confirmed" if employee.date_of_confirmation else "on_probation"),
        "confirmationDate": employee.date_of_confirmation,
        "daysRemaining": (end_date - date.today()).days,
        "latestReview": _serialize_review(latest_review) if latest_review else None,
        "latestAction": _serialize_action(latest_action) if latest_action else None,
    }


def _serialize_review(review: ProbationReview) -> dict[str, Any]:
    return {
        "id": review.id,
        "employeeId": review.employee_id,
        "managerId": review.manager_id,
        "reviewDate": review.review_date,
        "performanceRating": review.performance_rating,
        "conductRating": review.conduct_rating,
        "attendanceRating": review.attendance_rating,
        "recommendation": review.recommendation,
        "comments": review.comments,
        "status": review.status,
        "createdAt": review.created_at,
    }


def _serialize_action(action: ProbationAction) -> dict[str, Any]:
    return {
        "id": action.id,
        "employeeId": action.employee_id,
        "actionType": action.action_type,
        "effectiveDate": action.effective_date,
        "extendedUntil": action.extended_until,
        "remarks": action.remarks,
        "letterGenerated": action.letter_generated,
        "createdBy": action.created_by,
        "createdAt": action.created_at,
    }


def _create_alert(db: Session, employee: Employee, title: str, message: str, event_type: str) -> int:
    recipients: list[int] = []
    if employee.reporting_manager and employee.reporting_manager.user_id:
        recipients.append(employee.reporting_manager.user_id)
    hr_users = db.query(User).all()
    for user in hr_users:
        role = (user.role.name if user.role else "").lower()
        if role in {"hr", "hr_admin", "hr_manager", "super_admin", "admin"}:
            recipients.append(user.id)
    created = 0
    for user_id in set(recipients):
        create_notification(
            db,
            NotificationCreate(
                user_id=user_id,
                title=title,
                message=message,
                module="hrms",
                event_type=event_type,
                related_entity_type="employee",
                related_entity_id=employee.id,
                action_url="/hrms/probation",
                priority="high",
                channels=["in_app", "email"],
            ),
        )
        created += 1
    return created


def _query_visible_probation_employees(db: Session, current_user: User):
    query = db.query(Employee).filter(Employee.deleted_at.is_(None))
    if not _can_hr(current_user):
        if not current_user.employee:
            raise HTTPException(status_code=403, detail="No employee profile")
        query = query.filter(Employee.reporting_manager_id == current_user.employee.id)
    return query.filter(
        or_(
            Employee.probation_status.in_(["on_probation", "extended"]),
            Employee.probation_status.is_(None),
            Employee.status.in_(["Probation", "Active"]),
        )
    )


@router.get("/dashboard")
def probation_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    employees = _query_visible_probation_employees(db, current_user).all()
    due = [item for item in employees if _probation_end(item) <= date.today() + timedelta(days=15)]
    overdue = [item for item in employees if _probation_end(item) < date.today() and (item.probation_status or "on_probation") in {"on_probation", "extended"}]
    pending_reviews = db.query(func.count(ProbationReview.id)).filter(ProbationReview.status.in_(["pending", "submitted"])).scalar() or 0
    return {
        "onProbation": len([item for item in employees if (item.probation_status or "on_probation") == "on_probation"]),
        "extended": len([item for item in employees if item.probation_status == "extended"]),
        "dueSoon": len(due),
        "overdue": len(overdue),
        "pendingReviews": pending_reviews,
        "dueEmployees": [_serialize_employee(db, item) for item in sorted(due, key=_probation_end)[:10]],
    }


@router.get("/due-list")
def probation_due_list(
    days: int = Query(default=30, ge=0, le=180),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cutoff = date.today() + timedelta(days=days)
    employees = [item for item in _query_visible_probation_employees(db, current_user).all() if _probation_end(item) <= cutoff]
    return [_serialize_employee(db, item) for item in sorted(employees, key=_probation_end)]


@router.post("/alerts/run", dependencies=[Depends(RequirePermission("employee_view", "employee_update"))])
def run_probation_alerts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    created = 0
    today = date.today()
    employees = _query_visible_probation_employees(db, current_user).all()
    for employee in employees:
        days_left = (_probation_end(employee) - today).days
        if days_left in {15, 7, 3}:
            created += _create_alert(
                db,
                employee,
                "Probation confirmation due",
                f"{_employee_name(employee)}'s probation ends in {days_left} day(s).",
                f"probation_due_{days_left}",
            )
    return {"notificationsCreated": created}


@router.post("/{employee_id}/review")
def submit_probation_review(
    employee_id: int,
    payload: ProbationReviewPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = _load_employee(db, employee_id)
    _ensure_manager_or_hr(employee, current_user)
    if payload.recommendation not in {"confirm", "extend", "terminate"}:
        raise HTTPException(status_code=400, detail="Recommendation must be confirm, extend, or terminate")
    review = ProbationReview(
        organization_id=_org_id(current_user),
        employee_id=employee.id,
        manager_id=current_user.employee.id if current_user.employee else employee.reporting_manager_id,
        review_date=payload.reviewDate or date.today(),
        performance_rating=payload.performanceRating,
        conduct_rating=payload.conductRating,
        attendance_rating=payload.attendanceRating,
        recommendation=payload.recommendation,
        comments=payload.comments,
        status="submitted",
    )
    db.add(review)
    db.commit()
    return _serialize_review(review)


def _perform_action(
    db: Session,
    current_user: User,
    employee_id: int,
    action_type: str,
    payload: ProbationActionPayload,
) -> dict[str, Any]:
    if not _can_hr(current_user):
        raise HTTPException(status_code=403, detail="Only HR can process final probation action")
    employee = _load_employee(db, employee_id)
    effective = payload.effectiveDate or date.today()
    if action_type == "extend" and not payload.extendedUntil:
        raise HTTPException(status_code=400, detail="extendedUntil is required for extension")
    action = ProbationAction(
        organization_id=_org_id(current_user),
        employee_id=employee.id,
        action_type=action_type,
        effective_date=effective,
        extended_until=payload.extendedUntil,
        remarks=payload.remarks,
        letter_generated=False,
        created_by=current_user.id,
    )
    if action_type == "confirm":
        employee.probation_status = "confirmed"
        employee.date_of_confirmation = effective
        employee.status = "Active"
    elif action_type == "extend":
        employee.probation_status = "extended"
        employee.probation_end_date = payload.extendedUntil
        employee.status = "Probation"
    elif action_type == "terminate":
        employee.probation_status = "terminated"
        employee.date_of_exit = effective
        employee.status = "Terminated"
    db.add(action)
    db.query(ProbationReview).filter(ProbationReview.employee_id == employee.id, ProbationReview.status == "submitted").update({"status": "completed"})
    db.commit()
    return _serialize_action(action)


@router.post("/{employee_id}/confirm")
def confirm_probation(employee_id: int, payload: ProbationActionPayload, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _perform_action(db, current_user, employee_id, "confirm", payload)


@router.post("/{employee_id}/extend")
def extend_probation(employee_id: int, payload: ProbationActionPayload, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _perform_action(db, current_user, employee_id, "extend", payload)


@router.post("/{employee_id}/terminate")
def terminate_probation(employee_id: int, payload: ProbationActionPayload, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _perform_action(db, current_user, employee_id, "terminate", payload)


@router.get("/{employee_id}/letter")
def probation_letter(employee_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = _load_employee(db, employee_id)
    _ensure_manager_or_hr(employee, current_user)
    action = db.query(ProbationAction).filter(ProbationAction.employee_id == employee.id).order_by(ProbationAction.created_at.desc(), ProbationAction.id.desc()).first()
    if not action:
        raise HTTPException(status_code=404, detail="No probation action found")
    out_dir = os.path.join(settings.UPLOAD_DIR, "probation_letters")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"probation_{employee.id}_{action.action_type}.pdf")
    title = {
        "confirm": "Confirmation Letter",
        "extend": "Probation Extension Letter",
        "terminate": "Probation Termination Letter",
    }.get(action.action_type, "Probation Letter")
    lines = [
        title,
        "",
        f"Employee: {_employee_name(employee)} ({employee.employee_id})",
        f"Effective date: {action.effective_date}",
        f"Action: {action.action_type.title()}",
        f"Extended until: {action.extended_until or '-'}",
        "",
        action.remarks or "",
        "",
        "Authorized HR Signatory",
    ]
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(path, pagesize=A4)
        y = A4[1] - 56
        c.setFont("Helvetica-Bold", 16)
        c.drawString(48, y, title)
        c.setFont("Helvetica", 11)
        y -= 36
        for line in lines[2:]:
            c.drawString(48, y, str(line))
            y -= 20
        c.save()
    except Exception:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
    action.letter_generated = True
    db.commit()
    return FileResponse(path, media_type="application/pdf", filename=os.path.basename(path))
