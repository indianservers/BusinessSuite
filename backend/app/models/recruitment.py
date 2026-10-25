from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Numeric, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    code = Column(String(50), unique=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    designation_id = Column(Integer, ForeignKey("designations.id", ondelete="SET NULL"), nullable=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    job_type = Column(String(30))  # Full-time, Part-time, Contract, Intern
    location = Column(String(150))
    work_mode = Column(String(30), default="Office")  # Office, Remote, Hybrid
    openings = Column(Integer, default=1)
    min_experience = Column(Numeric(4, 1))
    max_experience = Column(Numeric(4, 1))
    min_salary = Column(Numeric(12, 2))
    max_salary = Column(Numeric(12, 2))
    description = Column(Text)
    requirements = Column(Text)
    benefits = Column(Text)
    skills_required = Column(Text)  # JSON array
    status = Column(String(30), default="Open")  # Draft, Open, On Hold, Closed
    posted_date = Column(Date)
    closing_date = Column(Date)
    is_published = Column(Boolean, default=False)
    hiring_manager_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    candidates = relationship("Candidate", back_populates="job")


class RecruitmentRequisition(Base):
    __tablename__ = "recruitment_requisitions"

    id = Column(Integer, primary_key=True, index=True)
    requisition_number = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    designation_id = Column(Integer, ForeignKey("designations.id", ondelete="SET NULL"), nullable=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    openings = Column(Integer, default=1)
    justification = Column(Text)
    target_joining_date = Column(Date)
    status = Column(String(30), default="Pending", index=True)
    requested_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    first_name = Column(String(80), nullable=False)
    last_name = Column(String(80), nullable=False)
    email = Column(String(150), nullable=False)
    phone = Column(String(20))
    phone_country_code = Column(String(5), nullable=True)
    current_company = Column(String(200))
    current_designation = Column(String(150))
    total_experience = Column(Numeric(4, 1))
    current_ctc = Column(Numeric(12, 2))
    expected_ctc = Column(Numeric(12, 2))
    notice_period_days = Column(Integer)
    current_location = Column(String(150))
    linkedin_url = Column(String(500))
    portfolio_url = Column(String(500))
    resume_url = Column(String(500))
    resume_parsed_data = Column(Text)  # JSON from AI parsing
    ai_score = Column(Numeric(5, 2))  # AI matching score
    ai_summary = Column(Text)  # AI generated summary
    source = Column(String(50))  # LinkedIn, Indeed, Referral, Portal, Walk-in
    status = Column(String(30), default="Applied")  # Applied, Screening, Interview, Offered, Hired, Rejected, Withdrawn
    applied_at = Column(DateTime(timezone=True), server_default=func.now())
    referred_by = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    job = relationship("Job", back_populates="candidates")
    interviews = relationship("Interview", back_populates="candidate", cascade="all, delete-orphan")
    offer = relationship("OfferLetter", back_populates="candidate", uselist=False)


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    round_number = Column(Integer, nullable=False, default=1)
    round_name = Column(String(100))  # HR Round, Technical, Managerial
    interview_type = Column(String(30))  # In-person, Video, Phone
    scheduled_at = Column(DateTime(timezone=True))
    duration_minutes = Column(Integer, default=60)
    interviewer_ids = Column(Text)  # JSON array of employee IDs
    meet_link = Column(String(500))
    venue = Column(String(300))
    status = Column(String(30), default="Scheduled")  # Scheduled, Completed, No-show, Cancelled
    result = Column(String(30))  # Selected, Rejected, On Hold
    overall_rating = Column(Numeric(3, 1))
    remarks = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    candidate = relationship("Candidate", back_populates="interviews")
    feedbacks = relationship("InterviewFeedback", back_populates="interview", cascade="all, delete-orphan")


class InterviewFeedback(Base):
    __tablename__ = "interview_feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False)
    interviewer_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    technical_score = Column(Numeric(3, 1))
    communication_score = Column(Numeric(3, 1))
    attitude_score = Column(Numeric(3, 1))
    overall_score = Column(Numeric(3, 1))
    strengths = Column(Text)
    weaknesses = Column(Text)
    recommendation = Column(String(20))  # Hire, Reject, Hold
    comments = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    interview = relationship("Interview", back_populates="feedbacks")


class OfferLetter(Base):
    __tablename__ = "offer_letters"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    offer_date = Column(Date)
    joining_date = Column(Date)
    designation = Column(String(150))
    department = Column(String(150))
    ctc = Column(Numeric(12, 2))
    basic = Column(Numeric(12, 2))
    template_id = Column(Integer, ForeignKey("document_templates.id", ondelete="SET NULL"), nullable=True)
    letter_url = Column(String(500))
    status = Column(String(30), default="Draft")  # Draft, Sent, Accepted, Declined, Expired
    expiry_date = Column(Date)
    accepted_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    candidate = relationship("Candidate", back_populates="offer")
