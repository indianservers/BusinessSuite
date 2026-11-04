"""Employee-scoped adapter over the existing platform field/value tables."""
from types import SimpleNamespace
from fastapi import HTTPException
from app.models.platform import CustomFieldDefinition, CustomFieldValue
from app.core.masking import can_view_sensitive_employee


def role_allowed(raw, actor):
    if not raw or actor.is_superuser:
        return True
    return getattr(getattr(actor, "role", None), "name", "").casefold() in {v.strip().casefold() for v in raw.split(",")}


def definitions(db, actor, employee_id=None):
    rows = db.query(CustomFieldDefinition).filter(CustomFieldDefinition.module.in_(["employees", "employee"]), CustomFieldDefinition.is_active.is_(True)).order_by(CustomFieldDefinition.display_order, CustomFieldDefinition.id).all()
    return [f for f in rows if role_allowed(f.visible_to_roles, actor) and (not f.is_sensitive or can_view_sensitive_employee(actor, employee_id))]


def serialize(db, actor, employee_id=None):
    fields = definitions(db, actor, employee_id)
    values = {row.definition_id: row.value_json if row.value_json is not None else row.value_text for row in db.query(CustomFieldValue).filter(CustomFieldValue.entity_type == "employee", CustomFieldValue.entity_id == employee_id)} if employee_id else {}
    return {"items": [{"id": f.id, "fieldKey": f.field_key, "fieldName": f.label, "fieldType": f.field_type.lower().replace(" ", "_"), "options": f.options_json, "section": f.section, "isRequired": f.is_required, "editable": role_allowed(f.editable_by_roles, actor), "value": values.get(f.id)} for f in fields]}


def save(db, actor, employee, incoming, *, validate_only=False):
    from app.apps.crm.api.router import _custom_field_storage
    fields = definitions(db, actor, employee.id)
    known = {f.field_key: f for f in fields}
    if set(incoming) - set(known):
        raise HTTPException(422, "Unknown or restricted employee custom field")
    for field in fields:
        if not role_allowed(field.editable_by_roles, actor):
            if field.field_key in incoming: raise HTTPException(403, "Custom field is read-only")
            continue
        row = db.query(CustomFieldValue).filter_by(definition_id=field.id, entity_type="employee", entity_id=employee.id).first()
        provided = field.field_key in incoming
        value = incoming[field.field_key] if provided else row.value_json if row and row.value_json is not None else row.value_text if row else None
        if not provided:
            if field.is_required and (value is None or value == "" or value == []):
                raise HTTPException(422,f"{field.label} is required")
            continue
        kind = field.field_type.lower().replace(" ", "_")
        kind = {"textbox": "text", "textarea": "long_text", "select": "dropdown", "boolean": "checkbox"}.get(kind, kind)
        normalized = _custom_field_storage(SimpleNamespace(field_type=kind, options_json=field.options_json, is_required=field.is_required, label=field.label), value)
        if not provided or validate_only: continue
        if row is None:
            row = CustomFieldValue(definition_id=field.id, entity_type="employee", entity_id=employee.id)
            db.add(row)
        # Retain typed JSON (including false/zero) and the existing scalar text projection.
        row.value_json = value
        row.value_text = normalized.get("value_text")
        row.updated_by = actor.id
