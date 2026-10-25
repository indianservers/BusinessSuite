from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, EmailStr


class JobCreate(BaseModel):
    title: str
    code: Optional[str] = None
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    branch_id: Optional[int] = None
    job_type: Optional[str] = None
    location: Optional[str] = None
    work_mode: str = "Office"
    openings: int = 1
    min_experience: Optional[Decimal] = None
    max_experience: Optional[Decimal] = None
    min_salary: Optional[Decimal] = None
    max_salary: Optional[Decimal] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    benefits: Optional[str] = None
    skills_required: Optional[str] = None
    posted_date: Optional[date] = None
    closing_date: Optional[date] = None
    hiring_manager_id: Optional[int] = None
    is_published: bool = False


class JobUpdate(JobCreate):
    title: Optional[str] = None
    status: Optional[str] = None


class JobSchema(JobCreate):
    id: int
    status: str

    class Config:
        from_attributes = True


class RecruitmentRequisitionCreate(BaseModel):
    title: str
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    branch_id: Optional[int] = None
    openings: int = 1
    justification: Optional[str] = None
    target_joining_date: Optional[date] = None


class RecruitmentRequisitionReview(BaseModel):
    action: str
    remarks: Optional[str] = None


class RecruitmentRequisitionSchema(RecruitmentRequisitionCreate):
    id: int
    requisition_number: str
    status: str
    requested_by: Optional[int] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    job_id: Optional[int] = None

    class Config:
        from_attributes = True


class CandidateCreate(BaseModel):
    job_id: int
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    phone_country_code: str | None = None
    current_company: Optional[str] = None
    current_designation: Optional[str] = None
    total_experience: Optional[Decimal] = None
    current_ctc: Optional[Decimal] = None
    expected_ctc: Optional[Decimal] = None
    notice_period_days: Optional[int] = None
    current_location: Optional[str] = None
    linkedin_url: Optional[str] = None
    source: Optional[str] = None
    referred_by: Optional[int] = None


class CandidateUpdate(BaseModel):
    status: Optional[str] = None
    ai_score: Optional[Decimal] = None
    ai_summary: Optional[str] = None


class CandidateSchema(BaseModel):
    id: int
    job_id: int
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    phone_country_code: str | None = None
    current_company: Optional[str] = None
    total_experience: Optional[Decimal] = None
    expected_ctc: Optional[Decimal] = None
    notice_period_days: Optional[int] = None
    resume_url: Optional[str] = None
    ai_score: Optional[Decimal] = None
    ai_summary: Optional[str] = None
    source: Optional[str] = None
    status: str
    applied_at: datetime

    class Config:
        from_attributes = True


class InterviewCreate(BaseModel):
    candidate_id: int
    round_number: int = 1
    round_name: Optional[str] = None
    interview_type: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    duration_minutes: int = 60
    interviewer_ids: Optional[str] = None
    meet_link: Optional[str] = None
    venue: Optional[str] = None


class InterviewFeedbackCreate(BaseModel):
    technical_score: Optional[Decimal] = None
    communication_score: Optional[Decimal] = None
    attitude_score: Optional[Decimal] = None
    overall_score: Optional[Decimal] = None
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    recommendation: Optional[str] = None
    comments: Optional[str] = None


class OfferLetterCreate(BaseModel):
    candidate_id: int
    offer_date: Optional[date] = None
    joining_date: Optional[date] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    ctc: Optional[Decimal] = None
    basic: Optional[Decimal] = None
    template_id: Optional[int] = None
    expiry_date: Optional[date] = None


class CandidateConversionCreate(BaseModel):
    employee_id: Optional[str] = None
    date_of_joining: date
    employment_type: str = "Full-time"
    create_user_account: bool = False
