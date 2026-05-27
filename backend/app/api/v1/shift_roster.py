from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.core.deps import RequirePermission, get_current_user, get_db
from app.crud.crud_attendance import crud_attendance
from app.models.attendance import Shift, ShiftRoster
from app.models.employee import Employee
from app.models.leave import LeaveRequest
from app.models.user import User


router = APIRouter(prefix="/hrms/shift-roster", tags=["HRMS Shift Roster"])


class RosterAssignRequest(BaseModel):
    employeeId: int
    shiftId: int
    rosterDate: date
    status: str = "draft"


class RosterBulkAssignRequest(BaseModel):
    shiftId: int
    fromDate: date
    toDate: date
    employeeIds: list[int] | None = None
    departmentId: int | None = None
    managerId: int | None = None
    status: str = "draft"


class RosterCopyWeekRequest(BaseModel):
    sourceWeekStart: date
    targetWeekStart: date
    employeeIds: list[int] | None = None
    departmentId: int | None = None
    status: str = "draft"


class RosterPublishRequest(BaseModel):
    fromDate: date
    toDate: date
    employeeIds: list[int] | None = None
    departmentId: int | None = None


class RosterSwapRequest(BaseModel):
    firstRosterId: int
    secondRosterId: int


def _has_permission(user: User, permission: str) -> bool:
    if user.is_superuser:
        return True
    return permission in {p.name for p in (user.role.permissions if user.role else [])}


def _user_company_id(user: User) -> int | None:
    if user.employee and user.employee.branch:
        return user.employee.branch.company_id
    return None


def _employee_company_id(employee: Employee) -> int | None:
    return employee.branch.company_id if employee.branch else None


def _employee_name(employee: Employee | None) -> str:
    if not employee:
        return "Unknown employee"
    return " ".join(part for part in [employee.first_name, employee.last_name] if part).strip() or employee.employee_id


def _normal_status(value: str) -> str:
    status = (value or "draft").strip().lower()
    if status not in {"draft", "published"}:
        raise HTTPException(status_code=400, detail="Roster status must be draft or published")
    return status


def _date_range(start: date, end: date) -> list[date]:
    if end < start:
        raise HTTPException(status_code=400, detail="toDate cannot be before fromDate")
    if (end - start).days > 62:
        raise HTTPException(status_code=400, detail="Roster range cannot exceed 63 days")
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _managed_employee_query(db: Session, user: User):
    query = db.query(Employee).options(joinedload(Employee.branch), joinedload(Employee.department)).filter(Employee.deleted_at.is_(None))
    if user.is_superuser:
        return query
    company_id = _user_company_id(user)
    if _has_permission(user, "attendance_manage"):
        if not company_id:
            raise HTTPException(status_code=403, detail="Company scope is required")
        return query.join(Employee.branch).filter_by(company_id=company_id)
    if user.employee:
        managed_ids = [user.employee.id]
        direct_reports = db.query(Employee.id).filter(Employee.reporting_manager_id == user.employee.id, Employee.deleted_at.is_(None)).all()
        managed_ids.extend(row.id for row in direct_reports)
        return query.filter(Employee.id.in_(managed_ids))
    raise HTTPException(status_code=403, detail="Employee profile is required")


def _load_employee(db: Session, employee_id: int, user: User) -> Employee:
    employee = _managed_employee_query(db, user).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found or not accessible")
    return employee


def _load_shift(db: Session, shift_id: int) -> Shift:
    shift = db.query(Shift).filter(Shift.id == shift_id, Shift.is_active == True).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    return shift


def _candidate_employees(
    db: Session,
    user: User,
    employee_ids: list[int] | None = None,
    department_id: int | None = None,
    manager_id: int | None = None,
) -> list[Employee]:
    query = _managed_employee_query(db, user)
    if employee_ids:
        query = query.filter(Employee.id.in_(employee_ids))
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    if manager_id:
        query = query.filter(Employee.reporting_manager_id == manager_id)
    employees = query.order_by(Employee.first_name, Employee.last_name).all()
    if not employees:
        raise HTTPException(status_code=404, detail="No accessible employees found for roster operation")
    return employees


def _weekly_hours(db: Session, employee_id: int, work_date: date, current_shift: Shift, ignore_roster_id: int | None = None) -> Decimal:
    week_start = work_date - timedelta(days=work_date.weekday())
    week_end = week_start + timedelta(days=6)
    rosters = db.query(ShiftRoster).options(joinedload(ShiftRoster.shift)).filter(
        ShiftRoster.employee_id == employee_id,
        ShiftRoster.roster_date >= week_start,
        ShiftRoster.roster_date <= week_end,
    )
    if ignore_roster_id:
        rosters = rosters.filter(ShiftRoster.id != ignore_roster_id)
    total = Decimal(str(current_shift.working_hours or 0))
    for roster in rosters.all():
        if roster.shift:
            total += Decimal(str(roster.shift.working_hours or 0))
    return total


