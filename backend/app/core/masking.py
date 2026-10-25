from app.access.catalog import permission_objects
from typing import Any

from app.models.user import User
from app.schemas.employee import EmployeeListSchema, EmployeeSchema


SENSITIVE_EMPLOYEE_FIELDS = {
    "date_of_birth",
    "marital_status",
    "blood_group",
    "religion",
    "category",
    "personal_email",
    "phone_number",
    "alternate_phone",
    "emergency_contact_name",
    "emergency_contact_number",
    "emergency_contact_relation",
    "present_address",
    "permanent_address",
    "present_city",
    "present_state",
    "present_pincode",
    "permanent_city",
    "permanent_state",
    "permanent_pincode",
    "bank_name",
    "bank_branch",
    "account_number",
    "ifsc_code",
    "pan_number",
    "aadhaar_number",
    "uan_number",
    "pf_number",
    "esic_number",
    "family_information",
    "health_information",
}


LIST_SENSITIVE_EMPLOYEE_FIELDS = {"personal_email", "phone_number"}


def user_has_permission(user: User, permission: str) -> bool:
    if user.is_superuser:
        return True
    return permission in {p.name for p in (permission_objects(user))}


def can_view_sensitive_employee(user: User, employee_id: int | None = None) -> bool:
    if user_has_permission(user, "employee_sensitive_view"):
        return True
    if employee_id is not None and user.employee and user.employee.id == employee_id:
        return True
    return False


def mask_email(value: str | None) -> str | None:
    if not value or "@" not in value:
        return mask_text(value)
    local, domain = value.split("@", 1)
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}{'*' * max(len(local) - len(visible), 3)}@{domain}"


def mask_identifier(value: Any, visible: int = 4) -> str | None:
    if value in (None, ""):
        return value
    text = str(value)
    if len(text) <= visible:
        return "*" * len(text)
    return f"{'*' * (len(text) - visible)}{text[-visible:]}"


def mask_phone(value: str | None) -> str | None:
    return mask_identifier(value, visible=4)


def mask_text(value: str | None) -> str | None:
    if value in (None, ""):
        return value
    return "Restricted"


def _mask_value(field: str, value: Any) -> Any:
    if field == "personal_email":
        return mask_email(value)
    if field in {
        "phone_number",
        "alternate_phone",
        "emergency_contact_number",
        "account_number",
        "pan_number",
        "aadhaar_number",
        "uan_number",
        "pf_number",
        "esic_number",
    }:
        return mask_identifier(value)
    if field in {"date_of_birth"}:
        return None
    return mask_text(value)


def mask_employee_detail(employee: Any, user: User) -> dict[str, Any]:
    data = EmployeeSchema.model_validate(employee).model_dump()
    if can_view_sensitive_employee(user, employee.id):
        return data
    # Document URLs and metadata reveal restricted identity and HR records.
    data['documents'] = []
    for field in SENSITIVE_EMPLOYEE_FIELDS:
        if field in data:
            data[field] = _mask_value(field, data[field])
    return data


def mask_employee_list_item(employee: Any, user: User) -> dict[str, Any]:
    data = EmployeeListSchema.model_validate(employee).model_dump()
    if can_view_sensitive_employee(user, employee.id):
        return data
    for field in LIST_SENSITIVE_EMPLOYEE_FIELDS:
        if field in data:
            data[field] = _mask_value(field, data[field])
    return data
