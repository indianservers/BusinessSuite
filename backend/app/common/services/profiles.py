"""One private profile for a login, its employee record and approved onboarding form."""

from __future__ import annotations
from app.access.catalog import permission_objects

import copy
import hashlib
import json
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError
from sqlalchemy import func, or_

from app.common.models import CommonPerson, CommonProfile
from app.common.services.identity import SharedIdentityService
from app.models.audit import AuditLog
from app.models.employee import (
    Employee,
    EmployeeEducation,
    EmployeeExperience,
    EmployeeSkill,
    EmployeeChangeRequest,
)
from app.models.user import User
from app.module_registry import is_app_enabled

NATIVE_FIELDS = {
    "first_name",
    "middle_name",
    "last_name",
    "preferred_display_name",
    "gender",
    "date_of_birth",
    "marital_status",
    "personal_email",
    "phone_number",
    "phone_number_country_code",
    "present_address",
    "present_city",
    "present_state",
    "present_pincode",
    "present_country",
    "permanent_address",
    "permanent_city",
    "permanent_state",
    "permanent_pincode",
    "emergency_contact_name",
    "emergency_contact_number",
    "emergency_contact_number_country_code",
    "emergency_contact_relation",
    "bio",
    "interests",
    "linkedin_url",
    "portfolio_url",
    "timezone",
}
EXTRA_FIELDS = {
    "guardian_name",
    "github_url",
    "locale",
    "languages",
    "degree",
    "college",
    "specialization",
    "current_year",
    "passout_year",
    "tenth_marks",
    "twelfth_marks",
    "available_from",
    "duration",
    "requested_role",
    "preferred_mode",
    "skills",
    "education",
    "experience",
}
EDITABLE_FIELDS = NATIVE_FIELDS | EXTRA_FIELDS
SELF_DIRECT = {
    "preferred_display_name",
    "bio",
    "interests",
    "linkedin_url",
    "github_url",
    "portfolio_url",
    "skills",
    "languages",
    "timezone",
    "locale",
}
APP_FIELDS = {
    "parent_name",
    "mobile",
    "mobile_country_code",
    "gender",
    "date_of_birth",
    "city",
    "state",
    "tenth_marks",
    "twelfth_marks",
    "degree",
    "current_year",
    "college",
    "specialization",
    "passout_year",
    "area_of_interest",
    "skills",
    "role",
    "mode",
    "available_from",
    "duration",
    "address",
    "linkedin",
    "emergency_contact",
    "emergency_contact_country_code",
    "employment_type",
    "department",
    "portfolio",
    "github",
    "consent",
}
APP_MAP = {
    "parent_name": "guardian_name",
    "mobile": "phone_number",
    "mobile_country_code": "phone_number_country_code",
    "city": "present_city",
    "state": "present_state",
    "address": "present_address",
    "area_of_interest": "interests",
    "role": "requested_role",
    "mode": "preferred_mode",
    "linkedin": "linkedin_url",
    "github": "github_url",
    "portfolio": "portfolio_url",
    "emergency_contact": "emergency_contact_number",
    "emergency_contact_country_code": "emergency_contact_number_country_code",
}


def tenant(user):
    from app.apps.srm.services.commercial import tenant as organization

    return organization(user)


def permissions(user):
    return {p.name for p in permission_objects(user)}


def can_manage(user):
    if (user.role and user.role.name.lower() == "intern") or (
        getattr(user, "employee", None)
        and (user.employee.employment_type or "").lower() == "intern"
    ):
        return False
    return bool(
        user.is_superuser
        or permissions(user).intersection(
            {"employee_update", "intern_management_manage"}
        )
    )


def employee_for(db, user):
    if not is_app_enabled("hrms"):
        return None
    employee = (
        db.query(Employee)
        .filter(Employee.user_id == user.id, Employee.deleted_at.is_(None))
        .first()
    )
    if employee and employee.branch and employee.branch.company_id != tenant(user):
        raise HTTPException(
            409,
            "The linked employee belongs to another organization. Contact HR to repair the account link",
        )
    return employee


