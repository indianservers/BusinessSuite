from typing import List, Optional
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from app.core.deps import get_db, get_current_user, RequirePermission
from app.crud import crud_leave
from app.models.user import User
from app.models.employee import Employee
from app.models.attendance import Holiday
from app.models.leave import LeaveRequest
from app.schemas.notification import NotificationCreate
from app.services.notifications import create_notification
from app.schemas.leave import (
    LeaveTypeCreate, LeaveTypeUpdate, LeaveTypeSchema,
    LeaveBalanceLedgerSchema, LeaveBalanceSchema, LeaveRequestCreate, LeaveApprovalRequest, LeaveRequestSchema,
    LeaveCalendarDay, LeaveCalendarResponse,
)

router = APIRouter(prefix="/leave", tags=["Leave Management"])


def _employee_display_name(employee: Employee) -> str:
    name = " ".join(part for part in [employee.first_name, employee.last_name] if part)
    return name or employee.employee_id or "An employee"


def _notify_user(db: Session, user_id: int, title: str, message: str, event_type: str, related_entity_id: int) -> None:
    create_notification(
        db,
        NotificationCreate(
            user_id=user_id,
            title=title,
            message=message,
            module="leave",
            event_type=event_type,
            related_entity_type="leave_request",
            related_entity_id=related_entity_id,
            action_url="/leave",
            channels=["in_app"],
        ),
    )


def _role_name(user: User) -> str:
    if user.is_superuser:
        return "super_admin"
    return (user.role.name if user.role else "").lower()


def _user_permissions(user: User) -> set[str]:
    return {permission.name for permission in (user.role.permissions if user.role else [])}


def _is_hr_admin(user: User) -> bool:
    return user.is_superuser or "hr_admin" in _user_permissions(user) or _role_name(user) in {"super_admin", "hr_admin", "hr_manager", "hr"}


def _department_id(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="department_id must match the numeric department id used by this HRMS database")


def _current_company_id(user: User) -> Optional[int]:
    if user.employee and user.employee.branch:
        return user.employee.branch.company_id
    return None


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="month must be between 1 and 12")
    start = date(year, month, 1)
    end = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1) - timedelta(days=1)
    return start, end


def _employee_leave_payload(employee: Employee, leaves: list[LeaveRequest]) -> dict:
    return {
        "employee_id": employee.id,
        "employee_name": _employee_display_name(employee),
        "profile_photo_url": employee.profile_photo_url,
        "department_name": employee.department.name if employee.department else None,
        "leaves": [
            {
                "leave_type_name": item.leave_type.name if item.leave_type else None,
                "from_date": item.from_date,
                "to_date": item.to_date,
                "days_count": item.days_count,
                "status": item.status,
                "is_half_day": item.is_half_day,
            }
            for item in leaves
        ],
    }


def _group_leaves_by_employee(requests: list[LeaveRequest]) -> list[dict]:
    grouped: dict[int, list[LeaveRequest]] = {}
    employees: dict[int, Employee] = {}
    for request in requests:
        if not request.employee:
            continue
        grouped.setdefault(request.employee_id, []).append(request)
        employees[request.employee_id] = request.employee
    return [_employee_leave_payload(employees[employee_id], grouped[employee_id]) for employee_id in sorted(grouped, key=lambda item: _employee_display_name(employees[item]))]


def _approved_leave_query(db: Session, from_date: date, to_date: date):
    return (
        db.query(LeaveRequest)
        .options(
            joinedload(LeaveRequest.employee).joinedload(Employee.department),
            joinedload(LeaveRequest.leave_type),
        )
        .filter(
            LeaveRequest.deleted_at.is_(None),
            LeaveRequest.status == "Approved",
            LeaveRequest.from_date <= to_date,
            LeaveRequest.to_date >= from_date,
        )
    )


# ── Leave Types ───────────────────────────────────────────────────────────────

@router.get("/types", response_model=List[LeaveTypeSchema])
def list_leave_types(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud_leave.get_all_leave_types(db)


@router.post("/types", response_model=LeaveTypeSchema, status_code=201)
def create_leave_type(
    data: LeaveTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("leave_manage")),
):
    from app.models.leave import LeaveType
    lt = LeaveType(**data.model_dump())
    db.add(lt)
    db.commit()
    db.refresh(lt)
    return lt