def _conflicts(db: Session, employee: Employee, shift: Shift, roster_date: date, existing: ShiftRoster | None = None) -> list[str]:
    conflicts: list[str] = []
    approved_leave = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee.id,
        LeaveRequest.status == "Approved",
        LeaveRequest.deleted_at.is_(None),
        LeaveRequest.from_date <= roster_date,
        LeaveRequest.to_date >= roster_date,
    ).first()
    if approved_leave:
        conflicts.append("Employee is on approved leave")
    if crud_attendance.is_weekly_off(db, shift.id, roster_date):
        conflicts.append("Selected shift has weekly off on this date")
    if existing and existing.shift_id != shift.id:
        conflicts.append("Existing shift assignment will be replaced")
    if _weekly_hours(db, employee.id, roster_date, shift, existing.id if existing else None) > Decimal("48"):
        conflicts.append("Weekly roster exceeds 48 planned hours")
    return conflicts


def _upsert_roster(db: Session, employee: Employee, shift: Shift, roster_date: date, status: str, user: User) -> tuple[ShiftRoster, list[str]]:
    existing = db.query(ShiftRoster).filter(
        ShiftRoster.employee_id == employee.id,
        ShiftRoster.roster_date == roster_date,
    ).first()
    conflicts = _conflicts(db, employee, shift, roster_date, existing)
    organization_id = _employee_company_id(employee)
    if existing:
        existing.shift_id = shift.id
        existing.status = status
        existing.assigned_by = user.id
        existing.organization_id = organization_id
        roster = existing
    else:
        roster = ShiftRoster(
            organization_id=organization_id,
            employee_id=employee.id,
            shift_id=shift.id,
            roster_date=roster_date,
            status=status,
            assigned_by=user.id,
        )
        db.add(roster)
    return roster, conflicts


def _serialize(roster: ShiftRoster, conflicts: list[str] | None = None) -> dict[str, Any]:
    employee = roster.employee
    shift = roster.shift
    return {
        "id": roster.id,
        "organizationId": roster.organization_id,
        "employeeId": roster.employee_id,
        "employee": {
            "id": employee.id,
            "employeeId": employee.employee_id,
            "name": _employee_name(employee),
            "departmentId": employee.department_id,
            "departmentName": employee.department.name if employee.department else None,
        } if employee else None,
        "shiftId": roster.shift_id,
        "shift": {
            "id": shift.id,
            "name": shift.name,
            "code": shift.code,
            "startTime": shift.start_time.isoformat() if shift.start_time else None,
            "endTime": shift.end_time.isoformat() if shift.end_time else None,
            "workingHours": float(shift.working_hours or 0),
        } if shift else None,
        "rosterDate": roster.roster_date,
        "status": roster.status,
        "assignedBy": roster.assigned_by,
        "createdAt": roster.created_at,
        "updatedAt": roster.updated_at,
        "conflicts": conflicts or [],
    }


