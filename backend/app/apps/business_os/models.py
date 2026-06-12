from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base_class import Base


class BOSEnabledModule(Base):
    __tablename__ = "bos_enabled_modules"
    __table_args__ = (UniqueConstraint("company_id", "module_key", name="uq_bos_enabled_module_company_key"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    module_key = Column(String(80), nullable=False, index=True)
    display_name = Column(String(160), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    is_financial_backbone = Column(Boolean, default=False, nullable=False)
    enabled_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    disabled_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    enabled_at = Column(DateTime(timezone=True), nullable=True)
    disabled_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class BOSModuleDependency(Base):
    __tablename__ = "bos_module_dependencies"
    __table_args__ = (UniqueConstraint("module_key", "depends_on_module_key", name="uq_bos_module_dependency"),)

    id = Column(Integer, primary_key=True, index=True)
    module_key = Column(String(80), nullable=False, index=True)
    depends_on_module_key = Column(String(80), nullable=False, index=True)
    dependency_type = Column(String(40), default="optional", nullable=False)
    reason = Column(Text)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BOSFeatureFlag(Base):
    __tablename__ = "bos_feature_flags"
    __table_args__ = (UniqueConstraint("company_id", "module_key", "flag_key", name="uq_bos_feature_flag"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    module_key = Column(String(80), nullable=False, index=True)
    flag_key = Column(String(120), nullable=False, index=True)
    enabled = Column(Boolean, default=False, nullable=False)
    value_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class BOSIntegrationRule(Base):
    __tablename__ = "bos_integration_rules"
    __table_args__ = (UniqueConstraint("company_id", "source_module", "target_module", "rule_key", name="uq_bos_integration_rule"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_key = Column(String(120), nullable=False, index=True)
    source_module = Column(String(80), nullable=False, index=True)
    target_module = Column(String(80), nullable=False, index=True)
    event_name = Column(String(120), nullable=False)
    action_name = Column(String(120), nullable=False)
    enabled = Column(Boolean, default=False, nullable=False, index=True)
    skip_when_source_disabled = Column(Boolean, default=True, nullable=False)
    skip_when_target_disabled = Column(Boolean, default=True, nullable=False)
    config_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class BOSEntityLink(Base):
    __tablename__ = "bos_entity_links"
    __table_args__ = (UniqueConstraint("company_id", "source_module", "source_entity", "source_entity_id", "target_module", "target_entity", "target_entity_id", name="uq_bos_entity_link"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    source_module = Column(String(80), nullable=False, index=True)
    source_entity = Column(String(120), nullable=False, index=True)
    source_entity_id = Column(String(80), nullable=False, index=True)
    target_module = Column(String(80), nullable=False, index=True)
    target_entity = Column(String(120), nullable=False, index=True)
    target_entity_id = Column(String(80), nullable=False, index=True)
    link_type = Column(String(80), default="related", nullable=False)
    active = Column(Boolean, default=True, nullable=False, index=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BOSLifecycleEvent(Base):
    __tablename__ = "bos_lifecycle_events"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    module_key = Column(String(80), nullable=False, index=True)
    entity_type = Column(String(120), nullable=False, index=True)
    entity_id = Column(String(80), nullable=False, index=True)
    event_name = Column(String(120), nullable=False, index=True)
    status = Column(String(40), default="completed", nullable=False, index=True)
    message = Column(Text)
    source_module = Column(String(80), nullable=True, index=True)
    target_module = Column(String(80), nullable=True, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    evidence_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class BOSPostingRule(Base):
    __tablename__ = "bos_posting_rules"
    __table_args__ = (UniqueConstraint("company_id", "source_module", "target_module", "posting_key", name="uq_bos_posting_rule"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    posting_key = Column(String(120), nullable=False, index=True)
    source_module = Column(String(80), nullable=False, index=True)
    target_module = Column(String(80), nullable=False, index=True)
    transaction_type = Column(String(120), nullable=False, index=True)
    enabled = Column(Boolean, default=False, nullable=False, index=True)
    requires_target_module = Column(Boolean, default=True, nullable=False)
    config_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

