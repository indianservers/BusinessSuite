"""Runtime for custom records. All reads use the caller's scoped ORM session.

Computed values are evaluated on read, not cached in JSON. Child edits, moves and
deletions therefore affect parent totals immediately without stale stored totals.
"""
import ast
import json
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import String, cast

from app.apps.customization.models import (
    CustomizationField, CustomizationFormulaField, CustomizationModule,
    CustomizationRecord, CustomizationRecordValue, CustomizationRollupField,
)
from app.apps.customization.services.validation import evaluate_condition, evaluate_formula


def module(db, name, lock=False):
    query = db.query(CustomizationModule).filter_by(module_api_name=name, enabled=True)
    row = (query.with_for_update() if lock else query).first()
    if not row:
        raise HTTPException(404, "Custom module not found")
    return row


def record(db, name, identifier, lock=False):
    module(db, name)
    query = db.query(CustomizationRecord).filter_by(module_api_name=name, id=identifier, deleted_at=None)
    row = (query.with_for_update() if lock else query).first()
    if not row:
        raise HTTPException(404, "Custom record not found")
    return row


def definitions(db, name):
    fields = db.query(CustomizationField).filter_by(module_name=name).all()
    formulas = {f.field_api_name: f.formula_expression for f in fields if f.field_type == "formula"}
    rollups = {f.field_api_name: f.rollup_config_json for f in fields if f.field_type == "rollup"}
    for row in db.query(CustomizationFormulaField).filter_by(module_name=name, active=True).all():
        if row.field_api_name in formulas and formulas[row.field_api_name] != row.expression:
            raise HTTPException(422, "Conflicting formula definitions")
        formulas[row.field_api_name] = row.expression
    for row in db.query(CustomizationRollupField).filter_by(module_name=name, active=True).all():
        rollups.setdefault(row.field_api_name, dict(related_module_name=row.related_module_name,
            aggregate_function=row.aggregate_function, aggregate_field=row.aggregate_field,
            **(row.filter_json or {})))
    if set(formulas) & set(rollups):
        raise HTTPException(422, "A computed field cannot be both a formula and a rollup")
    return fields, formulas, rollups


def json_scalar(value):
    if isinstance(value, Decimal):
        if not value.is_finite() or abs(value) > Decimal('1e15'):
            raise HTTPException(422, "Computed value exceeds numeric limits")
        # Decimal strings preserve precision across JSON and the browser.
        return format(value, 'f')
    return value


