from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.apps.admin_security.models import AdminAuditLog, AdminFieldSecurity, AdminProfile
from app.models.user import User


def permissions_for(user: User) -> set[str]:
    if user.is_superuser:
        return {"*"}
    return {p.name for p in (user.role.permissions if user.role else [])}


def audit(db: Session, user: User, event_type: str, module_name: str | None = None, resource_type: str | None = None, resource_id: int | None = None, detail: dict[str, Any] | None = None, status: str = "completed") -> None:
    db.add(AdminAuditLog(actor_user_id=user.id, event_type=event_type, module_name=module_name, resource_type=resource_type, resource_id=resource_id, detail_json=detail or {}, status=status))


def user_profile(db: Session, user: User) -> AdminProfile | None:
    role_name = user.role.name if user.role else None
    if not role_name:
        return None
    return db.query(AdminProfile).filter(AdminProfile.name.in_([role_name, role_name.replace("_", " ").title()]), AdminProfile.active.is_(True)).first()


def field_rules(db: Session, module_name: str, user: User) -> list[AdminFieldSecurity]:
    profile = user_profile(db, user)
    if not profile:
        return []
    return db.query(AdminFieldSecurity).filter(AdminFieldSecurity.module_name == module_name, AdminFieldSecurity.profile_id == profile.id).all()


def apply_field_security(db: Session, module_name: str, data: dict[str, Any], user: User) -> dict[str, Any]:
    result = dict(data)
    for rule in field_rules(db, module_name, user):
        if rule.field_name not in result:
            continue
        if not rule.can_view:
            result.pop(rule.field_name, None)
        elif rule.mask_value:
            result[rule.field_name] = "********"
    return result


def assert_editable_fields(db: Session, module_name: str, payload: dict[str, Any], user: User) -> None:
    blocked = []
    for rule in field_rules(db, module_name, user):
        if rule.field_name in payload and (not rule.can_view or not rule.can_edit):
            blocked.append(rule.field_name)
    if blocked:
        raise HTTPException(status_code=403, detail=f"Field update blocked by field-level security: {', '.join(sorted(blocked))}")
