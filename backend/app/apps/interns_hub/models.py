from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.sql import func
from app.db.base_class import Base


class InternTask(Base):
    __tablename__ = "intern_hub_tasks"
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(80), default="Project")
    priority = Column(String(20), default="Medium")
    status = Column(String(30), default="Pending")
    points = Column(Integer, default=10)
    due_date = Column(Date, nullable=False)
    instructions = Column(Text)
    objectives = Column(Text)
    deliverables = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class InternSubmission(Base):
    __tablename__ = "intern_hub_submissions"
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("intern_hub_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    notes = Column(Text, nullable=False)
    links = Column(JSON, default=list)
    files = Column(JSON, default=list)
    revision_note = Column(Text)
    status = Column(String(30), default="Pending Review")
    score = Column(Integer)
    feedback = Column(Text)
    strengths = Column(Text)
    improvements = Column(Text)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class InternReport(Base):
    __tablename__ = "intern_hub_reports"
    task_entries = Column(JSON, default=list)
    evidence = Column(JSON, default=list)
    in_progress = Column(Text)
    submitted_at = Column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("employee_id", "report_date", name="uq_intern_report_day"),)
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    report_date = Column(Date, nullable=False)
    work = Column(Text, nullable=False)
    learning = Column(Text, nullable=False)
    blockers = Column(Text)
    tomorrow = Column(Text)
    mood = Column(String(20))
    minutes = Column(Integer, default=0)
    status = Column(String(20), default="Draft")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class InternCourse(Base):
    __tablename__ = "intern_hub_courses"
    organization_id = Column(Integer, nullable=False, default=1, server_default="1", index=True)
    id = Column(Integer, primary_key=True)
    title = Column(String(180), nullable=False)
    description = Column(Text)
    level = Column(String(40), default="Beginner")
    lessons = Column(JSON, default=list)
    questions = Column(JSON, default=list)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"))
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))


class InternEnrollment(Base):
    __tablename__ = "intern_hub_enrollments"
    __table_args__ = (UniqueConstraint("employee_id", "course_id", name="uq_intern_enrollment"),)
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("intern_hub_courses.id", ondelete="CASCADE"), nullable=False)
    completed_lessons = Column(JSON, default=list)
    score = Column(Integer)


class InternCertificate(Base):
    __tablename__ = "intern_hub_certificates"
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(180), nullable=False)
    certificate_type = Column(String(40), default="Module Completion")
    verification_id = Column(String(80), unique=True)
    document_certificate_id = Column(Integer, ForeignKey("employee_certificates.id", ondelete="SET NULL"))
    issued_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    issued_at = Column(DateTime(timezone=True), server_default=func.now())


class InternFile(Base):
    __tablename__ = "intern_hub_files"
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(240), nullable=False)
    storage_key = Column(String(100), nullable=False, unique=True)
    size = Column(Integer, nullable=False)


class InternTicket(Base):
    __tablename__ = "intern_hub_tickets"
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    subject = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(30), default="Open")
    reply = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class InternApplication(Base):
    __tablename__ = "intern_hub_applications"
    organization_id = Column(Integer, nullable=False, default=1, server_default="1", index=True)
    lifecycle = Column(String(40), nullable=False, default="Pending Verification", server_default="Pending Verification")
    id = Column(Integer, primary_key=True)
    reference = Column(String(40), nullable=False, unique=True)
    email = Column(String(150), nullable=False, unique=True, index=True)
    full_name = Column(String(160), nullable=False)
    password_hash = Column(String(255), nullable=False)
    details = Column(JSON, nullable=False)
    identity_number_encrypted = Column(Text, nullable=False)
    identity_last4 = Column(String(4), nullable=False)
    status = Column(String(20), nullable=False, default="Pending", index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), unique=True)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    review_note = Column(Text)
    reviewed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
