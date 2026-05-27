from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from app.core.config import settings
from app.crud.base import CRUDBase
from app.models.attendance import Attendance, AttendancePunch, AttendanceRegularization, Holiday, Shift, ShiftRoster, ShiftRosterAssignment, ShiftWeeklyOff, OvertimeRequest


def _attendance_timezone():
    try:
        return ZoneInfo(settings.CELERY_TIMEZONE)
    except ZoneInfoNotFoundError:
        return timezone.utc


def _utc_day_bounds(work_date: date) -> tuple[datetime, datetime]:
    tz = _attendance_timezone()
    start = datetime.combine(work_date, time.min, tzinfo=tz).astimezone(timezone.utc)
    end = datetime.combine(work_date, time.max, tzinfo=tz).astimezone(timezone.utc)
    return start, end


class CRUDAttendance(CRUDBase):
    def __init__(self):
        super().__init__(Attendance)

    def get_shift_for_day(self, db: Session, employee_id: int, work_date: date) -> Optional[Shift]:
        from app.models.employee import Employee

        published_roster = (
            db.query(ShiftRoster)
            .filter(
                ShiftRoster.employee_id == employee_id,
                ShiftRoster.roster_date == work_date,
                ShiftRoster.status == "published",
            )
            .first()
        )
        if published_roster:
            return published_roster.shift

        roster = (
            db.query(ShiftRosterAssignment)
            .filter(
                ShiftRosterAssignment.employee_id == employee_id,
                ShiftRosterAssignment.work_date == work_date,
                ShiftRosterAssignment.status == "Published",
            )
            .first()
        )
        if roster:
            return roster.shift
        employee = db.query(Employee).filter(Employee.id == employee_id, Employee.deleted_at.is_(None)).first()
        if employee and employee.shift_id:
            return db.query(Shift).filter(Shift.id == employee.shift_id).first()
        return None

    def is_weekly_off(self, db: Session, shift_id: int, work_date: date) -> bool:
        week_of_month = ((work_date.day - 1) // 7) + 1
        return (
            db.query(ShiftWeeklyOff)
            .filter(
                ShiftWeeklyOff.shift_id == shift_id,
                ShiftWeeklyOff.weekday == work_date.weekday(),
                ShiftWeeklyOff.is_active == True,
                ShiftWeeklyOff.week_pattern.in_(["all", str(week_of_month)]),
            )
            .count()
            > 0
        )

    def compute_day(self, db: Session, employee_id: int, work_date: date) -> Attendance:
        record = (
            db.query(Attendance)
            .filter(Attendance.employee_id == employee_id, Attendance.attendance_date == work_date)
            .first()
        )
        if not record:
            record = Attendance(employee_id=employee_id, attendance_date=work_date, status="Absent")
            db.add(record)
            db.flush()
        self._ensure_defaults(record)

        shift = self.get_shift_for_day(db, employee_id, work_date)
        record.shift_id = shift.id if shift else None

        on_leave = self._is_on_leave(db, employee_id, work_date)
        if on_leave:
            record.status = "On Leave"
            record.computed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(record)
            return record

        if crud_holiday.is_holiday(db, work_date):
            record.status = "Holiday"
            record.computed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(record)
            return record

        if shift and self.is_weekly_off(db, shift.id, work_date):
            record.status = "Weekend"
            record.computed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(record)
            return record

        record.late_minutes = 0
        record.early_exit_minutes = 0
        record.short_minutes = 0
        record.is_late = False
        record.is_early_exit = False
        record.is_short_hours = False
        record.overtime_hours = Decimal("0")

        day_start, day_end = _utc_day_bounds(work_date)
        punches = (
            db.query(AttendancePunch)
            .filter(
                AttendancePunch.employee_id == employee_id,
                AttendancePunch.punch_time >= day_start,
                AttendancePunch.punch_time <= day_end,
            )
            .order_by(AttendancePunch.punch_time.asc())
            .all()
        )
        in_punches = [item for item in punches if item.punch_type == "IN"]
        out_punches = [item for item in punches if item.punch_type == "OUT"]
        if in_punches:
            record.check_in = in_punches[0].punch_time
            record.check_in_location = in_punches[0].location_text
            record.check_in_ip = in_punches[0].ip_address
            record.source = in_punches[0].source or record.source or "Web"
        if out_punches:
            record.check_out = out_punches[-1].punch_time
            record.check_out_location = out_punches[-1].location_text
            record.check_out_ip = out_punches[-1].ip_address
            record.source = out_punches[-1].source or record.source or "Web"

        if not record.check_in:
            record.status = "Absent"
            record.total_hours = Decimal("0")
            record.computed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(record)
            return record

        check_in = record.check_in.replace(tzinfo=timezone.utc) if record.check_in and record.check_in.tzinfo is None else record.check_in
        check_out = record.check_out.replace(tzinfo=timezone.utc) if record.check_out and record.check_out.tzinfo is None else record.check_out

        if check_out:
            total_hours = Decimal(str(round((check_out - check_in).total_seconds() / 3600, 2)))
            record.total_hours = total_hours
        else:
            total_hours = record.total_hours or Decimal("0")

        if shift:
            tz = _attendance_timezone()
            start_dt = datetime.combine(work_date, shift.start_time, tzinfo=tz).astimezone(timezone.utc)
            end_date = work_date + timedelta(days=1) if shift.is_night_shift or shift.end_time <= shift.start_time else work_date
            end_dt = datetime.combine(end_date, shift.end_time, tzinfo=tz).astimezone(timezone.utc)
            late_threshold = start_dt + timedelta(minutes=shift.grace_minutes or 0)
            early_threshold = end_dt - timedelta(minutes=shift.grace_minutes or 0)

            if check_in > late_threshold:
                record.late_minutes = int((check_in - start_dt).total_seconds() // 60)
                record.is_late = True
            if check_out and check_out < early_threshold:
                record.early_exit_minutes = int((end_dt - check_out).total_seconds() // 60)
                record.is_early_exit = True
            required_minutes = int(Decimal(shift.working_hours or 0) * 60)
            worked_minutes = int((total_hours or Decimal("0")) * 60)
            half_day_minutes = required_minutes // 2
            if record.check_out and worked_minutes < required_minutes:
                record.short_minutes = max(0, required_minutes - worked_minutes)
                record.is_short_hours = True
            if total_hours and total_hours > Decimal(shift.working_hours or 0):
                record.overtime_hours = total_hours - Decimal(shift.working_hours or 0)
            if record.check_out and worked_minutes < half_day_minutes:
                record.status = "Half-day"
            else:
                record.status = "Present"
        else:
            record.status = "Present"

        record.computed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(record)
        return record

    def _is_on_leave(self, db: Session, employee_id: int, work_date: date) -> bool:
        from app.models.leave import LeaveRequest

        return (
            db.query(LeaveRequest)
            .filter(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.status == "Approved",
                LeaveRequest.deleted_at.is_(None),
                LeaveRequest.from_date <= work_date,
                LeaveRequest.to_date >= work_date,
            )
            .first()
            is not None
        )

    def _ensure_defaults(self, record: Attendance) -> None:
        if record.source is None:
            record.source = "Web"
        if record.is_regularized is None:
            record.is_regularized = False
        if record.overtime_hours is None:
            record.overtime_hours = Decimal("0")
        if record.late_minutes is None:
            record.late_minutes = 0
        if record.early_exit_minutes is None:
            record.early_exit_minutes = 0
        if record.short_minutes is None:
            record.short_minutes = 0
        if record.is_late is None:
            record.is_late = False
        if record.is_early_exit is None:
            record.is_early_exit = False
        if record.is_short_hours is None:
            record.is_short_hours = False

    def get_today(self, db: Session, employee_id: int) -> Optional[Attendance]:
        today = date.today()
        return (
            db.query(Attendance)
            .filter(and_(Attendance.employee_id == employee_id, Attendance.attendance_date == today))
            .first()
        )

    def check_in(self, db: Session, employee_id: int, location: str = None, ip: str = None, source: str = "Web") -> Attendance:
        today = date.today()
        existing = self.get_today(db, employee_id)
        now = datetime.now(timezone.utc)

        if existing:
            self._ensure_defaults(existing)
            if not existing.check_in:
                existing.check_in = now
                existing.check_in_location = location
                existing.check_in_ip = ip
                existing.source = source or existing.source or "Web"
                existing.status = "Present"
                db.commit()
                db.refresh(existing)
            return existing

        record = Attendance(
            employee_id=employee_id,
            attendance_date=today,
            check_in=now,
            check_in_location=location,
            check_in_ip=ip,
            source=source,
            status="Present",
        )
        db.add(record)
        db.commit()
        self.compute_day(db, employee_id, today)
        db.refresh(record)
        self._ensure_defaults(record)
        return record

    def check_out(self, db: Session, employee_id: int, location: str = None, ip: str = None) -> Optional[Attendance]:
        record = self.get_today(db, employee_id)
        if not record or not record.check_in:
            return None

        now = datetime.now(timezone.utc)
        self._ensure_defaults(record)
        record.check_out = now
        record.check_out_location = location
        record.check_out_ip = ip

        db.commit()
        record = self.compute_day(db, employee_id, record.attendance_date)
        db.refresh(record)
        return record

    def get_employee_attendance(
        self, db: Session, employee_id: int, from_date: date, to_date: date
    ) -> List[Attendance]:
        return (
            db.query(Attendance)
            .filter(
                and_(
                    Attendance.employee_id == employee_id,
                    Attendance.attendance_date >= from_date,
                    Attendance.attendance_date <= to_date,
                )
            )
            .order_by(Attendance.attendance_date.desc())
            .all()
        )

    def get_monthly_summary(self, db: Session, employee_id: int, month: int, year: int) -> dict:
        from_date = date(year, month, 1)
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        to_date = date(year, month, last_day)

        records = self.get_employee_attendance(db, employee_id, from_date, to_date)
        status_counts = {}
        total_hours = Decimal("0")
        overtime_hours = Decimal("0")

        for r in records:
            status_counts[r.status] = status_counts.get(r.status, 0) + 1
            if r.total_hours:
                total_hours += r.total_hours
            if r.overtime_hours:
                overtime_hours += r.overtime_hours

        return {
            "employee_id": employee_id,
            "month": month,
            "year": year,
            "total_records": len(records),
            "present": status_counts.get("Present", 0),
            "absent": status_counts.get("Absent", 0),
            "half_day": status_counts.get("Half-day", 0),
            "wfh": status_counts.get("WFH", 0),
            "total_hours": float(total_hours),
            "overtime_hours": float(overtime_hours),
            "status_breakdown": status_counts,
        }

    def get_team_attendance(self, db: Session, manager_employee_id: int, attendance_date: date) -> List[dict]:
        from app.models.employee import Employee
        team = db.query(Employee).filter(
            Employee.reporting_manager_id == manager_employee_id,
            Employee.deleted_at.is_(None),
        ).all()
        result = []
        for emp in team:
            att = (
                db.query(Attendance)
                .filter(and_(Attendance.employee_id == emp.id, Attendance.attendance_date == attendance_date))
                .first()
            )
            result.append({
                "employee_id": emp.id,
                "employee_name": f"{emp.first_name} {emp.last_name}",
                "status": att.status if att else "Absent",
                "check_in": att.check_in if att else None,
                "check_out": att.check_out if att else None,
            })
        return result


class CRUDHoliday(CRUDBase):
    def __init__(self):
        super().__init__(Holiday)

    def get_upcoming(self, db: Session, limit: int = 10) -> List[Holiday]:
        today = date.today()
        return (
            db.query(Holiday)
            .filter(and_(Holiday.holiday_date >= today, Holiday.is_active == True))
            .order_by(Holiday.holiday_date)
            .limit(limit)
            .all()
        )

    def is_holiday(self, db: Session, check_date: date) -> bool:
        return db.query(Holiday).filter(
            and_(Holiday.holiday_date == check_date, Holiday.is_active == True)
        ).count() > 0


crud_attendance = CRUDAttendance()
crud_holiday = CRUDHoliday()
