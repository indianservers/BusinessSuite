from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base_class import Base


class AutomationWorkflow(Base):
    __tablename__ = "automation_workflows"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    description = Column(Text)
    module_name = Column(String(60), nullable=False, index=True)
    record_type = Column(String(80), nullable=False, index=True)
    trigger_type = Column(String(80), nullable=False, index=True)
    is_active = Column(Boolean, default=False, index=True)
    max_execution_depth = Column(Integer, default=5)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AutomationTrigger(Base):
    __tablename__ = "automation_triggers"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("automation_workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    trigger_type = Column(String(80), nullable=False, index=True)
    config_json = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AutomationCondition(Base):
    __tablename__ = "automation_conditions"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("automation_workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    condition_json = Column(JSON, nullable=False)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AutomationAction(Base):
    __tablename__ = "automation_actions"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("automation_workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(80), nullable=False, index=True)
    action_json = Column(JSON, nullable=False)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AutomationExecutionLog(Base):
    __tablename__ = "automation_execution_logs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    workflow_id = Column(Integer, ForeignKey("automation_workflows.id", ondelete="SET NULL"), nullable=True, index=True)
    module_name = Column(String(60), nullable=False, index=True)
    record_type = Column(String(80), nullable=True, index=True)
    record_id = Column(Integer, nullable=True, index=True)
    trigger_type = Column(String(80), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="success", index=True)
    depth = Column(Integer, default=0)
    request_json = Column(JSON)
    result_json = Column(JSON)
    error_message = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AutomationBlueprint(Base):
    __tablename__ = "automation_blueprints"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    module_name = Column(String(60), nullable=False, index=True)
    record_type = Column(String(80), nullable=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AutomationBlueprintStage(Base):
    __tablename__ = "automation_blueprint_stages"
    __table_args__ = (UniqueConstraint("blueprint_id", "stage_key", name="uq_automation_blueprint_stage_key"),)

    id = Column(Integer, primary_key=True, index=True)
    blueprint_id = Column(Integer, ForeignKey("automation_blueprints.id", ondelete="CASCADE"), nullable=False, index=True)
    stage_key = Column(String(80), nullable=False, index=True)
    label = Column(String(160), nullable=False)
    order_index = Column(Integer, default=0)
    required_fields_json = Column(JSON)
    requires_approval = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AutomationBlueprintTransition(Base):
    __tablename__ = "automation_blueprint_transitions"
    __table_args__ = (UniqueConstraint("blueprint_id", "from_stage_key", "to_stage_key", name="uq_automation_blueprint_transition"),)

    id = Column(Integer, primary_key=True, index=True)
    blueprint_id = Column(Integer, ForeignKey("automation_blueprints.id", ondelete="CASCADE"), nullable=False, index=True)
    from_stage_key = Column(String(80), nullable=False, index=True)
    to_stage_key = Column(String(80), nullable=False, index=True)
    required_fields_json = Column(JSON)
    requires_approval = Column(Boolean, default=False)
    automation_workflow_id = Column(Integer, ForeignKey("automation_workflows.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AutomationApprovalRule(Base):
    __tablename__ = "automation_approval_rules"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    module_name = Column(String(60), nullable=False, index=True)
    record_type = Column(String(80), nullable=False, index=True)
    condition_json = Column(JSON)
    is_active = Column(Boolean, default=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AutomationApprovalStep(Base):
    __tablename__ = "automation_approval_steps"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("automation_approval_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    step_order = Column(Integer, default=1)
    approver_role = Column(String(80), nullable=True, index=True)
    approver_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    escalation_hours = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AutomationApprovalRequest(Base):
    __tablename__ = "automation_approval_requests"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    rule_id = Column(Integer, ForeignKey("automation_approval_rules.id", ondelete="SET NULL"), nullable=True, index=True)
    module_name = Column(String(60), nullable=False, index=True)
    record_type = Column(String(80), nullable=False, index=True)
    record_id = Column(Integer, nullable=False, index=True)
    status = Column(String(30), default="draft", index=True)
    current_step = Column(Integer, default=1)
    submitted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    decided_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decision_comment = Column(Text)
    history_json = Column(JSON)
    payload_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AutomationAssignmentRule(Base):
    __tablename__ = "automation_assignment_rules"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    module_name = Column(String(60), nullable=False, index=True)
    record_type = Column(String(80), nullable=False, index=True)
    condition_json = Column(JSON)
    assignment_json = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AutomationCadence(Base):
    __tablename__ = "automation_cadences"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    module_name = Column(String(60), nullable=False, index=True)
    target_type = Column(String(80), nullable=False, index=True)
    stop_rules_json = Column(JSON)
    status = Column(String(30), default="active", index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AutomationCadenceStep(Base):
    __tablename__ = "automation_cadence_steps"

    id = Column(Integer, primary_key=True, index=True)
    cadence_id = Column(Integer, ForeignKey("automation_cadences.id", ondelete="CASCADE"), nullable=False, index=True)
    step_order = Column(Integer, default=1)
    step_type = Column(String(40), nullable=False, index=True)
    delay_hours = Column(Integer, default=0)
    payload_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AutomationWebhookEndpoint(Base):
    __tablename__ = "automation_webhook_endpoints"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    target_url = Column(String(500), nullable=False)
    event_types_json = Column(JSON)
    secret_ref = Column(String(180))
    is_active = Column(Boolean, default=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AutomationScheduledJob(Base):
    __tablename__ = "automation_scheduled_jobs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    job_type = Column(String(80), nullable=False, index=True)
    module_name = Column(String(60), nullable=False, index=True)
    record_type = Column(String(80), nullable=True, index=True)
    record_id = Column(Integer, nullable=True, index=True)
    status = Column(String(30), default="scheduled", index=True)
    run_at = Column(DateTime(timezone=True), nullable=True, index=True)
    payload_json = Column(JSON)
    attempts = Column(Integer, default=0)
    last_error = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

