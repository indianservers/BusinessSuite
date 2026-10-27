"""Bounded data-only authoring contracts. No executable expressions."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.apps.power_apps.node_registry import expression_paths

OPERATORS = ["equals", "not_equals", "greater_than", "less_than", "greater_or_equal", "less_or_equal", "contains", "starts_with", "ends_with", "is_empty", "is_not_empty", "in_list", "not_in_list", "date_before", "date_after", "boolean_equals"]

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

class Condition(Strict):
    join: Literal["and", "or"] = "and"
    rules: list["Condition | Rule"] = Field(default_factory=list, max_length=30)

class Rule(Strict):
    left: Any = None
    operator: Literal["equals", "not_equals", "greater_than", "less_than", "greater_or_equal", "less_or_equal", "contains", "starts_with", "ends_with", "is_empty", "is_not_empty", "in_list", "not_in_list", "date_before", "date_after", "boolean_equals"] = "equals"
    right: Any = None

class MappingOperation(Strict):
    op: Literal["default", "convert", "concat", "format_date", "format_number", "filter", "map", "rename", "conditional", "lookup", "path"]
    argument: Any = None

class FieldMapping(Strict):
    source: str | None = Field(default=None, max_length=300)
    constant: Any = None
    operations: list[MappingOperation] = Field(default_factory=list, max_length=12)
    target_type: Literal["any", "string", "number", "boolean", "date", "datetime", "array", "object"] = "any"
    nullable: bool = False

    @model_validator(mode="after")
    def safe(self):
        if self.source and (not self.source.startswith("{{") or not self.source.endswith("}}")):
            raise ValueError("Mapping source must be a complete safe reference")
        expression_paths(self.model_dump())
        return self

class BlockReference(Strict):
    resource_id: int = Field(ge=1, le=2147483647)
    version: int = Field(ge=1)
    node_ids: list[str] = Field(min_length=1, max_length=500)

class BlockParameter(Strict):
    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", max_length=60)
    node_id: str = Field(max_length=80)
    field: str = Field(max_length=80)
    data_type: Literal["any", "string", "number", "boolean", "array", "object"] = "any"
    default: Any = None

class BlockContract(Strict):
    @model_validator(mode="after")
    def safe_defaults(self):
        expression_paths(self.model_dump())
        return self
    inputs: list[BlockParameter] = Field(default_factory=list, max_length=30)
    outputs: list[BlockParameter] = Field(default_factory=list, max_length=30)

class MappingPreset(Strict):
    name: str = Field(min_length=1, max_length=80)
    mapping: FieldMapping
