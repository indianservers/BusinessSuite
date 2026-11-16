from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.db.base_class import Base


class TelegramIdentity(Base):
    __tablename__ = 'power_telegram_identities'
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('companies.id'), nullable=False, index=True)
    environment = Column(String(20), nullable=False)
    resource_id = Column(Integer, ForeignKey('power_apps_resources.id'), nullable=False)
    telegram_id = Column(String(20), nullable=False)
    interface = Column(String(20), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=True)
    contact_id = Column(Integer, nullable=True)
    lead_id = Column(Integer, nullable=True)
    display_name = Column(String(180), nullable=False, default='')
    verified_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint('resource_id', 'telegram_id', 'interface', name='uq_telegram_identity'),)


class TelegramLinkChallenge(Base):
    __tablename__ = 'power_telegram_link_challenges'
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    environment = Column(String(20), nullable=False)
    resource_id = Column(Integer, ForeignKey('power_apps_resources.id'), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    interface = Column(String(20), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    contact_id = Column(Integer, nullable=True)
    lead_id = Column(Integer, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)


class TelegramConversation(Base):
    __tablename__ = 'power_telegram_conversations'
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('companies.id'), nullable=False, index=True)
    environment = Column(String(20), nullable=False)
    resource_id = Column(Integer, ForeignKey('power_apps_resources.id'), nullable=False)
    chat_id = Column(String(20), nullable=False)
    telegram_id = Column(String(20), nullable=False)
    interface = Column(String(20), nullable=False)
    identity_id = Column(Integer, ForeignKey('power_telegram_identities.id'), nullable=True)
    status = Column(String(20), nullable=False, default='bot')
    assignee_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    state = Column(JSON, nullable=False, default=dict)
    lead_id = Column(Integer, nullable=True)
    task_id = Column(Integer, nullable=True)
    last_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint('resource_id', 'chat_id', 'interface', name='uq_telegram_conversation'),)


class TelegramMessage(Base):
    __tablename__ = 'power_telegram_messages'
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey('power_telegram_conversations.id'), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    environment = Column(String(20), nullable=False)
    resource_id = Column(Integer, ForeignKey('power_apps_resources.id'), nullable=False)
    direction = Column(String(20), nullable=False)
    text = Column(Text, nullable=False)
    update_id = Column(Integer, nullable=True)
    run_id = Column(Integer, ForeignKey('power_apps_executions.id'), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    client_key = Column(String(80), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint('resource_id', 'update_id', name='uq_telegram_message_update'), UniqueConstraint('conversation_id', 'client_key', name='uq_telegram_message_client'),)

class PowerEnvironment(Base):
    __tablename__ = "power_apps_environments"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    key = Column(String(20), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_power_environment"), CheckConstraint("key IN ('development','testing','production')", name="ck_power_environment_key"))

class PowerResource(Base):
    __tablename__ = "power_apps_resources"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    environment = Column(String(20), nullable=False)
    application_id = Column(String(40), nullable=False)
    name = Column(String(180), nullable=False)
    description = Column(Text, nullable=False, default="")
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    version = Column(Integer, nullable=False, default=1)
    definition = Column(JSON, nullable=False, default=dict)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (Index("ix_power_resources_scope", "organization_id", "environment", "application_id"), Index("ix_power_resources_lifecycle", "organization_id", "environment", "archived_at"), CheckConstraint("status = 'draft'", name="ck_power_resource_draft_only"), CheckConstraint("environment IN ('development','testing','production')", name="ck_power_resource_environment"))

class PowerVersion(Base):
    __tablename__ = "power_apps_versions"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    resource_id = Column(Integer, ForeignKey("power_apps_resources.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    snapshot = Column(JSON, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint("resource_id", "version", name="uq_power_resource_version"),)

class PowerActivity(Base):
    __tablename__ = "power_apps_activity"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    environment = Column(String(20), nullable=False)
    resource_id = Column(Integer, nullable=True)  # retained after resource deletion
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(40), nullable=False)
    resource_name = Column(String(180), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (Index("ix_power_activity_scope", "organization_id", "environment", "created_at"),)

class PowerExecution(Base):
    __tablename__ = "power_apps_executions"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    environment = Column(String(20), nullable=False)
    resource_id = Column(Integer, ForeignKey("power_apps_resources.id"), nullable=False)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    workflow_version = Column(Integer, nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    idempotency_key = Column(String(180), nullable=False)
    status = Column(String(20), nullable=False)
    attempt = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint("organization_id", "environment", "resource_id", "idempotency_key", name="uq_power_execution_idempotency"), Index("ix_power_execution_scope", "organization_id", "environment", "status"))
