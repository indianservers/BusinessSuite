from datetime import date, datetime, timedelta, timezone
from io import StringIO
from typing import List, Optional
import csv
import json
import time
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import Session, joinedload
from app.core.deps import get_db, get_current_user, RequirePermission
from app.core.hr_audit import record_employee_field_changes
from app.core.masking import mask_employee_detail, mask_employee_list_item
from app.core.security import get_password_hash
from app.crud.crud_employee import crud_employee
from app.models.audit import AuditLog
from app.models.user import Role, User
from app.models.employee import Employee, EmployeeDocument, EmployeeEducation, EmployeeExperience, EmployeeChangeRequest
from app.services.notifications import create_notification
from app.schemas.notification import NotificationCreate
from app.schemas.employee import (
    EmployeeCreate, EmployeeUpdate, EmployeeSchema, EmployeeListSchema,
    EmployeeEducationCreate, EmployeeEducationSchema,
    EmployeeExperienceCreate, EmployeeExperienceSchema,
    EmployeeSkillCreate, EmployeeSkillSchema,
    EmployeeDocumentCreate, EmployeeDocumentSchema, EmployeeDocumentVerificationUpdate,
    EmployeeLifecycleEventCreate, EmployeeLifecycleEventSchema,
    EmployeeChangeRequestCreate, EmployeeChangeRequestReview, EmployeeChangeRequestSchema,
)
from app.schemas.common import PaginatedResponse
import os, shutil
from app.core.config import settings

router = APIRouter(prefix="/employees", tags=["Employees"])
_DIRECTORY_SEARCH_BUCKETS: dict[int, list[float]] = {}


class EmployeeUserLinkUpdate(BaseModel):
    user_id: Optional[int] = None


class EmployeeUserAccountCreate(BaseModel):
    email: str
    password: str
    role_id: Optional[int] = None


class EmployeeUserOption(BaseModel):
    id: int
    email: str
    role: Optional[str] = None
    employee_id: Optional[int] = None
    employee_code: Optional[str] = None
    employee_name: Optional[str] = None


class EmployeeDirectoryItem(BaseModel):
    id: int
    employee_id: str
    full_name: str
    preferred_display_name: Optional[str] = None
    email: Optional[str] = None
    work_email: Optional[str] = None
    phone_number: Optional[str] = None
    office_extension: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    branch: Optional[str] = None
    reporting_manager: Optional[str] = None
    work_location: Optional[str] = None
    desk_code: Optional[str] = None
    timezone: Optional[str] = None
    skills_tags: Optional[str] = None
    profile_completeness: Optional[int] = None
    profile_photo_url: Optional[str] = None
    is_direct_report: bool = False
    contact_masked: bool = False


class EmployeeProfileCard(BaseModel):
    id: int
    employee_id: str
    full_name: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    branch: Optional[str] = None
    reporting_manager: Optional[str] = None
    work_location: Optional[str] = None
    desk_code: Optional[str] = None
    office_extension: Optional[str] = None
    timezone: Optional[str] = None
    skills: List[str] = []
    profile_photo_url: Optional[str] = None
    contact_masked: bool = False


class DirectoryCorrectionReport(BaseModel):
    employee_id: int
    field_name: str
    message: str


class DirectorySuggestion(BaseModel):
    id: int
    label: str
    subtitle: Optional[str] = None
    type: str = "employee"


class DirectoryEventItem(BaseModel):
    id: int
    employee_id: str
    full_name: str
    department: Optional[str] = None
    designation: Optional[str] = None
    event_date: date
    profile_photo_url: Optional[str] = None


def _role_key(user: User) -> str:
    if user.is_superuser:
        return "admin"
    name = (user.role.name if user.role else "").lower().replace(" ", "_")
    if name in {"admin", "super_admin"}:
        return "admin"
    if name in {"hr", "hr_admin", "hr_manager"}:
        return "hr"
    if name in {"ceo", "founder", "director", "executive"}:
        return "ceo"
    if name in {"manager", "team_lead", "department_head"}:
        return "manager"
    return "employee"


def _org_id(user: User) -> int | None:
    return getattr(user, "organization_id", None) or getattr(user, "company_id", None)


def _has_permission(user: User, permission: str) -> bool:
    if user.is_superuser:
        return True
    return permission in {p.name for p in (user.role.permissions if user.role else [])}


def _can_manage_directory(user: User) -> bool:
    return _role_key(user) in {"admin", "hr"}


def _is_team_related(viewer: User, employee: Employee) -> bool:
    if not viewer.employee:
        return False
    viewer_emp = viewer.employee
    return (
        employee.id == viewer_emp.id
        or employee.reporting_manager_id == viewer_emp.id
        or viewer_emp.reporting_manager_id is not None
        and employee.reporting_manager_id == viewer_emp.reporting_manager_id
    )


def _can_view_contact(user: User, employee: Employee) -> bool:
    visibility = employee.directory_visibility or "public"
    if _can_manage_directory(user) or _role_key(user) == "ceo":
        return visibility != "hidden"
    if visibility == "public":
        return True
    if visibility == "team":
        return _is_team_related(user, employee)
    return False


def _directory_name(employee: Employee) -> str:
    return employee.preferred_display_name or f"{employee.first_name} {employee.last_name}"


def _directory_query(db: Session):
    return (
        db.query(Employee)
        .options(
            joinedload(Employee.department),
            joinedload(Employee.designation),
            joinedload(Employee.branch),
            joinedload(Employee.reporting_manager),
        )
        .filter(
            Employee.deleted_at.is_(None),
            Employee.status.in_(["Active", "Probation", "On Leave"]),
            or_(Employee.directory_visibility.is_(None), Employee.directory_visibility != "hidden"),
        )
    )


