from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ApprovalRequestCreate(BaseModel):
    source_module: str
    approval_type: str
    entity_type: str
    entity_id: int
    title: str
    description: Optional[str] = None
    assigned_to_user_id: Optional[int] = None
    assigned_role: Optional[str] = None
    priority: str = "Normal"
    sla_due_at: Optional[datetime] = None
    escalation_user_id: Optional[int] = None
    escalation_role: Optional[str] = None
    ai_summary: Optional[str] = None
    context_json: Optional[dict[str, Any]] = None
    mobile_enabled: bool = True


class ApprovalDecision(BaseModel):
    reason: Optional[str] = None


class ApprovalCommentCreate(BaseModel):
    comment: str
    is_internal: bool = False


class ApprovalCommentSchema(BaseModel):
    id: int
    request_id: int
    author_user_id: Optional[int] = None
    comment: str
    is_internal: bool
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class ApprovalHistorySchema(BaseModel):
    id: int
    request_id: int
    event_type: str
    actor_user_id: Optional[int] = None
    before_status: Optional[str] = None
    after_status: Optional[str] = None
    reason: Optional[str] = None
    details_json: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class ApprovalRequestSchema(BaseModel):
    id: int
    source_module: str
    approval_type: str
    entity_type: str
    entity_id: int
    title: str
    description: Optional[str] = None
    requester_user_id: Optional[int] = None
    assigned_to_user_id: Optional[int] = None
    assigned_role: Optional[str] = None
    delegated_to_user_id: Optional[int] = None
    delegated_role: Optional[str] = None
    priority: str
    status: str
    sla_due_at: Optional[datetime] = None
    escalated_at: Optional[datetime] = None
    escalation_user_id: Optional[int] = None
    escalation_role: Optional[str] = None
    ai_summary: Optional[str] = None
    context_json: Optional[dict[str, Any]] = None
    decision_reason: Optional[str] = None
    decided_by: Optional[int] = None
    decided_at: Optional[datetime] = None
    mobile_enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    comments: list[ApprovalCommentSchema] = []
    history: list[ApprovalHistorySchema] = []
    model_config = ConfigDict(from_attributes=True)


class ApprovalInboxItem(BaseModel):
    id: str
    source: str
    source_module: str
    approval_type: str
    entity_type: str
    entity_id: int
    title: str
    description: Optional[str] = None
    requester_user_id: Optional[int] = None
    assigned_to_user_id: Optional[int] = None
    assigned_role: Optional[str] = None
    priority: str
    status: str
    sla_due_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    escalated_at: Optional[datetime] = None
    ai_summary: Optional[str] = None
    mobile_enabled: bool = True
    action_url: str
    can_decide: bool = False


class ApprovalSummary(BaseModel):
    total: int
    pending: int
    overdue: int
    escalated: int
    high_priority: int
    by_module: dict[str, int]
    by_type: dict[str, int]


class ApprovalInboxResponse(BaseModel):
    summary: ApprovalSummary
    items: list[ApprovalInboxItem]
