from __future__ import annotations
from app.access.catalog import permission_objects

import calendar
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.deps import RequirePermission, get_current_user, get_db
from app.models.attendance import Attendance, Holiday
from app.models.employee import Employee
from app.models.leave import LeaveBalance, LeaveBalanceLedger, LeaveRequest, LeaveType
from app.models.payroll import (
    EmployeeSalary,
    LeaveEncashmentLine,
    LeaveEncashmentPolicy,
    LeaveEncashmentRequest,
    LOPAdjustment,
    PayrollAttendanceInput,
    PayrollLWPEntry,
    PayrollPayGroup,
    PayrollPeriod,
)
from app.models.user import User

router = APIRouter(tags=["HRMS Leave Payroll"])


class LeaveEncashmentRequestPayload(BaseModel):
    employeeId: int | None = None
    leaveTypeId: int
    daysToEncash: Decimal = Field(..., gt=0)
    remarks: str | None = None


class LeaveEncashmentReviewPayload(BaseModel):
    remarks: str | None = None


class LWPSyncPayload(BaseModel):
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    employeeIds: list[int] | None = None
    approveInputs: bool = True
    includeAttendanceAbsence: bool = True


def _money(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _days(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _org_id(user: User) -> int | None:
    return getattr(user, "organization_id", None) or getattr(user, "company_id", None)


def _has_permission(user: User, permission: str) -> bool:
    if user.is_superuser:
        return True
    return permission in {p.name for p in (permission_objects(user))}


def _can_manage_leave_payroll(user: User) -> bool:
    return _has_permission(user, "payroll_run") or _has_permission(user, "leave_manage") or _has_permission(user, "leave_approve")


def _employee_for_user(user: User) -> Employee:
    if not user.employee:
        raise HTTPException(status_code=400, detail="No employee profile is linked to this account")
    return user.employee


def _employee_name(employee: Employee | None) -> str:
    if not employee:
        return "Employee"
    return " ".join(part for part in [employee.first_name, employee.last_name] if part) or employee.employee_id


def _month_bounds(month: str) -> tuple[date, date]:
    try:
        year, month_no = [int(part) for part in month.split("-")]
        return date(year, month_no, 1), date(year, month_no, calendar.monthrange(year, month_no)[1])
    except Exception as exc:
        raise HTTPException(status_code=400, detail="month must be in YYYY-MM format") from exc


def _period_for_month(db: Session, month: str, create: bool = True) -> PayrollPeriod | None:
    period_start, period_end = _month_bounds(month)
    period = (
        db.query(PayrollPeriod)
        .filter(PayrollPeriod.month == period_start.month, PayrollPeriod.year == period_start.year)
        .order_by(PayrollPeriod.id.desc())
        .first()
    )
    if period or not create:
        return period
    pay_group = db.query(PayrollPayGroup).filter(PayrollPayGroup.is_active == True).order_by(PayrollPayGroup.is_default.desc(), PayrollPayGroup.id).first()
    if not pay_group:
        pay_group = PayrollPayGroup(name="Default Payroll Group", code="DEFAULT", is_default=True, is_active=True)
        db.add(pay_group)
        db.flush()
    period = PayrollPeriod(
        pay_group_id=pay_group.id,
        month=period_start.month,
        year=period_start.year,
        financial_year=f"{period_start.year}-{str(period_start.year + 1)[-2:]}",
        period_start=period_start,
        period_end=period_end,
        payroll_date=period_end,
        status="Open",
    )
    db.add(period)
    db.flush()
    return period


def _leave_balance(db: Session, employee_id: int, leave_type_id: int, year: int) -> LeaveBalance:
    balance = (
        db.query(LeaveBalance)
        .filter(LeaveBalance.employee_id == employee_id, LeaveBalance.leave_type_id == leave_type_id, LeaveBalance.year == year)
        .first()
    )
    if not balance:
        raise HTTPException(status_code=400, detail="No leave balance is available for this leave type")
    return balance


def _available_days(balance: LeaveBalance) -> Decimal:
    return _days(balance.allocated) + _days(balance.carried_forward) - _days(balance.used) - _days(balance.pending)


def _active_policy(db: Session, leave_type_id: int, when: date) -> LeaveEncashmentPolicy | None:
    return (
        db.query(LeaveEncashmentPolicy)
        .filter(
            LeaveEncashmentPolicy.leave_type_id == leave_type_id,
            LeaveEncashmentPolicy.is_active == True,
            LeaveEncashmentPolicy.effective_from <= when,
            (LeaveEncashmentPolicy.effective_to.is_(None)) | (LeaveEncashmentPolicy.effective_to >= when),
        )
        .order_by(LeaveEncashmentPolicy.effective_from.desc(), LeaveEncashmentPolicy.id.desc())
        .first()
    )


def _encashment_rate(db: Session, employee_id: int) -> Decimal:
    salary = (
        db.query(EmployeeSalary)
        .filter(EmployeeSalary.employee_id == employee_id, EmployeeSalary.is_active == True)
        .order_by(EmployeeSalary.effective_from.desc(), EmployeeSalary.id.desc())
        .first()
    )
    if not salary:
        return Decimal("0")
    monthly = _money((salary.ctc or Decimal("0")) / Decimal("12"))
    return _money((salary.basic or monthly) / Decimal("26"))


def _is_unpaid_leave_type(leave_type: LeaveType | None) -> bool:
    marker = f"{getattr(leave_type, 'name', '')} {getattr(leave_type, 'code', '')}".lower()
    return any(token in marker for token in ("lop", "lwp", "loss of pay", "unpaid", "without pay"))


def _serialize_encashment(request: LeaveEncashmentRequest) -> dict[str, Any]:
    return {
        "id": request.id,
        "organizationId": request.organization_id,
        "employeeId": request.employee_id,
        "employeeName": _employee_name(request.employee),
        "employeeCode": request.employee.employee_id if request.employee else None,
        "leaveTypeId": request.leave_type_id,
        "leaveTypeName": request.leave_type.name if request.leave_type else None,
        "daysToEncash": float(_days(request.days_to_encash)),
        "encashmentRate": float(_money(request.encashment_rate)),
        "amount": float(_money(request.amount)),
        "status": request.status,
        "requestedAt": request.requested_at,
        "approvedBy": request.approved_by,
        "approvedAt": request.approved_at,
        "payrollRunId": request.payroll_run_id,
        "remarks": request.remarks,
    }


def _serialize_lwp(entry: PayrollLWPEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "organizationId": entry.organization_id,
        "employeeId": entry.employee_id,
        "employeeName": _employee_name(entry.employee),
        "employeeCode": entry.employee.employee_id if entry.employee else None,
        "payrollMonth": entry.payroll_month,
        "lwpDays": float(_days(entry.lwp_days)),
        "source": entry.source,
        "amountDeducted": float(_money(entry.amount_deducted)),
        "payrollRunId": entry.payroll_run_id,
        "createdAt": entry.created_at,
    }


def _load_encashment_request(db: Session, request_id: int, current_user: User) -> LeaveEncashmentRequest:
    query = (
        db.query(LeaveEncashmentRequest)
        .options(joinedload(LeaveEncashmentRequest.employee), joinedload(LeaveEncashmentRequest.leave_type))
        .filter(LeaveEncashmentRequest.id == request_id)
    )
    org_id = _org_id(current_user)
    if org_id is not None:
        query = query.filter(LeaveEncashmentRequest.organization_id == org_id)
    request = query.first()
    if not request:
        raise HTTPException(status_code=404, detail="Leave encashment request not found")
    return request


@router.post("/hrms/leave-encashment/request", status_code=201)
def create_leave_encashment_request(
    data: LeaveEncashmentRequestPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee_id = data.employeeId
    if employee_id is not None and not _can_manage_leave_payroll(current_user):
        raise HTTPException(status_code=403, detail="Only HR/payroll can request encashment for another employee")
    employee_id = employee_id or _employee_for_user(current_user).id
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.deleted_at.is_(None)).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    leave_type = db.query(LeaveType).filter(LeaveType.id == data.leaveTypeId, LeaveType.is_active == True).first()
    if not leave_type:
        raise HTTPException(status_code=404, detail="Leave type not found")
    if not leave_type.encashable:
        raise HTTPException(status_code=400, detail="This leave type is not encashable")

    today = date.today()
    balance = _leave_balance(db, employee_id, data.leaveTypeId, today.year)
    available = _available_days(balance)
    if data.daysToEncash > available:
        raise HTTPException(status_code=400, detail=f"Only {available} day(s) are available for encashment")
    policy = _active_policy(db, data.leaveTypeId, today)
    if policy and policy.max_days is not None and data.daysToEncash > _days(policy.max_days):
        raise HTTPException(status_code=400, detail=f"Policy allows maximum {policy.max_days} day(s) per request")
    rate = _encashment_rate(db, employee_id)
    amount = _money(rate * data.daysToEncash)
    request = LeaveEncashmentRequest(
        organization_id=_org_id(current_user),
        employee_id=employee_id,
        leave_type_id=data.leaveTypeId,
        days_to_encash=data.daysToEncash,
        encashment_rate=rate,
        amount=amount,
        status="submitted",
        remarks=data.remarks,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return _serialize_encashment(request)


@router.get("/hrms/leave-encashment")
def list_leave_encashment_requests(
    status: str | None = Query(None),
    employeeId: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(LeaveEncashmentRequest).options(joinedload(LeaveEncashmentRequest.employee), joinedload(LeaveEncashmentRequest.leave_type))
    org_id = _org_id(current_user)
    if org_id is not None:
        query = query.filter(LeaveEncashmentRequest.organization_id == org_id)
    if not _can_manage_leave_payroll(current_user):
        query = query.filter(LeaveEncashmentRequest.employee_id == _employee_for_user(current_user).id)
    elif employeeId:
        query = query.filter(LeaveEncashmentRequest.employee_id == employeeId)
    if status:
        query = query.filter(LeaveEncashmentRequest.status == status)
    return [_serialize_encashment(item) for item in query.order_by(LeaveEncashmentRequest.id.desc()).limit(500).all()]


@router.post("/hrms/leave-encashment/{request_id}/approve", dependencies=[Depends(RequirePermission("payroll_run", "leave_approve"))])
def approve_leave_encashment_request(
    request_id: int,
    data: LeaveEncashmentReviewPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    request = _load_encashment_request(db, request_id, current_user)
    if request.status not in {"submitted", "draft"}:
        raise HTTPException(status_code=400, detail="Only draft/submitted requests can be approved")
    today = date.today()
    balance = _leave_balance(db, request.employee_id, request.leave_type_id, today.year)
    if request.days_to_encash > _available_days(balance):
        raise HTTPException(status_code=400, detail="Leave balance is no longer sufficient")
    month = f"{today.year:04d}-{today.month:02d}"
    period = _period_for_month(db, month, create=True)
    policy = _active_policy(db, request.leave_type_id, today)
    line = LeaveEncashmentLine(
        period_id=period.id,
        employee_id=request.employee_id,
        policy_id=policy.id if policy else None,
        leave_type_id=request.leave_type_id,
        days=request.days_to_encash,
        rate_per_day=request.encashment_rate,
        amount=request.amount,
        tax_treatment=policy.tax_treatment if policy else "Taxable",
        status="Approved",
        approved_by=current_user.id,
        approved_at=datetime.now(timezone.utc),
    )
    db.add(line)
    db.flush()
    balance.used = _days(balance.used) + _days(request.days_to_encash)
    balance_after = _available_days(balance)
    db.add(
        LeaveBalanceLedger(
            employee_id=request.employee_id,
            leave_type_id=request.leave_type_id,
            leave_balance_id=balance.id,
            year=today.year,
            transaction_type="encashment",
            amount=-_days(request.days_to_encash),
            balance_after=balance_after,
            reason=data.remarks or "Leave encashment approved",
            created_by=current_user.id,
        )
    )
    request.status = "approved"
    request.approved_by = current_user.id
    request.approved_at = datetime.now(timezone.utc)
    request.leave_encashment_line_id = line.id
    if data.remarks:
        request.remarks = data.remarks
    db.commit()
    db.refresh(request)
    return _serialize_encashment(request)


@router.post("/hrms/leave-encashment/{request_id}/reject", dependencies=[Depends(RequirePermission("payroll_run", "leave_approve"))])
def reject_leave_encashment_request(
    request_id: int,
    data: LeaveEncashmentReviewPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    request = _load_encashment_request(db, request_id, current_user)
    if request.status in {"paid", "approved"}:
        raise HTTPException(status_code=400, detail="Approved or paid requests cannot be rejected")
    request.status = "rejected"
    request.approved_by = current_user.id
    request.approved_at = datetime.now(timezone.utc)
    request.remarks = data.remarks or request.remarks
    db.commit()
    db.refresh(request)
    return _serialize_encashment(request)


def _calculate_lwp_feed(db: Session, month: str, employee_ids: list[int] | None = None, include_attendance: bool = True) -> list[dict[str, Any]]:
    period_start, period_end = _month_bounds(month)
    employee_query = db.query(Employee).filter(Employee.status == "Active", Employee.deleted_at.is_(None))
    if employee_ids:
        employee_query = employee_query.filter(Employee.id.in_(employee_ids))
    employees = employee_query.order_by(Employee.first_name, Employee.last_name).all()
    working_days = Decimal(str(sum(1 for offset in range((period_end - period_start).days + 1) if date.fromordinal(period_start.toordinal() + offset).weekday() < 5)))
    holidays = Decimal(str(db.query(Holiday).filter(Holiday.is_active == True, Holiday.holiday_date >= period_start, Holiday.holiday_date <= period_end).count()))
    rows = []
    for employee in employees:
        leave_days = Decimal("0")
        leaves = db.query(LeaveRequest).filter(
            LeaveRequest.employee_id == employee.id,
            LeaveRequest.status == "Approved",
            LeaveRequest.from_date <= period_end,
            LeaveRequest.to_date >= period_start,
        ).all()
        for leave in leaves:
            if not _is_unpaid_leave_type(leave.leave_type):
                continue
            overlap_start = max(leave.from_date, period_start)
            overlap_end = min(leave.to_date, period_end)
            leave_days += Decimal("0.5") if leave.is_half_day else Decimal(str((overlap_end - overlap_start).days + 1))

        attendance_days = Decimal("0")
        if include_attendance:
            absent_rows = db.query(Attendance).filter(
                Attendance.employee_id == employee.id,
                Attendance.attendance_date >= period_start,
                Attendance.attendance_date <= period_end,
                Attendance.status.in_(["Absent", "LWP", "Leave Without Pay"]),
            ).all()
            attendance_days = Decimal(str(len(absent_rows)))

        manual_days = Decimal(
            db.query(func.coalesce(func.sum(LOPAdjustment.adjustment_days), 0))
            .join(PayrollPeriod, PayrollPeriod.id == LOPAdjustment.period_id)
            .filter(PayrollPeriod.month == period_start.month, PayrollPeriod.year == period_start.year, LOPAdjustment.employee_id == employee.id, LOPAdjustment.status == "Approved")
            .scalar()
            or 0
        )
        lwp_days = _days(leave_days + attendance_days + manual_days)
        if lwp_days <= 0:
            continue
        rate = _encashment_rate(db, employee.id)
        rows.append(
            {
                "employeeId": employee.id,
                "employeeCode": employee.employee_id,
                "employeeName": _employee_name(employee),
                "payrollMonth": month,
                "workingDays": float(max(Decimal("0"), working_days - holidays)),
                "leaveLwpDays": float(_days(leave_days)),
                "attendanceLwpDays": float(_days(attendance_days)),
                "manualLwpDays": float(_days(manual_days)),
                "lwpDays": float(lwp_days),
                "estimatedDeduction": float(_money(rate * lwp_days)),
            }
        )
    return rows


@router.get("/hrms/payroll/lwp-feed", dependencies=[Depends(RequirePermission("payroll_view", "payroll_run"))])
def get_lwp_feed(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = _calculate_lwp_feed(db, month)
    entries = (
        db.query(PayrollLWPEntry)
        .options(joinedload(PayrollLWPEntry.employee))
        .filter(PayrollLWPEntry.payroll_month == month)
        .order_by(PayrollLWPEntry.id.desc())
        .all()
    )
    org_id = _org_id(current_user)
    if org_id is not None:
        entries = [entry for entry in entries if entry.organization_id == org_id]
    return {"month": month, "preview": rows, "entries": [_serialize_lwp(entry) for entry in entries]}


@router.post("/hrms/payroll/lwp-sync", dependencies=[Depends(RequirePermission("payroll_run"))])
def sync_lwp_feed(
    data: LWPSyncPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    period = _period_for_month(db, data.month, create=True)
    rows = _calculate_lwp_feed(db, data.month, data.employeeIds, data.includeAttendanceAbsence)
    synced = 0
    for row in rows:
        employee_id = int(row["employeeId"])
        lwp_days = _days(row["lwpDays"])
        input_row = (
            db.query(PayrollAttendanceInput)
            .filter(PayrollAttendanceInput.period_id == period.id, PayrollAttendanceInput.employee_id == employee_id)
            .first()
        )
        working_days = Decimal(str(row["workingDays"] or 0))
        if not input_row:
            input_row = PayrollAttendanceInput(period_id=period.id, employee_id=employee_id)
            db.add(input_row)
            db.flush()
        input_row.working_days = working_days
        input_row.lop_days = lwp_days
        input_row.unpaid_leave_days = lwp_days
        input_row.payable_days = max(Decimal("0"), working_days - lwp_days)
        input_row.source_status = "Approved" if data.approveInputs else "Draft"
        input_row.locked_at = datetime.now(timezone.utc) if data.approveInputs else None
        entry = (
            db.query(PayrollLWPEntry)
            .filter(PayrollLWPEntry.employee_id == employee_id, PayrollLWPEntry.payroll_month == data.month, PayrollLWPEntry.source == "leave")
            .first()
        )
        if not entry:
            entry = PayrollLWPEntry(
                organization_id=_org_id(current_user),
                employee_id=employee_id,
                payroll_month=data.month,
                source="leave",
            )
            db.add(entry)
        entry.lwp_days = lwp_days
        entry.amount_deducted = _money(row["estimatedDeduction"])
        entry.payroll_attendance_input_id = input_row.id
        synced += 1
    db.commit()
    return {"month": data.month, "synced": synced, "periodId": period.id}
