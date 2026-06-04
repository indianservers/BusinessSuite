from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import csv
import io
import json
import math
from typing import List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.deps import get_db, get_current_user, RequirePermission
from app.crud.crud_attendance import crud_attendance, crud_holiday
from app.schemas.notification import NotificationCreate
from app.services.notifications import create_notification
from app.models.user import User
from app.models.attendance import (
    Shift, ShiftRosterAssignment, ShiftWeeklyOff, AttendanceRegularization, Holiday,
    Attendance, OvertimeRequest, AttendancePunch, AttendanceMonthLock, BiometricDevice,
    BiometricImportBatch, GeoAttendancePolicy, AttendancePunchProof,
)
from app.models.audit import AuditLog
from app.models.employee import Employee
from app.schemas.attendance import (
    ShiftCreate, ShiftSchema,
    ShiftRosterAssignmentCreate, ShiftRosterAssignmentSchema,
    ShiftWeeklyOffCreate, ShiftWeeklyOffSchema,
    HolidayCreate, HolidaySchema,
    CheckInRequest, CheckOutRequest,
    AttendancePunchCreate, AttendancePunchSchema, AttendanceMonthLockCreate, AttendanceMonthLockSchema,
    BiometricDeviceCreate, BiometricDeviceSchema, BiometricImportRequest, BiometricImportBatchSchema,
    BiometricAdapterImportRequest, BiometricReconcileRequest,
    GeoAttendancePolicyCreate, GeoAttendancePolicySchema, GeoPunchRequest, AttendancePunchProofSchema,
    AttendanceSchema, PunchRequest, RegularizationRequest,
    RegularizationApproval, RegularizationSchema,
    AttendanceBulkEntryRequest, AttendanceBulkEntryResponse, AttendanceRegisterResponse,
)
from app.schemas.attendance import ShiftCreate as ShiftUpdate
from app.schemas.attendance import HolidayCreate as HolidayUpdate

router = APIRouter(prefix="/attendance", tags=["Attendance"])


def _locked_month(db: Session, value: date) -> bool:
    return db.query(AttendanceMonthLock).filter(
        AttendanceMonthLock.month == value.month,
        AttendanceMonthLock.year == value.year,
        AttendanceMonthLock.status == "Locked",
    ).first() is not None


def _user_permissions(user: User) -> set[str]:
    return {permission.name for permission in (user.role.permissions if user.role else [])}


def _can_view_all_attendance(user: User) -> bool:
    return user.is_superuser or bool(_user_permissions(user).intersection({"attendance_view", "attendance_manage", "hr_admin"}))


def _can_view_employee_attendance(db: Session, user: User, employee_id: int) -> bool:
    if _can_view_all_attendance(user):
        return True
    if user.employee and user.employee.id == employee_id:
        return True
    if user.employee:
        return db.query(Employee.id).filter(
            Employee.id == employee_id,
            Employee.reporting_manager_id == user.employee.id,
            Employee.deleted_at.is_(None),
        ).first() is not None
    return False


def _employee_or_400(user: User) -> Employee:
    if not user.employee:
        raise HTTPException(status_code=400, detail="No employee profile linked to this user")
    return user.employee


def compute_attendance_summary(employee_id: int, work_date: date, db: Session) -> Attendance:
    return crud_attendance.compute_day(db, employee_id, work_date)


def _display_attendance_status(status: str | None) -> str:
    if status == "Weekend":
        return "Weekly Off"
    return status or "Absent"


def _stored_attendance_status(status: str) -> str:
    normalized = status.strip()
    if normalized == "Half Day":
        return "Half-day"
    if normalized == "Weekly Off":
        return "Weekend"
    return normalized


def _attendance_register_row(employee: Employee, attendance: Attendance | None, work_date: date) -> dict:
    return {
        "attendance_id": attendance.id if attendance else None,
        "employee_id": employee.id,
        "employee_code": employee.employee_id,
        "employee_name": " ".join(part for part in [employee.first_name, employee.last_name] if part) or employee.employee_id,
        "department": employee.department.name if employee.department else None,
        "branch": employee.branch.name if employee.branch else None,
        "date": work_date,
        "status": _display_attendance_status(attendance.status if attendance else "Absent"),
        "hours_worked": Decimal(str(attendance.total_hours or 0)) if attendance else Decimal("0"),
        "ot_hours": Decimal(str(attendance.overtime_hours or 0)) if attendance else Decimal("0"),
        "remarks": attendance.remarks if attendance else None,
    }


def _row_value(row: dict, preferred: Optional[str], aliases: list[str]) -> Optional[str]:
    normalized = {str(key).strip().lower(): value for key, value in row.items()}
    if preferred:
        value = normalized.get(preferred.strip().lower())
        if value not in (None, ""):
            return str(value).strip()
    for alias in aliases:
        value = normalized.get(alias)
        if value not in (None, ""):
            return str(value).strip()
    return None


