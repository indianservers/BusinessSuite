from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base_class import Base


class CustomizationModule(Base):
    __tablename__ = "customization_modules"
    __table_args__ = (UniqueConstraint("module_api_name", name="uq_customization_module_api_name"),)

    id = Column(Integer, primary_key=True, index=True)
    module_api_name = Column(String(100), nullable=False, index=True)
    module_label = Column(String(160), nullable=False)
    plural_label = Column(String(160), nullable=False)
    icon = Column(String(80))
    description = Column(Text)
    enabled = Column(Boolean, default=True, index=True)
    owner_field_enabled = Column(Boolean, default=True)
    timeline_enabled = Column(Boolean, default=True)
    activities_enabled = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CustomizationField(Base):
    __tablename__ = "customization_fields"
    __table_args__ = (UniqueConstraint("module_name", "field_api_name", name="uq_customization_field_module_api"),)

    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    field_api_name = Column(String(120), nullable=False, index=True)
    field_label = Column(String(160), nullable=False)
    field_type = Column(String(40), nullable=False, index=True)
    required = Column(Boolean, default=False)
    unique = Column(Boolean, default=False)
    default_value = Column(Text)
    help_text = Column(Text)
    options_source = Column(String(120))
    lookup_module = Column(String(100))
    formula_expression = Column(Text)
    rollup_config_json = Column(JSON)
    validation_json = Column(JSON)
    visible = Column(Boolean, default=True)
    editable = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CustomizationFieldOption(Base):
    __tablename__ = "customization_field_options"

    id = Column(Integer, primary_key=True, index=True)
    field_id = Column(Integer, ForeignKey("customization_fields.id", ondelete="CASCADE"), nullable=False, index=True)
    value = Column(String(160), nullable=False)
    label = Column(String(160), nullable=False)
    color = Column(String(40))
    order_index = Column(Integer, default=0)
    active = Column(Boolean, default=True, index=True)


class CustomizationLayout(Base):
    __tablename__ = "customization_layouts"

    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    layout_type = Column(String(40), default="detail", index=True)
    is_default = Column(Boolean, default=False, index=True)
    role_visibility_json = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CustomizationLayoutSection(Base):
    __tablename__ = "customization_layout_sections"

    id = Column(Integer, primary_key=True, index=True)
    layout_id = Column(Integer, ForeignKey("customization_layouts.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    order_index = Column(Integer, default=0)
    visible = Column(Boolean, default=True)


class CustomizationLayoutField(Base):
    __tablename__ = "customization_layout_fields"

    id = Column(Integer, primary_key=True, index=True)
    layout_id = Column(Integer, ForeignKey("customization_layouts.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("customization_layout_sections.id", ondelete="SET NULL"), nullable=True, index=True)
    field_id = Column(Integer, ForeignKey("customization_fields.id", ondelete="CASCADE"), nullable=False, index=True)
    order_index = Column(Integer, default=0)
    required_override = Column(Boolean)
    readonly = Column(Boolean, default=False)
    hidden = Column(Boolean, default=False)
    role_visibility_json = Column(JSON)


class CustomizationView(Base):
    __tablename__ = "customization_views"

    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    view_type = Column(String(40), default="list", index=True)
    filters_json = Column(JSON)
    columns_json = Column(JSON)
    sort_json = Column(JSON)
    shared = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CustomizationKanbanView(Base):
    __tablename__ = "customization_kanban_views"

    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    group_by_field = Column(String(120), nullable=False)
    card_fields_json = Column(JSON)
    transition_validation_json = Column(JSON)
    shared = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class CustomizationValidationRule(Base):
    __tablename__ = "customization_validation_rules"

    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    condition_json = Column(JSON, nullable=False)
    error_message = Column(Text, nullable=False)
    active = Column(Boolean, default=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class CustomizationRelatedList(Base):
    __tablename__ = "customization_related_lists"

    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    related_module_name = Column(String(100), nullable=False)
    relationship_type = Column(String(60), default="lookup")
    lookup_field = Column(String(120))
    label = Column(String(160), nullable=False)
    columns_json = Column(JSON)
    active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CustomizationButton(Base):
    __tablename__ = "customization_buttons"

    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    label = Column(String(160), nullable=False)
    action_type = Column(String(60), nullable=False)
    action_config_json = Column(JSON)
    placement = Column(String(60), default="record")
    active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CustomizationGlobalPicklist(Base):
    __tablename__ = "customization_global_picklists"
    __table_args__ = (UniqueConstraint("api_name", name="uq_customization_picklist_api"),)

    id = Column(Integer, primary_key=True, index=True)
    api_name = Column(String(120), nullable=False, index=True)
    label = Column(String(160), nullable=False)
    description = Column(Text)
    active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CustomizationGlobalPicklistValue(Base):
    __tablename__ = "customization_global_picklist_values"

    id = Column(Integer, primary_key=True, index=True)
    picklist_id = Column(Integer, ForeignKey("customization_global_picklists.id", ondelete="CASCADE"), nullable=False, index=True)
    value = Column(String(160), nullable=False)
    label = Column(String(160), nullable=False)
    order_index = Column(Integer, default=0)
    active = Column(Boolean, default=True)


class CustomizationFormulaField(Base):
    __tablename__ = "customization_formula_fields"

    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    field_api_name = Column(String(120), nullable=False, index=True)
    expression = Column(Text, nullable=False)
    return_type = Column(String(40), default="decimal")
    active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CustomizationRollupField(Base):
    __tablename__ = "customization_rollup_fields"

    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    field_api_name = Column(String(120), nullable=False, index=True)
    related_module_name = Column(String(100), nullable=False)
    aggregate_function = Column(String(40), nullable=False)
    aggregate_field = Column(String(120))
    filter_json = Column(JSON)
    active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CustomizationRecord(Base):
    __tablename__ = "customization_records"

    id = Column(Integer, primary_key=True, index=True)
    module_api_name = Column(String(100), nullable=False, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    values_json = Column(JSON, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CustomizationRecordValue(Base):
    __tablename__ = "customization_record_values"
    __table_args__ = (UniqueConstraint("record_id", "field_id", name="uq_customization_record_field"),)

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, ForeignKey("customization_records.id", ondelete="CASCADE"), nullable=False, index=True)
    field_id = Column(Integer, ForeignKey("customization_fields.id", ondelete="CASCADE"), nullable=False, index=True)
    value_json = Column(JSON)
    value_text = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CustomizationAuditLog(Base):
    __tablename__ = "customization_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(100), nullable=False, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    before_json = Column(JSON)
    after_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

