"""Validated, reusable SQL grid primitives. Callers supply an authorized query.

Field names are resolved from an adapter allowlist, never from SQL supplied by a
browser. Pagination, groups, facets and exports use the same filter expression.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Literal
import json

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import and_, or_, func


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str = Field(max_length=80)
    operator: Literal["equals", "not_equals", "contains", "starts_with", "ends_with", "between", "gt", "gte", "lt", "lte", "empty", "not_empty", "in"] = "equals"
    value: Any = None
    value2: Any = None


class FilterGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    logic: Literal["and", "or"] = "and"
    rules: list[Rule | FilterGroup] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def bound_tree(self):
        def size(group, depth=0):
            if depth > 4: raise ValueError("At most four nested filter levels are supported")
            return sum(size(r, depth + 1) if isinstance(r, FilterGroup) else 1 for r in group.rules)
        if size(self) > 50: raise ValueError("Use at most 50 filter conditions")
        return self


class GridSort(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(max_length=80)
    desc: bool = False


class GroupKey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str = Field(max_length=80)
    value: str | int | None


class GridQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    search: str = Field(default="", max_length=180)
    filters: FilterGroup = Field(default_factory=FilterGroup)
    sorting: list[GridSort] = Field(default_factory=list, max_length=6)
    grouping: list[str] = Field(default_factory=list, max_length=4)
    path: list[GroupKey] = Field(default_factory=list, max_length=4)
    page: int = Field(default=1, ge=1, le=10000000)
    pageSize: int = Field(default=50, ge=1, le=200)

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.grouping)) != len(self.grouping): raise ValueError("Grouping columns must be unique")
        if len({s.id for s in self.sorting}) != len(self.sorting): raise ValueError("Sort columns must be unique")
        if len(self.path) > len(self.grouping) or [p.field for p in self.path] != self.grouping[:len(self.path)]:
            raise ValueError("Invalid grouping path")
        return self


@dataclass(frozen=True)
class GridField:
    expression: Any
    kind: str = "text"
    label: str = ""
    groupable: bool = True


def parse_query(raw):
    try: return GridQuery.model_validate_json(raw)
    except (ValueError, ValidationError): raise HTTPException(422, "Invalid grid state or filter values")


def field_for(fields, name):
    if name not in fields: raise HTTPException(422, f"Unsupported grid field: {name}")
    return fields[name]


def typed(field, value):
    if value is None: return None
    try:
        if field.kind == "number":
            number = Decimal(str(value))
            if not number.is_finite() or abs(number) > Decimal("1e18"): raise ValueError()
            return number
        if field.kind == "id":
            number = int(str(value))
            if not 0 < number <= 9223372036854775807: raise ValueError()
            return number
        if field.kind == "date": return date.fromisoformat(str(value)[:10])
        if field.kind == "datetime": return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if not isinstance(value, (str, int, float, bool)) or len(str(value)) > 500: raise ValueError()
        return str(value)
    except (ValueError, TypeError, ArithmeticError): raise HTTPException(422, "A grid filter contains an invalid value")


def filter_expression(group, fields):
    clauses = []
    for rule in group.rules:
        if isinstance(rule, FilterGroup):
            if rule.rules: clauses.append(filter_expression(rule, fields))
            continue
        field = field_for(fields, rule.field); column = field.expression; op = rule.operator
        if op in {"empty", "not_empty"}:
            empty = or_(column.is_(None), column == "") if field.kind == "text" else column.is_(None)
            clauses.append(empty if op == "empty" else ~empty); continue
        if op == "in":
            if not isinstance(rule.value, list) or len(rule.value) > 500: raise HTTPException(422, "Choose up to 500 filter values")
            values = [typed(field, v) for v in rule.value if v is not None]
            clauses.append(or_(column.in_(values), column.is_(None)) if None in rule.value else column.in_(values)); continue
        value = typed(field, rule.value)
        if op in {"contains", "starts_with", "ends_with"}:
            if field.kind != "text" or value is None: raise HTTPException(422, "Text operators require a text field and value")
            escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%" if op == "contains" else f"{escaped}%" if op == "starts_with" else f"%{escaped}"
            clauses.append(column.ilike(pattern, escape="\\")); continue
        if op == "between":
            end = typed(field, rule.value2)
            if value is None or end is None or value > end: raise HTTPException(422, "Enter a valid filter range")
            clauses.append(column.between(value, end)); continue
        if value is None and op not in {"equals", "not_equals"}: raise HTTPException(422, "Enter a filter value")
        clauses.append({"equals": lambda: column == value, "not_equals": lambda: column != value, "gt": lambda: column > value, "gte": lambda: column >= value, "lt": lambda: column < value, "lte": lambda: column <= value}[op]())
    return (and_ if group.logic == "and" else or_)(*clauses) if clauses else True


def apply_filters(query, state, fields):
    for name in state.grouping:
        if not field_for(fields, name).groupable: raise HTTPException(422, "That column cannot be grouped")
    for sort in state.sorting: field_for(fields, sort.id)
    return query.filter(filter_expression(state.filters, fields))


def apply_path(query, state, fields):
    for key in state.path:
        field = field_for(fields, key.field)
        query = query.filter(field.expression == typed(field, key.value))
    return query


def apply_sort(query, state, fields, fallback):
    orders = [(field_for(fields, s.id).expression.desc() if s.desc else field_for(fields, s.id).expression.asc()).nullslast() for s in state.sorting]
    return query.order_by(None).order_by(*orders, fallback.asc())


def safe_cell(value):
    if value is None: return ""
    if isinstance(value, (date, datetime)): return value.isoformat()
    if isinstance(value, Decimal): return float(value)
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")): return "'" + value
    return value
