from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Numeric, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class PerformanceCycle(Base):
    __tablename__ = "appraisal_cycles"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(150), nullable=False)
    cycle_type = Column(String(20))  # annual, half_yearly, quarterly
    review_period_start = Column(Date)
    review_period_end = Column(Date)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    self_review_deadline = Column(Date)
    manager_review_deadline = Column(Date)
    status = Column(String(20), default="draft")  # draft, active, closed
    description = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    goals = relationship("PerformanceGoal", back_populates="cycle")
    reviews = relationship("PerformanceReview", back_populates="cycle")


class PerformanceGoal(Base):
    __tablename__ = "performance_goals"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    cycle_id = Column(Integer, ForeignKey("appraisal_cycles.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(30), default="individual")
    goal_type = Column(String(20), default="KRA")  # KRA, KPI, Objective
    weightage = Column(Numeric(5, 2), default=100)
    target_value = Column(String(500))
    achieved_value = Column(String(500))
    target = Column(String(500))
    target_date = Column(Date)
    achievement = Column(Text)
    self_rating = Column(Numeric(3, 1))
    manager_rating = Column(Numeric(3, 1))
    status = Column(String(20), default="active")  # draft, active, completed, cancelled
    set_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    employee = relationship("Employee", back_populates="goals")
    cycle = relationship("PerformanceCycle", back_populates="goals")


class PerformanceReview(Base):
    __tablename__ = "performance_reviews"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    cycle_id = Column(Integer, ForeignKey("appraisal_cycles.id", ondelete="CASCADE"), nullable=False)
    review_type = Column(String(20))  # self, manager, peer, 360
    overall_rating = Column(Numeric(3, 1))
    strengths = Column(Text)
    improvements = Column(Text)
    comments = Column(Text)
    status = Column(String(20), default="draft")  # draft, submitted, acknowledged
    submitted_at = Column(DateTime(timezone=True))
    acknowledged_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    cycle = relationship("PerformanceCycle", back_populates="reviews")
    rating_criteria = relationship(
        "PerformanceRatingCriteria",
        back_populates="review",
        cascade="all, delete-orphan",
    )


class CalibrationSession(Base):
    __tablename__ = "calibration_sessions"

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("appraisal_cycles.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    facilitator_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(30), default="Draft", index=True)
    scheduled_at = Column(DateTime(timezone=True))
    notes = Column(Text)
    audit_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    cycle = relationship("PerformanceCycle")
    participants = relationship("CalibrationParticipant", back_populates="session", cascade="all, delete-orphan")


class CalibrationParticipant(Base):
    __tablename__ = "calibration_participants"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("calibration_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    proposed_rating = Column(Numeric(3, 1))
    final_rating = Column(Numeric(3, 1))
    potential_rating = Column(Numeric(3, 1))
    notes = Column(Text)
    status = Column(String(30), default="Proposed", index=True)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("CalibrationSession", back_populates="participants")
    employee = relationship("Employee")


class OneOnOneRecord(Base):
    __tablename__ = "one_on_one_records"

    id = Column(Integer, primary_key=True, index=True)
    manager_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    meeting_date = Column(Date, nullable=False, index=True)
    talking_points_json = Column(JSON)
    action_items_json = Column(JSON)
    private_manager_notes = Column(Text)
    employee_notes = Column(Text)
    status = Column(String(30), default="Open", index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    manager = relationship("Employee", foreign_keys=[manager_id])
    employee = relationship("Employee", foreign_keys=[employee_id])


class PerformanceRatingCriteria(Base):
    __tablename__ = "performance_rating_criteria"

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey("performance_reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    criteria_name = Column(String(150), nullable=False)
    criteria_category = Column(String(80))
    rating = Column(Numeric(3, 1))
    comments = Column(Text)
    weightage = Column(Numeric(5, 2), default=0)

    review = relationship("PerformanceReview", back_populates="rating_criteria")


AppraisalCycle = PerformanceCycle


class GoalCheckIn(Base):
    __tablename__ = "goal_check_ins"

    id = Column(Integer, primary_key=True, index=True)
    goal_id = Column(Integer, ForeignKey("performance_goals.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    progress_percent = Column(Numeric(5, 2), default=0)
    confidence = Column(String(30), default="On Track")  # At Risk, On Track, Ahead
    update_text = Column(Text)
    blocker_text = Column(Text)
    manager_comment = Column(Text)
    checked_in_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    goal = relationship("PerformanceGoal")
    employee = relationship("Employee")


class ReviewTemplate(Base):
    __tablename__ = "review_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    template_type = Column(String(40), default="Performance", index=True)  # Performance, 360, Probation, Manager
    description = Column(Text)
    rating_scale_min = Column(Integer, default=1)
    rating_scale_max = Column(Integer, default=5)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    questions = relationship("ReviewTemplateQuestion", back_populates="template", cascade="all, delete-orphan")


class ReviewTemplateQuestion(Base):
    __tablename__ = "review_template_questions"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("review_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(30), default="Rating")  # Rating, Text, YesNo
    competency_code = Column(String(80), index=True)
    weightage = Column(Numeric(5, 2), default=0)
    is_required = Column(Boolean, default=True)
    order_sequence = Column(Integer, default=1)

    template = relationship("ReviewTemplate", back_populates="questions")


class Feedback360Request(Base):
    __tablename__ = "feedback_360_requests"

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("appraisal_cycles.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(String(30), default="Peer")  # Peer, Manager, Direct Report, Customer
    status = Column(String(30), default="Requested", index=True)
    due_date = Column(Date)
    submitted_at = Column(DateTime(timezone=True))
    responses_json = Column(JSON)
    overall_rating = Column(Numeric(3, 1))
    comments = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    cycle = relationship("PerformanceCycle")
    employee = relationship("Employee", foreign_keys=[employee_id])
    reviewer = relationship("Employee", foreign_keys=[reviewer_id])


class Competency(Base):
    __tablename__ = "competencies"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(80), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    category = Column(String(80), index=True)
    description = Column(Text)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RoleSkillRequirement(Base):
    __tablename__ = "role_skill_requirements"

    id = Column(Integer, primary_key=True, index=True)
    designation_id = Column(Integer, ForeignKey("designations.id", ondelete="CASCADE"), nullable=True, index=True)
    job_profile_id = Column(Integer, ForeignKey("job_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    competency_id = Column(Integer, ForeignKey("competencies.id", ondelete="CASCADE"), nullable=False, index=True)
    required_level = Column(Integer, default=3)
    importance = Column(String(30), default="Core")  # Core, Critical, Optional
    is_active = Column(Boolean, default=True, index=True)

    competency = relationship("Competency")


class EmployeeCompetencyAssessment(Base):
    __tablename__ = "employee_competency_assessments"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    competency_id = Column(Integer, ForeignKey("competencies.id", ondelete="CASCADE"), nullable=False, index=True)
    assessed_level = Column(Integer, default=1)
    assessment_source = Column(String(40), default="Manager")  # Self, Manager, Review, Certification
    assessed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assessed_at = Column(DateTime(timezone=True), server_default=func.now())
    evidence = Column(Text)

    employee = relationship("Employee")
    competency = relationship("Competency")


class CriticalRole(Base):
    __tablename__ = "critical_roles"

    id = Column(Integer, primary_key=True, index=True)
    role_name = Column(String(160), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    designation_id = Column(Integer, ForeignKey("designations.id", ondelete="SET NULL"), nullable=True, index=True)
    incumbent_employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True)
    business_impact = Column(String(40), default="High")
    vacancy_risk = Column(String(40), default="Medium")
    notes = Column(Text)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    successors = relationship("SuccessionCandidate", back_populates="critical_role", cascade="all, delete-orphan")


class SuccessionCandidate(Base):
    __tablename__ = "succession_candidates"

    id = Column(Integer, primary_key=True, index=True)
    critical_role_id = Column(Integer, ForeignKey("critical_roles.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    readiness_level = Column(String(40), default="Ready in 1-2 years", index=True)
    readiness_score = Column(Numeric(4, 2))
    development_actions_json = Column(JSON)
    mentor_employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(30), default="Active", index=True)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    critical_role = relationship("CriticalRole", back_populates="successors")
    employee = relationship("Employee", foreign_keys=[employee_id])
    mentor = relationship("Employee", foreign_keys=[mentor_employee_id])


class CompensationCycle(Base):
    __tablename__ = "compensation_cycles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    cycle_type = Column(String(40), default="Merit")  # Merit, Promotion, Bonus, Correction
    financial_year = Column(String(20), nullable=False, index=True)
    budget_amount = Column(Numeric(14, 2), default=0)
    budget_percent = Column(Numeric(5, 2), default=0)
    status = Column(String(30), default="Draft", index=True)
    starts_on = Column(Date)
    ends_on = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PayBand(Base):
    __tablename__ = "pay_bands"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    grade_band_id = Column(Integer, ForeignKey("grade_bands.id", ondelete="SET NULL"), nullable=True, index=True)
    location_id = Column(Integer, ForeignKey("work_locations.id", ondelete="SET NULL"), nullable=True, index=True)
    currency = Column(String(10), default="INR")
    min_ctc = Column(Numeric(14, 2), default=0)
    midpoint_ctc = Column(Numeric(14, 2), default=0)
    max_ctc = Column(Numeric(14, 2), default=0)
    effective_from = Column(Date)
    is_active = Column(Boolean, default=True, index=True)


class MeritRecommendation(Base):
    __tablename__ = "merit_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    compensation_cycle_id = Column(Integer, ForeignKey("compensation_cycles.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    current_ctc = Column(Numeric(14, 2), default=0)
    recommended_ctc = Column(Numeric(14, 2), default=0)
    increase_percent = Column(Numeric(5, 2), default=0)
    performance_rating = Column(Numeric(3, 1))
    compa_ratio = Column(Numeric(6, 3))
    manager_remarks = Column(Text)
    status = Column(String(30), default="Draft", index=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    cycle = relationship("CompensationCycle")
    employee = relationship("Employee")


class CompensationWorksheetRow(Base):
    __tablename__ = "compensation_worksheet_rows"

    id = Column(Integer, primary_key=True, index=True)
    compensation_cycle_id = Column(Integer, ForeignKey("compensation_cycles.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    manager_employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True)
    pay_band_id = Column(Integer, ForeignKey("pay_bands.id", ondelete="SET NULL"), nullable=True)
    current_ctc = Column(Numeric(14, 2), default=0)
    pay_band_min = Column(Numeric(14, 2), default=0)
    pay_band_midpoint = Column(Numeric(14, 2), default=0)
    pay_band_max = Column(Numeric(14, 2), default=0)
    proposed_merit_amount = Column(Numeric(14, 2), default=0)
    proposed_merit_percent = Column(Numeric(6, 2), default=0)
    proposed_ctc = Column(Numeric(14, 2), default=0)
    budget_impact = Column(Numeric(14, 2), default=0)
    approval_status = Column(String(30), default="Draft", index=True)
    performance_rating = Column(Numeric(3, 1))
    manager_notes = Column(Text)
    hr_notes = Column(Text)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    cycle = relationship("CompensationCycle")
    employee = relationship("Employee", foreign_keys=[employee_id])
    manager = relationship("Employee", foreign_keys=[manager_employee_id])
    pay_band = relationship("PayBand")
