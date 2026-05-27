from __future__ import annotations

import json
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.attendance import Attendance, Holiday
from app.models.employee import Employee
from app.models.user import User
from app.schemas.attendance import HolidayCalendarCreate, HolidayCalendarSchema, HolidayCalendarUpdate

router = APIRouter(prefix="/holidays", tags=["Holidays"])


def _user_permissions(user: User) -> set[str]:
    return {permission.name for permission in (user.role.permissions if user.role else [])}


def _ensure_hr_admin(user: User) -> None:
    if user.is_superuser or "hr_admin" in _user_permissions(user):
        return
    raise HTTPException(status_code=403, detail="Only HR admins can manage holidays")


def _parse_branches(value: str | None) -> list[int]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [int(item) for item in parsed]
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def _encode_branches(branches: Optional[list[int]]) -> str:
    return json.dumps(branches or [])


def _holiday_payload(holiday: Holiday) -> HolidayCalendarSchema:
    return HolidayCalendarSchema(
        id=holiday.id,
        name=holiday.name,
        holiday_date=holiday.holiday_date,
        holiday_type=holiday.holiday_type,
        description=holiday.description,
        applicable_branches=_parse_branches(holiday.applicable_branches),
        is_active=holiday.is_active,
        created_at=holiday.created_at,
    )


def _applies_to_branch(holiday: Holiday, branch_id: int | None) -> bool:
    branches = _parse_branches(holiday.applicable_branches)
    return not branches or branch_id in branches


def _mark_absent_attendance_as_holiday(db: Session, holiday: Holiday) -> None:
    branches = _parse_branches(holiday.applicable_branches)
    employee_query = db.query(Employee.id).filter(Employee.deleted_at.is_(None))
    if branches:
        employee_query = employee_query.filter(Employee.branch_id.in_(branches))
    employee_ids = [row[0] for row in employee_query.all()]
    if not employee_ids:
        return
    (
        db.query(Attendance)
        .filter(
            Attendance.attendance_date == holiday.holiday_date,
            Attendance.status == "Absent",
            Attendance.employee_id.in_(employee_ids),
        )
        .update({Attendance.status: "Holiday"}, synchronize_session=False)
    )


def _create_holiday(db: Session, data: HolidayCalendarCreate) -> Holiday:
    holiday = Holiday(
        name=data.name,
        holiday_date=data.holiday_date,
        holiday_type=data.holiday_type,
        description=data.description,
        applicable_branches=_encode_branches(data.applicable_branches),
        is_active=True,
    )
    db.add(holiday)
    db.flush()
    _mark_absent_attendance_as_holiday(db, holiday)
    return holiday


@router.get("", response_model=List[HolidayCalendarSchema])
def list_holidays(
    year: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    holiday_type: Optional[str] = Query(None, pattern="^(National|Regional|Optional)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    year = year or date.today().year
    query = db.query(Holiday).filter(Holiday.is_active == True, extract("year", Holiday.holiday_date) == year)
    if holiday_type:
        query = query.filter(Holiday.holiday_type == holiday_type)
    holidays = query.order_by(Holiday.holiday_date.asc()).all()
    if branch_id is not None:
        holidays = [holiday for holiday in holidays if _applies_to_branch(holiday, branch_id)]
    return [_holiday_payload(holiday) for holiday in holidays]


@router.get("/upcoming", response_model=List[HolidayCalendarSchema])
def upcoming_holidays(
    branch_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(Holiday)
        .filter(Holiday.is_active == True, Holiday.holiday_date >= date.today())
        .order_by(Holiday.holiday_date.asc())
    )
    holidays = []
    for holiday in query.all():
        if branch_id is None or _applies_to_branch(holiday, branch_id):
            holidays.append(holiday)
        if len(holidays) == 5:
            break
    return [_holiday_payload(holiday) for holiday in holidays]


@router.post("", response_model=HolidayCalendarSchema, status_code=201)
def create_holiday(
    data: HolidayCalendarCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_hr_admin(current_user)
    holiday = _create_holiday(db, data)
    db.commit()
    db.refresh(holiday)
    return _holiday_payload(holiday)


@router.post("/bulk", response_model=List[HolidayCalendarSchema], status_code=201)
def bulk_create_holidays(
    items: list[HolidayCalendarCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_hr_admin(current_user)
    holidays = [_create_holiday(db, item) for item in items]
    db.commit()
    for holiday in holidays:
        db.refresh(holiday)
    return [_holiday_payload(holiday) for holiday in holidays]


@router.put("/{holiday_id}", response_model=HolidayCalendarSchema)
def update_holiday(
    holiday_id: int,
    data: HolidayCalendarUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_hr_admin(current_user)
    holiday = db.query(Holiday).filter(Holiday.id == holiday_id, Holiday.is_active == True).first()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "applicable_branches":
            holiday.applicable_branches = _encode_branches(value)
        else:
            setattr(holiday, key, value)
    _mark_absent_attendance_as_holiday(db, holiday)
    db.commit()
    db.refresh(holiday)
    return _holiday_payload(holiday)


@router.delete("/{holiday_id}")
def delete_holiday(
    holiday_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_hr_admin(current_user)
    holiday = db.query(Holiday).filter(Holiday.id == holiday_id, Holiday.is_active == True).first()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    holiday.is_active = False
    db.commit()
    return {"message": "Holiday deleted"}
