"""Durable workforce operations shared by HRMS, PMS and the intern portal."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.db.base_class import Base


class WorkforceJob(Base):
    __tablename__ = "workforce_jobs"
    __table_args__ = (
        UniqueConstraint("organization_id", "request_key", name="uq_workforce_job_request"),
        Index("ix_workforce_jobs_org_state", "organization_id", "status", "id"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    request_key = Column(String(100), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    operation = Column(String(30), nullable=False)
    payload = Column(JSON, nullable=False)
    recipients = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default="Pending")
    cursor = Column(Integer, nullable=False, default=0)
    attempts = Column(Integer, nullable=False, default=0)
    error = Column(String(500))
    result = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WorkforceMessage(Base):
    __tablename__ = "workforce_messages"
    __table_args__ = (
        UniqueConstraint("job_id", "employee_id", name="uq_workforce_message_recipient"),
        Index("ix_workforce_message_inbox", "organization_id", "user_id", "acknowledged_at", "id"),
        Index("ix_workforce_message_employee", "organization_id", "employee_id", "id"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False)
    job_id = Column(Integer, ForeignKey("workforce_jobs.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    kind = Column(String(20), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False, default="normal")
    acknowledged_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))
    resolved_by = Column(Integer, ForeignKey("users.id"))
    resolution = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WorkforceJobFailure(Base):
    __tablename__ = "workforce_job_failures"
    __table_args__ = (UniqueConstraint("job_id", "record_id", name="uq_workforce_job_failure"),)
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("workforce_jobs.id"), nullable=False, index=True)
    record_id = Column(Integer, nullable=False)
    message = Column(String(300), nullable=False)
