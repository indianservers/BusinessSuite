from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=180)
    description: str | None = None
    module_name: str = Field(..., min_length=1, max_length=60)
    record_type: str = Field(..., min_length=1, max_length=80)
    trigger_type: str = Field(..., min_length=1, max_length=80)
    conditions: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    is_active: bool = False
    max_execution_depth: int = Field(default=5, ge=1, le=10)


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    module_name: str | None = None
    record_type: str | None = None
    trigger_type: str | None = None
    conditions: list[dict[str, Any]] | None = None
    actions: list[dict[str, Any]] | None = None
    is_active: bool | None = None
    max_execution_depth: int | None = Field(default=None, ge=1, le=10)


class WorkflowTestRequest(BaseModel):
    record: dict[str, Any] = {}
    module_name: str | None = None
    record_type: str | None = None
    record_id: int | None = None
    trigger_type: str | None = None
    depth: int = 0


class BlueprintCreate(BaseModel):
    name: str
    module_name: str
    record_type: str
    stages: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    is_active: bool = True


class BlueprintTransitionValidate(BaseModel):
    from_stage_key: str
    to_stage_key: str
    record: dict[str, Any] = {}


class ApprovalRuleCreate(BaseModel):
    name: str
    module_name: str
    record_type: str
    condition_json: dict[str, Any] | list[dict[str, Any]] | None = None
    steps: list[dict[str, Any]] = []
    is_active: bool = True


class ApprovalRequestCreate(BaseModel):
    rule_id: int | None = None
    module_name: str
    record_type: str
    record_id: int
    payload_json: dict[str, Any] | None = None


class ApprovalDecision(BaseModel):
    comment: str | None = None


class AssignmentRuleCreate(BaseModel):
    name: str
    module_name: str
    record_type: str
    condition_json: dict[str, Any] | list[dict[str, Any]] | None = None
    assignment_json: dict[str, Any]
    is_active: bool = True


class RuleTestRequest(BaseModel):
    record: dict[str, Any] = {}


class CadenceCreate(BaseModel):
    name: str
    module_name: str = "crm"
    target_type: str
    stop_rules_json: dict[str, Any] | None = None
    steps: list[dict[str, Any]] = []
    status: str = "active"


class CadenceEnrollRequest(BaseModel):
    record_type: str
    record_id: int
    payload_json: dict[str, Any] | None = None


class WebhookCreate(BaseModel):
    name: str
    target_url: str
    event_types_json: list[str] = []
    secret_ref: str | None = None
    is_active: bool = True


class WebhookTestRequest(BaseModel):
    payload: dict[str, Any] = {}


class AutomationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None

