from typing import Any

from pydantic import BaseModel, Field


class ModulePayload(BaseModel):
    module_api_name: str = Field(..., min_length=1, max_length=100)
    module_label: str
    plural_label: str
    icon: str | None = None
    description: str | None = None
    enabled: bool = True
    owner_field_enabled: bool = True
    timeline_enabled: bool = True
    activities_enabled: bool = True


class FieldPayload(BaseModel):
    module_name: str
    field_api_name: str
    field_label: str
    field_type: str
    required: bool = False
    unique: bool = False
    default_value: str | None = None
    help_text: str | None = None
    options_source: str | None = None
    lookup_module: str | None = None
    formula_expression: str | None = None
    rollup_config_json: dict[str, Any] | None = None
    validation_json: dict[str, Any] | None = None
    visible: bool = True
    editable: bool = True
    options: list[dict[str, Any]] = []


class FieldValidatePayload(BaseModel):
    value: Any = None
    record_id: int | None = None


class LayoutPayload(BaseModel):
    module_name: str
    name: str
    layout_type: str = "detail"
    is_default: bool = False
    role_visibility_json: dict[str, Any] | None = None


class LayoutSectionPayload(BaseModel):
    title: str
    order_index: int = 0
    visible: bool = True


class LayoutReorderPayload(BaseModel):
    fields: list[dict[str, Any]]


class ViewPayload(BaseModel):
    module_name: str
    name: str
    view_type: str = "list"
    filters_json: dict[str, Any] | list[dict[str, Any]] | None = None
    columns_json: list[str] | None = None
    sort_json: dict[str, Any] | None = None
    shared: bool = False
    is_default: bool = False


class KanbanPayload(BaseModel):
    module_name: str
    name: str
    group_by_field: str
    card_fields_json: list[str] | None = None
    transition_validation_json: dict[str, Any] | None = None
    shared: bool = False


class ValidationRulePayload(BaseModel):
    module_name: str
    name: str
    condition_json: dict[str, Any]
    error_message: str
    active: bool = True


class RuleTestPayload(BaseModel):
    record: dict[str, Any]


class RelatedListPayload(BaseModel):
    module_name: str
    related_module_name: str
    relationship_type: str = "lookup"
    lookup_field: str | None = None
    label: str
    columns_json: list[str] | None = None
    active: bool = True


class ButtonPayload(BaseModel):
    module_name: str
    label: str
    action_type: str
    action_config_json: dict[str, Any] | None = None
    placement: str = "record"
    active: bool = True


class ButtonExecutePayload(BaseModel):
    record_id: int | None = None
    payload: dict[str, Any] | None = None


class PicklistPayload(BaseModel):
    api_name: str
    label: str
    description: str | None = None
    active: bool = True
    values: list[dict[str, Any]] = []


class FormulaPayload(BaseModel):
    module_name: str
    field_api_name: str
    expression: str
    return_type: str = "decimal"
    active: bool = True


class FormulaTestPayload(BaseModel):
    expression: str
    record: dict[str, Any] = {}


class RollupPayload(BaseModel):
    module_name: str
    field_api_name: str
    related_module_name: str
    aggregate_function: str
    aggregate_field: str | None = None
    filter_json: dict[str, Any] | None = None
    active: bool = True


class DynamicRecordPayload(BaseModel):
    values: dict[str, Any]
    owner_user_id: int | None = None