def _apply_directory_filters(
    query,
    search: Optional[str] = None,
    department_id: Optional[int] = None,
    designation_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    location_id: Optional[int] = None,
    skills: Optional[str] = None,
    work_location: Optional[str] = None,
    employment_type: Optional[str] = None,
    worker_type: Optional[str] = None,
    timezone_filter: Optional[str] = None,
    has_photo: Optional[bool] = None,
    profile_completeness_min: Optional[int] = None,
    joined_after: Optional[date] = None,
    joined_before: Optional[date] = None,
):
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    if designation_id:
        query = query.filter(Employee.designation_id == designation_id)
    if branch_id:
        query = query.filter(Employee.branch_id == branch_id)
    if location_id:
        query = query.filter(Employee.location_id == location_id)
    if skills:
        query = query.filter(Employee.skills_tags.ilike(f"%{skills.strip()}%"))
    if work_location:
        query = query.filter(Employee.work_location == work_location)
    if employment_type:
        query = query.filter(Employee.employment_type == employment_type)
    if worker_type:
        query = query.filter(Employee.worker_type == worker_type)
    if timezone_filter:
        query = query.filter(Employee.timezone == timezone_filter)
    if has_photo is True:
        query = query.filter(Employee.profile_photo_url.isnot(None))
    elif has_photo is False:
        query = query.filter(Employee.profile_photo_url.is_(None))
    if profile_completeness_min is not None:
        query = query.filter(Employee.profile_completeness >= profile_completeness_min)
    if joined_after:
        query = query.filter(Employee.date_of_joining >= joined_after)
    if joined_before:
        query = query.filter(Employee.date_of_joining <= joined_before)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            (Employee.first_name.ilike(pattern))
            | (Employee.last_name.ilike(pattern))
            | (Employee.employee_id.ilike(pattern))
            | (Employee.work_email.ilike(pattern))
            | (Employee.personal_email.ilike(pattern))
            | (Employee.preferred_display_name.ilike(pattern))
            | (Employee.skills_tags.ilike(pattern))
        )
    return query


def _mask(value: Optional[str], visible: bool) -> Optional[str]:
    if visible:
        return value
    return "Hidden by privacy setting" if value else None


def _to_directory_item(employee: Employee, current_user: User) -> EmployeeDirectoryItem:
    can_contact = _can_view_contact(current_user, employee)
    return EmployeeDirectoryItem(
        id=employee.id,
        employee_id=employee.employee_id,
        full_name=_directory_name(employee),
        preferred_display_name=employee.preferred_display_name,
        email=_mask(employee.work_email or employee.personal_email, can_contact),
        work_email=_mask(employee.work_email, can_contact),
        phone_number=_mask(employee.phone_number, can_contact),
        office_extension=_mask(employee.office_extension, can_contact),
        department=employee.department.name if employee.department else None,
        designation=employee.designation.name if employee.designation else None,
        branch=employee.branch.name if employee.branch else None,
        reporting_manager=(
            f"{employee.reporting_manager.first_name} {employee.reporting_manager.last_name}"
            if employee.reporting_manager
            else None
        ),
        work_location=employee.work_location,
        desk_code=employee.desk_code,
        timezone=employee.timezone,
        skills_tags=employee.skills_tags,
        profile_completeness=employee.profile_completeness,
        profile_photo_url=employee.profile_photo_url,
        is_direct_report=bool(current_user.employee and employee.reporting_manager_id == current_user.employee.id),
        contact_masked=not can_contact,
    )


PROFILE_CHANGE_FIELDS = {
    "present_address",
    "permanent_address",
    "present_city",
    "present_state",
    "present_pincode",
    "permanent_city",
    "permanent_state",
    "permanent_pincode",
    "phone_number",
    "alternate_phone",
    "personal_email",
    "emergency_contact_name",
    "emergency_contact_number",
    "emergency_contact_relation",
    "bank_name",
    "bank_branch",
    "account_number",
    "account_type",
    "ifsc_code",
    "marital_status",
    "family_information",
    "health_information",
    "pan_number",
    "aadhaar_number",
}

SENSITIVE_PROFILE_FIELDS = {"bank_name", "bank_branch", "account_number", "account_type", "ifsc_code", "pan_number", "aadhaar_number"}


def _employee_current_values(employee: Employee | None, changes: dict) -> dict:
    if not employee:
        return {}
    values = {}
    for field in changes.keys():
        if hasattr(employee, field):
            values[field] = getattr(employee, field)
        elif field in {"education_details", "experience_details", "document_details", "nominee_details"}:
            values[field] = None
    return values


def _serialize_change_request(item: EmployeeChangeRequest, employee: Employee | None = None) -> dict:
    changes = item.field_changes_json or {}
    old_values = item.old_value_json or _employee_current_values(employee, changes)
    return {
        "id": item.id,
        "organization_id": item.organization_id,
        "employee_id": item.employee_id,
        "request_type": item.request_type,
        "field_name": item.field_name,
        "effective_date": item.effective_date,
        "field_changes_json": changes,
        "old_value_json": old_values,
        "new_value_json": item.new_value_json or changes,
        "document_path": item.document_path,
        "reason": item.reason,
        "status": item.status,
        "requested_by": item.requested_by,
        "reviewed_by": item.reviewed_by,
        "reviewed_at": item.reviewed_at,
        "review_remarks": item.review_remarks,
        "created_at": item.created_at,
        "employee_name": f"{employee.first_name} {employee.last_name}" if employee else None,
        "employee_code": employee.employee_id if employee else None,
        "current_values_json": old_values,
    }