def _parse_adapter_punch_time(value: str) -> datetime:
    cleaned = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _normalize_adapter_punch_type(value: Optional[str]) -> str:
    raw = (value or "IN").strip().lower()
    if raw in {"out", "o", "1", "check out", "checkout", "clock out"}:
        return "OUT"
    if raw in {"break_in", "break in", "break-in", "2"}:
        return "BREAK_IN"
    if raw in {"break_out", "break out", "break-out", "3"}:
        return "BREAK_OUT"
    return "IN"


def _employee_from_adapter_code(db: Session, code: str) -> Optional[Employee]:
    employee = db.query(Employee).filter(Employee.employee_id == code, Employee.deleted_at.is_(None)).first()
    if employee:
        return employee
    if code.isdigit():
        return db.query(Employee).filter(Employee.id == int(code), Employee.deleted_at.is_(None)).first()
    return None


def _record_biometric_punch(
    db: Session,
    employee_id: int,
    punch_time: datetime,
    punch_type: str,
    device_id: Optional[int],
    raw_payload: dict,
) -> bool:
    device_key = str(device_id or "")
    existing = db.query(AttendancePunch).filter(
        AttendancePunch.employee_id == employee_id,
        AttendancePunch.punch_time == punch_time,
        AttendancePunch.punch_type == punch_type,
        AttendancePunch.device_id == device_key,
    ).first()
    if existing:
        return False
    db.add(AttendancePunch(
        employee_id=employee_id,
        punch_time=punch_time,
        punch_type=punch_type,
        source="Biometric",
        device_id=device_key,
        raw_payload=json.dumps(raw_payload, default=str),
    ))
    return True


def _attendance_reconciliation(db: Session, from_date: date, to_date: date, employee_id: Optional[int] = None, recompute: bool = True) -> dict:
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date must be on or after from_date")
    employee_query = db.query(Employee).filter(Employee.deleted_at.is_(None), Employee.status.in_(["Active", "Probation", "Notice Period"]))
    if employee_id:
        employee_query = employee_query.filter(Employee.id == employee_id)
    employees = employee_query.order_by(Employee.employee_id).all()
    missing_punches = []
    duplicate_punches = []
    reconciled_days = 0
    cursor = from_date
    while cursor <= to_date:
        start = datetime.combine(cursor, datetime.min.time(), tzinfo=timezone.utc)
        end = datetime.combine(cursor, datetime.max.time(), tzinfo=timezone.utc)
        for employee in employees:
            punches = db.query(AttendancePunch).filter(
                AttendancePunch.employee_id == employee.id,
                AttendancePunch.punch_time >= start,
                AttendancePunch.punch_time <= end,
            ).order_by(AttendancePunch.punch_time).all()
            if recompute and punches:
                compute_attendance_summary(employee.id, cursor, db)
            by_key: dict[tuple[str, datetime, str], int] = {}
            for punch in punches:
                key = (punch.punch_type, punch.punch_time, punch.device_id or "")
                by_key[key] = by_key.get(key, 0) + 1
            for (punch_type, punch_time, device_key), count in by_key.items():
                if count > 1:
                    duplicate_punches.append({
                        "employee_id": employee.id,
                        "employee_code": employee.employee_id,
                        "date": cursor.isoformat(),
                        "punch_time": punch_time.isoformat(),
                        "punch_type": punch_type,
                        "device_id": device_key,
                        "count": count,
                    })
            punch_types = {punch.punch_type for punch in punches}
            if not punches:
                missing_punches.append({"employee_id": employee.id, "employee_code": employee.employee_id, "date": cursor.isoformat(), "missing": "IN_OUT"})
            else:
                if "IN" not in punch_types:
                    missing_punches.append({"employee_id": employee.id, "employee_code": employee.employee_id, "date": cursor.isoformat(), "missing": "IN"})
                if "OUT" not in punch_types:
                    missing_punches.append({"employee_id": employee.id, "employee_code": employee.employee_id, "date": cursor.isoformat(), "missing": "OUT"})
                if "IN" in punch_types and "OUT" in punch_types:
                    reconciled_days += 1
        cursor += timedelta(days=1)
    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "employee_count": len(employees),
        "reconciled_days": reconciled_days,
        "missing_punch_count": len(missing_punches),
        "duplicate_punch_count": len(duplicate_punches),
        "missing_punches": missing_punches,
        "duplicate_punches": duplicate_punches,
        "payroll_blocking": bool(missing_punches or duplicate_punches),
    }


def _attendance_timezone():
    try:
        return ZoneInfo(settings.CELERY_TIMEZONE)
    except ZoneInfoNotFoundError:
        return timezone.utc


def _business_date(value: datetime | None = None) -> date:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.date()
    return value.astimezone(_attendance_timezone()).date()


