from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from pydantic import BaseModel, Field


class AppraisalCycleCreate(BaseModel):
    organization_id: Optional[int] = None
    name: str
    cycle_type: Optional[str] = None
    review_period_start: Optional[date] = None
    review_period_end: Optional[date] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    self_review_deadline: Optional[date] = None
    manager_review_deadline: Optional[date] = None
    description: Optional[str] = None


class AppraisalCycleSchema(AppraisalCycleCreate):
    id: int
    status: str
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PerformanceGoalCreate(BaseModel):
    employee_id: Optional[int] = None
    cycle_id: int
    title: str
    description: Optional[str] = None
    category: str = "individual"
    goal_type: str = "KRA"
    weightage: Decimal = Decimal("100")
    target_value: Optional[Any] = None
    achieved_value: Optional[Any] = None
    target: Optional[str] = None
    target_date: Optional[date] = None


class PerformanceGoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    weightage: Optional[Decimal] = None
    target_value: Optional[Any] = None
    achieved_value: Optional[Any] = None
    target: Optional[str] = None
    achievement: Optional[str] = None
    self_rating: Optional[Decimal] = None
    status: Optional[str] = None


class PerformanceGoalSchema(PerformanceGoalCreate):
    id: int
    employee_id: int
    achievement: Optional[str] = None
    self_rating: Optional[Decimal] = None
    manager_rating: Optional[Decimal] = None
    status: str
    set_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PerformanceRatingCriteriaCreate(BaseModel):
    criteria_name: str
    criteria_category: Optional[str] = None
    rating: Decimal = Field(ge=1, le=5)
    comments: Optional[str] = None
    weightage: Decimal = Decimal("0")


class PerformanceRatingCriteriaSchema(PerformanceRatingCriteriaCreate):
    id: int
    review_id: int

    class Config:
        from_attributes = True


class PerformanceReviewCreate(BaseModel):
    employee_id: Optional[int] = None
    cycle_id: Optional[int] = None
    review_type: str = "Self"
    overall_rating: Optional[Decimal] = Field(default=None, ge=1, le=5)
    strengths: Optional[str] = None
    improvements: Optional[str] = None
    comments: Optional[str] = None
    rating_criteria: list[PerformanceRatingCriteriaCreate] = Field(default_factory=list)


class PerformanceReviewSchema(PerformanceReviewCreate):
    id: int
    reviewer_id: int
    status: str
    submitted_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    rating_criteria: list[PerformanceRatingCriteriaSchema] = Field(default_factory=list)

    class Config:
        from_attributes = True


class CalibrationParticipantCreate(BaseModel):
    employee_id: int
    proposed_rating: Optional[Decimal] = Field(default=None, ge=1, le=5)
    final_rating: Optional[Decimal] = Field(default=None, ge=1, le=5)
    potential_rating: Optional[Decimal] = Field(default=None, ge=1, le=5)
    notes: Optional[str] = None


class CalibrationParticipantSchema(CalibrationParticipantCreate):
    id: int
    session_id: int
    status: str
    updated_by: Optional[int] = None
    updated_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CalibrationSessionCreate(BaseModel):
    cycle_id: int
    name: str
    scheduled_at: Optional[datetime] = None
    notes: Optional[str] = None
    participants: list[CalibrationParticipantCreate] = Field(default_factory=list)


class CalibrationSessionUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    participants: list[CalibrationParticipantCreate] = Field(default_factory=list)


