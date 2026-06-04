from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.masking import mask_email, mask_identifier, mask_phone, mask_text
from app.models.audit import FieldAuditEvent
from app.models.employee import Employee
from app.models.platform import DataRetentionPolicy, LegalHold


SENSITIVE_FIELD_NAMES = {
    "ctc",
    "basic",
    "hra",
    "salary",
    "account_number",
    "bank_account",
    "ifsc_code",
    "pan_number",
    "aadhaar_number",
}

AUDITED_EMPLOYEE_FIELDS = {
    "account_number",
    "ifsc_code",
    "pan_number",
    "aadhaar_number",
    "reporting_manager_id",
    "designation_id",
    "department_id",
    "work_location",
    "status",
}

AUDITED_SALARY_FIELDS = {"ctc", "basic", "hra", "structure_id", "effective_from", "effective_to", "is_active"}

PLAINTEXT_ALLOWED_FIELDS = {
    "reporting_manager_id",
    "designation_id",
    "department_id",
    "work_location",
    "status",
    "structure_id",
    "effective_from",
    "effective_to",
    "is_active",
}

PRIVACY_EXPORT_EMPLOYEE_FIELDS = [
    "id",
    "employee_id",
    "first_name",
    "middle_name",
    "last_name",
    "work_email",
    "personal_email",
    "phone_number",
    "department_id",
    "designation_id",
    "reporting_manager_id",
    "status",
    "work_location",
    "date_of_joining",
    "date_of_exit",
]

PRIVACY_SENSITIVE_EMPLOYEE_FIELDS = [
    "account_number",
    "ifsc_code",
    "pan_number",
    "aadhaar_number",
    "bank_name",
    "bank_branch",
    "personal_email",
    "phone_number",
    "alternate_phone",
    "present_address",
    "permanent_address",
]


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (datetime,)):
        return value.isoformat()
    return str(value)


def value_hash(value: Any) -> str | None:
    text = _stringify(value)
    if text in (None, ""):
        return None
    salt = settings.SECRET_KEY or "ai-hrms"
    return hashlib.sha256(f"{salt}:{text}".encode("utf-8")).hexdigest()


def mask_field_value(field_name: str, value: Any) -> str | None:
    if value in (None, ""):
        return None
    if field_name in {"account_number", "bank_account", "pan_number", "aadhaar_number"}:
        return mask_identifier(value)
    if field_name in {"ifsc_code"}:
        text = str(value)
        return f"{text[:4]}{'*' * max(len(text) - 4, 2)}"
    if field_name in {"personal_email", "work_email"}:
        return mask_email(_stringify(value))
    if field_name in {"phone_number", "alternate_phone"}:
        return mask_phone(_stringify(value))
    if field_name in {"ctc", "basic", "hra", "salary"}:
        return mask_text(_stringify(value))
    return _stringify(value)


