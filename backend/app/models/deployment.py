from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, UniqueConstraint
from app.db.base_class import Base


class CollaborationEvent(Base):
    __tablename__ = "pms_collaboration_events"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)


class ScheduledJobRun(Base):
    __tablename__ = "scheduled_job_runs"
    __table_args__ = (UniqueConstraint("job_name", "period", name="uq_scheduled_job_period"),)
    id = Column(Integer, primary_key=True)
    job_name = Column(String(100), nullable=False)
    period = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    cursor = Column(Integer, nullable=False, default=0)
    attempts = Column(Integer, nullable=False, default=0)
    lease_until = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), nullable=False)
    error = Column(Text)
    result = Column(JSON)
