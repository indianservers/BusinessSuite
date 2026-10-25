"""Private self-service and HR management of shared employee/user profiles."""

from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.employee import Employee
from app.models.user import User
from app.common.services import profiles as service
from app.common.services.identity import SharedIdentityService

router = APIRouter(prefix="/profiles", tags=["Shared profiles"])


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: dict = Field(default_factory=dict, max_length=80)
    version: str | None = Field(None, max_length=64)
    reason: str = Field("Profile update", max_length=1000)


@router.get("/me")
def me(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    result = service.serialize_profile(db, actor, actor)
    db.commit()
    return result


@router.patch("/me")
def edit_me(
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return service.update_profile(
        db, actor, actor, data.values, data.version, data.reason
    )


@router.post("/me/photo")
async def own_photo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return await service.upload_photo(db, actor, actor, file)


@router.post("/users/{user_id}/photo")
async def user_photo(
    user_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    target = service.authorized_user(db, actor, user_id, write=True)
    return await service.upload_photo(db, target, actor, file)


@router.post("/employees/{employee_id}/photo")
async def employee_photo(
    employee_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    target = service.authorized_user(db, actor, employee_id=employee_id, write=True)
    return await service.upload_photo(db, target, actor, file)


@router.get("/directory")
def directory(
    search: str = Query("", max_length=150),
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    if not service.can_manage(actor):
        raise HTTPException(403, "HR profile management access is required")
    # Expose business directory information only; private profile fields require a scoped detail read.
    candidates = db.query(User).order_by(User.email).all()
    items = []
    for target in candidates:
        if service.tenant(target) != service.tenant(actor):
            continue
        try:
            service.authorized_user(db, actor, target.id)
            employee = service.employee_for(db, target)
        except HTTPException:
            continue
        name = (
            " ".join(filter(None, [employee.first_name, employee.last_name]))
            if employee
            else SharedIdentityService.display_name_for_user(target)
        )
        if (
            search
            and search.casefold()
            not in (
                name
                + " "
                + target.email
                + " "
                + (employee.employee_id if employee else "")
            ).casefold()
        ):
            continue
        items.append(
            {
                "userId": target.id,
                "displayName": name,
                "email": target.email,
                "employeeId": employee.id if employee else None,
                "employeeCode": employee.employee_id if employee else None,
                "kind": (
                    "intern"
                    if employee and (employee.employment_type or "").lower() == "intern"
                    else "employee" if employee else "user"
                ),
                "active": target.is_active,
            }
        )
    return {
        "items": items[(page - 1) * per_page : page * per_page],
        "total": len(items),
        "page": page,
        "perPage": per_page,
    }


@router.get("/employees/{employee_id}")
def employee_profile(
    employee_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    target = service.authorized_user(db, actor, employee_id=employee_id)
    result = service.serialize_profile(db, target, actor)
    db.commit()
    return result


@router.patch("/employees/{employee_id}")
def edit_employee_profile(
    employee_id: int,
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    target = service.authorized_user(db, actor, employee_id=employee_id, write=True)
    return service.update_profile(
        db, target, actor, data.values, data.version, data.reason
    )


@router.get("/users/{user_id}")
def user_profile(
    user_id: int, db: Session = Depends(get_db), actor: User = Depends(get_current_user)
):
    target = service.authorized_user(db, actor, user_id)
    result = service.serialize_profile(db, target, actor)
    db.commit()
    return result


@router.patch("/users/{user_id}")
def edit_user_profile(
    user_id: int,
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    target = service.authorized_user(db, actor, user_id, write=True)
    return service.update_profile(
        db, target, actor, data.values, data.version, data.reason
    )


def email_candidates(db, target, actor):
    if not service.is_app_enabled("hrms"):
        raise HTTPException(409, "Enable HRMS before connecting employee profiles")
    if not service.can_manage(actor):
        raise HTTPException(403, "HR profile management access is required")
    email = target.email.strip().casefold()
    from app.apps.interns_hub.models import InternApplication

    application = (
        db.query(InternApplication)
        .filter(
            InternApplication.organization_id == service.tenant(actor),
            func.lower(InternApplication.email) == email,
        )
        .first()
    )
    if application and application.status != "Approved":
        return []
    rows = (
        db.query(Employee)
        .filter(
            Employee.deleted_at.is_(None),
            Employee.status.in_(["Active", "Probation"]),
            or_(
                func.lower(Employee.personal_email) == email,
                func.lower(Employee.work_email) == email,
            ),
        )
        .all()
    )
    result = []
    for employee in rows:
        if (
            application
            and application.employee_id
            and application.employee_id != employee.id
        ):
            continue
        if service.employee_tenant(employee) != service.tenant(
            actor
        ) or employee.user_id not in {None, target.id}:
            continue
        # Reuse the existing manager scope even before the employee has a login.
        if not actor.is_superuser and (
            actor.role.name if actor.role else ""
        ).lower() not in {"admin", "super_admin", "hr", "hr_admin", "hr_company_admin"}:
            from app.apps.interns_hub.management_access import employee_query

            if (
                not employee_query(db, actor, include_employees=True)
                .filter(Employee.id == employee.id)
                .first()
            ):
                continue
        result.append(employee)
    return result


@router.get("/users/{user_id}/connect-preview")
def connect_preview(
    user_id: int, db: Session = Depends(get_db), actor: User = Depends(get_current_user)
):
    target = service.authorized_user(db, actor, user_id, write=True)
    rows = email_candidates(db, target, actor)
    return {
        "email": target.email,
        "candidates": [
            {
                "employeeId": e.id,
                "employeeCode": e.employee_id,
                "name": " ".join(filter(None, [e.first_name, e.last_name])),
                "linked": e.user_id == target.id,
            }
            for e in rows
        ],
        "message": "Choose the matching employee. Email matching never grants login or bypasses application approval.",
    }


class ConnectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employeeId: int = Field(gt=0)


@router.post("/users/{user_id}/connect-email")
def connect_email(
    user_id: int,
    data: ConnectInput,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    target = service.authorized_user(db, actor, user_id, write=True)
    db.refresh(target, with_for_update=True)
    employee = (
        db.query(Employee)
        .filter(Employee.id == data.employeeId)
        .with_for_update()
        .first()
    )
    if not employee or employee not in email_candidates(db, target, actor):
        raise HTTPException(409, "The employee is no longer an available email match")
    existing = service.employee_for(db, target)
    if existing and existing.id != employee.id:
        raise HTTPException(409, "This login already has a different employee profile")
    employee.user_id = target.id
    db.flush()
    SharedIdentityService.sync_from_employee(db, employee, target)
    result = service.serialize_profile(db, target, actor)
    service.audit(db, actor, target, "PROFILE_LINK", ["employee_id"])
    db.commit()
    return result
