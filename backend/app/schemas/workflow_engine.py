from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


class WorkflowStepDefinitionCreate(BaseModel):
    step_order: int
    step_type: str = "Approval"
    approver_type: str = "Role"
    approver_value: Optional[str] = None
    condition_expression: Optional[str] = None
    skip_if_condition: Optional[str] = None
    timeout_hours: Optional[int] = None
    reminder_hours: Optional[int] = None
    timeout_action: Optional[str] = "escalate"
    escalation_user_id: Optional[int] = None
    escalation_role: Optional[str] = None
    action_type: Optional[str] = None
    action_config: Optional[dict[str, Any]] = None
    delegation_type: Optional[str] = None
    delegation_value: Optional[str] = None
    delegation_starts_at: Optional[datetime] = None
    delegation_ends_at: Optional[datetime] = None
    metadata_json: Optional[dict[str, Any]] = None
    is_required: bool = True


class WorkflowStepDefinitionSchema(WorkflowStepDefinitionCreate):
    id: int
    workflow_id: int
    model_config = ConfigDict(from_attributes=True)


class WorkflowDefinitionCreate(BaseModel):
    name: str
    module: str
    trigger_event: str
    description: Optional[str] = None
    steps: list[WorkflowStepDefinitionCreate] = []


class WorkflowDefinitionSchema(BaseModel):
    id: int
    name: str
    module: str
    trigger_event: str
    description: Optional[str] = None
    is_active: bool
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    steps: list[WorkflowStepDefinitionSchema] = []
    model_config = ConfigDict(from_attributes=True)


class WorkflowInstanceCreate(BaseModel):
    workflow_id: Optional[int] = None
    module: str
    entity_type: str
    entity_id: int
    context_json: Optional[dict[str, Any]] = None


class WorkflowTaskDecision(BaseModel):
    decision: str
    reason: Optional[str] = None


class WorkflowTaskSchema(BaseModel):
    id: int
    instance_id: int
    assigned_to_user_id: Optional[int] = None
    assigned_role: Optional[str] = None
    original_assigned_to_user_id: Optional[int] = None
    original_assigned_role: Optional[str] = None
    delegated_to_user_id: Optional[int] = None
    delegated_role: Optional[str] = None
    delegation_reason: Optional[str] = None
    delegation_started_at: Optional[datetime] = None
    delegation_ends_at: Optional[datetime] = None
    status: str
    due_at: Optional[datetime] = None
    reminder_sent_at: Optional[datetime] = None
    escalated_at: Optional[datetime] = None
    escalated_to_user_id: Optional[int] = None
    decision: Optional[str] = None
    decision_reason: Optional[str] = None
    decided_by: Optional[int] = None
    decided_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class WorkflowInstanceSchema(BaseModel):
    id: int
    workflow_id: Optional[int] = None
    module: str
    entity_type: str
    entity_id: int
    requester_user_id: Optional[int] = None
    context_json: Optional[dict[str, Any]] = None
    status: str
    current_step_order: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class WorkflowDelegationCreate(BaseModel):
    delegator_user_id: Optional[int] = None
    delegator_role: Optional[str] = None
    delegate_to_user_id: Optional[int] = None
    delegate_to_role: Optional[str] = None
    module: Optional[str] = None
    reason: Optional[str] = None
    starts_at: datetime
    ends_at: datetime


class WorkflowDelegationSchema(WorkflowDelegationCreate):
    id: int
    is_active: bool
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class WorkflowAuditEventSchema(BaseModel):
    id: int
    instance_id: int
    task_id: Optional[int] = None
    step_definition_id: Optional[int] = None
    event_type: str
    actor_user_id: Optional[int] = None
    before_status: Optional[str] = None
    after_status: Optional[str] = None
    reason: Optional[str] = None
    details_json: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
