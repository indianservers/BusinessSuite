from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OnboardingTemplateTaskCreate(BaseModel):
    task_name: str
    description: Optional[str] = None
    category: str = "other"
    due_day_offset: int = Field(default=1, ge=0)
    assigned_to_role: str = "employee"
    is_mandatory: bool = True
    order_index: int = Field(default=1, ge=0)


class OnboardingTemplateTaskResponse(OnboardingTemplateTaskCreate):
    id: int
    template_id: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OnboardingTemplateCreate(BaseModel):
    organization_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    applicable_for: str = "all"
    is_active: bool = True


class OnboardingTemplateResponse(OnboardingTemplateCreate):
    id: int
    created_at: Optional[datetime] = None
    created_by: Optional[int] = None
    tasks: list[OnboardingTemplateTaskResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class EmployeeOnboardingStart(BaseModel):
    employee_id: int
    template_id: int
    start_date: Optional[date] = None


class EmployeeOnboardingTaskResponse(BaseModel):
    id: int
    employee_onboarding_id: int
    template_task_id: Optional[int] = None
    task_name: str
    category: Optional[str] = None
    due_date: Optional[date] = None
    assigned_to_user_id: Optional[int] = None
    status: str
    completed_at: Optional[datetime] = None
    completed_by: Optional[int] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EmployeeOnboardingResponse(BaseModel):
    id: int
    employee_id: int
    template_id: Optional[int] = None
    start_date: Optional[date] = None
    target_completion_date: Optional[date] = None
    status: str
    completion_percentage: int = 0
    created_at: Optional[datetime] = None
    created_by: Optional[int] = None
    tasks: list[EmployeeOnboardingTaskResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class OnboardingTaskAction(BaseModel):
    notes: Optional[str] = None
    reason: Optional[str] = None


class PolicyAcknowledgementCreate(BaseModel):
    employee_id: int
    policy_name: str
    policy_document_url: Optional[str] = None
    ip_address: Optional[str] = None


class PolicyAcknowledgementSchema(PolicyAcknowledgementCreate):
    id: int
    acknowledged_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
