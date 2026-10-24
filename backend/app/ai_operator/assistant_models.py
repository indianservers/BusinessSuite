"""Private assistant history and expiring, server-owned action proposals."""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    JSON,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from app.db.base_class import Base


class AssistantConversation(Base):
    __tablename__ = "pms_assistant_conversations"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id"), nullable=True)
    title = Column(String(160), nullable=False, default="New conversation")
    references = Column(JSON, nullable=False, default=dict)
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AssistantMessage(Base):
    __tablename__ = "pms_assistant_messages"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "request_key", name="uq_assistant_message_request"
        ),
    )
    id = Column(Integer, primary_key=True)
    conversation_id = Column(
        Integer,
        ForeignKey("pms_assistant_conversations.id"),
        nullable=False,
        index=True,
    )
    request_key = Column(String(64), nullable=False)
    request_hash = Column(String(64), nullable=False)
    prompt = Column(Text, nullable=False)
    tool = Column(String(80), nullable=False)
    arguments = Column(JSON, nullable=False)
    proposal = Column(JSON, nullable=True)
    approval_hash = Column(String(64))
    expires_at = Column(DateTime(timezone=True))
    status = Column(String(30), nullable=False, default="answered")
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
