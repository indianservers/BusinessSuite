from __future__ import annotations
from app.core.input_validation import contact_change_errors

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.employees import (
    PROFILE_CHANGE_FIELDS,
    SENSITIVE_PROFILE_FIELDS,
    _apply_profile_change,
    _employee_current_values,
    _has_permission,
    _org_id,
    _role_key,
    _serialize_change_request,
)
from app.core.deps import get_current_user, get_db
from app.models.employee import Employee, EmployeeChangeRequest
from app.models.user import User

router = APIRouter(tags=["HRMS Profile Change Requests"])


class ProfileChangeRequestPayload(BaseModel):
    requestType: str = "Profile Update"
    fieldName: str | None = None
    fieldChanges: dict[str, Any]
    reason: str | None = None
    documentPath: str | None = None
    effectiveDate: str | None = None


class ProfileChangeReviewPayload(BaseModel):
    remarks: str | None = None
    applyChanges: bool = True


def _load_employee(db: Session, employee_id: int, current_user: User) -> Employee:
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.deleted_at.is_(None)).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    from app.common.services.profiles import employee_tenant, tenant
    if employee_tenant(employee) != tenant(current_user):
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


def _can_manage(current_user: User) -> bool:
    return current_user.is_superuser or _has_permission(current_user, "employee_update") or _role_key(current_user) in {"admin", "hr"}


def _can_review_employee(employee: Employee, current_user: User) -> bool:
    if _can_manage(current_user):
        return True
    return bool(current_user.employee and employee.reporting_manager_id == current_user.employee.id)


def _can_view_employee(employee: Employee, current_user: User) -> bool:
    return _can_review_employee(employee, current_user) or bool(current_user.employee and current_user.employee.id == employee.id)


def _validate_changes(changes: dict[str, Any], current_user: User, employee: Employee) -> None:
    if not isinstance(changes, dict) or not changes:
        raise HTTPException(status_code=400, detail="fieldChanges must contain at least one field")
    errors=contact_change_errors(changes,employee)
    if errors:raise HTTPException(422,detail=errors)
    allowed_special = {"education_details", "experience_details", "document_details", "nominee_details", "unified_profile"}
    if "unified_profile" in changes:
        from app.common.services.profiles import normalize_values
        normalize_values(changes["unified_profile"], {key: getattr(employee, key, None) for key in ("phone_number", "phone_number_country_code", "emergency_contact_number", "emergency_contact_number_country_code")})
    unsupported = set(changes) - PROFILE_CHANGE_FIELDS - allowed_special
    if unsupported:
        raise HTTPException(status_code=400, detail=f"Unsupported change field(s): {', '.join(sorted(unsupported))}")
    if current_user.employee and current_user.employee.id == employee.id:
        return
    if SENSITIVE_PROFILE_FIELDS.intersection(changes.keys()) and not (_can_manage(current_user) or _has_permission(current_user, "payroll_run")):
        raise HTTPException(status_code=403, detail="Sensitive profile changes require HR/payroll access")


def _query_accessible_requests(db: Session, current_user: User):
    query = db.query(EmployeeChangeRequest).join(Employee, Employee.id == EmployeeChangeRequest.employee_id)
    org_id = _org_id(current_user)
    if org_id is not None:
        query = query.filter((EmployeeChangeRequest.organization_id == org_id) | (EmployeeChangeRequest.organization_id.is_(None)))
    if _can_manage(current_user):
        return query
    if not current_user.employee:
        raise HTTPException(status_code=403, detail="No employee profile is linked to this account")
    if _role_key(current_user) in {"manager"}:
        direct_report_ids = [row.id for row in db.query(Employee.id).filter(Employee.reporting_manager_id == current_user.employee.id, Employee.deleted_at.is_(None)).all()]
        return query.filter(EmployeeChangeRequest.employee_id.in_(direct_report_ids + [current_user.employee.id]))
    return query.filter(EmployeeChangeRequest.employee_id == current_user.employee.id)