@router.put("/types/{type_id}", response_model=LeaveTypeSchema)
def update_leave_type(
    type_id: int,
    data: LeaveTypeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("leave_manage")),
):
    from app.models.leave import LeaveType
    lt = db.query(LeaveType).filter(LeaveType.id == type_id).first()
    if not lt:
        raise HTTPException(status_code=404, detail="Leave type not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(lt, k, v)
    db.commit()
    db.refresh(lt)
    return lt


@router.delete("/types/{type_id}")
def delete_leave_type(
    type_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("leave_manage")),
):
    from app.models.leave import LeaveType
    lt = db.query(LeaveType).filter(LeaveType.id == type_id).first()
    if not lt:
        raise HTTPException(status_code=404, detail="Leave type not found")
    lt.is_active = False
    db.commit()
    return {"message": "Leave type deactivated"}


@router.get("/pending-count")
def pending_leave_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("leave_manage")),
):
    query = db.query(func.count(LeaveRequest.id)).filter(
        LeaveRequest.deleted_at.is_(None),
        LeaveRequest.status == "Pending",
    )
    company_id = _current_company_id(current_user)
    if company_id:
        query = query.filter(LeaveRequest.company_id == company_id)
    return {"pending": query.scalar() or 0}


# ── Leave Balance ─────────────────────────────────────────────────────────────

@router.get("/balance", response_model=List[LeaveBalanceSchema])
def my_leave_balance(
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile")
    import datetime
    yr = year or datetime.date.today().year
    balances = crud_leave.get_employee_leave_balances(db, current_user.employee.id, yr)
    result = []
    for b in balances:
        from decimal import Decimal
        available = b.allocated + b.carried_forward - b.used - b.pending
        result.append({
            "id": b.id,
            "employee_id": b.employee_id,
            "leave_type_id": b.leave_type_id,
            "leave_type": b.leave_type,
            "year": b.year,
            "allocated": b.allocated,
            "used": b.used,
            "pending": b.pending,
            "carried_forward": b.carried_forward,
            "available": available,
        })
    return result


@router.get("/balance/{employee_id}", response_model=List[LeaveBalanceSchema])
def employee_leave_balance(
    employee_id: int,
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("leave_manage")),
):
    import datetime
    yr = year or datetime.date.today().year
    return crud_leave.get_employee_leave_balances(db, employee_id, yr)


@router.get("/ledger", response_model=List[LeaveBalanceLedgerSchema])
def my_leave_ledger(
    leave_type_id: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile")
    return crud_leave.get_leave_ledger(
        db,
        employee_id=current_user.employee.id,
        leave_type_id=leave_type_id,
        year=year,
    )


@router.get("/ledger/{employee_id}", response_model=List[LeaveBalanceLedgerSchema])
def employee_leave_ledger(
    employee_id: int,
    leave_type_id: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("leave_manage")),
):
    return crud_leave.get_leave_ledger(
        db,
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        year=year,
    )


@router.post("/balance/allocate")
def allocate_leave(
    employee_id: int,
    leave_type_id: int,
    year: int,
    days: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("leave_manage")),
):
    from decimal import Decimal
    balance = crud_leave.allocate_leave_balance(db, employee_id, leave_type_id, year, Decimal(str(days)))
    return balance


@router.post("/accruals/run")
def run_leave_accruals(
    run_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("leave_manage")),
):
    return crud_leave.run_scheduled_leave_accruals(db, run_date=run_date, created_by=current_user.id)


@router.post("/carry-forward/run")
def run_leave_carry_forward(
    from_year: int = Query(..., ge=2000, le=2100),
    to_year: Optional[int] = Query(None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("leave_manage")),
):
    if to_year is not None and to_year <= from_year:
        raise HTTPException(status_code=400, detail="to_year must be after from_year")
    return crud_leave.run_leave_carry_forward(db, from_year=from_year, to_year=to_year, created_by=current_user.id)


# ── Leave Requests ────────────────────────────────────────────────────────────

