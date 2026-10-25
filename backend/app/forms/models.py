from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    LargeBinary,
    UniqueConstraint,
)
from sqlalchemy.orm import deferred
from sqlalchemy.sql import func
from app.db.base_class import Base


class SuiteForm(Base):
    __tablename__ = "suite_forms"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    module_key = Column(String(40), nullable=False, index=True)
    legacy_entry_id = Column(Integer, unique=True, nullable=True)
    workspace_id = Column(Integer, nullable=True)
    name = Column(String(120), nullable=False)
    draft = Column(JSON, nullable=False)
    published = Column(JSON, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    version = Column(Integer, nullable=False, default=0)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    open = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FormReply(Base):
    __tablename__ = "suite_form_replies"
    __table_args__ = (
        UniqueConstraint("form_id", "request_id", name="uq_suite_form_request"),
    )
    id = Column(Integer, primary_key=True)
    form_id = Column(
        Integer,
        ForeignKey("suite_forms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    legacy_entry_id = Column(Integer, unique=True, nullable=True)
    task_id = Column(Integer, nullable=True)
    request_id = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False)
    answers = Column(JSON, nullable=False)
    labels = Column(JSON, nullable=False)
    submitted_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status = Column(String(20), default="new", nullable=False)


class FormFile(Base):
    __tablename__ = "suite_form_files"
    id = Column(String(32), primary_key=True)
    reply_id = Column(
        Integer,
        ForeignKey("suite_form_replies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_id = Column(String(60), nullable=False)
    filename = Column(String(255), nullable=False)
    media_type = Column(String(100), nullable=False)
    body = deferred(Column(LargeBinary, nullable=False))


class FormChallenge(Base):
    __tablename__ = "suite_form_challenges"
    id = Column(String(32), primary_key=True)
    form_id = Column(
        Integer,
        ForeignKey("suite_forms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    answer_hash = Column(String(64), nullable=False)
    ip_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False, nullable=False)


class FormRateBucket(Base):
    __tablename__ = "suite_form_rate_buckets"
    key = Column(String(64), primary_key=True)
    window = Column(Integer, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