def _apply_profile_change(db: Session, employee: Employee, changes: dict) -> None:
    for field, value in (changes or {}).items():
        if field in PROFILE_CHANGE_FIELDS and hasattr(employee, field):
            setattr(employee, field, value)
        elif field == "education_details":
            rows = value if isinstance(value, list) else [value]
            for row in rows:
                if isinstance(row, dict) and row.get("degree"):
                    db.add(EmployeeEducation(employee_id=employee.id, **{key: row.get(key) for key in [
                        "degree", "specialization", "institution", "board_university", "pass_year", "percentage_cgpa", "document_url",
                    ] if key in row}))
        elif field == "experience_details":
            rows = value if isinstance(value, list) else [value]
            for row in rows:
                if isinstance(row, dict) and row.get("company_name"):
                    db.add(EmployeeExperience(employee_id=employee.id, **{key: row.get(key) for key in [
                        "company_name", "designation", "from_date", "to_date", "is_current", "responsibilities", "relieving_letter_url",
                    ] if key in row}))
        elif field == "document_details":
            rows = value if isinstance(value, list) else [value]
            for row in rows:
                if isinstance(row, dict) and row.get("document_type"):
                    db.add(EmployeeDocument(employee_id=employee.id, **{key: row.get(key) for key in [
                        "document_type", "document_name", "document_number", "file_url", "expiry_date",
                    ] if key in row}))


def _rate_limit_directory_search(current_user: User) -> None:
    now = time.time()
    bucket = [stamp for stamp in _DIRECTORY_SEARCH_BUCKETS.get(current_user.id, []) if now - stamp < 60]
    if len(bucket) >= 120:
        raise HTTPException(status_code=429, detail="Too many directory searches. Please wait a minute.")
    bucket.append(now)
    _DIRECTORY_SEARCH_BUCKETS[current_user.id] = bucket


def _parse_date(value: Optional[str], row_number: int, field_name: str):
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"{field_name} must be YYYY-MM-DD on row {row_number}")


@router.get("/directory", response_model=PaginatedResponse[EmployeeDirectoryItem])
def employee_directory(
    search: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    designation_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    location_id: Optional[int] = Query(None),
    skills: Optional[str] = Query(None),
    work_location: Optional[str] = Query(None),
    employment_type: Optional[str] = Query(None),
    worker_type: Optional[str] = Query(None),
    timezone_filter: Optional[str] = Query(None, alias="timezone"),
    has_photo: Optional[bool] = Query(None),
    profile_completeness_min: Optional[int] = Query(None, ge=0, le=100),
    joined_after: Optional[date] = Query(None),
    joined_before: Optional[date] = Query(None),
    team_only: bool = Query(False),
    sort_by: str = Query("name"),
    sort_order: str = Query("asc"),
    include_counts: bool = Query(False),
    include_facets: bool = Query(False),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if search:
        _rate_limit_directory_search(current_user)
    query = _apply_directory_filters(
        _directory_query(db),
        search=search,
        department_id=department_id,
        designation_id=designation_id,
        branch_id=branch_id,
        location_id=location_id,
        skills=skills,
        work_location=work_location,
        employment_type=employment_type,
        worker_type=worker_type,
        timezone_filter=timezone_filter,
        has_photo=has_photo,
        profile_completeness_min=profile_completeness_min,
        joined_after=joined_after,
        joined_before=joined_before,
    )
    if team_only:
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="No employee profile is linked to this user")
        query = query.filter(Employee.reporting_manager_id == current_user.employee.id)

    total = query.count()
    sort_map = {
        "name": Employee.first_name,
        "department": Employee.department_id,
        "joining_date": Employee.date_of_joining,
        "location": Employee.location_id,
        "designation": Employee.designation_id,
    }
    sort_column = sort_map.get(sort_by, Employee.first_name)
    query = query.order_by(desc(sort_column) if sort_order == "desc" else asc(sort_column), asc(Employee.last_name))
    items = (
        query
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    import math

    return PaginatedResponse(
        items=[_to_directory_item(item, current_user) for item in items],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.get("/directory/export")
def export_employee_directory(
    search: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    designation_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    location_id: Optional[int] = Query(None),
    team_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = _apply_directory_filters(
        _directory_query(db),
        search=search,
        department_id=department_id,
        designation_id=designation_id,
        branch_id=branch_id,
        location_id=location_id,
    )
    if team_only:
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="No employee profile is linked to this user")
        query = query.filter(Employee.reporting_manager_id == current_user.employee.id)

    rows = query.order_by(Employee.first_name.asc(), Employee.last_name.asc()).limit(5000).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["employee_id", "name", "email", "phone", "department", "designation", "branch", "manager", "location"])
    for employee in rows:
        item = _to_directory_item(employee, current_user)
        writer.writerow([
            item.employee_id,
            item.full_name,
            item.email or "",
            item.phone_number or "",
            item.department or "",
            item.designation or "",
            item.branch or "",
            item.reporting_manager or "",
            item.work_location or "",
        ])
    db.add(AuditLog(
        user_id=current_user.id,
        method="GET",
        endpoint="/api/v1/employees/directory/export",
        status_code=200,
        entity_type="employee_directory",
        action="EXPORT",
        description=f"Exported {len(rows)} directory rows with role masking",
    ))
    db.commit()
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=employee_directory.csv"},
    )