@router.post("/apply", response_model=LeaveRequestSchema, status_code=201)
def apply_leave(
    data: LeaveRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile")
    try:
        result = crud_leave.create_leave_request(db, current_user.employee.id, data.model_dump())
        manager = None
        if current_user.employee.reporting_manager_id:
            manager = db.query(Employee).filter(Employee.id == current_user.employee.reporting_manager_id).first()
        if manager and manager.user_id:
            _notify_user(
                db,
                manager.user_id,
                "Leave Request Pending Approval",
                f"{_employee_display_name(current_user.employee)} has applied for leave from {result.from_date} to {result.to_date}.",
                "leave_submitted",
                result.id,
            )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/my-requests", response_model=List[LeaveRequestSchema])
def my_leave_requests(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile")
    items, _ = crud_leave.get_leave_requests(
        db, employee_id=current_user.employee.id, status=status,
        skip=(page-1)*per_page, limit=per_page
    )
    return items


@router.get("/requests", response_model=List[LeaveRequestSchema])
def all_leave_requests(
    employee_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("leave_approve")),
):
    items, _ = crud_leave.get_leave_requests(
        db, employee_id=employee_id, status=status,
        company_id=None if current_user.is_superuser else _current_company_id(current_user),
        skip=(page-1)*per_page, limit=per_page
    )
    return items


@router.get("/calendar", response_model=LeaveCalendarResponse)
def leave_calendar(
    from_date: date = Query(...),
    to_date: date = Query(...),
    scope: str = Query("team", pattern="^(mine|team|all)$"),
    department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date cannot be before from_date")
    if (to_date - from_date).days > 92:
        raise HTTPException(status_code=400, detail="Calendar range cannot exceed 93 days")

    role_name = _role_name(current_user)
    can_view_all = current_user.is_superuser or role_name in {"super_admin", "hr_manager", "hr_admin", "hr"}
    can_view_team = can_view_all or role_name in {"manager", "team_lead", "department_head"}

    if scope == "all" and not can_view_all:
        scope = "team"
    if scope == "team" and not can_view_team:
        scope = "mine"

    query = (
        db.query(LeaveRequest)
        .options(joinedload(LeaveRequest.employee), joinedload(LeaveRequest.leave_type))
        .filter(
            LeaveRequest.deleted_at.is_(None),
            LeaveRequest.status.in_(["Pending", "Approved"]),
            LeaveRequest.from_date <= to_date,
            LeaveRequest.to_date >= from_date,
        )
    )
    company_id = None if current_user.is_superuser else _current_company_id(current_user)
    if company_id:
        query = query.filter(LeaveRequest.company_id == company_id)

    if department_id:
        query = query.join(Employee, LeaveRequest.employee_id == Employee.id).filter(Employee.department_id == department_id)

    if scope == "mine":
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="No employee profile")
        query = query.filter(LeaveRequest.employee_id == current_user.employee.id)
    elif scope == "team" and not can_view_all:
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="No employee profile")
        direct_report_ids = [
            row.id for row in db.query(Employee.id).filter(Employee.reporting_manager_id == current_user.employee.id).all()
        ]
        allowed_ids = direct_report_ids + [current_user.employee.id]
        query = query.filter(LeaveRequest.employee_id.in_(allowed_ids))

    requests = query.order_by(LeaveRequest.from_date, LeaveRequest.id).all()
    holidays = (
        db.query(Holiday)
        .filter(Holiday.is_active == True, Holiday.holiday_date >= from_date, Holiday.holiday_date <= to_date)
        .order_by(Holiday.holiday_date)
        .all()
    )

    day_map = {}
    current = from_date
    while current <= to_date:
        day_map[current] = {
            "date": current,
            "leave_count": 0,
            "pending_count": 0,
            "approved_count": 0,
            "employees_on_leave": [],
            "holidays": [],
        }
        current += timedelta(days=1)

    for holiday in holidays:
        day_map[holiday.holiday_date]["holidays"].append(holiday)

    for request in requests:
        current = max(request.from_date, from_date)
        end = min(request.to_date, to_date)
        while current <= end:
            day = day_map[current]
            day["employees_on_leave"].append(request)
            day["leave_count"] += 1
            if request.status == "Pending":
                day["pending_count"] += 1
            elif request.status == "Approved":
                day["approved_count"] += 1
            current += timedelta(days=1)

    days = [LeaveCalendarDay(**day_map[key]) for key in sorted(day_map)]
    return {
        "from_date": from_date,
        "to_date": to_date,
        "scope": scope,
        "total_leave_days": sum(day.leave_count for day in days),
        "days": days,
    }


