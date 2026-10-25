from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.sql import func
from app.db.base_class import Base


class AccessMembership(Base):
    __tablename__ = "suite_access_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "company_id", name="uq_suite_access_membership"),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    active = Column(Boolean, nullable=False, default=True)
    is_admin = Column(Boolean, nullable=False, default=False)


class AccessPolicy(Base):
    __tablename__ = "suite_access_policies"
    __table_args__ = (
        UniqueConstraint("user_id", "company_id", name="uq_suite_access_policy"),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    grants = Column(JSON, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default="active")
    version = Column(Integer, nullable=False, default=1)
    updated_by = Column(Integer, ForeignKey("users.id"))
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AccessRole(Base):
    __tablename__ = "suite_access_roles"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    module_key = Column(String(80), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    permissions = Column(JSON, nullable=False, default=list)
    actions = Column(JSON, nullable=False, default=list)
    scope = Column(String(30), nullable=False, default="own")
    active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)


class AccessTemplate(Base):
    __tablename__ = "suite_access_templates"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    grants = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    active = Column(Boolean, nullable=False, default=True)


class AccessAudit(Base):
    __tablename__ = "suite_access_audit"
    id = Column(Integer, primary_key=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("users.id"), index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    operation = Column(String(80), nullable=False)
    before_json = Column(JSON)
    after_json = Column(JSON)
    reason = Column(Text, nullable=False)
    source_ip = Column(String(80))
    session_id = Column(Integer)
    outcome = Column(String(20), nullable=False, default="success")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


@event.listens_for(AccessAudit, "before_update")
@event.listens_for(AccessAudit, "before_delete")
def immutable_audit(*args):
    raise ValueError("Access audit events are append-only")
