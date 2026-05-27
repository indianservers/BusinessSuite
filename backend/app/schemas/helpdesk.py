from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class HelpdeskCategorySchema(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    sla_hours: int
    assigned_team: Optional[str] = None
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class HelpdeskKnowledgeArticleCreate(BaseModel):
    category_id: Optional[int] = None
    title: str
    body: str
    keywords: Optional[str] = None
    version: str = "1.0"
    is_published: bool = False


class HelpdeskKnowledgeArticleSchema(HelpdeskKnowledgeArticleCreate):
    id: int
    created_by: Optional[int] = None
    published_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class HelpdeskEscalationRuleCreate(BaseModel):
    category_id: Optional[int] = None
    priority: str = "Medium"
    escalate_after_hours: int = 24
    escalate_to_user_id: Optional[int] = None
    escalation_team: Optional[str] = None


class HelpdeskEscalationRuleSchema(HelpdeskEscalationRuleCreate):
    id: int
    is_active: bool
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class HelpdeskTicketEscalation(BaseModel):
    escalated_to: Optional[int] = None
    escalation_reason: str


class HelpdeskTicketCreate(BaseModel):
    subject: str
    description: str
    category_id: Optional[int] = None
    priority: str = "Medium"


class HelpdeskTicketStatusUpdate(BaseModel):
    status: str


class HelpdeskTicketAssign(BaseModel):
    assign_to_user_id: int
