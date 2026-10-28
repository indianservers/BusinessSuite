"""Durable transactional emails, committed atomically with their source changes."""
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, Index, func
from app.db.base_class import Base


class EmailOutbox(Base):
    __tablename__ = "email_outbox"
    __table_args__ = (Index("ix_email_outbox_status_created", "status", "created_at"),)
    id = Column(Integer, primary_key=True)
    event_key = Column(String(180), nullable=False, unique=True)
    organization_id = Column(Integer, nullable=True)
    module = Column(String(60), nullable=False)
    recipient_user_id = Column(Integer, nullable=True)
    recipient = Column(String(254), nullable=False)
    subject = Column(String(240), nullable=False)
    body = Column(Text, nullable=False)
    is_html = Column(Boolean, nullable=False, default=False)
    status = Column(String(30), nullable=False, default="queued")
    provider_message_id = Column(String(200), nullable=True)
    error = Column(String(240), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    accepted_at = Column(DateTime(timezone=True), nullable=True)
