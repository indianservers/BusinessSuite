"""Backward compatible presentation settings stored beside existing option values."""
from fastapi import HTTPException

PLACES = {"create", "edit", "quick_create", "detail"}
CHOICES = {"dropdown", "radio", "combobox", "multi_select"}


def validate_values(db, entity, organization_id, values, record_id=None):
    """Validate before record creation or any identity side effects."""
    from app.apps.crm.api import router as core
    core._validate_required_custom_fields(db, entity, record_id, organization_id, values)
    by_key = {}
    for field in core._custom_field_definitions(db, entity, organization_id):
        for key in (str(field.id), field.field_key, field.label, field.field_name):
            if key: by_key[key] = field
    for key, value in values.items():
        if str(key) not in by_key:
            raise HTTPException(422, f"Unknown custom field: {key}")
        core._custom_field_storage(by_key[str(key)], value)


def option_values(raw):
    if isinstance(raw,str):
        return [value.strip() for value in raw.replace("\n",",").split(",") if value.strip()]
    return raw.get("values", []) if isinstance(raw, dict) else raw or []


def validate_config(data, record=None):
    raw = data.get("options_json", record.options_json if record else [])
    values = option_values(raw)
    if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() or len(v) > 500 for v in values) or len(values) != len(set(values)):
        raise HTTPException(422, "Options must be unique non-empty text values")
    kind = data.get("field_type", record.field_type if record else "text")
    if kind in CHOICES and not values:
        raise HTTPException(422, "Choice fields require at least one option")
    ui = raw.get("ui", {}) if isinstance(raw, dict) else {}
    if not isinstance(ui, dict):
        raise HTTPException(422, "Invalid field presentation settings")
    places = ui.get("places", sorted(PLACES))
    if not isinstance(places, list) or any(not isinstance(p, str) or p not in PLACES for p in places):
        raise HTTPException(422, "Invalid places where shown")
    required = data.get("is_required", record.is_required if record else False)
    visible = data.get("is_visible", record.is_visible if record else True)
    if required and (not visible or not {"create", "quick_create"}.issubset(places)):
        raise HTTPException(422, "Required fields must be visible in create and quick-add forms")
    if record:
        for key in ("entity", "field_key", "field_type"):
            if key in data and data[key] != getattr(record, key):
                raise HTTPException(409, "Field type, identifier and entity cannot change; create a new field to preserve existing values")
        if kind in CHOICES and not set(option_values(record.options_json)).issubset(values):
            raise HTTPException(409, "Keep existing options to preserve saved record values")
