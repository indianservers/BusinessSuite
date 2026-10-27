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
from app.apps.power_apps.runtime_models import Scope


class Credential(Scope, Base):
    __tablename__ = "power_connector_credentials"
    id = Column(Integer, primary_key=True)
    connector_id = Column(String(80), nullable=False)
    name = Column(String(180), nullable=False)
    auth_type = Column(String(30), nullable=False)
    encrypted_value = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    revoked_at = Column(DateTime(timezone=True))
    sharing = Column(JSON, nullable=False, default=list)
    hosts = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Connection(Scope, Base):
    __tablename__ = "power_connector_connections"
    id = Column(Integer, primary_key=True)
    connector_id = Column(String(80), nullable=False)
    connector_version = Column(Integer, nullable=False, default=1)
    name = Column(String(180), nullable=False)
    credential_id = Column(Integer, ForeignKey("power_connector_credentials.id"))
    config = Column(JSON, nullable=False, default=dict)
    scopes = Column(JSON, nullable=False, default=list)
    sharing = Column(JSON, nullable=False, default=list)
    writes_enabled = Column(Boolean, nullable=False, default=False)
    enabled = Column(Boolean, nullable=False, default=True)
    health = Column(String(30), nullable=False, default="unverified")
    last_verified_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    revision = Column(Integer, nullable=False, default=1)
    refresh_token = Column(String(36))  # fencing token, never an OAuth token
    refresh_until = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index(
            "ix_power_connections_scope",
            "organization_id",
            "environment",
            "connector_id",
        ),
    )


class OAuthState(Scope, Base):
    __tablename__ = "power_connector_oauth_states"
    id = Column(Integer, primary_key=True)
    connection_id = Column(
        Integer, ForeignKey("power_connector_connections.id"), nullable=False
    )
    state_hash = Column(String(64), nullable=False, unique=True)
    encrypted_verifier = Column(Text, nullable=False)
    redirect_uri = Column(String(500), nullable=False)
    scopes = Column(JSON, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True))
    connection_revision = Column(Integer, nullable=False)


class EgressGrant(Scope, Base):
    __tablename__ = "power_connector_egress_grants"
    id = Column(Integer, primary_key=True)
    host = Column(String(253), nullable=False)
    port = Column(Integer, nullable=False)
    addresses = Column(JSON, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "environment",
            "host",
            "port",
            name="uq_power_egress_target",
        ),
    )


class Operation(Scope, Base):
    __tablename__ = "power_connector_operations"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("power_apps_executions.id"))
    step_id = Column(Integer, ForeignKey("power_automation_steps.id"), unique=True)
    connection_id = Column(
        Integer, ForeignKey("power_connector_connections.id"), nullable=False
    )
    connector_id = Column(String(80), nullable=False)
    action_id = Column(String(80), nullable=False)
    operation_key = Column(String(64), nullable=False, unique=True)
    input_hash = Column(String(64), nullable=False)
    credential_version = Column(Integer)
    mutates = Column(Boolean, nullable=False)
    status = Column(String(30), nullable=False, default="prepared")
    dispatched_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    output = Column(JSON)
    error_category = Column(String(60))
    error = Column(String(400))
    correlation_id = Column(String(64), nullable=False)
    __table_args__ = (
        Index(
            "ix_power_operations_monitor",
            "organization_id",
            "environment",
            "connector_id",
            "status",
        ),
    )


class RequestLog(Scope, Base):
    __tablename__ = "power_connector_requests"
    id = Column(Integer, primary_key=True)
    operation_id = Column(Integer, ForeignKey("power_connector_operations.id"))
    connection_id = Column(Integer, ForeignKey("power_connector_connections.id"))
    connector_id = Column(String(80), nullable=False)
    action_id = Column(String(80), nullable=False)
    run_id = Column(Integer)
    correlation_id = Column(String(64), nullable=False)
    status = Column(String(30), nullable=False)
    http_status = Column(Integer)
    duration_ms = Column(Integer, nullable=False)
    error_category = Column(String(60))
    attempt = Column(Integer, nullable=False, default=1)
    response_preview = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index(
            "ix_power_requests_scope_time",
            "organization_id",
            "environment",
            "created_at",
        ),
    )


class ConnectionAudit(Scope, Base):
    __tablename__ = "power_connector_audit"
    id = Column(Integer, primary_key=True)
    connection_id = Column(Integer)
    credential_id = Column(Integer)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(60), nullable=False)
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ConnectorGate(Scope, Base):
    __tablename__ = "power_connector_gates"
    id = Column(Integer, primary_key=True)
    connection_id = Column(
        Integer,
        ForeignKey("power_connector_connections.id"),
        nullable=False,
        unique=True,
    )
    window_at = Column(DateTime(timezone=True), nullable=False)
    request_count = Column(Integer, nullable=False, default=0)
    failures = Column(Integer, nullable=False, default=0)
    open_until = Column(DateTime(timezone=True))
    leases = Column(JSON, nullable=False, default=dict)


class CustomAction(Scope, Base):
    __tablename__ = "power_connector_custom_actions"
    id = Column(Integer, primary_key=True)
    name = Column(String(180), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    connection_id = Column(
        Integer, ForeignKey("power_connector_connections.id"), nullable=False
    )
    request = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
