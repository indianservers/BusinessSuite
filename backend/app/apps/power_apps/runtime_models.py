"""Additive durable state; definitions and immutable snapshots remain PowerResource/PowerVersion."""

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    JSON,
    Text,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.sql import func
from app.db.base_class import Base


class Scope:
    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    environment = Column(String(20), nullable=False)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)


class AutomationDeployment(Scope, Base):
    __tablename__ = "power_automation_deployments"
    id = Column(Integer, primary_key=True)
    resource_id = Column(
        Integer, ForeignKey("power_apps_resources.id"), nullable=False, unique=True
    )
    version_id = Column(Integer, ForeignKey("power_apps_versions.id"), nullable=True)
    status = Column(String(20), nullable=False, default="draft")
    validated_version = Column(Integer)
    revision = Column(Integer, nullable=False, default=1)
    policy = Column(JSON, nullable=False, default=dict)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AutomationRun(Scope, Base):
    __tablename__ = "power_automation_run_states"
    id = Column(Integer, ForeignKey("power_apps_executions.id"), primary_key=True)
    version_id = Column(Integer, ForeignKey("power_apps_versions.id"), nullable=False)
    trigger_id = Column(Integer)
    trigger_kind = Column(String(30), nullable=False)
    effective_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    correlation_id = Column(String(36), nullable=False, unique=True)
    plan = Column(JSON, nullable=False, default=dict)
    input_payload = Column(JSON, nullable=False)
    variables = Column(JSON, nullable=False, default=dict)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    deadline = Column(DateTime(timezone=True), nullable=False)
    error_type = Column(String(100))
    error = Column(Text)
    payloads_purged_at = Column(DateTime(timezone=True), index=True)
    __table_args__ = (
        Index(
            "ix_power_run_tenant_time", "organization_id", "environment", "started_at"
        ),
    )


class AutomationStep(Scope, Base):
    __tablename__ = "power_automation_steps"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("power_apps_executions.id"), nullable=False)
    node_id = Column(String(180), nullable=False)
    original_node_id = Column(String(80), nullable=False)
    scope = Column(String(160), nullable=False, default="")
    local_context = Column(JSON, nullable=False, default=dict)
    status = Column(String(24), nullable=False, default="pending")
    attempt = Column(Integer, nullable=False, default=0)
    input_payload = Column(JSON)
    output = Column(JSON)
    active_ports = Column(JSON, nullable=False, default=list)
    error_type = Column(String(100))
    error = Column(Text)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("run_id", "node_id", name="uq_power_step_node"),)


class AutomationJob(Scope, Base):
    __tablename__ = "power_automation_jobs"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("power_apps_executions.id"), nullable=False)
    step_id = Column(
        Integer, ForeignKey("power_automation_steps.id"), nullable=False, unique=True
    )
    status = Column(String(24), nullable=False, default="queued")
    available_at = Column(DateTime(timezone=True), nullable=False)
    lease_token = Column(String(36))
    lease_until = Column(DateTime(timezone=True))
    heartbeat_at = Column(DateTime(timezone=True))
    claims = Column(Integer, nullable=False, default=0)
    __table_args__ = (
        Index("ix_power_job_claim", "status", "available_at", "lease_until"),
        Index("ix_power_job_tenant", "organization_id", "environment", "status"),
    )


class AutomationWait(Scope, Base):
    __tablename__ = "power_automation_waits"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("power_apps_executions.id"), nullable=False)
    step_id = Column(
        Integer, ForeignKey("power_automation_steps.id"), nullable=False, unique=True
    )
    wake_at = Column(DateTime(timezone=True), nullable=False)
    event_key = Column(String(120))
    kind = Column(String(24), nullable=False, default="time")
    status = Column(String(20), nullable=False, default="waiting")
    __table_args__ = (Index("ix_power_wait_due", "status", "wake_at"),)


class AutomationTrigger(Scope, Base):
    __tablename__ = "power_automation_triggers"
    id = Column(Integer, primary_key=True)
    resource_id = Column(Integer, ForeignKey("power_apps_resources.id"), nullable=False)
    kind = Column(String(30), nullable=False)
    enabled = Column(Boolean, nullable=False, default=False)
    endpoint = Column(String(64), unique=True)
    encrypted_secret = Column(Text)
    secret_version = Column(Integer, nullable=False, default=1)
    config = Column(JSON, nullable=False, default=dict)
    next_at = Column(DateTime(timezone=True))
    last_at = Column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("resource_id", "kind", name="uq_power_trigger_kind"),
        Index("ix_power_trigger_due", "kind", "enabled", "next_at"),
    )


class AutomationEvent(Scope, Base):
    __tablename__ = "power_automation_events"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("power_apps_executions.id"))
    resource_id = Column(Integer, nullable=False)
    step_id = Column(Integer)
    kind = Column(String(40), nullable=False)
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    __table_args__ = (Index("ix_power_event_run", "run_id", "id"),)


class AutomationDeadLetter(Scope, Base):
    __tablename__ = "power_automation_dead_letters"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("power_apps_executions.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("power_automation_jobs.id"), nullable=False)
    reason = Column(String(100), nullable=False)
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AutomationReplay(Scope, Base):
    __tablename__ = "power_automation_replays"
    id = Column(Integer, primary_key=True)
    trigger_id = Column(
        Integer, ForeignKey("power_automation_triggers.id"), nullable=False
    )
    nonce_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("trigger_id", "nonce_hash", name="uq_power_trigger_replay"),
    )


class AutomationWorker(Base):
    __tablename__ = "power_automation_workers"
    id = Column(String(100), primary_key=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=False)
    scheduler_at = Column(DateTime(timezone=True))
    processed = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="running")


# Published snapshots are immutable even to accidental ORM updates in future code.
from sqlalchemy import event, select, or_
from app.apps.power_apps.models import PowerVersion


@event.listens_for(PowerVersion, "before_update")
@event.listens_for(PowerVersion, "before_delete")
def immutable_published_snapshot(mapper, connection, target):
    published = connection.execute(
        select(AutomationDeployment.id)
        .where(AutomationDeployment.version_id == target.id)
        .limit(1)
    ).first()
    used = connection.execute(
        select(AutomationRun.id).where(AutomationRun.version_id == target.id).limit(1)
    ).first()
    from app.apps.power_apps.approvals.models import ApprovalPolicy,RequestState
    approval_published=connection.execute(select(ApprovalPolicy.id).where(ApprovalPolicy.published_version_id==target.id).limit(1)).first()
    approval_used=connection.execute(select(RequestState.id).where(RequestState.version_id==target.id).limit(1)).first()
    if published or used or approval_published or approval_used:
        raise ValueError("Published workflow snapshots are immutable")
