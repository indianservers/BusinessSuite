"""Durable, owner-bound multi-module plans and checkpoint receipts."""
from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.db.base_class import Base


class SuiteRun(Base):
    __tablename__ = 'ai_suite_runs'
    __table_args__ = (UniqueConstraint('user_id', 'request_key', name='uq_suite_user_request'),)
    security_context = Column(JSON)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey('user_sessions.id'), nullable=True)
    workspace_id = Column(Integer, ForeignKey('pms_workspaces.id'), nullable=True)
    scope_key = Column(String(100), nullable=False, index=True)
    request_key = Column(String(100), nullable=False)
    request_hash = Column(String(64), nullable=False)
    command = Column(Text, nullable=False)
    plan = Column(JSON, nullable=True)
    plan_hash = Column(String(64), nullable=True)
    snapshots = Column(JSON, nullable=False, default=dict)
    status = Column(String(40), nullable=False, default='planning', index=True)
    approval_id = Column(Integer, ForeignKey('ai_action_approvals.id'), nullable=True)
    receipts = Column(JSON, nullable=False, default=list)
    result = Column(JSON, nullable=True)
    active_step = Column(Integer, nullable=True)
    lease_until = Column(DateTime(timezone=True), nullable=True)
    error_code = Column(String(80), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
