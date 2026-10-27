"""Additive metadata; conversations, messages, files and tasks remain canonical."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.db.base_class import Base


class Reaction(Base):
    __tablename__ = "communication_chat_reactions"
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("pms_chat_messages.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    emoji = Column(String(24), primary_key=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Pin(Base):
    __tablename__ = "communication_chat_pins"
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("pms_chat_messages.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class SavedMessage(Base):
    __tablename__ = "communication_chat_saved"
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("pms_chat_messages.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Draft(Base):
    __tablename__ = "communication_chat_drafts"
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("pms_chat_conversations.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    thread_id = Column(Integer, primary_key=True, default=0)
    body = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class Revision(Base):
    __tablename__ = "communication_chat_revisions"
    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("pms_chat_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class ConversationContext(Base):
    __tablename__ = "communication_chat_contexts"
    __table_args__ = (UniqueConstraint("workspace_id", "module", "entity_type", "entity_id", name="uq_communication_context"),)
    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("pms_chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    module = Column(String(40), nullable=False)
    entity_type = Column(String(40), nullable=False)
    entity_id = Column(Integer, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class FollowUp(Base):
    __tablename__ = "communication_chat_followups"
    __table_args__ = (UniqueConstraint("conversation_id", "created_by", "client_id", name="uq_communication_followup_request"), Index("ix_communication_followup_due", "status", "due_at"))
    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("pms_chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("pms_chat_messages.id"), nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    client_id = Column(String(80), nullable=False)
    request_hash = Column(String(64), nullable=False)
    title = Column(String(220), nullable=False)
    description = Column(Text, nullable=False, default="")
    priority = Column(String(12), nullable=False, default="Medium")
    status = Column(String(20), nullable=False, default="Open")
    due_at = Column(DateTime, nullable=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id"), nullable=True, index=True)
    reminded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now())


class Preference(Base):
    __tablename__ = "communication_chat_preferences"
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("pms_chat_conversations.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    mode = Column(String(16), nullable=False, default="all")
    favorite = Column(Boolean, nullable=False, default=False)
    dnd_until = Column(DateTime)


class Presence(Base):
    __tablename__ = "communication_chat_presence"
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("pms_chat_conversations.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    seen_at = Column(DateTime, nullable=False)
    typing_until = Column(DateTime, nullable=True)


class CommunicationEvent(Base):
    __tablename__ = "communication_chat_events"
    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("pms_chat_conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class MeetingLink(Base):
    __tablename__ = "communication_chat_meetings"
    __table_args__ = (UniqueConstraint("conversation_id", "created_by", "client_id", name="uq_communication_meeting_request"),)
    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("pms_chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id = Column(Integer, ForeignKey("pms_calendar_events.id", ondelete="CASCADE"), nullable=False, unique=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    client_id = Column(String(80), nullable=False)
    request_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