class Reader:
    def __init__(self, db):
        self.db, self.cache, self.active, self.count = db, {}, set(), 0
        self.metadata = {}

    def values(self, row):
        key = (row.module_api_name, row.id)
        if key in self.cache:
            return self.cache[key]
        if key in self.active or len(self.active) >= 16:
            raise HTTPException(422, "Computed relationship cycle or depth limit exceeded")
        self.count += 1
        if self.count > 5000:
            raise HTTPException(422, "Computed record evaluation exceeds limits")
        self.active.add(key)
        try:
            if row.module_api_name not in self.metadata:
                self.metadata[row.module_api_name] = definitions(self.db, row.module_api_name)
            fields, formulas, rollups = self.metadata[row.module_api_name]
            values = dict(row.values_json or {})
            for name, config in rollups.items():
                values[name] = self.aggregate(row, config or {})
            pending = dict(formulas)
            while pending:
                progressed = False
                for name, expression in list(pending.items()):
                    dependencies = {n.id for n in ast.walk(ast.parse(expression, mode='eval')) if isinstance(n, ast.Name)} - {'min', 'max', 'round', 'abs'}
                    if dependencies & set(pending):
                        continue
                    if dependencies - set(values):
                        raise HTTPException(422, f"Formula {name} references missing values")
                    values[name] = json_scalar(evaluate_formula(expression, values))
                    del pending[name]
                    progressed = True
                if not progressed:
                    raise HTTPException(422, "Formula dependency cycle")
            self.cache[key] = values
            return values
        finally:
            self.active.remove(key)

    def aggregate(self, parent, config):
        related = config.get('related_module_name')
        module(self.db, related)
        links = self.db.query(CustomizationField).filter_by(module_name=related, field_type='lookup', lookup_module=parent.module_api_name).all()
        lookup = config.get('lookup_field')
        if lookup:
            links = [f for f in links if f.field_api_name == lookup]
        if len(links) != 1:
            raise HTTPException(422, "Rollup requires one unambiguous lookup_field to its parent")
        query = self.db.query(CustomizationRecord).filter(
            CustomizationRecord.module_api_name == related,
            CustomizationRecord.deleted_at.is_(None),
            CustomizationRecord.values_json[links[0].field_api_name].as_integer() == parent.id,
        )
        rows = query.limit(5001).all()
        if len(rows) > 5000:
            raise HTTPException(422, "Rollup exceeds record limit")
        condition = config.get('condition')
        numbers = []
        count = 0
        for child in rows:
            # Count need not evaluate unrelated computed child fields.
            values = self.values(child) if config.get('aggregate_function') != 'count' else dict(child.values_json or {})
            if condition and not evaluate_condition(condition, values):
                continue
            count += 1
            if config.get('aggregate_function') != 'count':
                raw = values.get(config.get('aggregate_field'))
                if raw is None:
                    continue
                try:
                    number = Decimal(str(raw))
                    if not number.is_finite() or isinstance(raw, bool):
                        raise ValueError()
                except Exception:
                    raise HTTPException(422, "Rollup requires numeric aggregate values") from None
                numbers.append(number)
        operation = config.get('aggregate_function')
        if operation == 'count':
            return count
        if operation == 'sum':
            return json_scalar(sum(numbers, Decimal(0)))
        if operation == 'avg':
            return json_scalar(sum(numbers, Decimal(0)) / len(numbers)) if numbers else None
        if operation in {'min', 'max'}:
            return json_scalar((min if operation == 'min' else max)(numbers)) if numbers else None
        raise HTTPException(422, "Unsupported rollup operation")

    def serialize(self, row):
        result = {c.name: getattr(row, c.name) for c in row.__table__.columns}
        result['values_json'] = self.values(row)
        for name, value in result.items():
            if isinstance(value, datetime):
                result[name] = value.isoformat()
        return result


def prepare(db, name, supplied, previous=None):
    fields, formulas, rollups = definitions(db, name)
    computed = set(formulas) | set(rollups)
    automatic = {f.field_api_name for f in fields if f.field_type == 'auto_number'}
    if (computed | automatic) & set(supplied):
        raise HTTPException(422, "Computed fields are read-only; omit them when saving")
    values = {k: v for k, v in (previous or {}).items() if k not in computed}
    values.update(supplied)
    for field in fields:
        if field.field_api_name not in values and field.default_value is not None and field.field_type not in {'formula', 'rollup', 'auto_number'}:
            value = field.default_value
            if field.field_type in {'number', 'decimal', 'currency', 'percentage', 'checkbox', 'multi_select'}:
                try:
                    value = json.loads(value)
                except (ValueError, TypeError):
                    raise HTTPException(422, f"Invalid default for {field.field_label}") from None
            values[field.field_api_name] = value
    return values


def persist_values(db, row):
    for field in db.query(CustomizationField).filter_by(module_name=row.module_api_name).all():
        if field.field_api_name not in row.values_json:
            continue
        value = row.values_json[field.field_api_name]
        stored = db.query(CustomizationRecordValue).filter_by(record_id=row.id, field_id=field.id).first()
        if stored is None:
            stored = CustomizationRecordValue(record_id=row.id, field_id=field.id)
            db.add(stored)
        stored.value_json, stored.value_text = value, str(value) if value is not None else None


def prevent_linked_delete(db, row):
    for field in db.query(CustomizationField).filter_by(field_type='lookup', lookup_module=row.module_api_name).all():
        linked = db.query(CustomizationRecord).filter(
            CustomizationRecord.module_api_name == field.module_name,
            CustomizationRecord.deleted_at.is_(None),
            CustomizationRecord.values_json[field.field_api_name].as_integer() == row.id,
        ).first()
        if linked:
            raise HTTPException(409, "Record is referenced by another custom record; unlink it first")


def query_records(db, name, search=None):
    module(db, name)
    query = db.query(CustomizationRecord).filter_by(module_api_name=name, deleted_at=None)
    if search:
        escaped = search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        query = query.filter(cast(CustomizationRecord.values_json, String).ilike(f'%{escaped}%', escape='\\'))
    return query
