from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.sql import func
from app.db.base_class import Base


class OperatorProvider(Base):
    __tablename__ = "ai_operator_providers"
    __table_args__ = (UniqueConstraint("scope_key", "provider", name="uq_operator_provider_scope"),)
    id = Column(Integer, primary_key=True)
    scope_key = Column(String(100), nullable=False, index=True)
    provider = Column(String(20), nullable=False)
    model = Column(String(120), nullable=False)
    encrypted_key = Column(Text, nullable=False)
    enabled = Column(Boolean, nullable=False, default=False)
    data_sharing_allowed = Column(Boolean, nullable=False, default=False)
    allow_workspace_inheritance = Column(Boolean, nullable=False, default=False, server_default='false')
    max_tokens = Column(Integer, nullable=False, default=3000)
    input_price = Column(Numeric(14, 6), nullable=True)
    output_price = Column(Numeric(14, 6), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OperatorRun(Base):
    __tablename__ = "ai_operator_runs"
    __table_args__ = (UniqueConstraint("user_id", "request_key", name="uq_operator_command_request"),)
    security_context = Column(JSON)
    id = Column(Integer, primary_key=True)
    scope_key = Column(String(100), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id"), nullable=False)
    request_key = Column(String(100), nullable=False)
    request_hash = Column(String(64), nullable=False)
    command = Column(Text, nullable=False)
    input_mode = Column(String(10), nullable=False)
    provider = Column(String(20), nullable=False)
    status = Column(String(30), nullable=False, default="planning")
    selection = Column(JSON, nullable=False)
    snapshots = Column(JSON, nullable=False, default=dict)
    plan = Column(JSON, nullable=True)
    plan_hash = Column(String(64), nullable=True)
    approval_id = Column(Integer, ForeignKey("ai_action_approvals.id"), nullable=True)
    result = Column(JSON, nullable=True)
    error_code = Column(String(60), nullable=True)
    background = Column(Boolean, nullable=False, default=False)
    execution_mode = Column(String(20), nullable=False, default="atomic")
    parent_run_id = Column(Integer, ForeignKey("ai_operator_runs.id", name="fk_operator_parent_run"), nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    timezone = Column(String(80), nullable=False, default="Asia/Kolkata")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OperatorApiLog(Base):
    __tablename__ = "ai_operator_api_logs"
    id = Column(Integer, primary_key=True)
    scope_key = Column(String(100), nullable=False, index=True)
    module = Column(String(40), nullable=False, default='PMS', server_default='PMS')
    suite_run_id = Column(Integer, ForeignKey('ai_suite_runs.id'), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    run_id = Column(Integer, ForeignKey("ai_operator_runs.id"), nullable=True, index=True)
    provider = Column(String(20), nullable=False)
    model = Column(String(120), nullable=False)
    purpose = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False)
    error_code = Column(String(60), nullable=True)
    http_status = Column(Integer, nullable=True)
    provider_request_id = Column(String(180), nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    estimated_cost = Column(Numeric(18, 8), nullable=True)
    duration_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class OperatorJob(Base):
    __tablename__ = "ai_operator_jobs"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("ai_operator_runs.id"), nullable=False, index=True)
    kind = Column(String(20), nullable=False)
    dedupe_key = Column(String(100), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default="queued", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    failures = Column(Integer, nullable=False, default=0)
    available_at = Column(DateTime(timezone=True), nullable=False)
    lease_token = Column(String(64), nullable=True)
    lease_until = Column(DateTime(timezone=True), nullable=True)
    error_code = Column(String(60), nullable=True)


class OperatorStep(Base):
    __tablename__ = "ai_operator_steps"
    __table_args__ = (UniqueConstraint("run_id", "position", name="uq_operator_step_position"),)
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("ai_operator_runs.id"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    depends_on = Column(JSON, nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    receipt = Column(JSON, nullable=True)
    error_code = Column(String(60), nullable=True)


class OperatorEvent(Base):
    __tablename__ = "ai_operator_events"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("ai_operator_runs.id"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OperatorProposal(Base):
    __tablename__ = "ai_operator_proposals"
    __table_args__ = (UniqueConstraint("user_id", "request_key", name="uq_operator_proposal_request"),)
    security_context = Column(JSON)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    scope_key = Column(String(100), nullable=False, index=True)
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id"), nullable=True)
    kind = Column(String(30), nullable=False)
    approval_id = Column(Integer, ForeignKey("ai_action_approvals.id"), nullable=True)
    request_key = Column(String(100), nullable=False)
    request_hash = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    plan_hash = Column(String(64), nullable=False)
    status = Column(String(30), nullable=False, default="awaiting_approval")
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OperatorMonitor(Base):
    __tablename__ = "ai_operator_monitors"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id"), nullable=False, index=True)
    scope_key = Column(String(100), nullable=False)
    name = Column(String(180), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    interval_minutes = Column(Integer, nullable=False, default=60)
    next_check_at = Column(DateTime(timezone=True), nullable=False, index=True)
    finding_hash = Column(String(64), nullable=True)
    findings = Column(JSON, nullable=True)
    checked_at = Column(DateTime(timezone=True), nullable=True)
    error_code = Column(String(60), nullable=True)

from app.ai_operator.assistant_models import AssistantConversation, AssistantMessage  # noqa: F401
from app.ai_operator.workbench_models import AssistantArtifact, AssistantSignal  # noqa: F401
from app.ai_operator.suite_models import SuiteRun  # noqa: F401
