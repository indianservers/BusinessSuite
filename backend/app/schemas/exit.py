from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ExitRecordCreate(BaseModel):
    employee_id: int
    exit_type: Optional[str] = None
    resignation_date: Optional[date] = None
    last_working_date: Optional[date] = None
    notice_period_days: Optional[int] = None
    notice_waived: bool = False
    reason: Optional[str] = None
    status: str = "Initiated"
    final_settlement_amount: Optional[Decimal] = None
    final_settlement_date: Optional[date] = None


class ExitRecordUpdate(BaseModel):
    exit_type: Optional[str] = None
    resignation_date: Optional[date] = None
    last_working_date: Optional[date] = None
    notice_period_days: Optional[int] = None
    notice_waived: Optional[bool] = None
    reason: Optional[str] = None
    status: Optional[str] = None
    final_settlement_amount: Optional[Decimal] = None
    final_settlement_date: Optional[date] = None


class ExitRecordSchema(ExitRecordCreate):
    id: int
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class ExitChecklistItemCreate(BaseModel):
    exit_record_id: int
    task_name: str
    assigned_to_role: Optional[str] = None
    assigned_to_user: Optional[int] = None
    remarks: Optional[str] = None


class ExitChecklistItemSchema(ExitChecklistItemCreate):
    id: int
    is_completed: bool = False
    completed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class ExitInterviewCreate(BaseModel):
    exit_record_id: int
    interview_date: Optional[date] = None
    reason_for_leaving: Optional[str] = None
    job_satisfaction: Optional[int] = None
    management_satisfaction: Optional[int] = None
    work_environment_satisfaction: Optional[int] = None
    growth_satisfaction: Optional[int] = None
    would_rejoin: Optional[bool] = None
    feedback: Optional[str] = None
    suggestions: Optional[str] = None


class ExitInterviewSchema(ExitInterviewCreate):
    id: int
    conducted_by: Optional[int] = None
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
