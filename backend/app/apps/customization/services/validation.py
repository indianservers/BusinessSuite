from __future__ import annotations

import ast
import re
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.apps.customization.models import CustomizationField, CustomizationRecord, CustomizationValidationRule


FIELD_TYPES = {
    "text", "textarea", "rich_text", "number", "decimal", "percentage", "currency", "date", "datetime",
    "checkbox", "picklist", "multi_select", "lookup", "user_lookup", "file", "auto_number", "formula",
    "rollup", "email", "phone", "url",
}

SAFE_ACTION_TYPES = {"open_url", "create_task", "submit_approval", "webhook", "timeline_event", "noop"}
ROLLUP_FUNCTIONS = {"sum", "count", "avg", "min", "max"}
VALIDATION_OPERATORS = {
    "equals", "not_equals", "contains", "greater_than", "less_than", "greater_or_equal",
    "less_or_equal", "is_empty", "is_not_empty", "in", "not_in",
}


def validate_api_name(value: str, label: str = "API name") -> None:
    if not re.match(r"^[a-z][a-z0-9_]*$", value or ""):
        raise HTTPException(status_code=400, detail=f"{label} must start with a lowercase letter and contain only lowercase letters, numbers, and underscores")


def validate_field_metadata(field_type: str, formula_expression: str | None = None, rollup_config_json: dict[str, Any] | None = None) -> None:
    if field_type not in FIELD_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported field type: {field_type}")
    if field_type == "formula" and not formula_expression:
        raise HTTPException(status_code=400, detail="Formula fields require formula_expression")
    if field_type == "formula" and formula_expression:
        validate_formula_expression(formula_expression)
    if field_type == "rollup":
        validate_rollup_config(rollup_config_json)


def validate_rollup_config(config: dict[str, Any] | None) -> None:
    if not config:
        raise HTTPException(status_code=400, detail="Rollup config is required")
    if config.get("aggregate_function") not in ROLLUP_FUNCTIONS:
        raise HTTPException(status_code=400, detail="Unsupported rollup aggregate function")
    if not config.get("related_module_name"):
        raise HTTPException(status_code=400, detail="Rollup related_module_name is required")


def validate_formula_expression(expression: str) -> None:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid formula syntax: {exc.msg}") from exc
    allowed = (
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
        ast.USub, ast.UAdd, ast.Name, ast.Load, ast.Constant, ast.Call,
    )
    allowed_functions = {"min", "max", "round", "abs"}
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            raise HTTPException(status_code=400, detail="Formula contains unsupported syntax")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in allowed_functions:
                raise HTTPException(status_code=400, detail="Formula contains unsupported function")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise HTTPException(status_code=400, detail="Formula contains unsafe name")


def evaluate_formula(expression: str, record: dict[str, Any]) -> Any:
    validate_formula_expression(expression)
    variables = {key: Decimal(str(value)) if isinstance(value, (int, float, str)) and str(value).replace(".", "", 1).replace("-", "", 1).isdigit() else value for key, value in record.items()}
    try:
        return eval(compile(ast.parse(expression, mode="eval"), "<customization_formula>", "eval"), {"__builtins__": {}, "min": min, "max": max, "round": round, "abs": abs}, variables)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Formula evaluation failed: {exc}") from exc


def validate_rule_condition(condition: dict[str, Any]) -> None:
    if condition.get("operator") not in VALIDATION_OPERATORS:
        raise HTTPException(status_code=400, detail="Unsupported validation operator")
    if "field" not in condition:
        raise HTTPException(status_code=400, detail="Validation field is required")


def evaluate_condition(condition: dict[str, Any], record: dict[str, Any]) -> bool:
    validate_rule_condition(condition)
    actual = record.get(condition["field"])
    expected = condition.get("value")
    operator = condition["operator"]
    if operator == "equals":
        return actual == expected
    if operator == "not_equals":
        return actual != expected
    if operator == "contains":
        return str(expected).lower() in str(actual or "").lower()
    if operator == "greater_than":
        return float(actual or 0) > float(expected)
    if operator == "less_than":
        return float(actual or 0) < float(expected)
    if operator == "greater_or_equal":
        return float(actual or 0) >= float(expected)
    if operator == "less_or_equal":
        return float(actual or 0) <= float(expected)
    if operator == "is_empty":
        return actual in (None, "", [], {})
    if operator == "is_not_empty":
        return actual not in (None, "", [], {})
    if operator == "in":
        return actual in (expected or [])
    if operator == "not_in":
        return actual not in (expected or [])
    return False


def validate_field_value(db: Session, field: CustomizationField, value: Any, record_id: int | None = None) -> None:
    if field.required and value in (None, "", [], {}):
        raise HTTPException(status_code=400, detail=f"{field.field_label} is required")
    if value in (None, ""):
        return
    if field.field_type in {"number"} and not isinstance(value, int):
        raise HTTPException(status_code=400, detail=f"{field.field_label} must be a whole number")
    if field.field_type in {"decimal", "percentage", "currency"}:
        try:
            Decimal(str(value))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"{field.field_label} must be numeric") from exc
    if field.field_type == "checkbox" and not isinstance(value, bool):
        raise HTTPException(status_code=400, detail=f"{field.field_label} must be true or false")
    if field.field_type == "email" and "@" not in str(value):
        raise HTTPException(status_code=400, detail=f"{field.field_label} must be an email")
    if field.field_type == "url" and not str(value).startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail=f"{field.field_label} must be a URL")
    if field.field_type == "picklist":
        allowed = [item.get("value") for item in (field.validation_json or {}).get("options", [])]
        if allowed and value not in allowed:
            raise HTTPException(status_code=400, detail=f"{field.field_label} must be one of: {', '.join(allowed)}")
    if field.unique:
        records = db.query(CustomizationRecord).filter(CustomizationRecord.module_api_name == field.module_name, CustomizationRecord.deleted_at == None).all()
        for record in records:
            if record_id and record.id == record_id:
                continue
            if str((record.values_json or {}).get(field.field_api_name)) == str(value):
                raise HTTPException(status_code=400, detail=f"{field.field_label} must be unique")


def validate_record_payload(db: Session, module_name: str, values: dict[str, Any], record_id: int | None = None) -> None:
    fields = db.query(CustomizationField).filter(CustomizationField.module_name == module_name, CustomizationField.visible == True).all()
    field_map = {field.field_api_name: field for field in fields}
    for field in fields:
        validate_field_value(db, field, values.get(field.field_api_name, field.default_value), record_id)
    unknown = [key for key in values if key not in field_map]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown custom fields: {', '.join(sorted(unknown))}")
    rules = db.query(CustomizationValidationRule).filter(CustomizationValidationRule.module_name == module_name, CustomizationValidationRule.active == True).all()
    for rule in rules:
        if evaluate_condition(rule.condition_json, values):
            raise HTTPException(status_code=400, detail=rule.error_message)