def employee_tenant(employee):
    if employee.branch:
        return employee.branch.company_id
    if employee.user:
        return tenant(employee.user)
    return 1


def authorized_user(db, actor, ident=None, employee_id=None, write=False):
    if employee_id is not None:
        employee = (
            db.query(Employee)
            .filter(Employee.id == employee_id, Employee.deleted_at.is_(None))
            .first()
        )
        if not employee or employee_tenant(employee) != tenant(actor):
            raise HTTPException(404, "Profile not found")
        if not employee.user_id:
            raise HTTPException(
                409,
                "Link this employee to an active login account before managing the shared profile",
            )
        ident = employee.user_id
    target = db.get(User, ident or actor.id)
    if not target or tenant(target) != tenant(actor):
        raise HTTPException(404, "Profile not found")
    if target.id != actor.id:
        if not can_manage(actor) and (
            write
            or not permissions(actor).intersection(
                {"employee_view", "intern_management_view"}
            )
        ):
            raise HTTPException(403, "HR profile management access is required")
        # Department/project managers retain their established employee visibility scope.
        if not actor.is_superuser and (
            actor.role.name if actor.role else ""
        ).lower() not in {"admin", "super_admin", "hr", "hr_admin", "hr_company_admin"}:
            employee = employee_for(db, target)
            if not employee:
                raise HTTPException(
                    403,
                    "Only organization HR administrators can manage account-only profiles",
                )
            from app.apps.interns_hub.management_access import employee_query

            if (
                not employee_query(db, actor, include_employees=True)
                .filter(Employee.id == employee.id)
                .first()
            ):
                raise HTTPException(404, "Profile not found in your permitted scope")
    return target


def ensure_profile(db, user, employee=None):
    person = db.query(CommonPerson).filter(CommonPerson.user_id == user.id).first()
    if person and person.organization_id not in {None, tenant(user)}:
        raise HTTPException(409, "The linked profile belongs to another organization")
    if not person:
        person = SharedIdentityService.ensure_person_for_user(
            db,
            user,
            organization_id=tenant(user),
            source_module="hrms" if employee else "common",
        )
    if not person.profile:
        person.profile = CommonProfile(person_id=person.id, profile_data_json={})
        db.add(person.profile)
        db.flush()
    return person, person.profile


def approved_application(db, user, employee):
    if not employee or not is_app_enabled("hrms"):
        return None
    from app.apps.interns_hub.models import InternApplication

    return (
        db.query(InternApplication)
        .filter(
            InternApplication.organization_id == tenant(user),
            InternApplication.employee_id == employee.id,
            InternApplication.status == "Approved",
        )
        .first()
    )


def seed_application_profile(db, employee, application):
    """Preserve the complete safe form snapshot; never copy credentials or raw IDs."""
    if not employee.user or application.organization_id != employee_tenant(employee):
        raise HTTPException(
            409, "Application and employee must belong to the same organization"
        )
    person, profile = ensure_profile(db, employee.user, employee)
    data = copy.deepcopy(profile.profile_data_json or {})
    if data.get("application", {}).get("id") == application.id:
        return
    safe = {
        key: value
        for key, value in (application.details or {}).items()
        if key in APP_FIELDS
    }
    data["application"] = {
        "id": application.id,
        "reference": application.reference,
        "email": application.email,
        "full_name": application.full_name,
        "status": application.status,
        "submitted_at": jsonable_encoder(application.created_at),
        "identity_type": (application.details or {}).get("identity_type"),
        "identity_last4": application.identity_last4,
        "values": safe,
    }
    current = data.get("profile", {})
    for original, value in safe.items():
        key = APP_MAP.get(original, original)
        if key not in EDITABLE_FIELDS or key in {"skills", "education", "experience"}:
            continue
        if key not in current and value is not None:
            current[key] = value
        if (
            key in {"linkedin_url", "portfolio_url"}
            and not getattr(employee, key, None)
            and value
        ):
            setattr(employee, key, str(value))
    data["profile"] = current
    profile.profile_data_json = data
    SharedIdentityService.sync_from_employee(db, employee)