@router.get("/directory/filters")
def employee_directory_filters(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base = _directory_query(db)
    departments = (
        base.filter(Employee.department_id.isnot(None))
        .with_entities(Employee.department_id, func.count(Employee.id))
        .group_by(Employee.department_id)
        .all()
    )
    designations = (
        base.filter(Employee.designation_id.isnot(None))
        .with_entities(Employee.designation_id, func.count(Employee.id))
        .group_by(Employee.designation_id)
        .all()
    )
    branches = (
        base.filter(Employee.branch_id.isnot(None))
        .with_entities(Employee.branch_id, func.count(Employee.id))
        .group_by(Employee.branch_id)
        .all()
    )
    work_locations = (
        base.filter(Employee.work_location.isnot(None))
        .with_entities(Employee.work_location, func.count(Employee.id))
        .group_by(Employee.work_location)
        .all()
    )
    skills: dict[str, int] = {}
    for row in base.filter(Employee.skills_tags.isnot(None)).with_entities(Employee.skills_tags).limit(1000).all():
        for skill in str(row[0] or "").replace(";", ",").split(","):
            value = skill.strip()
            if value:
                skills[value] = skills.get(value, 0) + 1
    return {
        "departments": [{"id": item[0], "count": item[1]} for item in departments],
        "designations": [{"id": item[0], "count": item[1]} for item in designations],
        "branches": [{"id": item[0], "count": item[1]} for item in branches],
        "work_locations": [{"name": item[0], "count": item[1]} for item in work_locations],
        "skills": [{"name": key, "count": value} for key, value in sorted(skills.items())[:50]],
    }


@router.get("/recent-joiners", response_model=List[EmployeeDirectoryItem])
def recent_joiners(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    since = date.today() - timedelta(days=days)
    rows = (
        _directory_query(db)
        .filter(Employee.date_of_joining >= since)
        .order_by(Employee.date_of_joining.desc())
        .limit(limit)
        .all()
    )
    return [_to_directory_item(row, current_user) for row in rows]


@router.get("/birthdays", response_model=List[DirectoryEventItem])
def upcoming_birthdays(
    days: int = Query(30, ge=1, le=90),
    include_private: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if include_private and not _can_manage_directory(current_user):
        raise HTTPException(status_code=403, detail="Private birthday access is limited to HR/Admin")
    today = date.today()
    until = today + timedelta(days=days)
    rows = _directory_query(db).filter(Employee.date_of_birth.isnot(None)).all()
    items = []
    for employee in rows:
        event_date = employee.date_of_birth.replace(year=today.year)
        if event_date < today:
            event_date = event_date.replace(year=today.year + 1)
        if today <= event_date <= until:
            items.append(DirectoryEventItem(
                id=employee.id,
                employee_id=employee.employee_id,
                full_name=_directory_name(employee),
                department=employee.department.name if employee.department else None,
                designation=employee.designation.name if employee.designation else None,
                event_date=event_date,
                profile_photo_url=employee.profile_photo_url,
            ))
    return sorted(items, key=lambda item: item.event_date)


@router.get("/work-anniversaries", response_model=List[DirectoryEventItem])
def upcoming_work_anniversaries(
    days: int = Query(30, ge=1, le=90),
    include_private: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if include_private and not _can_manage_directory(current_user):
        raise HTTPException(status_code=403, detail="Private anniversary access is limited to HR/Admin")
    today = date.today()
    until = today + timedelta(days=days)
    rows = _directory_query(db).all()
    items = []
    for employee in rows:
        event_date = employee.date_of_joining.replace(year=today.year)
        if event_date < today:
            event_date = event_date.replace(year=today.year + 1)
        if today <= event_date <= until:
            items.append(DirectoryEventItem(
                id=employee.id,
                employee_id=employee.employee_id,
                full_name=_directory_name(employee),
                department=employee.department.name if employee.department else None,
                designation=employee.designation.name if employee.designation else None,
                event_date=event_date,
                profile_photo_url=employee.profile_photo_url,
            ))
    return sorted(items, key=lambda item: item.event_date)


@router.get("/org-search", response_model=List[DirectorySuggestion])
def org_search_autocomplete(
    q: str = Query("", min_length=0),
    limit: int = Query(8, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _rate_limit_directory_search(current_user)
    query = _directory_query(db)
    if q.strip():
        pattern = f"%{q.strip()}%"
        query = query.filter(
            (Employee.first_name.ilike(pattern))
            | (Employee.last_name.ilike(pattern))
            | (Employee.employee_id.ilike(pattern))
            | (Employee.preferred_display_name.ilike(pattern))
            | (Employee.skills_tags.ilike(pattern))
        )
    rows = query.order_by(Employee.first_name.asc()).limit(limit).all()
    return [
        DirectorySuggestion(
            id=row.id,
            label=_directory_name(row),
            subtitle=f"{row.employee_id} | {row.designation.name if row.designation else 'No designation'}",
        )
        for row in rows
    ]


@router.get("/{employee_id}/profile-card", response_model=EmployeeProfileCard)
def employee_profile_card(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = (
        _directory_query(db)
        .filter(Employee.id == employee_id)
        .first()
    )
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    can_contact = _can_view_contact(current_user, employee)
    db.add(AuditLog(
        user_id=current_user.id,
        method="GET",
        endpoint=f"/api/v1/employees/{employee_id}/profile-card",
        status_code=200,
        entity_type="employee",
        entity_id=employee_id,
        action="VIEW",
        description="Viewed employee directory profile card",
    ))
    db.commit()
    return EmployeeProfileCard(
        id=employee.id,
        employee_id=employee.employee_id,
        full_name=_directory_name(employee),
        email=_mask(employee.work_email or employee.personal_email, can_contact),
        phone_number=_mask(employee.phone_number, can_contact),
        department=employee.department.name if employee.department else None,
        designation=employee.designation.name if employee.designation else None,
        branch=employee.branch.name if employee.branch else None,
        reporting_manager=(
            f"{employee.reporting_manager.first_name} {employee.reporting_manager.last_name}"
            if employee.reporting_manager
            else None
        ),
        work_location=employee.work_location,
        desk_code=employee.desk_code,
        office_extension=_mask(employee.office_extension, can_contact),
        timezone=employee.timezone,
        skills=[skill.strip() for skill in (employee.skills_tags or "").replace(";", ",").split(",") if skill.strip()],
        profile_photo_url=employee.profile_photo_url,
        contact_masked=not can_contact,
    )


@router.post("/directory/report-correction", status_code=201)
def report_directory_correction(
    data: DirectoryCorrectionReport,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = db.query(Employee).filter(Employee.id == data.employee_id, Employee.deleted_at.is_(None)).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.add(AuditLog(
        user_id=current_user.id,
        method="POST",
        endpoint="/api/v1/employees/directory/report-correction",
        status_code=201,
        entity_type="employee",
        entity_id=employee.id,
        action="DIRECTORY_CORRECTION",
        new_values=json.dumps({"field": data.field_name, "message": data.message}),
        description=f"Directory correction reported for {employee.employee_id}",
    ))
    hr_users = (
        db.query(User)
        .join(Role, User.role_id == Role.id, isouter=True)
        .filter(or_(User.is_superuser == True, Role.name.in_(["hr", "hr_admin", "hr_manager", "admin"])))
        .limit(20)
        .all()
    )
    for user in hr_users:
        create_notification(db, NotificationCreate(
            user_id=user.id,
            title="Directory correction reported",
            message=f"{current_user.email} reported {data.field_name} for {employee.employee_id}: {data.message}",
            module="employees",
            event_type="directory_correction",
            related_entity_type="employee",
            related_entity_id=employee.id,
            action_url=f"/employees/{employee.id}",
            channels=["in_app"],
        ))
    db.commit()
    return {"message": "Correction report submitted"}


@router.get("/", response_model=PaginatedResponse[EmployeeListSchema])
def list_employees(
    search: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    designation_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    employment_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_view")),
):
    skip = (page - 1) * per_page
    items, total = crud_employee.search(
        db,
        search=search,
        department_id=department_id,
        branch_id=branch_id,
        designation_id=designation_id,
        status=status,
        employment_type=employment_type,
        skip=skip,
        limit=per_page,
    )
    import math
    return PaginatedResponse(
        items=[mask_employee_list_item(item, current_user) for item in items],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.post("/", response_model=EmployeeSchema, status_code=status.HTTP_201_CREATED)
def create_employee(
    data: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_create")),
):
    if data.employee_id and crud_employee.get_by_employee_id(db, data.employee_id):
        raise HTTPException(status_code=400, detail="Employee ID already exists")
    if data.create_user_account and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only admin can create login users")
    return crud_employee.create_with_user(db, obj_in=data, created_by=current_user.id)


@router.get("/stats")
def employee_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_view")),
):
    return crud_employee.get_headcount_stats(db)


@router.get("/count")
def employee_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_view")),
):
    total = db.query(func.count(Employee.id)).filter(Employee.deleted_at.is_(None)).scalar() or 0
    active = db.query(func.count(Employee.id)).filter(
        Employee.deleted_at.is_(None),
        Employee.status.in_(["Active", "Probation"]),
    ).scalar() or 0
    return {"total": total, "active": active}


@router.get("/documents/expiring", response_model=List[EmployeeDocumentSchema])
def list_expiring_employee_documents(
    days: int = Query(60, ge=0, le=365),
    department_id: Optional[int] = Query(None),
    document_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_view")),
):
    today = date.today()
    query = db.query(EmployeeDocument).join(Employee).filter(
        Employee.deleted_at.is_(None),
        EmployeeDocument.expiry_date.isnot(None),
        EmployeeDocument.expiry_date <= today + timedelta(days=days),
    )
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    if document_type:
        query = query.filter(EmployeeDocument.document_type == document_type)
    return query.order_by(EmployeeDocument.expiry_date.asc()).limit(500).all()


@router.get("/export")
def export_employees(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_export")),
):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "employee_id", "first_name", "last_name", "personal_email", "phone_number",
        "date_of_joining", "employment_type", "status", "work_location",
        "branch_id", "department_id", "designation_id", "reporting_manager_id",
    ])

    query = db.query(Employee).filter(Employee.deleted_at.is_(None))
    if status_filter:
        query = query.filter(Employee.status == status_filter)
    for emp in query.order_by(Employee.employee_id).all():
        writer.writerow([
            emp.employee_id,
            emp.first_name,
            emp.last_name,
            emp.personal_email or "",
            emp.phone_number or "",
            emp.date_of_joining.isoformat() if emp.date_of_joining else "",
            emp.employment_type,
            emp.status,
            emp.work_location,
            emp.branch_id or "",
            emp.department_id or "",
            emp.designation_id or "",
            emp.reporting_manager_id or "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=employees_export.csv"},
    )


@router.post("/import", status_code=201)
async def import_employees(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_import")),
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV import is supported")

    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(StringIO(raw))
    required = {"first_name", "last_name", "date_of_joining"}
    headers = set(reader.fieldnames or [])
    missing = sorted(required - headers)
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing columns: {', '.join(missing)}")

    created = 0
    errors = []
    seen_employee_ids = set()
    for row_number, row in enumerate(reader, start=2):
        row_errors = []
        first_name = (row.get("first_name") or "").strip()
        last_name = (row.get("last_name") or "").strip()
        employee_id = (row.get("employee_id") or "").strip() or f"EMPIMP{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{row_number:04d}"
        if not first_name:
            row_errors.append("first_name is required")
        if not last_name:
            row_errors.append("last_name is required")
        if crud_employee.get_by_employee_id(db, employee_id):
            row_errors.append(f"employee_id {employee_id} already exists")
        if employee_id in seen_employee_ids:
            row_errors.append(f"employee_id {employee_id} is duplicated in this import")

        try:
            joining_date = _parse_date(row.get("date_of_joining"), row_number, "date_of_joining")
            confirmation_date = _parse_date(row.get("date_of_confirmation"), row_number, "date_of_confirmation")
        except ValueError as exc:
            row_errors.append(str(exc))
            joining_date = None
            confirmation_date = None

        if not joining_date:
            row_errors.append("date_of_joining is required")

        def optional_int(field: str):
            value = (row.get(field) or "").strip()
            if not value:
                return None
            try:
                return int(value)
            except ValueError:
                row_errors.append(f"{field} must be a number")
                return None

        branch_id = optional_int("branch_id")
        department_id = optional_int("department_id")
        designation_id = optional_int("designation_id")
        reporting_manager_id = optional_int("reporting_manager_id")

        if row_errors:
            errors.append({"row": row_number, "employee_id": employee_id, "errors": row_errors})
            seen_employee_ids.add(employee_id)
            continue

        employee = Employee(
            employee_id=employee_id,
            first_name=first_name,
            last_name=last_name,
            personal_email=(row.get("personal_email") or "").strip() or None,
            phone_number=(row.get("phone_number") or "").strip() or None,
            date_of_joining=joining_date,
            date_of_confirmation=confirmation_date,
            employment_type=(row.get("employment_type") or "Full-time").strip() or "Full-time",
            status=(row.get("status") or "Active").strip() or "Active",
            work_location=(row.get("work_location") or "Office").strip() or "Office",
            branch_id=branch_id,
            department_id=department_id,
            designation_id=designation_id,
            reporting_manager_id=reporting_manager_id,
        )
        db.add(employee)
        seen_employee_ids.add(employee_id)
        created += 1

    db.commit()
    create_notification(
        db,
        NotificationCreate(
            user_id=current_user.id,
            title="Employee import completed",
            message=f"{created} employees imported. {len(errors)} rows need correction.",
            module="employee",
            event_type="employee_import_completed",
            action_url="/employees",
            priority="high" if errors else "normal",
            channels=["in_app", "email"],
        ),
    )
    return {"created": created, "failed": len(errors), "errors": errors}


@router.get("/me", response_model=EmployeeSchema)
def get_my_employee_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=404, detail="Employee profile not linked")
    emp = crud_employee.get_with_details(db, current_user.employee.id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee profile not found")
    return mask_employee_detail(emp, current_user)


@router.get("/me/completeness")
def my_profile_completeness(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=404, detail="Employee profile not linked")
    employee = db.query(Employee).filter(
        Employee.id == current_user.employee.id,
        Employee.deleted_at.is_(None),
    ).first()
    fields = {
        "personal_email": employee.personal_email,
        "phone_number": employee.phone_number,
        "date_of_birth": employee.date_of_birth,
        "present_address": employee.present_address,
        "permanent_address": employee.permanent_address,
        "emergency_contact_name": employee.emergency_contact_name,
        "emergency_contact_number": employee.emergency_contact_number,
        "bank_name": employee.bank_name,
        "account_number": employee.account_number,
        "ifsc_code": employee.ifsc_code,
        "pan_number": employee.pan_number,
        "profile_photo_url": employee.profile_photo_url,
    }
    completed = [key for key, value in fields.items() if value]
    missing = [key for key, value in fields.items() if not value]
    percent = round((len(completed) / len(fields)) * 100, 2)
    pending_requests = db.query(EmployeeChangeRequest).filter(
        EmployeeChangeRequest.employee_id == employee.id,
        EmployeeChangeRequest.status == "Pending",
    ).count()
    return {
        "employee_id": employee.id,
        "percent": percent,
        "completed": completed,
        "missing": missing,
        "pending_change_requests": pending_requests,
    }


@router.post("/change-requests", response_model=EmployeeChangeRequestSchema, status_code=201)
def create_employee_change_request(
    data: EmployeeChangeRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_superuser and not any(p.name == "employee_update" for p in (current_user.role.permissions if current_user.role else [])):
        if not current_user.employee or current_user.employee.id != data.employee_id:
            raise HTTPException(status_code=403, detail="Not authorized to request changes for this employee")
    employee = db.query(Employee).filter(
        Employee.id == data.employee_id,
        Employee.deleted_at.is_(None),
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    changes = data.field_changes_json or {}
    if not isinstance(changes, dict) or not changes:
        raise HTTPException(status_code=400, detail="field_changes_json must contain at least one field")
    if SENSITIVE_PROFILE_FIELDS.intersection(changes.keys()) and not (
        current_user.employee and current_user.employee.id == employee.id
    ) and not (_has_permission(current_user, "employee_update") or _has_permission(current_user, "payroll_run")):
        raise HTTPException(status_code=403, detail="Sensitive profile changes require HR/payroll access")
    values = data.model_dump()
    values["organization_id"] = _org_id(current_user)
    values["field_name"] = data.field_name or (next(iter(changes.keys())) if len(changes) == 1 else "multiple")
    values["old_value_json"] = _employee_current_values(employee, changes)
    values["new_value_json"] = changes
    item = EmployeeChangeRequest(**values, requested_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/change-requests", response_model=List[EmployeeChangeRequestSchema])
def list_employee_change_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(EmployeeChangeRequest)
    role_name = (current_user.role.name if current_user.role else "").lower().replace(" ", "_")
    has_employee_view = current_user.is_superuser or any(p.name == "employee_view" for p in (current_user.role.permissions if current_user.role else []))
    has_employee_update = current_user.is_superuser or any(p.name == "employee_update" for p in (current_user.role.permissions if current_user.role else []))
    if not has_employee_view and not current_user.employee:
        raise HTTPException(status_code=403, detail="Not authorized to view change requests")
    if not has_employee_update:
        if role_name in {"manager", "team_lead", "department_head"} and current_user.employee:
            direct_report_ids = [
                row.id for row in db.query(Employee.id).filter(
                    Employee.reporting_manager_id == current_user.employee.id,
                    Employee.deleted_at.is_(None),
                ).all()
            ]
            allowed_employee_ids = set(direct_report_ids + [current_user.employee.id])
            query = query.filter(EmployeeChangeRequest.employee_id.in_(allowed_employee_ids or {0}))
        elif current_user.employee:
            query = query.filter(EmployeeChangeRequest.employee_id == current_user.employee.id)
        else:
            raise HTTPException(status_code=403, detail="Not authorized to view change requests")
    if status_filter:
        query = query.filter(EmployeeChangeRequest.status == status_filter)
    if employee_id:
        if not has_employee_update and current_user.employee and employee_id != current_user.employee.id:
            if role_name not in {"manager", "team_lead", "department_head"}:
                raise HTTPException(status_code=403, detail="Not authorized to view this employee's change requests")
        query = query.filter(EmployeeChangeRequest.employee_id == employee_id)
    items = query.order_by(EmployeeChangeRequest.id.desc()).limit(300).all()
    employees = {
        emp.id: emp
        for emp in db.query(Employee).filter(
            Employee.id.in_([item.employee_id for item in items] or [0]),
            Employee.deleted_at.is_(None),
        ).all()
    }
    payload = []
    for item in items:
        employee = employees.get(item.employee_id)
        changes = item.field_changes_json or {}
        current_values = {
            field: getattr(employee, field, None)
            for field in changes.keys()
            if employee and hasattr(employee, field)
        }
        if item.old_value_json is None and current_values:
            item.old_value_json = current_values
        payload.append(_serialize_change_request(item, employee))
    return payload


@router.get("/user-options", response_model=List[EmployeeUserOption])
def list_employee_user_options(
    search: Optional[str] = Query(None),
    include_employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_update")),
):
    query = db.query(User).outerjoin(Employee, Employee.user_id == User.id)
    if search:
        term = f"%{search}%"
        query = query.filter(User.email.ilike(term))
    if include_employee_id:
        query = query.filter((Employee.id.is_(None)) | (Employee.id == include_employee_id))
    else:
        query = query.filter(Employee.id.is_(None))

    users = query.order_by(User.email).limit(100).all()
    options = []
    for user in users:
        employee = user.employee
        options.append(
            {
                "id": user.id,
                "email": user.email,
                "role": user.role.name if user.role else None,
                "employee_id": employee.id if employee else None,
                "employee_code": employee.employee_id if employee else None,
                "employee_name": f"{employee.first_name} {employee.last_name}" if employee else None,
            }
        )
    return options


@router.put("/change-requests/{request_id}/review", response_model=EmployeeChangeRequestSchema)
def review_employee_change_request(
    request_id: int,
    data: EmployeeChangeRequestReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.query(EmployeeChangeRequest).filter(EmployeeChangeRequest.id == request_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Change request not found")
    employee = db.query(Employee).filter(
        Employee.id == item.employee_id,
        Employee.deleted_at.is_(None),
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    has_employee_update = any(p.name == "employee_update" for p in (current_user.role.permissions if current_user.role else []))
    is_direct_manager = bool(current_user.employee and employee.reporting_manager_id == current_user.employee.id)
    if not (current_user.is_superuser or has_employee_update or is_direct_manager):
        raise HTTPException(status_code=403, detail="Not authorized to review this change request")
    if item.status != "Pending":
        raise HTTPException(status_code=400, detail="Change request already reviewed")
    if data.status not in {"Approved", "Rejected"}:
        raise HTTPException(status_code=400, detail="Status must be Approved or Rejected")
    item.status = data.status
    item.reviewed_by = current_user.id
    item.reviewed_at = datetime.now(timezone.utc)
    item.review_remarks = data.review_remarks
    if data.status == "Approved" and data.apply_changes:
        changes = item.field_changes_json or {}
        if SENSITIVE_PROFILE_FIELDS.intersection(changes.keys()) and not (
            current_user.is_superuser or _has_permission(current_user, "employee_update") or _has_permission(current_user, "payroll_run")
        ):
            raise HTTPException(status_code=403, detail="Sensitive profile changes require HR/payroll approval")
        org_fields = {
            "branch_id", "department_id", "designation_id", "business_unit_id", "cost_center_id",
            "location_id", "grade_band_id", "position_id", "reporting_manager_id", "status", "worker_type",
        }
        for field, value in changes.items():
            if field in org_fields and hasattr(employee, field):
                setattr(employee, field, value)
        _apply_profile_change(db, employee, changes)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{employee_id}/user-link", response_model=EmployeeSchema)
def update_employee_user_link(
    employee_id: int,
    data: EmployeeUserLinkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_update")),
):
    emp = db.query(Employee).filter(Employee.id == employee_id, Employee.deleted_at.is_(None)).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    if data.user_id is None:
        emp.user_id = None
        db.commit()
        db.refresh(emp)
        return emp

    user = db.query(User).filter(User.id == data.user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Active user not found")

    existing = db.query(Employee).filter(
        Employee.user_id == data.user_id,
        Employee.id != employee_id,
        Employee.deleted_at.is_(None),
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"User is already linked to employee {existing.employee_id}",
        )

    emp.user_id = data.user_id
    db.commit()
    db.refresh(emp)
    return emp


@router.post("/{employee_id}/user-account", response_model=EmployeeSchema, status_code=status.HTTP_201_CREATED)
def create_employee_user_account(
    employee_id: int,
    data: EmployeeUserAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_update")),
):
    emp = db.query(Employee).filter(Employee.id == employee_id, Employee.deleted_at.is_(None)).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    if emp.user_id:
        raise HTTPException(status_code=400, detail="Employee already has a linked user account")

    email = data.email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    if len(data.password or "") < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="User email already exists")

    role_id = data.role_id
    if role_id:
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
    else:
        role = db.query(Role).filter(func.lower(Role.name).like("%employee%")).order_by(Role.id.asc()).first()
        role_id = role.id if role else None

    user = User(
        email=email,
        hashed_password=get_password_hash(data.password),
        role_id=role_id,
        is_superuser=False,
        is_active=True,
    )
    db.add(user)
    db.flush()

    emp.user_id = user.id
    db.add(AuditLog(
        user_id=current_user.id,
        method="POST",
        endpoint=f"/api/v1/employees/{employee_id}/user-account",
        status_code=201,
        entity_type="employee_user_account",
        entity_id=employee_id,
        action="CREATE_AND_LINK",
        new_values=json.dumps({"employee_code": emp.employee_id, "email": email, "created_user_id": user.id}),
        description=f"Created and linked employee user account for {emp.employee_id}",
    ))
    db.commit()
    db.refresh(emp)
    return emp


@router.get("/{employee_id}", response_model=EmployeeSchema)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_view")),
):
    emp = crud_employee.get_with_details(db, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return mask_employee_detail(emp, current_user)


@router.put("/{employee_id}", response_model=EmployeeSchema)
def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_update")),
):
    emp = db.query(Employee).filter(Employee.id == employee_id, Employee.deleted_at.is_(None)).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    record_employee_field_changes(db, emp, data.model_dump(exclude_unset=True), current_user.id)
    return crud_employee.update(db, db_obj=emp, obj_in=data)


@router.get("/{employee_id}/lifecycle", response_model=List[EmployeeLifecycleEventSchema])
def list_lifecycle_events(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_view")),
):
    emp = db.query(Employee).filter(Employee.id == employee_id, Employee.deleted_at.is_(None)).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return crud_employee.list_lifecycle_events(db, employee_id)


@router.post("/{employee_id}/lifecycle", response_model=EmployeeLifecycleEventSchema, status_code=201)
def add_lifecycle_event(
    employee_id: int,
    data: EmployeeLifecycleEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_update")),
):
    emp = db.query(Employee).filter(Employee.id == employee_id, Employee.deleted_at.is_(None)).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return crud_employee.add_lifecycle_event(
        db,
        employee=emp,
        data=data.model_dump(),
        created_by=current_user.id,
    )


@router.delete("/{employee_id}")
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_delete")),
):
    emp = db.query(Employee).filter(Employee.id == employee_id, Employee.deleted_at.is_(None)).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp.status = "Terminated"
    emp.deleted_at = datetime.now(timezone.utc)
    emp.deleted_by = current_user.id
    db.commit()
    return {"message": "Employee terminated"}


# ── Education ────────────────────────────────────────────────────────────────

@router.post("/{employee_id}/education", response_model=EmployeeEducationSchema, status_code=201)
def add_education(
    employee_id: int,
    data: EmployeeEducationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_update")),
):
    return crud_employee.add_education(db, employee_id, data.model_dump())


@router.delete("/{employee_id}/education/{edu_id}")
def delete_education(
    employee_id: int,
    edu_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_update")),
):
    from app.models.employee import EmployeeEducation
    edu = db.query(EmployeeEducation).filter_by(id=edu_id, employee_id=employee_id).first()
    if not edu:
        raise HTTPException(status_code=404, detail="Education record not found")
    db.delete(edu)
    db.commit()
    return {"message": "Deleted"}


# ── Experience ───────────────────────────────────────────────────────────────

@router.post("/{employee_id}/experience", response_model=EmployeeExperienceSchema, status_code=201)
def add_experience(
    employee_id: int,
    data: EmployeeExperienceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_update")),
):
    return crud_employee.add_experience(db, employee_id, data.model_dump())


# ── Skills ───────────────────────────────────────────────────────────────────

@router.post("/{employee_id}/skills", response_model=EmployeeSkillSchema, status_code=201)
def add_skill(
    employee_id: int,
    data: EmployeeSkillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_update")),
):
    return crud_employee.add_skill(db, employee_id, data.model_dump())


# ── Documents ────────────────────────────────────────────────────────────────

@router.post("/{employee_id}/documents", response_model=EmployeeDocumentSchema, status_code=201)
async def upload_document(
    employee_id: int,
    document_type: str = Form(...),
    document_name: Optional[str] = Form(None),
    document_number: Optional[str] = Form(None),
    expiry_date: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    can_update = current_user.is_superuser or any(p.name == "employee_update" for p in (current_user.role.permissions if current_user.role else []))
    is_self = bool(current_user.employee and current_user.employee.id == employee_id)
    if not (can_update or is_self):
        raise HTTPException(status_code=403, detail="Not authorized to upload documents for this employee")
    # Validate file type
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in settings.allowed_extensions_list:
        raise HTTPException(status_code=400, detail=f"File type not allowed. Allowed: {settings.ALLOWED_EXTENSIONS}")

    upload_path = os.path.join(settings.UPLOAD_DIR, "employee_docs", str(employee_id))
    os.makedirs(upload_path, exist_ok=True)

    import uuid
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(upload_path, filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    file_url = f"/uploads/employee_docs/{employee_id}/{filename}"
    try:
        parsed_expiry_date = _parse_date(expiry_date, 0, "expiry_date") if expiry_date else None
    except ValueError:
        raise HTTPException(status_code=400, detail="expiry_date must be YYYY-MM-DD")

    return crud_employee.add_document(db, employee_id, {
        "document_type": document_type,
        "document_name": document_name or file.filename,
        "document_number": document_number,
        "file_url": file_url,
        "expiry_date": parsed_expiry_date,
    })


@router.put("/{employee_id}/documents/{document_id}/verify", response_model=EmployeeDocumentSchema)
def verify_employee_document(
    employee_id: int,
    document_id: int,
    data: EmployeeDocumentVerificationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_update")),
):
    if data.verification_status not in {"Pending", "Verified", "Rejected"}:
        raise HTTPException(status_code=400, detail="verification_status must be Pending, Verified, or Rejected")
    document = db.query(EmployeeDocument).filter_by(id=document_id, employee_id=employee_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    document.verification_status = data.verification_status
    document.is_verified = data.verification_status == "Verified"
    document.verified_by = current_user.id
    document.verified_at = datetime.now(timezone.utc)
    document.verifier_name = data.verifier_name
    document.verifier_company = data.verifier_company
    document.verification_notes = data.verification_notes
    db.commit()
    db.refresh(document)
    return document


@router.post("/{employee_id}/photo")
async def upload_photo(
    employee_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    can_update = current_user.is_superuser or any(p.name == "employee_update" for p in (current_user.role.permissions if current_user.role else []))
    is_self = bool(current_user.employee and current_user.employee.id == employee_id)
    if not (can_update or is_self):
        raise HTTPException(status_code=403, detail="Not authorized to upload photo for this employee")
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ["jpg", "jpeg", "png"]:
        raise HTTPException(status_code=400, detail="Only JPG/PNG allowed for photos")

    upload_path = os.path.join(settings.UPLOAD_DIR, "photos")
    os.makedirs(upload_path, exist_ok=True)

    import uuid
    filename = f"{employee_id}_{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(upload_path, filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    emp = crud_employee.get(db, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    emp.profile_photo_url = f"/uploads/photos/{filename}"
    db.commit()
    return {"url": emp.profile_photo_url}
