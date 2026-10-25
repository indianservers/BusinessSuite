"""Owner/project-scoped assistant preferences, playbooks and execution evidence."""
from sqlalchemy import Column, Integer, String, JSON, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from app.db.base_class import Base


class AssistantArtifact(Base):
    __tablename__ = 'pms_assistant_artifacts'
    __table_args__ = (UniqueConstraint('user_id', 'project_id', 'kind', 'key', name='uq_assistant_artifact_key'),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey('pms_projects.id'), nullable=False, index=True)
    scope_key = Column(String(100), nullable=False)
    kind = Column(String(24), nullable=False, index=True)
    key = Column(String(100), nullable=False)
    title = Column(String(180), nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AssistantSignal(Base):
    __tablename__ = 'pms_assistant_signals'
    __table_args__ = (UniqueConstraint('user_id', 'request_key', name='uq_assistant_signal_request'),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey('pms_projects.id'), nullable=False, index=True)
    request_key = Column(String(100), nullable=False)
    kind = Column(String(40), nullable=False, index=True)
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