class CalibrationSessionSchema(BaseModel):
    id: int
    cycle_id: int
    name: str
    facilitator_user_id: Optional[int] = None
    status: str
    scheduled_at: Optional[datetime] = None
    notes: Optional[str] = None
    audit_json: Optional[list[dict[str, Any]]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    participants: list[CalibrationParticipantSchema] = Field(default_factory=list)

    class Config:
        from_attributes = True


class OneOnOneRecordCreate(BaseModel):
    manager_id: Optional[int] = None
    employee_id: int
    meeting_date: date
    talking_points_json: list[dict[str, Any]] = Field(default_factory=list)
    action_items_json: list[dict[str, Any]] = Field(default_factory=list)
    private_manager_notes: Optional[str] = None
    employee_notes: Optional[str] = None
    status: str = "Open"


class OneOnOneRecordSchema(OneOnOneRecordCreate):
    id: int
    manager_id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CriticalRoleCreate(BaseModel):
    role_name: str
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    incumbent_employee_id: Optional[int] = None
    business_impact: str = "High"
    vacancy_risk: str = "Medium"
    notes: Optional[str] = None
    is_active: bool = True


class SuccessionCandidateCreate(BaseModel):
    critical_role_id: int
    employee_id: int
    readiness_level: str = "Ready in 1-2 years"
    readiness_score: Optional[Decimal] = None
    development_actions_json: list[dict[str, Any]] = Field(default_factory=list)
    mentor_employee_id: Optional[int] = None
    notes: Optional[str] = None


class SuccessionCandidateSchema(SuccessionCandidateCreate):
    id: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CriticalRoleSchema(CriticalRoleCreate):
    id: int
    created_at: datetime
    successors: list[SuccessionCandidateSchema] = Field(default_factory=list)

    class Config:
        from_attributes = True


class GoalCheckInCreate(BaseModel):
    goal_id: int
    progress_percent: Decimal = Decimal("0")
    confidence: str = "On Track"
    update_text: Optional[str] = None
    blocker_text: Optional[str] = None


class GoalCheckInSchema(GoalCheckInCreate):
    id: int
    employee_id: int
    manager_comment: Optional[str] = None
    checked_in_at: datetime

    class Config:
        from_attributes = True


class ReviewTemplateQuestionCreate(BaseModel):
    question_text: str
    question_type: str = "Rating"
    competency_code: Optional[str] = None
    weightage: Decimal = Decimal("0")
    is_required: bool = True
    order_sequence: int = 1


class ReviewTemplateQuestionSchema(ReviewTemplateQuestionCreate):
    id: int
    template_id: int

    class Config:
        from_attributes = True


class ReviewTemplateCreate(BaseModel):
    name: str
    template_type: str = "Performance"
    description: Optional[str] = None
    rating_scale_min: int = 1
    rating_scale_max: int = 5
    is_active: bool = True
    questions: list[ReviewTemplateQuestionCreate] = []


class ReviewTemplateSchema(BaseModel):
    id: int
    name: str
    template_type: str
    description: Optional[str] = None
    rating_scale_min: int
    rating_scale_max: int
    is_active: bool
    created_at: datetime
    questions: list[ReviewTemplateQuestionSchema] = []

    class Config:
        from_attributes = True


class Feedback360RequestCreate(BaseModel):
    cycle_id: int
    employee_id: int
    reviewer_id: int
    relationship_type: str = "Peer"
    due_date: Optional[date] = None


class Feedback360Submit(BaseModel):
    responses_json: list[dict[str, Any]] = []
    overall_rating: Optional[Decimal] = None
    comments: Optional[str] = None


class Feedback360RequestSchema(Feedback360RequestCreate):
    id: int
    status: str
    submitted_at: Optional[datetime] = None
    responses_json: Optional[list[dict[str, Any]]] = None
    overall_rating: Optional[Decimal] = None
    comments: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CompetencyCreate(BaseModel):
    code: str
    name: str
    category: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True


class CompetencySchema(CompetencyCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class RoleSkillRequirementCreate(BaseModel):
    designation_id: Optional[int] = None
    job_profile_id: Optional[int] = None
    competency_id: int
    required_level: int = 3
    importance: str = "Core"
    is_active: bool = True


class RoleSkillRequirementSchema(RoleSkillRequirementCreate):
    id: int

    class Config:
        from_attributes = True


class EmployeeCompetencyAssessmentCreate(BaseModel):
    employee_id: int
    competency_id: int
    assessed_level: int = 1
    assessment_source: str = "Manager"
    evidence: Optional[str] = None


class EmployeeCompetencyAssessmentSchema(EmployeeCompetencyAssessmentCreate):
    id: int
    assessed_by: Optional[int] = None
    assessed_at: datetime

    class Config:
        from_attributes = True


class CompensationCycleCreate(BaseModel):
    name: str
    cycle_type: str = "Merit"
    financial_year: str
    budget_amount: Decimal = Decimal("0")
    budget_percent: Decimal = Decimal("0")
    starts_on: Optional[date] = None
    ends_on: Optional[date] = None


class CompensationCycleSchema(CompensationCycleCreate):
    id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class PayBandCreate(BaseModel):
    name: str
    grade_band_id: Optional[int] = None
    location_id: Optional[int] = None
    currency: str = "INR"
    min_ctc: Decimal = Decimal("0")
    midpoint_ctc: Decimal = Decimal("0")
    max_ctc: Decimal = Decimal("0")
    effective_from: Optional[date] = None
    is_active: bool = True


class PayBandSchema(PayBandCreate):
    id: int

    class Config:
        from_attributes = True


class MeritRecommendationCreate(BaseModel):
    compensation_cycle_id: int
    employee_id: int
    current_ctc: Decimal = Decimal("0")
    recommended_ctc: Decimal = Decimal("0")
    performance_rating: Optional[Decimal] = None
    compa_ratio: Optional[Decimal] = None
    manager_remarks: Optional[str] = None


class MeritRecommendationReview(BaseModel):
    status: str
    manager_remarks: Optional[str] = None


class MeritRecommendationSchema(MeritRecommendationCreate):
    id: int
    increase_percent: Decimal
    status: str
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CompensationWorksheetRowCreate(BaseModel):
    compensation_cycle_id: int
    employee_id: int
    pay_band_id: Optional[int] = None
    current_ctc: Decimal = Decimal("0")
    proposed_merit_amount: Decimal = Decimal("0")
    proposed_merit_percent: Decimal = Decimal("0")
    performance_rating: Optional[Decimal] = None
    manager_notes: Optional[str] = None


class CompensationWorksheetRowUpdate(BaseModel):
    pay_band_id: Optional[int] = None
    proposed_merit_amount: Optional[Decimal] = None
    proposed_merit_percent: Optional[Decimal] = None
    approval_status: Optional[str] = None
    manager_notes: Optional[str] = None
    hr_notes: Optional[str] = None


class CompensationWorksheetRowSchema(CompensationWorksheetRowCreate):
    id: int
    manager_employee_id: Optional[int] = None
    pay_band_min: Decimal
    pay_band_midpoint: Decimal
    pay_band_max: Decimal
    proposed_ctc: Decimal
    budget_impact: Decimal
    approval_status: str
    hr_notes: Optional[str] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
