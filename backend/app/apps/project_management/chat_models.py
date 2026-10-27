"""Additive messaging schema; legacy DM and workspace-entry IDs remain untouched."""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.sql import func
from app.db.base_class import Base


class ChatConversation(Base):
    __tablename__ = "pms_chat_conversations"
    id = Column(Integer, primary_key=True)
    workspace_id = Column(
        Integer,
        ForeignKey("pms_workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key = Column(String(120), unique=True, nullable=False)
    kind = Column(String(12), nullable=False)
    name = Column(String(120), nullable=False, default="")
    description = Column(String(1000), nullable=False, default="")
    visibility = Column(String(12), nullable=False, default="private")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    legacy_dm_id = Column(
        Integer, ForeignKey("pms_direct_conversations.id"), unique=True
    )
    archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class ChatMember(Base):
    __tablename__ = "pms_chat_members"
    conversation_id = Column(
        Integer,
        ForeignKey("pms_chat_conversations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    history_after = Column(Integer, nullable=False, default=0)
    read_id = Column(Integer, nullable=False, default=0)
    muted = Column(Boolean, nullable=False, default=False)
    active = Column(Boolean, nullable=False, default=True)


class ChatMessage(Base):
    __tablename__ = "pms_chat_messages"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "author_id", "client_id", name="uq_pms_chat_request"
        ),
        Index("ix_pms_chat_timeline", "conversation_id", "id"),
        Index("ix_pms_chat_thread", "parent_id", "id"),
    )
    id = Column(Integer, primary_key=True)
    conversation_id = Column(
        Integer,
        ForeignKey("pms_chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    client_id = Column(String(80), nullable=False)
    body = Column(Text, nullable=False, default="")
    parent_id = Column(Integer, ForeignKey("pms_chat_messages.id"), nullable=True)
    legacy_dm_message_id = Column(
        Integer, ForeignKey("pms_direct_messages.id"), unique=True
    )
    legacy_entry_id = Column(
        Integer, ForeignKey("pms_workspace_entries.id"), unique=True
    )
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    edited_at = Column(DateTime)
    deleted_at = Column(DateTime)


class ChatAttachment(Base):
    __tablename__ = "pms_chat_attachments"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(
        Integer,
        ForeignKey("pms_chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id = Column(Integer, ForeignKey("pms_chat_messages.id"), index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(180), nullable=False)
    mime = Column(String(100), nullable=False)
    size = Column(Integer, nullable=False)
    path = Column(Text, nullable=False)
    project_file_id = Column(Integer, ForeignKey("pms_file_assets.id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

# Shared communication metadata extends these canonical records.
from app.shared.communication import models as communication_models  # noqa: F401,E402
