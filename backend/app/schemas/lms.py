from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from typing import Any
from pydantic import BaseModel, ConfigDict


class LearningCourseCreate(BaseModel):
    code: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    delivery_mode: str = "Online"
    duration_hours: Decimal = Decimal("0")
    content_standard: str = "Internal"
    scorm_package_url: Optional[str] = None
    scorm_version: Optional[str] = None
    xapi_activity_id: Optional[str] = None
    xapi_launch_url: Optional[str] = None
    external_launch_url: Optional[str] = None
    completion_callback_url: Optional[str] = None
    metadata_json: Optional[dict[str, Any]] = None
    is_mandatory: bool = False


class LearningCourseSchema(LearningCourseCreate):
    id: int
    is_active: bool
    created_by: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class LearningAssignmentCreate(BaseModel):
    course_id: int
    employee_id: int
    due_date: Optional[date] = None


class LearningAssignmentUpdate(BaseModel):
    status: str
    score: Optional[Decimal] = None


class LearningAssignmentSchema(LearningAssignmentCreate):
    id: int
    assigned_by: Optional[int] = None
    status: str
    completed_at: Optional[datetime] = None
    score: Optional[Decimal] = None
    model_config = ConfigDict(from_attributes=True)


class LearningCertificationCreate(BaseModel):
    employee_id: int
    course_id: Optional[int] = None
    title: str
    certificate_url: Optional[str] = None
    issued_on: Optional[date] = None
    expires_on: Optional[date] = None
    renewal_required: bool = False
    renewal_due_on: Optional[date] = None
    reminder_days: int = 30


class LearningCertificationSchema(LearningCertificationCreate):
    id: int
    status: str
    renewal_status: str
    last_reminder_at: Optional[datetime] = None
    verified_by: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class CertificationRenewalCreate(BaseModel):
    certification_id: int
    due_on: Optional[date] = None
    notes: Optional[str] = None


class CertificationRenewalUpdate(BaseModel):
    status: str
    evidence_url: Optional[str] = None
    notes: Optional[str] = None


class CertificationRenewalSchema(BaseModel):
    id: int
    certification_id: int
    employee_id: int
    due_on: date
    status: str
    reminder_sent_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    evidence_url: Optional[str] = None
    notes: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