def audit(db, actor, target, action, fields):
    # Field names only: personal profile values do not belong in general audit logs.
    db.add(
        AuditLog(
            user_id=actor.id,
            method="PROFILE",
            endpoint=f"/profiles/users/{target.id}",
            entity_type="shared_profile",
            entity_id=target.id,
            action=action,
            description="Profile fields: " + ", ".join(sorted(fields)),
            module="common",
        )
    )


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Education(Strict):
    id: int | None = Field(None, gt=0)
    degree: str = Field(min_length=1, max_length=100)
    institution: str | None = Field(None, max_length=200)
    specialization: str | None = Field(None, max_length=150)
    board_university: str | None = Field(None, max_length=200)
    pass_year: int | None = Field(None, ge=1950, le=2100)
    percentage_cgpa: float | None = Field(None, ge=0, le=100, allow_inf_nan=False)


class Experience(Strict):
    id: int | None = Field(None, gt=0)
    company_name: str = Field(min_length=1, max_length=200)
    designation: str | None = Field(None, max_length=150)
    from_date: date | None = None
    to_date: date | None = None
    is_current: bool = False
    responsibilities: str | None = Field(None, max_length=4000)


class Collections(Strict):
    education: list[Education] | None = Field(None, max_length=30)
    experience: list[Experience] | None = Field(None, max_length=30)


def normalize_values(values, existing=None):
    from app.core.input_validation import (
        clean_text,
        national_phone,
        calling_code,
        email_address,
    )

    if not isinstance(values, dict):
        raise HTTPException(422, "Profile changes must be an object")
    unknown = set(values) - EDITABLE_FIELDS
    if unknown:
        raise HTTPException(
            422, "These fields cannot be changed here: " + ", ".join(sorted(unknown))
        )
    result = {}
    existing = existing or {}
    try:
        for key, value in values.items():
            if key in {"education", "experience"}:
                normalized = Collections(**{key: value}).model_dump(
                    exclude_unset=True, mode="json"
                )[key]
                if normalized is None:
                    raise ValueError(f"{key} must be a list")
                for item in normalized:
                    if (
                        key == "experience"
                        and item.get("to_date")
                        and item.get("from_date")
                        and item["to_date"] < item["from_date"]
                    ):
                        raise ValueError(
                            "Experience end date cannot precede its start date"
                        )
                result[key] = normalized
            elif key in {"tenth_marks", "twelfth_marks"}:
                if value is not None and (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not 0 <= value <= 100
                ):
                    raise ValueError("Marks must be from 0 to 100")
                result[key] = value
            elif key == "passout_year":
                if value is not None and (
                    isinstance(value, bool)
                    or not isinstance(value, int)
                    or not 1950 <= value <= 2100
                ):
                    raise ValueError("Enter a valid pass-out year")
                result[key] = value
            elif key in {"date_of_birth", "available_from"}:
                parsed = date.fromisoformat(value) if value else None
                if key == "date_of_birth" and parsed and parsed >= date.today():
                    raise ValueError("Date of birth must be in the past")
                result[key] = parsed.isoformat() if parsed else None
            elif key == "skills":
                if not isinstance(value, list) or len(value) > 30:
                    raise ValueError("Choose up to 30 skills")
                result[key] = list(
                    dict.fromkeys(clean_text(item, 100) for item in value)
                )
            else:
                maximum = (
                    4000
                    if key in {"bio", "present_address", "permanent_address"}
                    else 1000 if key in {"interests", "languages"} else 200
                )
                if key in {"phone_number", "emergency_contact_number"}:
                    result[key] = national_phone(value) if value else None
                elif key.endswith("_country_code"):
                    result[key] = calling_code(value) if value else None
                elif key == "personal_email":
                    result[key] = email_address(value) if value else None
                elif key in {"linkedin_url", "portfolio_url", "github_url"}:
                    result[key] = str(HttpUrl(value)) if value else None
                else:
                    result[key] = (
                        clean_text(
                            value,
                            maximum,
                            required=key == "first_name",
                            multiline=key
                            in {
                                "bio",
                                "present_address",
                                "permanent_address",
                                "interests",
                            },
                        )
                        if value is not None
                        else None
                    )
                if key == "first_name" and not result[key]:
                    raise ValueError("First name is required")
                maximum = (
                    80
                    if key in {"first_name", "middle_name", "last_name"}
                    else (
                        150
                        if key == "personal_email"
                        else 180 if key == "preferred_display_name" else None
                    )
                )
                if maximum and result[key] is not None and len(result[key]) > maximum:
                    raise ValueError(f"{key} must be {maximum} characters or fewer")
        merged = {**existing, **result}
        if (
            len(
                " ".join(
                    filter(
                        None,
                        [
                            merged.get("first_name"),
                            merged.get("middle_name"),
                            merged.get("last_name"),
                        ],
                    )
                )
            )
            > 180
        ):
            raise ValueError("Combined profile name must be 180 characters or fewer")
        for key in {"phone_number", "emergency_contact_number"}:
            if ({key, key + "_country_code"} & values.keys()) and merged.get(key):
                national_phone(merged[key])
                calling_code(merged.get(key + "_country_code"))
        if result.get("timezone"):
            ZoneInfo(result["timezone"])
    except (ValueError, TypeError, ValidationError, ZoneInfoNotFoundError) as exc:
        raise HTTPException(422, str(exc))
    return result


