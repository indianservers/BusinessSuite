from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class AiAgent(Base):
    __tablename__ = "ai_agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False, index=True)
    code = Column(String(120), nullable=False, unique=True, index=True)
    module = Column(String(40), nullable=False, index=True)
    description = Column(Text)
    system_prompt = Column(Text, nullable=False)
    model = Column(String(80))
    temperature = Column(Float, default=0.2)
    is_active = Column(Boolean, default=True, index=True)
    requires_approval = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tools = relationship("AiAgentTool", back_populates="agent", cascade="all, delete-orphan")


class AiAgentTool(Base):
    __tablename__ = "ai_agent_tools"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False, index=True)
    tool_name = Column(String(120), nullable=False, index=True)
    tool_description = Column(Text)
    input_schema_json = Column(JSON, nullable=False)
    module = Column(String(40), nullable=False, index=True)
    permission_required = Column(String(120))
    risk_level = Column(String(30), default="low", index=True)
    requires_approval = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    agent = relationship("AiAgent", back_populates="tools")


class AiConversation(Base):
    __tablename__ = "ai_conversations"

    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    security_context = Column(JSON)
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(Integer, ForeignKey("ai_agents.id", ondelete="SET NULL"), nullable=True, index=True)
    module = Column(String(40), nullable=False, index=True)
    title = Column(String(220), nullable=False)
    related_entity_type = Column(String(80), index=True)
    related_entity_id = Column(String(80), index=True)
    status = Column(String(30), default="active", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    agent = relationship("AiAgent")
    messages = relationship("AiMessage", back_populates="conversation", cascade="all, delete-orphan")


class AiMessage(Base):
    __tablename__ = "ai_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    role = Column(String(30), nullable=False, index=True)
    content = Column(Text)
    tool_call_json = Column(JSON)
    tool_result_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("AiConversation", back_populates="messages")


class AiActionApproval(Base):
    __tablename__ = "ai_action_approvals"

    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    security_context = Column(JSON)
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    agent_id = Column(Integer, ForeignKey("ai_agents.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    module = Column(String(40), nullable=False, index=True)
    action_type = Column(String(120), nullable=False, index=True)
    related_entity_type = Column(String(80), index=True)
    related_entity_id = Column(String(80), index=True)
    proposed_action_json = Column(JSON, nullable=False)
    status = Column(String(30), default="pending", index=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    execution_status = Column(String(30), default="pending", index=True)
    executed_at = Column(DateTime(timezone=True))
    execution_result_json = Column(JSON)
    execution_error = Column(Text)
    idempotency_key = Column(String(160), index=True)
    rejected_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    agent = relationship("AiAgent")
    conversation = relationship("AiConversation")


class AiAuditLog(Base):
    __tablename__ = "ai_audit_logs"

    organization_id = Column(Integer, nullable=True, index=True)
    session_id = Column(Integer, nullable=True)
    correlation_id = Column(String(64), nullable=True, index=True)
    event_key = Column(String(64), nullable=True, unique=True, index=True)
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    agent_id = Column(Integer, ForeignKey("ai_agents.id", ondelete="SET NULL"), nullable=True, index=True)
    module = Column(String(40), nullable=False, index=True)
    action = Column(String(140), nullable=False, index=True)
    related_entity_type = Column(String(80), index=True)
    related_entity_id = Column(String(80), index=True)
    input_json = Column(JSON)
    output_json = Column(JSON)
    status = Column(String(30), default="success", index=True)
    ip_address = Column(String(64))
    user_agent = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    agent = relationship("AiAgent")


class AiAgentSetting(Base):
    __tablename__ = "ai_agent_settings"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    agent_id = Column(Integer, ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False, index=True)
    is_enabled = Column(Boolean, default=True, index=True)
    auto_action_enabled = Column(Boolean, default=False)
    approval_required = Column(Boolean, default=True)
    data_access_scope = Column(String(80), default="own_records")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    agent = relationship("AiAgent")


class AiUsageLimit(Base):
    __tablename__ = "ai_usage_limits"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    agent_id = Column(Integer, ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=True, index=True)
    module = Column(String(40), nullable=True, index=True)
    limit_type = Column(String(40), nullable=False, index=True)
    max_requests = Column(Integer, nullable=False)
    period = Column(String(20), nullable=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    agent = relationship("AiAgent")


class AiUsageEvent(Base):
    __tablename__ = "ai_usage_events"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    agent_id = Column(Integer, ForeignKey("ai_agents.id", ondelete="SET NULL"), nullable=True, index=True)
    module = Column(String(40), nullable=True, index=True)
    event_type = Column(String(40), nullable=False, index=True)
    token_input = Column(Integer, default=0)
    token_output = Column(Integer, default=0)
    estimated_cost = Column(Numeric(12, 6))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    agent = relationship("AiAgent")


class AiAgentPermission(Base):
    __tablename__ = "ai_agent_permissions"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    agent_id = Column(Integer, ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    can_use = Column(Boolean, default=True)
    can_configure = Column(Boolean, default=False)
    can_approve_actions = Column(Boolean, default=False)
    can_view_logs = Column(Boolean, default=False)
    can_export_conversations = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    agent = relationship("AiAgent")


class AiSecuritySetting(Base):
    __tablename__ = "ai_security_settings"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, unique=True, index=True)
    ai_enabled = Column(Boolean, default=True)
    crm_ai_enabled = Column(Boolean, default=True)
    pms_ai_enabled = Column(Boolean, default=True)
    hrms_ai_enabled = Column(Boolean, default=True)
    cross_ai_enabled = Column(Boolean, default=True)
    emergency_message = Column(Text)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AiCostLog(Base):
    __tablename__ = "ai_cost_logs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    agent_id = Column(Integer, ForeignKey("ai_agents.id", ondelete="SET NULL"), nullable=True, index=True)
    conversation_id = Column(Integer, ForeignKey("ai_conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    model = Column(String(80), index=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    estimated_cost = Column(Numeric(12, 6))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AiMessageFeedback(Base):
    __tablename__ = "ai_message_feedback"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("ai_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(Integer, ForeignKey("ai_agents.id", ondelete="SET NULL"), nullable=True, index=True)
    rating = Column(String(20), nullable=False, index=True)
    feedback_text = Column(Text)
    feedback_type = Column(String(40), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AiHandoffNote(Base):
    __tablename__ = "ai_handoff_notes"
    organization_id = Column(Integer, ForeignKey("companies.id"), index=True)
    security_context = Column(JSON)

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    agent_id = Column(Integer, ForeignKey("ai_agents.id", ondelete="SET NULL"), nullable=True, index=True)
    module = Column(String(40), nullable=False, index=True)
    related_entity_type = Column(String(80), index=True)
    related_entity_id = Column(String(80), index=True)
    assigned_to = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    priority = Column(String(20), default="medium", index=True)
    summary = Column(String(300), nullable=False)
    reason = Column(Text)
    recommended_action = Column(Text)
    status = Column(String(30), default="open", index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


from sqlalchemy import event as _ai_event
@_ai_event.listens_for(AiAuditLog,"before_update")
@_ai_event.listens_for(AiAuditLog,"before_delete")
def _protect_ai_audit(mapper,connection,target):
    raise ValueError("AI audit events are append-only")
