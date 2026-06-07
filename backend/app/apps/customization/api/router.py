from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.apps.customization.models import (
    CustomizationAuditLog,
    CustomizationButton,
    CustomizationField,
    CustomizationFieldOption,
    CustomizationFormulaField,
    CustomizationGlobalPicklist,
    CustomizationGlobalPicklistValue,
    CustomizationKanbanView,
    CustomizationLayout,
    CustomizationLayoutField,
    CustomizationLayoutSection,
    CustomizationModule,
    CustomizationRecord,
    CustomizationRecordValue,
    CustomizationRelatedList,
    CustomizationRollupField,
    CustomizationValidationRule,
    CustomizationView,
)
from app.apps.customization.schemas import (
    ButtonExecutePayload,
    ButtonPayload,
    DynamicRecordPayload,
    FieldPayload,
    FieldValidatePayload,
    FormulaPayload,
    FormulaTestPayload,
    KanbanPayload,
    LayoutPayload,
    LayoutReorderPayload,
    LayoutSectionPayload,
    ModulePayload,
    PicklistPayload,
    RelatedListPayload,
    RollupPayload,
    RuleTestPayload,
    ValidationRulePayload,
    ViewPayload,
)
from app.apps.customization.services.validation import (
    SAFE_ACTION_TYPES,
    evaluate_condition,
    evaluate_formula,
    validate_api_name,
    validate_field_metadata,
    validate_field_value,
    validate_formula_expression,
    validate_record_payload,
    validate_rollup_config,
    validate_rule_condition,
)
from app.core.deps import RequirePermission, get_db
from app.models.user import User


router = APIRouter(tags=["Customization Studio"])
customization_router = APIRouter(prefix="/customization", tags=["Customization Studio"])
dynamic_router = APIRouter(prefix="/custom", tags=["Dynamic Custom Records"])


def _serialize(item) -> dict[str, Any] | None:
    if item is None:
        return None
    data: dict[str, Any] = {}
    for column in item.__table__.columns:
        value = getattr(item, column.name)
        if isinstance(value, datetime):
            value = value.isoformat()
        data[column.name] = value
    return data


def _audit(db: Session, user: User, entity_type: str, entity_id: int | None, action: str, before=None, after=None) -> None:
    db.add(CustomizationAuditLog(entity_type=entity_type, entity_id=entity_id, action=action, actor_user_id=user.id, before_json=before, after_json=after))


def _require_module(db: Session, module_api_name: str) -> CustomizationModule:
    module = db.query(CustomizationModule).filter(CustomizationModule.module_api_name == module_api_name, CustomizationModule.enabled == True).first()
    if not module:
        raise HTTPException(status_code=404, detail="Custom module not found")
    return module


@customization_router.get("/module-info")
def module_info(current_user: User = Depends(RequirePermission("customization_view", "customization_manage"))):
    return {"module": "customization", "title": "Customization Studio", "permissions": ["customization_view", "customization_manage"]}


