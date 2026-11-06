from __future__ import annotations
from app.core.input_validation import normalize_phone

import ast
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from app.core.input_validation import email_address, national_phone, calling_code
from urllib.parse import urlsplit
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.apps.customization.models import CustomizationField, CustomizationRecord, CustomizationValidationRule


FIELD_TYPES = {
    "text", "textarea", "rich_text", "number", "decimal", "percentage", "currency", "date", "datetime",
    "checkbox", "picklist", "radio", "combobox", "multi_select", "lookup", "user_lookup", "file", "auto_number", "formula",
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
    if config.get('aggregate_function') != 'count' and not config.get('aggregate_field'):
        raise HTTPException(422, 'Numeric rollups require an aggregate_field')
    if config.get('condition'):
        validate_rule_condition(config['condition'])


def validate_formula_expression(expression: str) -> None:
    from app.core.formula_limits import bounded_formula_tree
    bounded_formula_tree(expression)
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
    def numeric(value):
        if not isinstance(value, (int, float, Decimal, str)) or isinstance(value, str) and len(value) > 100:
            raise ValueError('Numeric input required')
        value = Decimal(str(int(value) if isinstance(value, bool) else value))
        if not value.is_finite() or abs(value) > Decimal('1e15'):
            raise ValueError('Numeric limit exceeded')
        return value

    def calculate(node):
        if isinstance(node, ast.Constant):
            return numeric(node.value)
        if isinstance(node, ast.Name):
            return numeric(record.get(node.id))
        if isinstance(node, ast.UnaryOp):
            value = calculate(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp):
            left, right = calculate(node.left), calculate(node.right)
            import operator
            operators = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Mod: operator.mod}
            return numeric(operators[type(node.op)](left, right))
        if isinstance(node, ast.Call):
            values = [calculate(arg) for arg in node.args]
            if node.func.id == 'round':
                if len(values) not in {1, 2}:
                    raise ValueError('round requires one or two arguments')
                places = values[1] if len(values) == 2 else Decimal(0)
                if places != int(places) or not -15 <= places <= 15:
                    raise ValueError('round precision must be an integer from -15 to 15')
                return numeric(round(values[0], int(places)))
            return numeric({'min': min, 'max': max, 'abs': abs}[node.func.id](*values))
        raise ValueError('Unsupported formula syntax')
    try:
        return calculate(ast.parse(expression, mode='eval').body)
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
    if field.field_type in {'lookup', 'user_lookup'}:
        if type(value) is not int or value < 1:
            raise HTTPException(422, f'{field.field_label} requires a record identifier')
        if field.field_type == 'lookup':
            from app.apps.customization.services.records import record
            record(db, field.lookup_module, value, lock=True)
        else:
            from app.models.user import User
            if not db.query(User).filter_by(id=value, is_active=True).first():
                raise HTTPException(422, 'Choose an active user in your company')
    if field.field_type in {'date', 'datetime'}:
        try:
            if not isinstance(value, str):
                raise ValueError()
            (date.fromisoformat if field.field_type == 'date' else datetime.fromisoformat)(value)
        except ValueError:
            raise HTTPException(422, f'{field.field_label} requires a valid ISO {field.field_type}') from None
    if field.field_type == 'multi_select':
        allowed = {o['value'] for o in (field.validation_json or {}).get('options', [])}
        if not isinstance(value, list) or any(not isinstance(v, str) for v in value) or len(value) != len(set(value)) or (allowed and set(value) - allowed):
            raise HTTPException(422, f'{field.field_label} requires distinct configured options')
    if field.field_type in {"number"} and (isinstance(value,bool) or not isinstance(value, int)):
        raise HTTPException(status_code=400, detail=f"{field.field_label} must be a whole number")
    if field.field_type in {"decimal", "percentage", "currency"}:
        try:
            numeric=Decimal(str(value))
            if isinstance(value,bool) or not numeric.is_finite():raise ValueError()
            if field.field_type=='percentage' and not 0<=numeric<=100:raise ValueError()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"{field.field_label} must be numeric") from exc
    if field.field_type == "checkbox" and not isinstance(value, bool):
        raise HTTPException(status_code=400, detail=f"{field.field_label} must be true or false")
    if field.field_type == "email":
        try:email_address(value)
        except ValueError as exc:raise HTTPException(422,detail=str(exc)) from None
    if field.field_type == "url":
        try:
            parsed=urlsplit(value)
            if parsed.scheme not in {'http','https'} or not parsed.hostname or any(c.isspace() for c in value):raise ValueError()
        except (TypeError,ValueError):raise HTTPException(422,detail=f'{field.field_label} must be a complete HTTP or HTTPS URL') from None
    if field.field_type in {"picklist", "radio", "combobox"}:
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


def validate_record_payload(db: Session, module_name: str, values: dict[str, Any], record_id: int | None = None, *, run_rules: bool = True) -> None:
    fields = db.query(CustomizationField).filter(CustomizationField.module_name == module_name).all()
    field_map = {field.field_api_name: field for field in fields}
    existing = db.get(CustomizationRecord,record_id) if record_id else None
    previous = existing.values_json or {} if existing else {}
    for field in fields:
        if field.field_type in {'formula', 'rollup', 'auto_number'}:
            continue
        if not field.visible or not field.editable:
            if field.field_api_name in values and values[field.field_api_name]!=previous.get(field.field_api_name):
                raise HTTPException(403,f"{field.field_label} is read-only or hidden")
            continue
        validate_field_value(db, field, values.get(field.field_api_name, field.default_value), record_id)
    companions=set()
    for field in fields:
        if field.field_type=='phone':
            key=field.field_api_name
            companions.add(key+'_country_code')
            if values.get(key) not in (None,''):
                try:normalize_phone(values[key],values.get(key+'_country_code'))
                except ValueError as exc:raise HTTPException(422,detail=[{'loc':['body',key],'msg':str(exc),'type':'value_error'}]) from None
    from app.apps.customization.services.records import definitions
    _, formulas, rollups = definitions(db, module_name)
    unknown = [key for key in values if key not in field_map and key not in companions and key not in formulas and key not in rollups]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown custom fields: {', '.join(sorted(unknown))}")
    if not run_rules:
        return
    rules = db.query(CustomizationValidationRule).filter(CustomizationValidationRule.module_name == module_name, CustomizationValidationRule.active == True).all()
    for rule in rules:
        if evaluate_condition(rule.condition_json, values):
            raise HTTPException(status_code=400, detail=rule.error_message)