@router.get("/hrms/profile-change-requests")
def list_profile_change_requests(
    status: str | None = Query(None),
    employeeId: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = _query_accessible_requests(db, current_user)
    if status:
        query = query.filter(EmployeeChangeRequest.status.in_({status, status.capitalize(), status.upper()}))
    if employeeId:
        employee = _load_employee(db, employeeId, current_user)
        if not _can_view_employee(employee, current_user):
            raise HTTPException(status_code=403, detail="Not authorized to view this employee's requests")
        query = query.filter(EmployeeChangeRequest.employee_id == employeeId)
    items = query.order_by(EmployeeChangeRequest.id.desc()).limit(500).all()
    employees = {emp.id: emp for emp in db.query(Employee).filter(Employee.id.in_([item.employee_id for item in items] or [0])).all()}
    return [_serialize_change_request(item, employees.get(item.employee_id)) for item in items]


@router.get("/hrms/profile-change-requests/{request_id}")
def get_profile_change_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _query_accessible_requests(db, current_user).filter(EmployeeChangeRequest.id == request_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Profile change request not found")
    employee = db.query(Employee).filter(Employee.id == item.employee_id).first()
    return _serialize_change_request(item, employee)


@router.post("/hrms/employees/{employee_id}/change-request", status_code=201)
def create_profile_change_request(
    employee_id: int,
    data: ProfileChangeRequestPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = _load_employee(db, employee_id, current_user)
    if not (_can_manage(current_user) or (current_user.employee and current_user.employee.id == employee.id)):
        raise HTTPException(status_code=403, detail="Employees can create requests only for their own profile")
    _validate_changes(data.fieldChanges, current_user, employee)
    old_values = _employee_current_values(employee, data.fieldChanges)
    item = EmployeeChangeRequest(
        organization_id=_org_id(current_user),
        employee_id=employee.id,
        request_type=data.requestType,
        field_name=data.fieldName or (next(iter(data.fieldChanges.keys())) if len(data.fieldChanges) == 1 else "multiple"),
        field_changes_json=data.fieldChanges,
        old_value_json=old_values,
        new_value_json=data.fieldChanges,
        document_path=data.documentPath,
        status="Pending",
        reason=data.reason,
        requested_by=current_user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_change_request(item, employee)


def _review_request(request_id: int, action: str, data: ProfileChangeReviewPayload, db: Session, current_user: User):
    item = _query_accessible_requests(db, current_user).filter(EmployeeChangeRequest.id == request_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Profile change request not found")
    employee = _load_employee(db, item.employee_id, current_user)
    if not _can_review_employee(employee, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to review this profile change")
    if item.status != "Pending":
        raise HTTPException(status_code=400, detail="Profile change request already reviewed")
    changes = item.field_changes_json or {}
    if action == "approve" and SENSITIVE_PROFILE_FIELDS.intersection(changes.keys()) and not (
        _can_manage(current_user) or _has_permission(current_user, "payroll_run")
    ):
        raise HTTPException(status_code=403, detail="Sensitive profile changes require HR/payroll approval")
    item.status = "Approved" if action == "approve" else "Rejected"
    item.reviewed_by = current_user.id
    item.reviewed_at = datetime.now(timezone.utc)
    item.review_remarks = data.remarks
    if action == "approve" and data.applyChanges:
        _apply_profile_change(db, employee, changes)
    db.commit()
    db.refresh(item)
    return _serialize_change_request(item, employee)


@router.post("/hrms/profile-change-requests/{request_id}/approve")
def approve_profile_change_request(
    request_id: int,
    data: ProfileChangeReviewPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _review_request(request_id, "approve", data, db, current_user)


@router.post("/hrms/profile-change-requests/{request_id}/reject")
def reject_profile_change_request(
    request_id: int,
    data: ProfileChangeReviewPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _review_request(request_id, "reject", data, db, current_user)