def _utc_day_bounds(work_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(work_date, time.min)
    end = datetime.combine(work_date, time.max)
    return start, end


def _attendance_now() -> datetime:
    return datetime.now(_attendance_timezone()).replace(tzinfo=None)


def _attendance_payload(record: Attendance | None) -> dict | None:
    if not record:
        return None
    return jsonable_encoder(AttendanceSchema.model_validate(record))


def _punch_payload(punch: AttendancePunch) -> dict:
    return jsonable_encoder(AttendancePunchSchema.model_validate(punch))


def _distance_meters(lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal) -> float:
    radius = 6371000
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    delta_phi = math.radians(float(lat2 - lat1))
    delta_lambda = math.radians(float(lon2 - lon1))
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@router.get("/today-summary")
def today_attendance_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_view")),
):
    today = date.today()
    total_employees = db.query(func.count(Employee.id)).filter(
        Employee.deleted_at.is_(None),
        Employee.status.in_(["Active", "Probation"]),
    ).scalar() or 0
    present = db.query(func.count(Attendance.id)).filter(
        Attendance.attendance_date == today,
        Attendance.status.in_(["Present", "WFH", "Half-day"]),
    ).scalar() or 0
    on_leave = db.query(func.count(Attendance.id)).filter(
        Attendance.attendance_date == today,
        Attendance.status == "On Leave",
    ).scalar() or 0
    return {
        "date": today.isoformat(),
        "present": present,
        "on_leave": on_leave,
        "absent": max(total_employees - present - on_leave, 0),
        "total_employees": total_employees,
    }


# ── Shifts ───────────────────────────────────────────────────────────────────

@router.get("/shifts", response_model=List[ShiftSchema])
def list_shifts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Shift).filter(Shift.is_active == True).all()


