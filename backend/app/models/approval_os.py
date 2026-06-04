from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True, index=True)
    source_module = Column(String(80), nullable=False, index=True)
    approval_type = Column(String(80), nullable=False, index=True)
    entity_type = Column(String(80), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    title = Column(String(220), nullable=False)
    description = Column(Text)
    requester_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_to_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_role = Column(String(120), index=True)
    delegated_to_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    delegated_role = Column(String(120))
    priority = Column(String(30), default="Normal", index=True)
    status = Column(String(30), default="Pending", index=True)
    sla_due_at = Column(DateTime(timezone=True), index=True)
    escalated_at = Column(DateTime(timezone=True))
    escalation_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    escalation_role = Column(String(120))
    ai_summary = Column(Text)
    context_json = Column(JSON)
    decision_reason = Column(Text)
    decided_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at = Column(DateTime(timezone=True))
    mobile_enabled = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    comments = relationship("ApprovalComment", back_populates="request", cascade="all, delete-orphan")
    history = relationship("ApprovalHistory", back_populates="request", cascade="all, delete-orphan")


class ApprovalComment(Base):
    __tablename__ = "approval_comments"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    author_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    comment = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    request = relationship("ApprovalRequest", back_populates="comments")


class ApprovalHistory(Base):
    __tablename__ = "approval_history"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(60), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    before_status = Column(String(30))
    after_status = Column(String(30))
    reason = Column(Text)
    details_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    request = relationship("ApprovalRequest", back_populates="history")