def sync_collections(employee, key, values):
    relationship, model = (
        ("educations", EmployeeEducation)
        if key == "education"
        else ("experiences", EmployeeExperience)
    )
    old = {row.id: row for row in getattr(employee, relationship)}
    updated = []
    for item in values:
        ident = item.get("id")
        if ident and ident not in old:
            raise HTTPException(
                422, "Education/experience record does not belong to this employee"
            )
        row = old[ident] if ident else model(employee_id=employee.id)
        for field, value in item.items():
            if field != "id":
                setattr(
                    row,
                    field,
                    (
                        date.fromisoformat(value)
                        if field in {"from_date", "to_date"} and value
                        else value
                    ),
                )
        updated.append(row)
    setattr(employee, relationship, updated)


def apply_values(db, user, values, employee=None):
    person, profile = ensure_profile(db, user, employee)
    data = copy.deepcopy(profile.profile_data_json or {})
    data["profile"] = {**data.get("profile", {}), **values}
    profile.profile_data_json = data
    if employee:
        for key, value in values.items():
            if key in NATIVE_FIELDS:
                setattr(
                    employee,
                    key,
                    (
                        date.fromisoformat(value)
                        if key == "date_of_birth" and value
                        else value
                    ),
                )
            elif key in {"education", "experience"}:
                sync_collections(employee, key, value)
            elif key == "skills":
                previous = {row.skill_name.casefold(): row for row in employee.skills}
                employee.skills = [
                    previous.get(name.casefold())
                    or EmployeeSkill(employee_id=employee.id, skill_name=name)
                    for name in value
                ]
        academic = {
            "degree": "degree",
            "college": "institution",
            "specialization": "specialization",
            "passout_year": "pass_year",
        }
        qualifications = [
            row
            for row in employee.educations
            if row.degree not in {"10th Standard", "12th Standard"}
        ]
        primary = next(
            (row for row in qualifications if row.is_highest_qualification),
            qualifications[-1] if qualifications else None,
        )
        if set(values).intersection(academic):
            if not primary and values.get("degree"):
                primary = EmployeeEducation(
                    employee_id=employee.id, degree=values["degree"]
                )
                employee.educations.append(primary)
            if primary:
                for key, field in academic.items():
                    if key in values:
                        if key == "degree" and not values[key]:
                            raise HTTPException(
                                422,
                                "Qualification name cannot be cleared; manage education records instead",
                            )
                        setattr(primary, field, values[key])
        for key, degree in [
            ("tenth_marks", "10th Standard"),
            ("twelfth_marks", "12th Standard"),
        ]:
            if key in values:
                row = next(
                    (row for row in employee.educations if row.degree == degree), None
                )
                if row:
                    row.percentage_cgpa = values[key]
                elif values[key] is not None:
                    employee.educations.append(
                        EmployeeEducation(
                            employee_id=employee.id,
                            degree=degree,
                            percentage_cgpa=values[key],
                        )
                    )
        if "education" in values and not primary:
            data["profile"].update({key: None for key in academic})
            profile.profile_data_json = copy.deepcopy(data)
        SharedIdentityService.sync_from_employee(db, employee)
    else:
        for key in {
            "first_name",
            "middle_name",
            "last_name",
            "phone_number",
            "phone_number_country_code",
        } & values.keys():
            setattr(person, key, values[key])
        names = [
            values.get(key, getattr(person, key, None))
            for key in ["first_name", "middle_name", "last_name"]
        ]
        person.display_name = (
            values.get("preferred_display_name")
            or " ".join(filter(None, names))
            or person.display_name
        )
        for key in {
            "preferred_display_name",
            "bio",
            "timezone",
            "locale",
        } & values.keys():
            setattr(profile, key, values[key])
    db.flush()