def record_field_audit(
    db: Session,
    *,
    module: str,
    entity_type: str,
    entity_id: int,
    employee_id: int | None,
    field_name: str,
    old_value: Any,
    new_value: Any,
    actor_user_id: int | None,
    action: str = "updated",
    reason: str | None = None,
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> FieldAuditEvent | None:
    if _stringify(old_value) == _stringify(new_value):
        return None
    is_sensitive = field_name in SENSITIVE_FIELD_NAMES
    plaintext_allowed = field_name in PLAINTEXT_ALLOWED_FIELDS
    event = FieldAuditEvent(
        module=module,
        entity_type=entity_type,
        entity_id=entity_id,
        employee_id=employee_id,
        field_name=field_name,
        action=action,
        old_value_masked=mask_field_value(field_name, old_value),
        new_value_masked=mask_field_value(field_name, new_value),
        old_value_hash=value_hash(old_value),
        new_value_hash=value_hash(new_value),
        old_value_plaintext=_stringify(old_value) if plaintext_allowed else None,
        new_value_plaintext=_stringify(new_value) if plaintext_allowed else None,
        is_sensitive=is_sensitive,
        actor_user_id=actor_user_id,
        reason=reason,
        request_id=request_id,
        metadata_json=metadata or {},
    )
    db.add(event)
    return event


def record_employee_field_changes(db: Session, employee: Employee, incoming: dict[str, Any], actor_user_id: int | None, reason: str | None = None) -> None:
    for field in AUDITED_EMPLOYEE_FIELDS:
        if field in incoming:
            record_field_audit(
                db,
                module="employee",
                entity_type="employee",
                entity_id=employee.id,
                employee_id=employee.id,
                field_name=field,
                old_value=getattr(employee, field, None),
                new_value=incoming[field],
                actor_user_id=actor_user_id,
                reason=reason,
            )


def record_salary_field_changes(
    db: Session,
    *,
    employee_id: int,
    entity_type: str,
    entity_id: int | None,
    old_values: dict[str, Any],
    new_values: dict[str, Any],
    actor_user_id: int | None,
    action: str = "updated",
    reason: str | None = None,
) -> None:
    entity_id = entity_id or employee_id
    for field in AUDITED_SALARY_FIELDS:
        if field in new_values:
            record_field_audit(
                db,
                module="payroll",
                entity_type=entity_type,
                entity_id=entity_id,
                employee_id=employee_id,
                field_name=field,
                old_value=old_values.get(field),
                new_value=new_values.get(field),
                actor_user_id=actor_user_id,
                action=action,
                reason=reason,
            )


def has_active_legal_hold(db: Session, employee_id: int) -> bool:
    return db.query(LegalHold).filter(
        LegalHold.status == "Active",
        or_(LegalHold.entity_id == employee_id, LegalHold.entity_id.is_(None)),
        LegalHold.module.in_(["employee", "hrms", "payroll"]),
    ).first() is not None


def statutory_retention_blockers(db: Session, employee: Employee) -> list[str]:
    blockers: list[str] = []
    now = datetime.now(timezone.utc)
    for policy in db.query(DataRetentionPolicy).filter(DataRetentionPolicy.is_active.is_(True)).all():
        if policy.module not in {"employee", "hrms", "payroll"}:
            continue
        if policy.record_type not in {"employee", "employee_profile", "payroll"}:
            continue
        created_at = employee.created_at or now
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if created_at + timedelta(days=policy.retention_days) > now:
            blockers.append(f"{policy.module}:{policy.record_type}:{policy.retention_days}d")
    return blockers


def privacy_export_package(db: Session, employee: Employee) -> dict[str, Any]:
    employee_data = {}
    for field in PRIVACY_EXPORT_EMPLOYEE_FIELDS:
        employee_data[field] = _stringify(getattr(employee, field, None))
    sensitive = {
        field: {
            "masked": mask_field_value(field, getattr(employee, field, None)),
            "hash": value_hash(getattr(employee, field, None)),
        }
        for field in PRIVACY_SENSITIVE_EMPLOYEE_FIELDS
        if getattr(employee, field, None) not in (None, "")
    }
    audit_rows = db.query(FieldAuditEvent).filter(FieldAuditEvent.employee_id == employee.id).order_by(FieldAuditEvent.created_at.desc()).limit(300).all()
    return {
        "employee": employee_data,
        "sensitive_identifiers": sensitive,
        "field_audit": [
            {
                "id": row.id,
                "module": row.module,
                "field_name": row.field_name,
                "action": row.action,
                "old_value_masked": row.old_value_masked,
                "new_value_masked": row.new_value_masked,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in audit_rows
        ],
    }


def anonymize_employee(db: Session, employee: Employee, actor_user_id: int | None, reason: str | None = None) -> dict[str, Any]:
    changed: list[str] = []
    replacement = {
        "first_name": "Anonymized",
        "middle_name": None,
        "last_name": f"Employee {employee.id}",
        "work_email": f"anon-{employee.id}@redacted.local",
        "personal_email": None,
        "phone_number": None,
        "alternate_phone": None,
        "account_number": None,
        "ifsc_code": None,
        "pan_number": None,
        "aadhaar_number": None,
        "bank_name": None,
        "bank_branch": None,
        "present_address": None,
        "permanent_address": None,
        "status": "Anonymized",
    }
    for field, new_value in replacement.items():
        old_value = getattr(employee, field, None)
        if old_value != new_value:
            record_field_audit(
                db,
                module="employee",
                entity_type="employee",
                entity_id=employee.id,
                employee_id=employee.id,
                field_name=field,
                old_value=old_value,
                new_value=new_value,
                actor_user_id=actor_user_id,
                action="privacy_anonymized",
                reason=reason,
            )
            setattr(employee, field, new_value)
            changed.append(field)
    return {"employee_id": employee.id, "anonymized_fields": changed}


def dumps_result(value: dict[str, Any]) -> str:
    return json.dumps(value, default=str, sort_keys=True)