@customization_router.get("/modules")
def list_modules(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_view", "customization_manage"))):
    items = db.query(CustomizationModule).order_by(CustomizationModule.module_label).all()
    return {"items": [_serialize(item) for item in items], "total": len(items)}


@customization_router.post("/modules", status_code=201)
def create_module(data: ModulePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_modules_manage", "customization_manage"))):
    validate_api_name(data.module_api_name, "Module API name")
    if db.query(CustomizationModule).filter(CustomizationModule.module_api_name == data.module_api_name).first():
        raise HTTPException(status_code=400, detail="Module API name already exists")
    item = CustomizationModule(**data.model_dump(), created_by=current_user.id)
    db.add(item)
    db.flush()
    _audit(db, current_user, "module", item.id, "created", after=data.model_dump())
    db.commit()
    db.refresh(item)
    return _serialize(item)


@customization_router.get("/modules/{module_id}")
def get_module(module_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_view", "customization_manage"))):
    item = db.query(CustomizationModule).filter(CustomizationModule.id == module_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Module not found")
    return _serialize(item)


@customization_router.put("/modules/{module_id}")
def update_module(module_id: int, data: ModulePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_modules_manage", "customization_manage"))):
    item = db.query(CustomizationModule).filter(CustomizationModule.id == module_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Module not found")
    before = _serialize(item)
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    _audit(db, current_user, "module", item.id, "updated", before=before, after=data.model_dump())
    db.commit()
    return _serialize(item)


@customization_router.delete("/modules/{module_id}", status_code=204)
def delete_module(module_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_modules_manage", "customization_manage"))):
    item = db.query(CustomizationModule).filter(CustomizationModule.id == module_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Module not found")
    before = _serialize(item)
    item.enabled = False
    _audit(db, current_user, "module", item.id, "disabled", before=before, after=_serialize(item))
    db.commit()
    return None


@customization_router.get("/fields")
def list_fields(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_view", "customization_manage"))):
    items = db.query(CustomizationField).order_by(CustomizationField.module_name, CustomizationField.field_label).all()
    return {"items": [_serialize(item) for item in items], "total": len(items)}


@customization_router.post("/fields", status_code=201)
def create_field(data: FieldPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_fields_manage", "customization_manage"))):
    validate_api_name(data.field_api_name, "Field API name")
    validate_field_metadata(data.field_type, data.formula_expression, data.rollup_config_json)
    if db.query(CustomizationField).filter(CustomizationField.module_name == data.module_name, CustomizationField.field_api_name == data.field_api_name).first():
        raise HTTPException(status_code=400, detail="Field API name already exists for module")
    validation_json = dict(data.validation_json or {})
    if data.options:
        validation_json["options"] = data.options
    item = CustomizationField(**data.model_dump(exclude={"options", "validation_json"}), validation_json=validation_json, created_by=current_user.id)
    db.add(item)
    db.flush()
    for index, option in enumerate(data.options):
        db.add(CustomizationFieldOption(field_id=item.id, value=option["value"], label=option.get("label") or option["value"], color=option.get("color"), order_index=option.get("order_index", index), active=option.get("active", True)))
    _audit(db, current_user, "field", item.id, "created", after=data.model_dump())
    db.commit()
    db.refresh(item)
    return _serialize(item)


@customization_router.get("/fields/{field_id}")
def get_field(field_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_view", "customization_manage"))):
    item = db.query(CustomizationField).filter(CustomizationField.id == field_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Field not found")
    data = _serialize(item)
    data["options"] = [_serialize(option) for option in db.query(CustomizationFieldOption).filter(CustomizationFieldOption.field_id == field_id).order_by(CustomizationFieldOption.order_index).all()]
    return data


@customization_router.put("/fields/{field_id}")
def update_field(field_id: int, data: FieldPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_fields_manage", "customization_manage"))):
    item = db.query(CustomizationField).filter(CustomizationField.id == field_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Field not found")
    validate_field_metadata(data.field_type, data.formula_expression, data.rollup_config_json)
    before = _serialize(item)
    for key, value in data.model_dump(exclude={"options"}).items():
        setattr(item, key, value)
    _audit(db, current_user, "field", item.id, "updated", before=before, after=data.model_dump())
    db.commit()
    return _serialize(item)


@customization_router.delete("/fields/{field_id}", status_code=204)
def delete_field(field_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_fields_manage", "customization_manage"))):
    item = db.query(CustomizationField).filter(CustomizationField.id == field_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Field not found")
    before = _serialize(item)
    item.visible = False
    item.editable = False
    _audit(db, current_user, "field", item.id, "disabled", before=before, after=_serialize(item))
    db.commit()
    return None


@customization_router.post("/fields/{field_id}/validate")
def validate_field(field_id: int, data: FieldValidatePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_view", "customization_manage"))):
    field = db.query(CustomizationField).filter(CustomizationField.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    validate_field_value(db, field, data.value, data.record_id)
    return {"valid": True}


@customization_router.get("/layouts")
def list_layouts(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_view", "customization_manage"))):
    items = db.query(CustomizationLayout).order_by(CustomizationLayout.module_name, CustomizationLayout.name).all()
    return {"items": [_serialize(item) for item in items], "total": len(items)}


@customization_router.post("/layouts", status_code=201)
def create_layout(data: LayoutPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_layouts_manage", "customization_manage"))):
    item = CustomizationLayout(**data.model_dump(), created_by=current_user.id)
    db.add(item)
    db.flush()
    _audit(db, current_user, "layout", item.id, "created", after=data.model_dump())
    db.commit()
    return _serialize(item)


@customization_router.get("/layouts/{layout_id}")
def get_layout(layout_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_view", "customization_manage"))):
    item = db.query(CustomizationLayout).filter(CustomizationLayout.id == layout_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Layout not found")
    data = _serialize(item)
    data["sections"] = [_serialize(section) for section in db.query(CustomizationLayoutSection).filter(CustomizationLayoutSection.layout_id == layout_id).order_by(CustomizationLayoutSection.order_index).all()]
    data["fields"] = [_serialize(field) for field in db.query(CustomizationLayoutField).filter(CustomizationLayoutField.layout_id == layout_id).order_by(CustomizationLayoutField.order_index).all()]
    return data


@customization_router.put("/layouts/{layout_id}")
def update_layout(layout_id: int, data: LayoutPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_layouts_manage", "customization_manage"))):
    item = db.query(CustomizationLayout).filter(CustomizationLayout.id == layout_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Layout not found")
    before = _serialize(item)
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    _audit(db, current_user, "layout", item.id, "updated", before=before, after=data.model_dump())
    db.commit()
    return _serialize(item)


@customization_router.post("/layouts/{layout_id}/sections", status_code=201)
def add_layout_section(layout_id: int, data: LayoutSectionPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_layouts_manage", "customization_manage"))):
    if not db.query(CustomizationLayout).filter(CustomizationLayout.id == layout_id).first():
        raise HTTPException(status_code=404, detail="Layout not found")
    item = CustomizationLayoutSection(layout_id=layout_id, **data.model_dump())
    db.add(item)
    db.flush()
    _audit(db, current_user, "layout_section", item.id, "created", after=data.model_dump())
    db.commit()
    return _serialize(item)


@customization_router.post("/layouts/{layout_id}/fields/reorder")
def reorder_layout_fields(layout_id: int, data: LayoutReorderPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_layouts_manage", "customization_manage"))):
    if not db.query(CustomizationLayout).filter(CustomizationLayout.id == layout_id).first():
        raise HTTPException(status_code=404, detail="Layout not found")
    db.query(CustomizationLayoutField).filter(CustomizationLayoutField.layout_id == layout_id).delete()
    for index, field in enumerate(data.fields):
        if not db.query(CustomizationField).filter(CustomizationField.id == field["field_id"]).first():
            raise HTTPException(status_code=404, detail=f"Field {field['field_id']} not found")
        db.add(CustomizationLayoutField(layout_id=layout_id, section_id=field.get("section_id"), field_id=field["field_id"], order_index=field.get("order_index", index), required_override=field.get("required_override"), readonly=field.get("readonly", False), hidden=field.get("hidden", False), role_visibility_json=field.get("role_visibility_json")))
    _audit(db, current_user, "layout", layout_id, "fields_reordered", after=data.model_dump())
    db.commit()
    return {"status": "updated", "count": len(data.fields)}


def _crud_collection(model, payload_model, permission: str, entity_type: str):
    @customization_router.get(f"/{entity_type}")
    def list_items(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_view", "customization_manage"))):
        items = db.query(model).order_by(model.id.desc()).all()
        return {"items": [_serialize(item) for item in items], "total": len(items)}

    @customization_router.post(f"/{entity_type}", status_code=201)
    def create_item(data: dict[str, Any], db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(permission, "customization_manage"))):
        payload = payload_model.model_validate(data).model_dump()
        if entity_type == "validation-rules":
            validate_rule_condition(payload["condition_json"])
        if entity_type == "formulas":
            validate_formula_expression(payload["expression"])
        if entity_type == "rollups":
            validate_rollup_config(
                {
                    "aggregate_function": payload["aggregate_function"],
                    "related_module_name": payload["related_module_name"],
                }
            )
        if entity_type == "buttons" and payload["action_type"] not in SAFE_ACTION_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported button action type")
        item = model(**payload, created_by=current_user.id)
        db.add(item)
        db.flush()
        _audit(db, current_user, entity_type, item.id, "created", after=payload)
        db.commit()
        return _serialize(item)


_crud_collection(CustomizationView, ViewPayload, "customization_views_manage", "views")
_crud_collection(CustomizationKanbanView, KanbanPayload, "customization_views_manage", "kanban")
_crud_collection(CustomizationValidationRule, ValidationRulePayload, "customization_validation_manage", "validation-rules")
_crud_collection(CustomizationRelatedList, RelatedListPayload, "customization_manage", "related-lists")
_crud_collection(CustomizationButton, ButtonPayload, "customization_buttons_manage", "buttons")
_crud_collection(CustomizationFormulaField, FormulaPayload, "customization_fields_manage", "formulas")
_crud_collection(CustomizationRollupField, RollupPayload, "customization_fields_manage", "rollups")


@customization_router.put("/views/{view_id}")
def update_view(view_id: int, data: ViewPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_views_manage", "customization_manage"))):
    item = db.query(CustomizationView).filter(CustomizationView.id == view_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="View not found")
    before = _serialize(item)
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    _audit(db, current_user, "view", item.id, "updated", before=before, after=data.model_dump())
    db.commit()
    return _serialize(item)


@customization_router.delete("/views/{view_id}", status_code=204)
def delete_view(view_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_views_manage", "customization_manage"))):
    item = db.query(CustomizationView).filter(CustomizationView.id == view_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="View not found")
    db.delete(item)
    _audit(db, current_user, "view", view_id, "deleted")
    db.commit()
    return None


@customization_router.post("/validation-rules/{rule_id}/test")
def test_validation_rule(rule_id: int, data: RuleTestPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_validation_manage", "customization_manage"))):
    rule = db.query(CustomizationValidationRule).filter(CustomizationValidationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Validation rule not found")
    triggered = evaluate_condition(rule.condition_json, data.record)
    return {"triggered": triggered, "error_message": rule.error_message if triggered else None}


@customization_router.post("/buttons/{button_id}/execute")
def execute_button(button_id: int, data: ButtonExecutePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_buttons_manage", "customization_manage"))):
    button = db.query(CustomizationButton).filter(CustomizationButton.id == button_id, CustomizationButton.active == True).first()
    if not button:
        raise HTTPException(status_code=404, detail="Button not found")
    if button.action_type not in SAFE_ACTION_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported button action type")
    _audit(db, current_user, "button", button.id, "executed", after={"record_id": data.record_id, "payload": data.payload})
    db.commit()
    return {"status": "executed", "action_type": button.action_type, "record_id": data.record_id}


@customization_router.get("/picklists")
def list_picklists(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_view", "customization_manage"))):
    items = db.query(CustomizationGlobalPicklist).order_by(CustomizationGlobalPicklist.label).all()
    return {"items": [_serialize(item) for item in items], "total": len(items)}


@customization_router.post("/picklists", status_code=201)
def create_picklist(data: PicklistPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_fields_manage", "customization_manage"))):
    validate_api_name(data.api_name, "Picklist API name")
    item = CustomizationGlobalPicklist(**data.model_dump(exclude={"values"}), created_by=current_user.id)
    db.add(item)
    db.flush()
    for index, value in enumerate(data.values):
        db.add(CustomizationGlobalPicklistValue(picklist_id=item.id, value=value["value"], label=value.get("label") or value["value"], order_index=value.get("order_index", index), active=value.get("active", True)))
    _audit(db, current_user, "picklist", item.id, "created", after=data.model_dump())
    db.commit()
    return _serialize(item)


@customization_router.post("/formulas/test")
def test_formula(data: FormulaTestPayload, current_user: User = Depends(RequirePermission("customization_view", "customization_manage"))):
    result = evaluate_formula(data.expression, data.record)
    return {"valid": True, "result": str(result)}


@customization_router.get("/audit-logs")
def audit_logs(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_view", "customization_manage"))):
    items = db.query(CustomizationAuditLog).order_by(CustomizationAuditLog.created_at.desc()).limit(200).all()
    return {"items": [_serialize(item) for item in items], "total": len(items)}


@dynamic_router.get("/{module_api_name}")
def list_dynamic_records(module_api_name: str, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_view", "customization_manage"))):
    _require_module(db, module_api_name)
    items = db.query(CustomizationRecord).filter(CustomizationRecord.module_api_name == module_api_name, CustomizationRecord.deleted_at == None).order_by(CustomizationRecord.created_at.desc()).all()
    return {"items": [_serialize(item) for item in items], "total": len(items)}


@dynamic_router.post("/{module_api_name}", status_code=201)
def create_dynamic_record(module_api_name: str, data: DynamicRecordPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_manage"))):
    _require_module(db, module_api_name)
    validate_record_payload(db, module_api_name, data.values)
    item = CustomizationRecord(module_api_name=module_api_name, owner_user_id=data.owner_user_id, values_json=data.values, created_by=current_user.id)
    db.add(item)
    db.flush()
    for field in db.query(CustomizationField).filter(CustomizationField.module_name == module_api_name).all():
        if field.field_api_name in data.values:
            db.add(CustomizationRecordValue(record_id=item.id, field_id=field.id, value_json=data.values[field.field_api_name], value_text=str(data.values[field.field_api_name]) if data.values[field.field_api_name] is not None else None))
    _audit(db, current_user, "dynamic_record", item.id, "created", after={"module": module_api_name, "values": data.values})
    db.commit()
    db.refresh(item)
    return _serialize(item)


@dynamic_router.get("/{module_api_name}/{record_id}")
def get_dynamic_record(module_api_name: str, record_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_view", "customization_manage"))):
    _require_module(db, module_api_name)
    item = db.query(CustomizationRecord).filter(CustomizationRecord.module_api_name == module_api_name, CustomizationRecord.id == record_id, CustomizationRecord.deleted_at == None).first()
    if not item:
        raise HTTPException(status_code=404, detail="Custom record not found")
    return _serialize(item)


@dynamic_router.put("/{module_api_name}/{record_id}")
def update_dynamic_record(module_api_name: str, record_id: int, data: DynamicRecordPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_manage"))):
    _require_module(db, module_api_name)
    item = db.query(CustomizationRecord).filter(CustomizationRecord.module_api_name == module_api_name, CustomizationRecord.id == record_id, CustomizationRecord.deleted_at == None).first()
    if not item:
        raise HTTPException(status_code=404, detail="Custom record not found")
    validate_record_payload(db, module_api_name, data.values, record_id)
    before = _serialize(item)
    item.values_json = data.values
    item.owner_user_id = data.owner_user_id
    item.updated_by = current_user.id
    _audit(db, current_user, "dynamic_record", item.id, "updated", before=before, after={"module": module_api_name, "values": data.values})
    db.commit()
    return _serialize(item)


@dynamic_router.delete("/{module_api_name}/{record_id}", status_code=204)
def delete_dynamic_record(module_api_name: str, record_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("customization_manage"))):
    _require_module(db, module_api_name)
    item = db.query(CustomizationRecord).filter(CustomizationRecord.module_api_name == module_api_name, CustomizationRecord.id == record_id, CustomizationRecord.deleted_at == None).first()
    if not item:
        raise HTTPException(status_code=404, detail="Custom record not found")
    before = _serialize(item)
    item.deleted_at = datetime.now(timezone.utc)
    _audit(db, current_user, "dynamic_record", item.id, "deleted", before=before)
    db.commit()
    return None


router.include_router(customization_router)
router.include_router(dynamic_router)