def apply_approved_profile(db, employee, values):
    if not employee.user:
        raise HTTPException(409, "Employee needs a linked account")
    current = serialize_profile(db, employee.user, employee.user)
    clean = normalize_values(values, current["values"])
    apply_values(db, employee.user, clean, employee)


def serialize_profile(db, user, actor):
    employee = employee_for(db, user)
    from app.api.v1.profile_change_requests import _can_review_employee
    person, profile = ensure_profile(db, user, employee)
    application = approved_application(db, user, employee)
    if application:
        seed_application_profile(db, employee, application)
    data = profile.profile_data_json or {}
    values = {key: None for key in EDITABLE_FIELDS}
    values.update(
        {
            key: value
            for key, value in data.get("profile", {}).items()
            if key in EDITABLE_FIELDS
        }
    )
    if employee:
        for key in NATIVE_FIELDS:
            native = getattr(employee, key, None)
            if (
                native is not None
                or key not in values
                or key in data.get("profile", {})
                and data["profile"][key] is None
            ):
                values[key] = jsonable_encoder(native)
        values["education"] = [
            {key: jsonable_encoder(getattr(row, key)) for key in Education.model_fields}
            for row in employee.educations
        ]
        values["experience"] = [
            {
                key: jsonable_encoder(getattr(row, key))
                for key in Experience.model_fields
            }
            for row in employee.experiences
        ]
        values["skills"] = [row.skill_name for row in employee.skills]
        primary_rows = [
            row
            for row in employee.educations
            if row.degree not in {"10th Standard", "12th Standard"}
        ]
        primary = next(
            (row for row in primary_rows if row.is_highest_qualification),
            primary_rows[-1] if primary_rows else None,
        )
        if primary:
            values.update(
                degree=primary.degree,
                college=primary.institution,
                specialization=primary.specialization,
                passout_year=primary.pass_year,
            )
        for key, degree in [
            ("tenth_marks", "10th Standard"),
            ("twelfth_marks", "12th Standard"),
        ]:
            row = next(
                (row for row in employee.educations if row.degree == degree), None
            )
            if row:
                values[key] = jsonable_encoder(row.percentage_cgpa)
    else:
        for key in {
            "first_name",
            "middle_name",
            "last_name",
            "phone_number",
            "phone_number_country_code",
        }:
            if values.get(key) is None:
                values[key] = getattr(person, key, None)
        values["bio"] = values.get("bio") or profile.bio
        values["preferred_display_name"] = (
            values.get("preferred_display_name") or profile.preferred_display_name
        )
        values["personal_email"] = values.get("personal_email") or user.email
    values["education"] = values.get("education") or []
    values["experience"] = values.get("experience") or []
    values["skills"] = values.get("skills") or []
    values["timezone"] = values.get("timezone") or profile.timezone
    values["locale"] = values.get("locale") or profile.locale
    pending = (
        db.query(EmployeeChangeRequest)
        .filter(
            EmployeeChangeRequest.employee_id == employee.id,
            EmployeeChangeRequest.status == "Pending",
        )
        .order_by(EmployeeChangeRequest.id.desc())
        .all()
        if employee
        else []
    )
    pending = [
        {
            "id": row.id,
            "status": row.status,
            "reason": row.reason,
            "created_at": jsonable_encoder(row.created_at),
            "values": (row.field_changes_json or {}).get("unified_profile", {}),
        }
        for row in pending
        if "unified_profile" in (row.field_changes_json or {})
    ]
    version = hashlib.sha256(
        json.dumps(
            {"values": values, "pending": [p["id"] for p in pending]},
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()[:24]
    employment = (
        {
            "employee_id": employee.employee_id,
            "employment_type": employee.employment_type,
            "status": employee.status,
            "date_of_joining": jsonable_encoder(employee.date_of_joining),
            "date_of_exit": jsonable_encoder(employee.date_of_exit),
            "branch": employee.branch.name if employee.branch else None,
            "department": employee.department.name if employee.department else None,
            "designation": employee.designation.name if employee.designation else None,
            "manager": (
                " ".join(
                    filter(
                        None,
                        [
                            employee.reporting_manager.first_name,
                            employee.reporting_manager.last_name,
                        ],
                    )
                )
                if employee.reporting_manager
                else None
            ),
            "work_email": employee.work_email,
            "work_location": employee.work_location,
        }
        if employee
        else None
    )
    required = [
        "first_name",
        "personal_email",
        "phone_number",
        "present_address",
        "present_city",
        "skills",
        "education",
        "emergency_contact_number",
        "bio",
    ]
    missing = [key for key in required if not values.get(key)]
    documents = (
        [
            {
                "id": row.id,
                "name": row.document_name or row.document_type,
                "status": row.verification_status,
                "source": "Employee record",
            }
            for row in employee.documents
        ]
        if employee
        else []
    )
    if application:
        from app.apps.interns_hub.management_models import ApplicationDocument

        documents += [
            {
                "id": row.id,
                "name": row.name,
                "status": "Submitted",
                "source": "Application",
            }
            for row in db.query(ApplicationDocument)
            .filter(ApplicationDocument.application_id == application.id)
            .all()
        ]
    return {
        "userId": user.id,
        "employeeId": employee.id if employee else None,
        "personId": person.id,
        "kind": (
            "intern"
            if employee and (employee.employment_type or "").lower() == "intern"
            else "employee" if employee else "user"
        ),
        "displayName": (
            employee.preferred_display_name
            or " ".join(
                filter(
                    None,
                    [employee.first_name, employee.middle_name, employee.last_name],
                )
            )
            if employee
            else person.display_name
        ),
        "loginEmail": user.email,
        "role": user.role.name if user.role else None,
        "accountActive": user.is_active,
        "values": values,
        "version": version,
        "employment": employment,
        "application": data.get("application") if application else None,
        "documents": documents,
        "photoUrl": (
            employee.profile_photo_url if employee else profile.profile_photo_url
        ),
        "completeness": round((len(required) - len(missing)) / len(required) * 100),
        "missingFields": missing,
        "canEdit": actor.id == user.id or can_manage(actor),
        "canManage": can_manage(actor),
        "canReview": bool(employee and _can_review_employee(employee, actor)),
        "requiresApprovalFields": (
            sorted(EDITABLE_FIELDS - SELF_DIRECT)
            if employee and not can_manage(actor)
            else []
        ),
        "pendingRequests": pending,
    }


def update_profile(db, user, actor, values, version=None, reason="Profile update"):
    employee = employee_for(db, user)
    if employee:
        db.refresh(employee, with_for_update=True)
    person, profile = ensure_profile(db, user, employee)
    db.refresh(profile, with_for_update=True)
    current = serialize_profile(db, user, actor)
    if version and current["version"] != version:
        raise HTTPException(
            409,
            "This profile has changed. Reload it before saving; your draft is still available",
        )
    clean = normalize_values(values, current["values"])
    clean = {
        key: value
        for key, value in clean.items()
        if value != current["values"].get(key)
    }
    protected = {
        key: value
        for key, value in clean.items()
        if employee and not can_manage(actor) and key not in SELF_DIRECT
    }
    direct = {key: value for key, value in clean.items() if key not in protected}
    # Validate ownership before either immediate writes or a pending request.
    for key, relationship in [
        ("education", "educations"),
        ("experience", "experiences"),
    ]:
        if employee and key in clean:
            own = {row.id for row in getattr(employee, relationship)}
            if any(row.get("id") and row["id"] not in own for row in clean[key]):
                raise HTTPException(
                    422, "Education/experience record does not belong to this employee"
                )
    if direct:
        apply_values(db, user, direct, employee)
    request_id = None
    if protected:
        item = EmployeeChangeRequest(
            organization_id=tenant(user),
            employee_id=employee.id,
            request_type="Unified Profile Update",
            field_name="unified_profile",
            field_changes_json={"unified_profile": protected},
            old_value_json={
                "unified_profile": {
                    key: current["values"].get(key) for key in protected
                }
            },
            new_value_json={"unified_profile": protected},
            status="Pending",
            reason=reason,
            requested_by=actor.id,
        )
        db.add(item)
        db.flush()
        request_id = item.id
    if clean:
        audit(
            db,
            actor,
            user,
            "PROFILE_REQUEST" if protected else "PROFILE_UPDATE",
            clean.keys(),
        )
    db.commit()
    return {
        "profile": serialize_profile(db, user, actor),
        "pendingRequestId": request_id,
        "message": (
            "Saved. Employee record changes are awaiting HR approval."
            if protected
            else "Profile saved across connected modules."
        ),
    }


async def upload_photo(db, user, actor, file):
    import io
    from pathlib import Path
    from uuid import uuid4
    from PIL import Image, ImageOps, UnidentifiedImageError
    from app.core.config import settings
    from app.core.storage import persist_file

    content = await file.read(3 * 1024 * 1024 + 1)
    await file.close()
    if len(content) > 3 * 1024 * 1024:
        raise HTTPException(413, "Profile photos must be 3 MB or smaller")
    try:
        with Image.open(io.BytesIO(content)) as photo:
            if (
                photo.format not in {"PNG", "JPEG"}
                or photo.width * photo.height > 16_000_000
            ):
                raise HTTPException(
                    422, "Choose a PNG or JPEG photo up to 16 megapixels"
                )
            photo.load()
            clean = ImageOps.exif_transpose(photo).convert("RGBA")
            clean.info.clear()
            clean.thumbnail((1024, 1024))
            output = io.BytesIO()
            clean.save(output, format="PNG")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(422, "This file is not a valid PNG or JPEG photo")
    employee = employee_for(db, user)
    person, profile = ensure_profile(db, user, employee)
    filename = uuid4().hex + ".png"
    path = (
        Path(settings.UPLOAD_DIR).resolve()
        / "_private"
        / "profiles"
        / str(tenant(user))
        / str(user.id)
        / filename
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(output.getvalue())
    try:
        persist_file(str(path))
        reference = (
            "/uploads/"
            + path.relative_to(Path(settings.UPLOAD_DIR).resolve()).as_posix()
        )
        profile.profile_photo_url = reference
        if employee:
            employee.profile_photo_url = reference
        audit(db, actor, user, "PROFILE_PHOTO", ["profile_photo_url"])
        result = serialize_profile(db, user, actor)
        db.commit()
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    return result