@router.get("/team-calendar")
def team_leave_calendar(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    department_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from_date, to_date = _month_bounds(year, month)
    query = _approved_leave_query(db, from_date, to_date).join(Employee, LeaveRequest.employee_id == Employee.id)

    if _is_hr_admin(current_user):
        resolved_department_id = _department_id(department_id)
        if resolved_department_id:
            query = query.filter(Employee.department_id == resolved_department_id)
    else:
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="No employee profile")
        direct_report_ids = [
            row.id for row in db.query(Employee.id).filter(
                Employee.reporting_manager_id == current_user.employee.id,
                Employee.deleted_at.is_(None),
            ).all()
        ]
        if direct_report_ids:
            query = query.filter(LeaveRequest.employee_id.in_(direct_report_ids))
        elif current_user.employee.department_id:
            query = query.filter(
                Employee.department_id == current_user.employee.department_id,
                Employee.id != current_user.employee.id,
                Employee.deleted_at.is_(None),
            )
        else:
            return []

    requests = query.order_by(Employee.first_name, Employee.last_name, LeaveRequest.from_date).all()
    return _group_leaves_by_employee(requests)


@router.get("/department-calendar")
def department_leave_calendar(
    department_id: str = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date cannot be before from_date")
    resolved_department_id = _department_id(department_id)
    if not _is_hr_admin(current_user):
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="No employee profile")
        direct_report_exists = db.query(Employee.id).filter(
            Employee.reporting_manager_id == current_user.employee.id,
            Employee.department_id == resolved_department_id,
            Employee.deleted_at.is_(None),
        ).first()
        if current_user.employee.department_id != resolved_department_id and not direct_report_exists:
            raise HTTPException(status_code=403, detail="Not authorized to view this department calendar")

    requests = (
        _approved_leave_query(db, from_date, to_date)
        .join(Employee, LeaveRequest.employee_id == Employee.id)
        .filter(Employee.department_id == resolved_department_id, Employee.deleted_at.is_(None))
        .order_by(Employee.first_name, Employee.last_name, LeaveRequest.from_date)
        .all()
    )
    return _group_leaves_by_employee(requests)


@router.get("/today-absences")
def today_absences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = date.today()
    query = _approved_leave_query(db, today, today).join(Employee, LeaveRequest.employee_id == Employee.id)

    if not _is_hr_admin(current_user):
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="No employee profile")
        direct_report_ids = [
            row.id for row in db.query(Employee.id).filter(
                Employee.reporting_manager_id == current_user.employee.id,
                Employee.deleted_at.is_(None),
            ).all()
        ]
        if direct_report_ids:
            query = query.filter(LeaveRequest.employee_id.in_(direct_report_ids))
        elif current_user.employee.department_id:
            query = query.filter(
                Employee.department_id == current_user.employee.department_id,
                Employee.id != current_user.employee.id,
                Employee.deleted_at.is_(None),
            )
        else:
            return []

    requests = query.order_by(Employee.first_name, Employee.last_name, LeaveRequest.from_date).all()
    return _group_leaves_by_employee(requests)


@router.put("/requests/{request_id}/approve")
def approve_leave(
    request_id: int,
    data: LeaveApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("leave_approve")),
):
    result = crud_leave.approve_leave_request(
        db, request_id, data.status, current_user.id, data.review_remarks
    )
    if not result:
        raise HTTPException(status_code=404, detail="Leave request not found or already processed")
    emp = db.query(Employee).filter(Employee.id == result.employee_id).first()
    if emp and emp.user_id:
        remarks = f" Remarks: {data.review_remarks}" if data.review_remarks else ""
        _notify_user(
            db,
            emp.user_id,
            f"Leave {data.status}",
            f"Your leave request ({result.from_date} - {result.to_date}) has been {data.status.lower()}.{remarks}",
            f"leave_{data.status.lower()}",
            result.id,
        )
    return {"message": f"Leave request {data.status}"}


@router.put("/requests/{request_id}/cancel")
def cancel_leave(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.leave import LeaveRequest
    req = db.query(LeaveRequest).filter(
        LeaveRequest.id == request_id,
        LeaveRequest.deleted_at.is_(None),
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if current_user.employee and req.employee_id != current_user.employee.id:
        if not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Not authorized")
    if req.status not in ["Pending"]:
        raise HTTPException(status_code=400, detail="Can only cancel pending requests")
    cancelled = crud_leave.cancel_leave_request(db, request_id, current_user.id)
    if not cancelled:
        raise HTTPException(status_code=400, detail="Can only cancel pending requests")
    return {"message": "Leave request cancelled"}
