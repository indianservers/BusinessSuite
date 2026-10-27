"""Approval-specific metadata around existing requests, versions and runtime waits."""

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    JSON,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    Text,
    event,
    Index,
)
from app.db.base_class import Base
from app.apps.power_apps.runtime_models import Scope


class ApprovalPolicy(Scope, Base):
    __tablename__ = "power_approval_policies"
    id = Column(Integer, primary_key=True)
    resource_id = Column(
        Integer, ForeignKey("power_apps_resources.id"), nullable=False, unique=True
    )
    runtime_resource_id = Column(Integer, ForeignKey("power_apps_resources.id"))
    published_version_id = Column(Integer, ForeignKey("power_apps_versions.id"))
    enabled = Column(Boolean, nullable=False, default=False)


class RequestState(Scope, Base):
    __tablename__ = "power_approval_request_states"
    id = Column(Integer, ForeignKey("approval_requests.id"), primary_key=True)
    policy_id = Column(
        Integer, ForeignKey("power_approval_policies.id"), nullable=False
    )
    version_id = Column(Integer, ForeignKey("power_apps_versions.id"), nullable=False)
    run_id = Column(Integer, ForeignKey("power_apps_executions.id"), unique=True)
    revision = Column(Integer, nullable=False, default=1)
    cycle = Column(Integer, nullable=False, default=1)
    fields = Column(JSON, nullable=False, default=dict)
    active_step_id = Column(Integer, ForeignKey("power_automation_steps.id"))
    submission_key = Column(String(100), nullable=False)
    head_hash = Column(String(64), nullable=False, default="")
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "environment",
            "owner_user_id",
            "submission_key",
            name="uq_power_approval_submission",
        ),
    )


class Assignment(Scope, Base):
    __tablename__ = "power_approval_assignments"
    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey("approval_requests.id"), nullable=False)
    step_id = Column(Integer, ForeignKey("power_automation_steps.id"), nullable=False)
    stage_name = Column(String(180), nullable=False)
    cycle = Column(Integer, nullable=False, default=1)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    original_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"))
    delegation_id = Column(Integer, ForeignKey("power_approval_delegations.id"))
    status = Column(String(24), nullable=False, default="pending")
    decision_actor_id = Column(Integer, ForeignKey("users.id"))
    decision_key = Column(String(100))
    decision_reason = Column(Text)
    decided_at = Column(DateTime(timezone=True))
    due_at = Column(DateTime(timezone=True), nullable=False)
    assigned_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "request_id",
            "step_id",
            "cycle",
            "original_user_id",
            name="uq_power_approval_assignment",
        ),
    )


class Delegation(Scope, Base):
    __tablename__ = "power_approval_delegations"
    id = Column(Integer, primary_key=True)
    alternate_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    policy_id = Column(Integer, ForeignKey("power_approval_policies.id"))
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    reason = Column(String(1000), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)


class Attachment(Scope, Base):
    __tablename__ = "power_approval_attachments"
    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey("approval_requests.id"), nullable=False)
    request_revision = Column(Integer, nullable=False)
    name = Column(String(180), nullable=False)
    storage_path = Column(String(500), nullable=False)
    sha256 = Column(String(64), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


# Evidence and completed voting seats are immutable through ordinary ORM operations.
from sqlalchemy import select, inspect
from sqlalchemy.orm import Session
from app.models.approval_os import ApprovalRequest, ApprovalHistory


@event.listens_for(Session, "before_flush")
def immutable_approval_evidence(db, context, instances):
    for item in db.dirty | db.deleted:
        if isinstance(item, ApprovalHistory):
            origin = (
                db.connection()
                .execute(
                    select(ApprovalRequest.source_module).where(
                        ApprovalRequest.id == item.request_id
                    )
                )
                .scalar()
            )
            if origin == "power_apps":
                raise ValueError("Approval evidence is append-only")
        if isinstance(item, Assignment):
            original = inspect(item).attrs.decided_at.history
            was_decided = bool(original.deleted and original.deleted[0]) or bool(
                not original.has_changes() and item.decided_at
            )
            if was_decided and (
                item in db.deleted or db.is_modified(item, include_collections=False)
            ):
                raise ValueError("Completed approval decisions are immutable")


Index(
    "ix_power_approval_state_scope",
    RequestState.organization_id,
    RequestState.environment,
    RequestState.owner_user_id,
)
Index(
    "ix_power_approval_assignment_inbox",
    Assignment.organization_id,
    Assignment.environment,
    Assignment.user_id,
    Assignment.status,
    Assignment.due_at,
)
Index(
    "ix_power_approval_delegation_period",
    Delegation.organization_id,
    Delegation.environment,
    Delegation.owner_user_id,
    Delegation.ends_at,
)
Index(
    "ix_power_approval_attachment_request",
    Attachment.request_id,
    Attachment.request_revision,
)