@router.post("/shifts", response_model=ShiftSchema, status_code=201)
def create_shift(
    data: ShiftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    shift = Shift(**data.model_dump())
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


@router.put("/shifts/{shift_id}", response_model=ShiftSchema)
def update_shift(
    shift_id: int,
    data: ShiftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(shift, k, v)
    db.commit()
    db.refresh(shift)
    return shift


@router.delete("/shifts/{shift_id}")
def delete_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    shift.is_active = False
    db.commit()
    return {"message": "Shift deactivated"}


@router.get("/weekly-offs", response_model=List[ShiftWeeklyOffSchema])
def list_weekly_offs(
    shift_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    query = db.query(ShiftWeeklyOff).filter(ShiftWeeklyOff.is_active == True)
    if shift_id:
        query = query.filter(ShiftWeeklyOff.shift_id == shift_id)
    return query.order_by(ShiftWeeklyOff.shift_id, ShiftWeeklyOff.weekday).all()


@router.post("/weekly-offs", response_model=ShiftWeeklyOffSchema, status_code=201)
def create_weekly_off(
    data: ShiftWeeklyOffCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    shift = db.query(Shift).filter(Shift.id == data.shift_id, Shift.is_active == True).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    weekly_off = ShiftWeeklyOff(**data.model_dump())
    db.add(weekly_off)
    db.commit()
    db.refresh(weekly_off)
    return weekly_off


@router.post("/roster", response_model=ShiftRosterAssignmentSchema, status_code=201)
def assign_roster(
    data: ShiftRosterAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    shift = db.query(Shift).filter(Shift.id == data.shift_id, Shift.is_active == True).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    existing = db.query(ShiftRosterAssignment).filter(
        ShiftRosterAssignment.employee_id == data.employee_id,
        ShiftRosterAssignment.work_date == data.work_date,
    ).first()
    if existing:
        existing.shift_id = data.shift_id
        existing.status = data.status
        db.commit()
        db.refresh(existing)
        return existing
    assignment = ShiftRosterAssignment(**data.model_dump())
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


# ── Holidays ─────────────────────────────────────────────────────────────────

@router.get("/holidays", response_model=List[HolidaySchema])
def list_holidays(
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Holiday).filter(Holiday.is_active == True)
    if year:
        from sqlalchemy import extract
        q = q.filter(extract("year", Holiday.holiday_date) == year)
    return q.order_by(Holiday.holiday_date).all()


@router.post("/holidays", response_model=HolidaySchema, status_code=201)
def create_holiday(
    data: HolidayCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    holiday = Holiday(**data.model_dump())
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    return holiday


@router.put("/holidays/{holiday_id}", response_model=HolidaySchema)
def update_holiday(
    holiday_id: int,
    data: HolidayUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    holiday = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(holiday, k, v)
    db.commit()
    db.refresh(holiday)
    return holiday


@router.delete("/holidays/{holiday_id}")
def delete_holiday(
    holiday_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    holiday = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    holiday.is_active = False
    db.commit()
    return {"message": "Holiday deleted"}


# ── Check-in / Check-out ──────────────────────────────────────────────────────

@router.post("/check-in", response_model=AttendanceSchema)
def check_in(
    data: CheckInRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile linked to this user")
    if _locked_month(db, date.today()):
        raise HTTPException(status_code=400, detail="Attendance month is locked")
    return crud_attendance.check_in(
        db,
        current_user.employee.id,
        location=data.check_in_location,
        ip=data.check_in_ip,
        source=data.source,
    )


@router.post("/check-out", response_model=AttendanceSchema)
def check_out(
    data: CheckOutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile linked to this user")
    if _locked_month(db, date.today()):
        raise HTTPException(status_code=400, detail="Attendance month is locked")
    record = crud_attendance.check_out(
        db,
        current_user.employee.id,
        location=data.check_out_location,
        ip=data.check_out_ip,
    )
    if not record:
        raise HTTPException(status_code=400, detail="No check-in found for today")
    return record


@router.post("/punches", response_model=AttendancePunchSchema, status_code=201)
def create_raw_punch(
    data: AttendancePunchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee_id = data.employee_id
    if employee_id and not current_user.is_superuser:
        if not current_user.employee or current_user.employee.id != employee_id:
            raise HTTPException(status_code=403, detail="Not authorized to punch for another employee")
    if not employee_id:
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="No employee profile")
        employee_id = current_user.employee.id
    if _locked_month(db, data.punch_time.date()):
        raise HTTPException(status_code=400, detail="Attendance month is locked")
    punch = AttendancePunch(**data.model_dump(exclude={"employee_id"}), employee_id=employee_id)
    db.add(punch)
    db.commit()
    db.refresh(punch)
    compute_attendance_summary(employee_id, _business_date(punch.punch_time), db)
    return punch


@router.post("/punch", status_code=201)
def punch_attendance(
    data: PunchRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = _employee_or_400(current_user)
    now = _attendance_now()
    work_date = _business_date(now)
    if _locked_month(db, work_date):
        raise HTTPException(status_code=400, detail="Attendance month is locked")

    punch = AttendancePunch(
        employee_id=employee.id,
        punch_time=now,
        punch_type=data.punch_type,
        source=data.source.title(),
        ip_address=request.client.host if request.client else None,
        latitude=data.latitude,
        longitude=data.longitude,
        location_text=data.location_text,
    )
    db.add(punch)
    db.commit()
    db.refresh(punch)
    attendance = compute_attendance_summary(employee.id, work_date, db)
    return {
        "attendance": _attendance_payload(attendance),
        "punch": _punch_payload(punch),
    }


@router.post("/biometric/devices", response_model=BiometricDeviceSchema, status_code=201)
def create_biometric_device(
    data: BiometricDeviceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    device = BiometricDevice(**data.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.get("/biometric/devices", response_model=List[BiometricDeviceSchema])
def list_biometric_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    return db.query(BiometricDevice).order_by(BiometricDevice.name).all()


@router.post("/biometric/import", response_model=BiometricImportBatchSchema, status_code=201)
def import_biometric_punches(
    data: BiometricImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    errors = []
    imported = 0
    skipped = 0
    for index, row in enumerate(data.rows, start=1):
        if _locked_month(db, row.punch_time.date()):
            errors.append({"row": index, "error": "Attendance month is locked"})
            continue
        existing = db.query(AttendancePunch).filter(
            AttendancePunch.employee_id == row.employee_id,
            AttendancePunch.punch_time == row.punch_time,
            AttendancePunch.punch_type == row.punch_type,
            AttendancePunch.device_id == str(data.device_id or ""),
        ).first()
        if existing:
            skipped += 1
            continue
        db.add(AttendancePunch(
            employee_id=row.employee_id,
            punch_time=row.punch_time,
            punch_type=row.punch_type,
            source="Biometric",
            device_id=str(data.device_id or row.device_user_id or ""),
            raw_payload=json.dumps(row.model_dump(), default=str),
        ))
        imported += 1
        compute_attendance_summary(row.employee_id, _business_date(row.punch_time), db)
    batch = BiometricImportBatch(
        device_id=data.device_id,
        source_filename=data.source_filename,
        imported_rows=imported,
        skipped_rows=skipped,
        error_rows=len(errors),
        status="Imported With Errors" if errors else "Imported",
        error_report_json=json.dumps(errors),
        imported_by=current_user.id,
    )
    if data.device_id:
        device = db.query(BiometricDevice).filter(BiometricDevice.id == data.device_id).first()
        if device:
            device.last_sync_at = datetime.now(timezone.utc)
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.post("/biometric/import-adapter", response_model=BiometricImportBatchSchema, status_code=201)
def import_biometric_adapter_file(
    data: BiometricAdapterImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    reader = csv.DictReader(io.StringIO(data.csv_text.strip()))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV header row is required")

    errors = []
    imported = 0
    skipped = 0
    for index, row in enumerate(reader, start=2):
        employee_code = _row_value(row, data.employee_code_column, ["employee_code", "emp_code", "employee_id", "user_id", "uid", "pin", "enroll_id"])
        raw_time = _row_value(row, data.punch_time_column, ["punch_time", "timestamp", "time", "date_time", "datetime", "log_time", "punch datetime"])
        raw_type = _row_value(row, data.punch_type_column, ["punch_type", "type", "status", "direction", "state"])
        if not employee_code or not raw_time:
            errors.append({"row": index, "error": "Employee code and punch time are required", "payload": row})
            continue
        employee = _employee_from_adapter_code(db, employee_code)
        if not employee:
            errors.append({"row": index, "error": f"Employee not found for code {employee_code}", "payload": row})
            continue
        try:
            punch_time = _parse_adapter_punch_time(raw_time)
        except ValueError:
            errors.append({"row": index, "error": f"Invalid punch time {raw_time}", "payload": row})
            continue
        if _locked_month(db, punch_time.date()):
            errors.append({"row": index, "error": "Attendance month is locked", "payload": row})
            continue
        imported_now = _record_biometric_punch(
            db=db,
            employee_id=employee.id,
            punch_time=punch_time,
            punch_type=_normalize_adapter_punch_type(raw_type),
            device_id=data.device_id,
            raw_payload={"adapter": data.adapter, "row": row},
        )
        if imported_now:
            imported += 1
            compute_attendance_summary(employee.id, _business_date(punch_time), db)
        else:
            skipped += 1

    batch = BiometricImportBatch(
        device_id=data.device_id,
        source_filename=data.source_filename or f"{data.adapter}-adapter.csv",
        imported_rows=imported,
        skipped_rows=skipped,
        error_rows=len(errors),
        status="Imported With Errors" if errors else "Imported",
        error_report_json=json.dumps(errors, default=str),
        imported_by=current_user.id,
    )
    if data.device_id:
        device = db.query(BiometricDevice).filter(BiometricDevice.id == data.device_id).first()
        if device:
            device.last_sync_at = datetime.now(timezone.utc)
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.post("/biometric/reconcile")
def reconcile_biometric_attendance(
    data: BiometricReconcileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    return _attendance_reconciliation(db, data.from_date, data.to_date, data.employee_id, data.recompute)


@router.get("/reports/missing-punches")
def missing_punch_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    result = _attendance_reconciliation(db, from_date, to_date, employee_id, recompute=False)
    return {
        "from_date": result["from_date"],
        "to_date": result["to_date"],
        "missing_punch_count": result["missing_punch_count"],
        "duplicate_punch_count": result["duplicate_punch_count"],
        "payroll_blocking": result["payroll_blocking"],
        "rows": result["missing_punches"],
        "duplicates": result["duplicate_punches"],
    }


@router.post("/geo/policies", response_model=GeoAttendancePolicySchema, status_code=201)
def create_geo_policy(
    data: GeoAttendancePolicyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    policy = GeoAttendancePolicy(**data.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@router.get("/geo/policies", response_model=List[GeoAttendancePolicySchema])
def list_geo_policies(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    return db.query(GeoAttendancePolicy).filter(GeoAttendancePolicy.is_active == True).order_by(GeoAttendancePolicy.name).all()


@router.post("/geo/punch", response_model=AttendancePunchProofSchema, status_code=201)
def create_geo_punch(
    data: GeoPunchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile linked to this user")
    if _locked_month(db, data.punch_time.date()):
        raise HTTPException(status_code=400, detail="Attendance month is locked")
    status = "Verified"
    message = "Geo punch accepted"
    policy = db.query(GeoAttendancePolicy).filter(GeoAttendancePolicy.id == data.policy_id).first() if data.policy_id else None
    if policy:
        distance = _distance_meters(data.latitude, data.longitude, policy.latitude, policy.longitude)
        if distance > (policy.radius_meters or 0):
            status = "Exception"
            message = f"Outside geofence by {round(distance - (policy.radius_meters or 0), 2)} meters"
        if policy.require_selfie and not data.selfie_url:
            status = "Exception"
            message = "Selfie proof is required"
        if policy.require_qr and not data.qr_code:
            status = "Exception"
            message = "QR proof is required"
    punch = AttendancePunch(
        employee_id=current_user.employee.id,
        punch_time=data.punch_time,
        punch_type=data.punch_type,
        source="Mobile",
        latitude=data.latitude,
        longitude=data.longitude,
        location_text=data.location_text,
        raw_payload=json.dumps(data.model_dump(), default=str),
    )
    db.add(punch)
    db.flush()
    proof = AttendancePunchProof(
        punch_id=punch.id,
        proof_type="Geo",
        proof_url=data.selfie_url,
        latitude=data.latitude,
        longitude=data.longitude,
        qr_code=data.qr_code,
        validation_status=status,
        validation_message=message,
    )
    db.add(proof)
    db.commit()
    db.refresh(proof)
    compute_attendance_summary(current_user.employee.id, _business_date(data.punch_time), db)
    return proof


@router.get("/punches", response_model=List[AttendancePunchSchema])
def list_raw_punches(
    employee_id: Optional[int] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    query = db.query(AttendancePunch)
    if employee_id:
        query = query.filter(AttendancePunch.employee_id == employee_id)
    if from_date:
        query = query.filter(AttendancePunch.punch_time >= datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc))
    if to_date:
        query = query.filter(AttendancePunch.punch_time <= datetime.combine(to_date, datetime.max.time(), tzinfo=timezone.utc))
    return query.order_by(AttendancePunch.punch_time.desc()).limit(500).all()


@router.post("/locks", response_model=AttendanceMonthLockSchema, status_code=201)
def lock_attendance_month(
    data: AttendanceMonthLockCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    existing = db.query(AttendanceMonthLock).filter(
        AttendanceMonthLock.month == data.month,
        AttendanceMonthLock.year == data.year,
    ).first()
    if existing:
        existing.status = "Locked"
        existing.reason = data.reason
        existing.locked_by = current_user.id
        existing.locked_at = datetime.now(timezone.utc)
        existing.unlocked_by = None
        existing.unlocked_at = None
        db.add(AuditLog(
            user_id=current_user.id,
            method="POST",
            endpoint="/attendance/locks",
            entity_type="attendance_month_lock",
            entity_id=existing.id,
            action="LOCK",
            description=f"Attendance locked for {data.month}/{data.year}",
        ))
        db.commit()
        db.refresh(existing)
        return existing
    lock = AttendanceMonthLock(**data.model_dump(), locked_by=current_user.id)
    db.add(lock)
    db.flush()
    db.add(AuditLog(
        user_id=current_user.id,
        method="POST",
        endpoint="/attendance/locks",
        entity_type="attendance_month_lock",
        entity_id=lock.id,
        action="LOCK",
        description=f"Attendance locked for {data.month}/{data.year}",
    ))
    db.commit()
    db.refresh(lock)
    return lock


@router.get("/locks", response_model=List[AttendanceMonthLockSchema])
def list_attendance_month_locks(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    query = db.query(AttendanceMonthLock)
    if month:
        query = query.filter(AttendanceMonthLock.month == month)
    if year:
        query = query.filter(AttendanceMonthLock.year == year)
    if status:
        query = query.filter(AttendanceMonthLock.status == status)
    return query.order_by(AttendanceMonthLock.year.desc(), AttendanceMonthLock.month.desc(), AttendanceMonthLock.id.desc()).limit(200).all()


@router.put("/locks/{lock_id}/unlock", response_model=AttendanceMonthLockSchema)
def unlock_attendance_month(
    lock_id: int,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    lock = db.query(AttendanceMonthLock).filter(AttendanceMonthLock.id == lock_id).first()
    if not lock:
        raise HTTPException(status_code=404, detail="Attendance lock not found")
    lock.status = "Unlocked"
    lock.reason = reason or lock.reason
    lock.unlocked_by = current_user.id
    lock.unlocked_at = datetime.now(timezone.utc)
    db.add(AuditLog(
        user_id=current_user.id,
        method="PUT",
        endpoint=f"/attendance/locks/{lock_id}/unlock",
        entity_type="attendance_month_lock",
        entity_id=lock.id,
        action="UNLOCK",
        description=f"Attendance unlocked for {lock.month}/{lock.year}",
    ))
    db.commit()
    db.refresh(lock)
    return lock


@router.get("/register", response_model=AttendanceRegisterResponse)
def attendance_register(
    work_date: date = Query(..., alias="date"),
    search: Optional[str] = Query(None),
    branch_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_view")),
):
    query = db.query(Employee).filter(Employee.deleted_at.is_(None))
    if branch_id:
        query = query.filter(Employee.branch_id == branch_id)
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    if search:
        term = f"%{search}%"
        query = query.filter(
            (Employee.employee_id.ilike(term))
            | (Employee.first_name.ilike(term))
            | (Employee.last_name.ilike(term))
            | (Employee.work_email.ilike(term))
        )
    employees = query.order_by(Employee.employee_id, Employee.first_name).limit(500).all()
    attendance_rows = db.query(Attendance).filter(
        Attendance.employee_id.in_([employee.id for employee in employees] or [0]),
        Attendance.attendance_date == work_date,
    ).all()
    by_employee = {row.employee_id: row for row in attendance_rows}
    items = [_attendance_register_row(employee, by_employee.get(employee.id), work_date) for employee in employees]
    summary = {
        "present": Decimal("0"),
        "absent": Decimal("0"),
        "half_day": Decimal("0"),
        "holiday": Decimal("0"),
        "weekly_off": Decimal("0"),
        "wfh": Decimal("0"),
        "overtime_hours": Decimal("0"),
    }
    for item in items:
        status = item["status"]
        if status == "Present":
            summary["present"] += Decimal("1")
        elif status == "Half-day":
            summary["half_day"] += Decimal("1")
            summary["present"] += Decimal("0.5")
        elif status == "Holiday":
            summary["holiday"] += Decimal("1")
        elif status == "Weekly Off":
            summary["weekly_off"] += Decimal("1")
        elif status == "WFH":
            summary["wfh"] += Decimal("1")
            summary["present"] += Decimal("1")
        else:
            summary["absent"] += Decimal("1")
        summary["overtime_hours"] += Decimal(str(item["ot_hours"] or 0))
    return {"items": items, "total": len(items), **summary}


@router.post("/bulk-entry", response_model=AttendanceBulkEntryResponse)
def save_bulk_attendance(
    data: AttendanceBulkEntryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    saved_items = []
    for entry in data.entries:
        if _locked_month(db, entry.date):
            raise HTTPException(status_code=423, detail=f"Attendance is locked for {entry.date.month}/{entry.date.year}")
        employee = db.query(Employee).filter(Employee.id == entry.employee_id, Employee.deleted_at.is_(None)).first()
        if not employee:
            raise HTTPException(status_code=404, detail=f"Employee {entry.employee_id} not found")
        attendance = db.query(Attendance).filter(
            Attendance.employee_id == entry.employee_id,
            Attendance.attendance_date == entry.date,
        ).first()
        if not attendance:
            attendance = Attendance(employee_id=entry.employee_id, attendance_date=entry.date, source="Manual")
            db.add(attendance)
            db.flush()
        status = _stored_attendance_status(entry.status)
        attendance.status = status
        attendance.source = "Manual"
        attendance.total_hours = Decimal(str(entry.hours_worked or 0))
        attendance.overtime_hours = Decimal(str(entry.ot_hours or 0))
        attendance.remarks = entry.remarks
        if status in {"Absent", "Holiday", "Weekend"}:
            attendance.check_in = None
            attendance.check_out = None
            if status in {"Absent", "Holiday", "Weekend"} and attendance.total_hours is None:
                attendance.total_hours = Decimal("0")
        elif attendance.total_hours and not attendance.check_in:
            attendance.check_in = datetime.combine(entry.date, time(hour=9))
            attendance.check_out = attendance.check_in + timedelta(hours=float(attendance.total_hours))
        attendance.computed_at = datetime.now(timezone.utc)
        db.add(AuditLog(
            user_id=current_user.id,
            method="POST",
            endpoint="/attendance/bulk-entry",
            entity_type="attendance",
            entity_id=attendance.id,
            action="UPSERT",
            description=f"Manual attendance {status} saved for employee {employee.employee_id} on {entry.date}",
        ))
        saved_items.append(_attendance_register_row(employee, attendance, entry.date))
    db.commit()
    return {"saved": len(saved_items), "items": saved_items}


@router.get("/today")
def get_today_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = _employee_or_400(current_user)
    today = _business_date()
    day_start, day_end = _utc_day_bounds(today)
    record = compute_attendance_summary(employee.id, today, db)
    punches = (
        db.query(AttendancePunch)
        .filter(
            AttendancePunch.employee_id == employee.id,
            AttendancePunch.punch_time >= day_start,
            AttendancePunch.punch_time <= day_end,
        )
        .order_by(AttendancePunch.punch_time.asc())
        .all()
    )
    attendance_payload = _attendance_payload(record)
    payload = {
        "attendance": attendance_payload,
        "punches": [_punch_payload(punch) for punch in punches],
    }
    if attendance_payload:
        payload.update(attendance_payload)
    return payload


# ── Employee Attendance History ───────────────────────────────────────────────

@router.get("/my")
def my_attendance(
    from_date: date = Query(...),
    to_date: date = Query(...),
    page: int | None = Query(None, ge=1),
    page_size: int | None = Query(None, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = _employee_or_400(current_user)
    query = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
        Attendance.attendance_date >= from_date,
        Attendance.attendance_date <= to_date,
    ).order_by(Attendance.attendance_date.desc())
    if page is None and page_size is None:
        return query.all()
    effective_page = page or 1
    effective_page_size = page_size or 50
    total = query.count()
    items = query.offset((effective_page - 1) * effective_page_size).limit(effective_page_size).all()
    return {"items": items, "total": total, "page": effective_page, "page_size": effective_page_size}


@router.get("/employee/{employee_id}", response_model=List[AttendanceSchema])
def employee_attendance(
    employee_id: int,
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_view")),
):
    return crud_attendance.get_employee_attendance(db, employee_id, from_date, to_date)


@router.get("/summary/monthly")
def monthly_summary(
    employee_id: Optional[int] = Query(None),
    month: int = Query(...),
    year: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    emp_id = employee_id
    if not emp_id:
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="No employee profile")
        emp_id = current_user.employee.id
    return crud_attendance.get_monthly_summary(db, emp_id, month, year)


@router.post("/compute/{employee_id}/{work_date}", response_model=AttendanceSchema)
def compute_attendance_day(
    employee_id: int,
    work_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    return crud_attendance.compute_day(db, employee_id, work_date)


# ── Regularization ───────────────────────────────────────────────────────────

@router.post("/regularize", response_model=RegularizationSchema, status_code=201)
def request_regularization(
    data: RegularizationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = _employee_or_400(current_user)
    requested_check_in = data.requested_check_in or data.expected_check_in
    requested_check_out = data.requested_check_out or data.expected_check_out
    attendance_id = data.attendance_id
    if attendance_id:
        attendance = db.query(Attendance).filter(
            Attendance.id == attendance_id,
            Attendance.employee_id == employee.id,
        ).first()
        if not attendance:
            raise HTTPException(status_code=404, detail="Attendance record not found")
    else:
        if not data.date:
            raise HTTPException(status_code=422, detail="date is required when attendance_id is not provided")
        attendance = db.query(Attendance).filter(
            Attendance.employee_id == employee.id,
            Attendance.attendance_date == data.date,
        ).first()
        if not attendance:
            attendance = Attendance(employee_id=employee.id, attendance_date=data.date, status="Absent")
            db.add(attendance)
            db.flush()
        attendance_id = attendance.id
    attendance.is_regularized = True
    reg = AttendanceRegularization(
        attendance_id=attendance_id,
        employee_id=employee.id,
        requested_check_in=requested_check_in,
        requested_check_out=requested_check_out,
        reason=data.reason,
    )
    db.add(reg)
    manager = db.query(Employee).filter(Employee.id == employee.reporting_manager_id, Employee.deleted_at.is_(None)).first() if employee.reporting_manager_id else None
    if manager and manager.user_id:
        db.flush()
        create_notification(db, NotificationCreate(
            user_id=manager.user_id,
            title="Attendance regularization requested",
            message=f"{employee.first_name} {employee.last_name} requested attendance correction for {attendance.attendance_date}.",
            module="HRMS",
            event_type="attendance_regularization_requested",
            related_entity_type="attendance_regularization",
            related_entity_id=reg.id,
            action_url="/hrms/attendance",
            priority="normal",
        ))
    else:
        db.commit()
    db.commit()
    db.refresh(reg)
    return reg


@router.get("/regularize/pending", response_model=List[RegularizationSchema])
def pending_regularizations(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    return db.query(AttendanceRegularization).filter(
        AttendanceRegularization.status == "Pending"
    ).all()


@router.put("/regularize/{reg_id}/approve")
def approve_regularization(
    reg_id: int,
    data: RegularizationApproval,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("attendance_manage")),
):
    from datetime import datetime, timezone
    reg = db.query(AttendanceRegularization).filter(AttendanceRegularization.id == reg_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Regularization not found")

    reg.status = data.status
    reg.reviewed_by = current_user.id
    reg.reviewed_at = datetime.now(timezone.utc)
    reg.review_remarks = data.review_remarks

    if data.status == "Approved":
        attendance = crud_attendance.get(db, reg.attendance_id)
        if attendance:
            if reg.requested_check_in:
                attendance.check_in = reg.requested_check_in
            if reg.requested_check_out:
                attendance.check_out = reg.requested_check_out
            attendance.is_regularized = True

    db.commit()
    return {"message": f"Regularization {data.status}"}


@router.get("/team")
def team_attendance(
    from_date: Optional[date] = Query(None),
    to_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from_date = from_date or date.today()
    end_date = to_date or from_date
    if end_date < from_date:
        raise HTTPException(status_code=400, detail="to_date cannot be before from_date")

    query = db.query(Employee).filter(Employee.deleted_at.is_(None))
    if _can_view_all_attendance(current_user):
        employees = query.order_by(Employee.first_name, Employee.last_name).all()
    else:
        employee = _employee_or_400(current_user)
        employees = query.filter(Employee.reporting_manager_id == employee.id).order_by(Employee.first_name, Employee.last_name).all()

    employee_ids = [item.id for item in employees]
    attendance_rows = db.query(Attendance).filter(
        Attendance.employee_id.in_(employee_ids or [0]),
        Attendance.attendance_date >= from_date,
        Attendance.attendance_date <= end_date,
    ).all()
    by_key = {(item.employee_id, item.attendance_date): item for item in attendance_rows}
    items = []
    cursor = from_date
    while cursor <= end_date:
        for employee in employees:
            attendance = by_key.get((employee.id, cursor))
            items.append({
                "employee_id": employee.id,
                "employee_code": employee.employee_id,
                "employee_name": f"{employee.first_name} {employee.last_name}",
                "attendance_date": cursor,
                "status": attendance.status if attendance else "Absent",
                "check_in": attendance.check_in if attendance else None,
                "check_out": attendance.check_out if attendance else None,
                "total_hours": attendance.total_hours if attendance else None,
                "is_late": attendance.is_late if attendance else False,
                "is_early_exit": attendance.is_early_exit if attendance else False,
            })
        cursor += timedelta(days=1)
    return {"items": items, "from_date": from_date, "to_date": end_date, "total": len(items)}


@router.get("/{employee_id}", response_model=List[AttendanceSchema])
def employee_attendance_by_id(
    employee_id: int,
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_view_employee_attendance(db, current_user, employee_id):
        raise HTTPException(status_code=403, detail="Not authorized to view this employee's attendance")
    return crud_attendance.get_employee_attendance(db, employee_id, from_date, to_date)