@router.get("")
def list_shift_roster(
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    departmentId: int | None = Query(None),
    employeeId: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _date_range(from_, to)
    employees = _candidate_employees(
        db,
        current_user,
        employee_ids=[employeeId] if employeeId else None,
        department_id=departmentId,
    )
    employee_ids = [employee.id for employee in employees]
    rosters = (
        db.query(ShiftRoster)
        .options(joinedload(ShiftRoster.shift), joinedload(ShiftRoster.employee).joinedload(Employee.department))
        .filter(
            ShiftRoster.employee_id.in_(employee_ids),
            ShiftRoster.roster_date >= from_,
            ShiftRoster.roster_date <= to,
        )
        .order_by(ShiftRoster.roster_date, ShiftRoster.employee_id)
        .all()
    )
    return {
        "employees": [
            {
                "id": employee.id,
                "employeeId": employee.employee_id,
                "name": _employee_name(employee),
                "departmentId": employee.department_id,
                "departmentName": employee.department.name if employee.department else None,
            }
            for employee in employees
        ],
        "rosters": [_serialize(roster) for roster in rosters],
    }


@router.get("/my")
def my_upcoming_roster(
    from_: date | None = Query(None, alias="from"),
    days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="Employee profile is required")
    start = from_ or date.today()
    end = start + timedelta(days=days - 1)
    rosters = (
        db.query(ShiftRoster)
        .options(joinedload(ShiftRoster.shift), joinedload(ShiftRoster.employee).joinedload(Employee.department))
        .filter(
            ShiftRoster.employee_id == current_user.employee.id,
            ShiftRoster.roster_date >= start,
            ShiftRoster.roster_date <= end,
            ShiftRoster.status == "published",
        )
        .order_by(ShiftRoster.roster_date)
        .all()
    )
    return [_serialize(row) for row in rosters]


@router.post("/assign")
def assign_shift_roster(
    payload: RosterAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    status = _normal_status(payload.status)
    employee = _load_employee(db, payload.employeeId, current_user)
    shift = _load_shift(db, payload.shiftId)
    roster, conflicts = _upsert_roster(db, employee, shift, payload.rosterDate, status, current_user)
    db.commit()
    db.refresh(roster)
    return _serialize(roster, conflicts)


@router.post("/bulk-assign")
def bulk_assign_shift_roster(
    payload: RosterBulkAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    status = _normal_status(payload.status)
    dates = _date_range(payload.fromDate, payload.toDate)
    shift = _load_shift(db, payload.shiftId)
    employees = _candidate_employees(db, current_user, payload.employeeIds, payload.departmentId, payload.managerId)
    results = []
    conflicts: list[dict[str, Any]] = []
    for employee in employees:
        for roster_date in dates:
            roster, row_conflicts = _upsert_roster(db, employee, shift, roster_date, status, current_user)
            db.flush()
            results.append(roster)
            if row_conflicts:
                conflicts.append({"employeeId": employee.id, "rosterDate": roster_date, "messages": row_conflicts})
    db.commit()
    return {"assigned": len(results), "conflicts": conflicts}


@router.post("/copy-week")
def copy_week_shift_roster(
    payload: RosterCopyWeekRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    status = _normal_status(payload.status)
    employees = _candidate_employees(db, current_user, payload.employeeIds, payload.departmentId)
    employee_ids = [employee.id for employee in employees]
    source_end = payload.sourceWeekStart + timedelta(days=6)
    source_rows = db.query(ShiftRoster).filter(
        ShiftRoster.employee_id.in_(employee_ids),
        ShiftRoster.roster_date >= payload.sourceWeekStart,
        ShiftRoster.roster_date <= source_end,
    ).all()
    employee_map = {employee.id: employee for employee in employees}
    copied = 0
    conflicts: list[dict[str, Any]] = []
    for source in source_rows:
        employee = employee_map.get(source.employee_id)
        shift = db.query(Shift).filter(Shift.id == source.shift_id, Shift.is_active == True).first()
        if not employee or not shift:
            continue
        target_date = payload.targetWeekStart + timedelta(days=(source.roster_date - payload.sourceWeekStart).days)
        roster, row_conflicts = _upsert_roster(db, employee, shift, target_date, status, current_user)
        db.flush()
        copied += 1
        if row_conflicts:
            conflicts.append({"employeeId": employee.id, "rosterDate": target_date, "messages": row_conflicts})
    db.commit()
    return {"copied": copied, "conflicts": conflicts}


@router.post("/publish")
def publish_shift_roster(
    payload: RosterPublishRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    _date_range(payload.fromDate, payload.toDate)
    employees = _candidate_employees(db, current_user, payload.employeeIds, payload.departmentId)
    employee_ids = [employee.id for employee in employees]
    rows = db.query(ShiftRoster).filter(
        ShiftRoster.employee_id.in_(employee_ids),
        ShiftRoster.roster_date >= payload.fromDate,
        ShiftRoster.roster_date <= payload.toDate,
    ).all()
    for row in rows:
        row.status = "published"
    db.commit()
    return {"published": len(rows)}


@router.post("/swap")
def swap_shift_roster(
    payload: RosterSwapRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    first = db.query(ShiftRoster).filter(ShiftRoster.id == payload.firstRosterId).first()
    second = db.query(ShiftRoster).filter(ShiftRoster.id == payload.secondRosterId).first()
    if not first or not second:
        raise HTTPException(status_code=404, detail="Roster entry not found")
    _load_employee(db, first.employee_id, current_user)
    _load_employee(db, second.employee_id, current_user)
    first.shift_id, second.shift_id = second.shift_id, first.shift_id
    first.assigned_by = current_user.id
    second.assigned_by = current_user.id
    db.commit()
    db.refresh(first)
    db.refresh(second)
    return {"swapped": True, "rosters": [_serialize(first), _serialize(second)]}


@router.delete("/{roster_id}")
def delete_shift_roster(
    roster_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    roster = db.query(ShiftRoster).options(joinedload(ShiftRoster.employee).joinedload(Employee.branch)).filter(ShiftRoster.id == roster_id).first()
    if not roster:
        raise HTTPException(status_code=404, detail="Roster entry not found")
    _load_employee(db, roster.employee_id, current_user)
    db.delete(roster)
    db.commit()
    return {"message": "Roster entry deleted"}
