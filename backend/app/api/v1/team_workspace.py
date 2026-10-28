"""Manager decisions are restricted to current direct reports, including on writes."""
from datetime import date, timedelta
import calendar
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.access.catalog import permission_objects
from app.core.deps import get_current_user, get_db
from app.core.employee_scope import employee_tenant_scope
from app.models.employee import Employee
from app.models.leave import LeaveRequest
from app.models.attendance import AttendanceRegularization
from app.models.expense import ExpenseClaim
from app.models.performance import OneOnOneRecord

router = APIRouter(prefix="/my-team", dependencies=[Depends(employee_tenant_scope)])


def members(db, user):
    if not user.employee:
        return []
    return db.query(Employee).filter(Employee.reporting_manager_id == user.employee.id, Employee.deleted_at.is_(None)).order_by(Employee.first_name, Employee.id).all()


def permitted(user, name):
    return user.is_superuser or name in {p.name for p in permission_objects(user)}


@router.get("/availability")
def availability(month: int = Query(default=date.today().month, ge=1, le=12), year: int = Query(default=date.today().year, ge=2000, le=2200), db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.models.attendance import Holiday, Attendance
    team = members(db, user)
    people = {row.id: row for row in team}
    start, end = date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    leaves = db.query(LeaveRequest).filter(LeaveRequest.employee_id.in_(list(people)), LeaveRequest.deleted_at.is_(None), LeaveRequest.status.in_(["Pending", "Approved"]), LeaveRequest.from_date <= end, LeaveRequest.to_date >= start).all()
    holidays = db.query(Holiday).filter(Holiday.is_active.is_(True), Holiday.holiday_date >= start, Holiday.holiday_date <= end).all()
    today = date.today()
    attendance = db.query(Attendance).filter(Attendance.employee_id.in_(list(people)), Attendance.attendance_date == today).all()
    days = []
    for i in range((end - start).days + 1):
        current = start + timedelta(days=i)
        days.append({"date": current, "leaves": [{"employee_name": f"{people[row.employee_id].first_name} {people[row.employee_id].last_name}", "status": row.status} for row in leaves if row.from_date <= current <= row.to_date], "holidays": [row.name for row in holidays if row.holiday_date == current]})
    moments = []
    for row in team:
        for kind, original in [("Birthday", row.date_of_birth), ("Work anniversary", row.date_of_joining)]:
            if not original:
                continue
            for moment_year in [today.year, today.year + 1]:
                candidate = date(moment_year, original.month, min(original.day, calendar.monthrange(moment_year, original.month)[1]))
                if today <= candidate <= today + timedelta(days=7):
                    moments.append({"employee_id": row.id, "name": f"{row.first_name} {row.last_name}", "kind": kind, "date": candidate})
    return {"offset": start.weekday(), "days": days, "moments": moments,
            "today": [{"employee_id": row.employee_id, "name": f"{people[row.employee_id].first_name} {people[row.employee_id].last_name}", "status": row.status} for row in attendance],
            "probation_due": [{"employee_id": row.id, "name": f"{row.first_name} {row.last_name}", "due_date": row.probation_end_date} for row in team if row.probation_end_date and row.probation_status in {"on_probation", "extended"} and row.probation_end_date <= today + timedelta(days=30)]}


@router.get("")
def workspace(db: Session = Depends(get_db), user=Depends(get_current_user)):
    team = members(db, user)
    people = {row.id: row for row in team}
    decisions = []
    for kind, model in [("leave", LeaveRequest), ("attendance", AttendanceRegularization), ("expense", ExpenseClaim)]:
        expected = "submitted" if kind == "expense" else "Pending"
        query = db.query(model).filter(model.employee_id.in_(list(people)), model.status == expected)
        if kind == "leave":
            query = query.filter(LeaveRequest.deleted_at.is_(None))
        for row in query.order_by(model.id).all():
            person = people[row.employee_id]
            title = f"{row.from_date} to {row.to_date}" if kind == "leave" else row.reason if kind == "attendance" else f"{row.claim_type}: {row.amount} {row.currency}"
            can_decide = kind == "expense" or permitted(user, "leave_approve" if kind == "leave" else "attendance_manage")
            decisions.append({"id": row.id, "kind": kind, "employee_id": row.employee_id,
                              "employee_name": f"{person.first_name} {person.last_name}", "title": title,
                              "created_at": row.created_at, "can_decide": can_decide})
    followups = db.query(OneOnOneRecord).filter(OneOnOneRecord.manager_id == user.employee.id,
        OneOnOneRecord.employee_id.in_(list(people))).order_by(OneOnOneRecord.meeting_date, OneOnOneRecord.id).all() if user.employee else []
    return {"team": [{"id": row.id, "name": f"{row.first_name} {row.last_name}", "employee_code": row.employee_id, "status": row.status} for row in team],
            "decisions": sorted(decisions, key=lambda item: str(item["created_at"] or "")),
            "followups": [{"id": row.id, "employee_id": row.employee_id, "employee_name": f"{people[row.employee_id].first_name} {people[row.employee_id].last_name}",
                           "title": (row.talking_points_json or {}).get("followup_title", "Team follow-up"),
                           "due_date": row.meeting_date, "status": row.status} for row in followups if isinstance(row.talking_points_json, dict) and "followup_title" in row.talking_points_json]}


class Decision(BaseModel):
    decision: Literal["approve", "reject"]
    remarks: str = Field(min_length=3, max_length=1000)


@router.put("/decisions/{kind}/{record_id}")
def decide(kind: Literal["leave", "attendance", "expense"], record_id: int, data: Decision,
           db: Session = Depends(get_db), user=Depends(get_current_user)):
    model = {"leave": LeaveRequest, "attendance": AttendanceRegularization, "expense": ExpenseClaim}[kind]
    row = db.query(model).filter(model.id == record_id, model.employee_id.in_([m.id for m in members(db, user)])).with_for_update().first()
    if not row or (kind == "leave" and row.deleted_at):
        raise HTTPException(404, "Team request not found")
    if row.status != ("submitted" if kind == "expense" else "Pending"):
        raise HTTPException(409, "This request has already been reviewed")
    status = "Approved" if data.decision == "approve" else "Rejected"
    if kind == "leave":
        if not permitted(user, "leave_approve"):
            raise HTTPException(403, "Leave approval permission required")
        from app.api.v1.leave import approve_leave
        from app.schemas.leave import LeaveApprovalRequest
        return approve_leave(record_id, LeaveApprovalRequest(status=status, review_remarks=data.remarks), db, user)
    if kind == "attendance":
        if not permitted(user, "attendance_manage"):
            raise HTTPException(403, "Attendance management permission required")
        from app.api.v1.attendance import approve_regularization
        from app.api.v1.attendance import _locked_month
        from app.schemas.attendance import RegularizationApproval
        if status == "Approved" and row.attendance and _locked_month(db, row.attendance.attendance_date):
            raise HTTPException(409, "Attendance period is locked; use a payroll adjustment instead")
        # The normal attendance endpoint remains responsible for applying approved punches.
        return approve_regularization(record_id, RegularizationApproval(status=status, review_remarks=data.remarks), db, user)
    from app.api.v1.expenses import manager_review_claim
    from app.schemas.expense import ExpenseClaimReview
    return manager_review_claim(record_id, ExpenseClaimReview(status="manager_approved" if data.decision == "approve" else "rejected", remarks=data.remarks), db, user)


class Followup(BaseModel):
    employee_id: int
    title: str = Field(min_length=3, max_length=200)
    due_date: date


@router.post("/followups", status_code=201)
def add_followup(data: Followup, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if data.employee_id not in {row.id for row in members(db, user)}:
        raise HTTPException(404, "Direct report not found")
    row = OneOnOneRecord(manager_id=user.employee.id, employee_id=data.employee_id, meeting_date=data.due_date,
                         talking_points_json={"followup_title": data.title}, status="Open", created_by=user.id)
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id}


@router.put("/followups/{record_id}/complete")
def complete_followup(record_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = db.query(OneOnOneRecord).filter(OneOnOneRecord.id == record_id,
        OneOnOneRecord.manager_id == (user.employee.id if user.employee else -1),
        OneOnOneRecord.employee_id.in_([m.id for m in members(db, user)])).first()
    if not row or not isinstance(row.talking_points_json, dict) or "followup_title" not in row.talking_points_json:
        raise HTTPException(404, "Follow-up not found")
    row.status = "Completed"; db.commit()
    return {"id": row.id, "status": row.status}
