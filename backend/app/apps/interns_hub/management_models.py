"""HRMS program records. No task execution or approval states live here."""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, JSON, Numeric, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.db.base_class import Base


class InternBatch(Base):
    __tablename__ = "intern_batches"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_intern_batch_code"),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    name = Column(String(180), nullable=False)
    code = Column(String(40), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    manager_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mentor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    additional_mentors = Column(JSON, default=list)
    project_id = Column(Integer, ForeignKey("pms_projects.id"), nullable=False, index=True)
    batch_type = Column(String(20), nullable=False, default="Intern", server_default="Intern")
    coordinator_user_id = Column(Integer, ForeignKey("users.id"))
    project_ids = Column(JSON, default=list)
    task_templates = Column(JSON, default=list)
    program = Column(String(100), nullable=False, default="Internship")
    specialization = Column(String(160))
    description = Column(Text)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    capacity = Column(Integer, nullable=False)
    expected_hours = Column(Numeric(4, 1), default=8)
    reporting_frequency = Column(String(20), default="Daily")
    policy = Column(JSON, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default="Draft", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class InternBatchMembership(Base):
    __tablename__ = "intern_batch_memberships"
    __table_args__ = (Index("ix_intern_membership_active", "batch_id", "status", "employee_id"), UniqueConstraint("batch_id", "employee_id", "active_slot", name="uq_intern_active_membership"))
    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey("intern_batches.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="Active")
    active_slot = Column(Integer, nullable=True, default=1)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    left_at = Column(DateTime(timezone=True))
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    previous_batch_id = Column(Integer, ForeignKey("intern_batches.id"))
    reason = Column(Text)


class InternDistribution(Base):
    __tablename__ = "intern_task_distribution_jobs"
    __table_args__ = (UniqueConstraint("organization_id", "idempotency_key", name="uq_intern_distribution_key"),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id"), nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    idempotency_key = Column(String(100), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    recipients = Column(JSON, nullable=False)
    batch_ids = Column(JSON, default=list)
    reviewer_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    maximum_score = Column(Integer, nullable=False, default=100)
    due_date = Column(Date, nullable=False)
    cursor = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="Pending", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    error = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class InternTaskSchedule(Base):
    __tablename__ = "intern_task_schedules"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipients = Column(JSON, nullable=False)
    batch_ids = Column(JSON, default=list)
    reviewer_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    maximum_score = Column(Integer, default=100)
    interval_days = Column(Integer, nullable=False, default=1, server_default="1")
    frequency = Column(String(10), nullable=False)
    next_run = Column(Date, nullable=False, index=True)
    until = Column(Date, nullable=False)
    active = Column(Integer, nullable=False, default=1)
    last_error = Column(String(500))


class InternCompletionReview(Base):
    __tablename__ = "intern_completion_reviews"
    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey("intern_batches.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    decision = Column(String(30), nullable=False)
    reviewer_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    note = Column(Text)
    verification_id = Column(String(80), unique=True)
    certificate_id = Column(Integer, ForeignKey("intern_hub_certificates.id"))
    snapshot = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class InternReportReview(Base):
    __tablename__ = "intern_report_reviews"
    id = Column(Integer, primary_key=True)
    report_snapshot = Column(JSON)
    report_id = Column(Integer, ForeignKey("intern_hub_reports.id"), nullable=False, index=True)
    reviewer_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    decision = Column(String(30), nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class InternLegacyTaskMap(Base):
    __tablename__ = "intern_legacy_task_maps"
    legacy_task_id = Column(Integer, ForeignKey("intern_hub_tasks.id"), primary_key=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id"), nullable=False, unique=True)


class InternLegacyFileMap(Base):
    __tablename__ = "intern_legacy_file_maps"
    legacy_file_id = Column(Integer, ForeignKey("intern_hub_files.id"), primary_key=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id"), primary_key=True)
    file_id = Column(Integer, ForeignKey("pms_file_assets.id"), nullable=False, unique=True)


class ApplicationEvent(Base):
    __tablename__="intern_application_events"
    id=Column(Integer,primary_key=True)
    application_id=Column(Integer,ForeignKey("intern_hub_applications.id"),nullable=False,index=True)
    actor_user_id=Column(Integer,ForeignKey("users.id"))
    state=Column(String(40),nullable=False)
    note=Column(Text)
    created_at=Column(DateTime(timezone=True),server_default=func.now())

class ApplicationDocument(Base):
    __tablename__="intern_application_documents"
    id=Column(Integer,primary_key=True)
    application_id=Column(Integer,ForeignKey("intern_hub_applications.id"),index=True)
    claim_hash=Column(String(64),nullable=False,unique=True)
    uploader_hash=Column(String(64),index=True)
    name=Column(String(255),nullable=False)
    category=Column(String(30),nullable=False)
    storage_path=Column(Text,nullable=False)
    mime_type=Column(String(100),nullable=False)
    size=Column(Integer,nullable=False)
    created_at=Column(DateTime(timezone=True),server_default=func.now())
