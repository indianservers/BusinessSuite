from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False)
    module = Column(String(80), nullable=False, index=True)
    trigger_event = Column(String(120), nullable=False, index=True)
    description = Column(Text)
    is_active = Column(Boolean, default=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    steps = relationship("WorkflowStepDefinition", back_populates="workflow", cascade="all, delete-orphan", order_by="WorkflowStepDefinition.step_order")


class WorkflowStepDefinition(Base):
    __tablename__ = "workflow_step_definitions"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    step_order = Column(Integer, nullable=False)
    step_type = Column(String(40), default="Approval")
    approver_type = Column(String(40), default="Role")  # User, Role, Manager, HR
    approver_value = Column(String(120))
    condition_expression = Column(Text)
    skip_if_condition = Column(Text)
    timeout_hours = Column(Integer)
    reminder_hours = Column(Integer)
    timeout_action = Column(String(40), default="escalate")
    escalation_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    escalation_role = Column(String(120))
    action_type = Column(String(80))
    action_config = Column(JSON)
    delegation_type = Column(String(40))  # User, Role
    delegation_value = Column(String(120))
    delegation_starts_at = Column(DateTime(timezone=True))
    delegation_ends_at = Column(DateTime(timezone=True))
    metadata_json = Column(JSON)
    is_required = Column(Boolean, default=True)

    workflow = relationship("WorkflowDefinition", back_populates="steps")


class WorkflowInstance(Base):
    __tablename__ = "workflow_instances"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflow_definitions.id", ondelete="SET NULL"), nullable=True, index=True)
    module = Column(String(80), nullable=False, index=True)
    entity_type = Column(String(80), nullable=False)
    entity_id = Column(Integer, nullable=False, index=True)
    requester_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    context_json = Column(JSON)
    status = Column(String(30), default="Pending", index=True)
    current_step_order = Column(Integer, default=1)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))


class WorkflowTask(Base):
    __tablename__ = "workflow_tasks"

    id = Column(Integer, primary_key=True, index=True)
    instance_id = Column(Integer, ForeignKey("workflow_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    step_definition_id = Column(Integer, ForeignKey("workflow_step_definitions.id", ondelete="SET NULL"), nullable=True)
    assigned_to_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_role = Column(String(120), index=True)
    original_assigned_to_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    original_assigned_role = Column(String(120))
    delegated_to_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    delegated_role = Column(String(120))
    delegation_reason = Column(Text)
    delegation_started_at = Column(DateTime(timezone=True))
    delegation_ends_at = Column(DateTime(timezone=True))
    status = Column(String(30), default="Pending", index=True)
    due_at = Column(DateTime(timezone=True))
    reminder_sent_at = Column(DateTime(timezone=True))
    escalated_at = Column(DateTime(timezone=True))
    escalated_to_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decision = Column(String(30))
    decision_reason = Column(Text)
    decided_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WorkflowDelegation(Base):
    __tablename__ = "workflow_delegations"

    id = Column(Integer, primary_key=True, index=True)
    delegator_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    delegator_role = Column(String(120), index=True)
    delegate_to_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    delegate_to_role = Column(String(120), index=True)
    module = Column(String(80), index=True)
    reason = Column(Text)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WorkflowAuditEvent(Base):
    __tablename__ = "workflow_audit_events"

    id = Column(Integer, primary_key=True, index=True)
    instance_id = Column(Integer, ForeignKey("workflow_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("workflow_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    step_definition_id = Column(Integer, ForeignKey("workflow_step_definitions.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(60), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    before_status = Column(String(30))
    after_status = Column(String(30))
    reason = Column(Text)
    details_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
