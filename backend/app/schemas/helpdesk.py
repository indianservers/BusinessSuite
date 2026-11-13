from datetime import datetime
from typing import Optional,Literal
from pydantic import BaseModel, ConfigDict,Field,field_validator


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
    escalated_to: Optional[int] = Field(default=None,gt=0,le=2147483647)
    escalation_reason: str = Field(min_length=1,max_length=4000)
    expected_version: int | None = Field(default=None,ge=1)

    @field_validator('escalation_reason')
    @classmethod
    def reason_required(cls,value):
        if not value.strip():raise ValueError('Supply an escalation reason')
        return value


class HelpdeskTicketCreate(BaseModel):
    subject: str
    description: str
    category_id: Optional[int] = None
    priority: str = "Medium"


class HelpdeskTicketStatusUpdate(BaseModel):
    status: Literal['Open','In Progress','Pending','Resolved','Closed']
    expected_version: int | None = Field(default=None,ge=1)


class HelpdeskTicketAssign(BaseModel):
    assign_to_user_id: int = Field(gt=0,le=2147483647)
    expected_version: int | None = Field(default=None,ge=1)


class HelpdeskTicketReply(BaseModel):
    model_config=ConfigDict(extra='forbid')
    message: str = Field(min_length=1,max_length=8000)
    is_internal: bool = False
    expected_version: int | None = Field(default=None,ge=1)
