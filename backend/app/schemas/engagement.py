from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict


class AnnouncementCreate(BaseModel):
    title: str
    body: str
    audience: str = "All"
    target_department_id: Optional[int] = None
    target_location_id: Optional[int] = None
    expires_at: Optional[datetime] = None
    requires_acknowledgement: bool = False
    is_published: bool = False


class AnnouncementSchema(AnnouncementCreate):
    id: int
    published_at: Optional[datetime] = None
    created_by: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class AnnouncementAcknowledgementSchema(BaseModel):
    id: int
    announcement_id: int
    employee_id: int
    acknowledged_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class EngagementSurveyCreate(BaseModel):
    title: str
    survey_type: str = "Pulse"
    question: Optional[str] = None
    options_json: Optional[list[str]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str = "Draft"


class EngagementSurveySchema(EngagementSurveyCreate):
    id: int
    created_by: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class EngagementSurveyResponseCreate(BaseModel):
    survey_id: int
    employee_id: Optional[int] = None
    score: Optional[Decimal] = None
    comments: Optional[str] = None


class EngagementSurveyResponseSchema(EngagementSurveyResponseCreate):
    id: int
    employee_id: int
    submitted_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class RecognitionCreate(BaseModel):
    to_employee_id: int
    title: str
    message: Optional[str] = None
    badge: Optional[str] = None
    points: int = 0
    is_public: bool = True


class RecognitionSchema(RecognitionCreate):
    id: int
    from_employee_id: Optional[int] = None
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class RecognitionReactionCreate(BaseModel):
    emoji: str = "clap"
