from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, JSON
from sqlalchemy.sql import func
from app.db.base_class import Base


class CustomFieldDefinition(Base):
    __tablename__ = "custom_field_definitions"

    id = Column(Integer, primary_key=True, index=True)
    module = Column(String(80), nullable=False, index=True)
    section = Column(String(120), default="General")
    field_key = Column(String(120), nullable=False, index=True)
    label = Column(String(150), nullable=False)
    field_type = Column(String(40), default="Text")
    options_json = Column(JSON)
    validation_json = Column(JSON)
    is_required = Column(Boolean, default=False)
    is_sensitive = Column(Boolean, default=False)
    visible_to_roles = Column(String(250))
    editable_by_roles = Column(String(250))
    display_order = Column(Integer, default=100)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CustomFieldValue(Base):
    __tablename__ = "custom_field_values"

    id = Column(Integer, primary_key=True, index=True)
    definition_id = Column(Integer, ForeignKey("custom_field_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(80), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    value_text = Column(Text)
    value_json = Column(JSON)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CustomFormDefinition(Base):
    __tablename__ = "custom_form_definitions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False)
    code = Column(String(100), nullable=False, unique=True, index=True)
    module = Column(String(80), nullable=False, index=True)
    entity_type = Column(String(80), nullable=False, index=True)
    description = Column(Text)
    trigger_event = Column(String(120))
    visible_to_roles = Column(String(250))
    editable_by_roles = Column(String(250))
    allow_multiple_submissions = Column(Boolean, default=False)
    workflow_required = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CustomFormField(Base):
    __tablename__ = "custom_form_fields"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("custom_form_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    field_definition_id = Column(Integer, ForeignKey("custom_field_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    section = Column(String(120), default="General")
    display_order = Column(Integer, default=100)
    is_required_override = Column(Boolean)
    help_text = Column(Text)
    visibility_condition_json = Column(JSON)


class CustomFormSubmission(Base):
    __tablename__ = "custom_form_submissions"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("custom_form_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(80), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    status = Column(String(30), default="Submitted", index=True)
    submitted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True))
    review_remarks = Column(Text)
    values_json = Column(JSON, nullable=False)


class ReportDefinition(Base):
    __tablename__ = "report_definitions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    code = Column(String(80), nullable=False, unique=True, index=True)
    module = Column(String(80), nullable=False, index=True)
    field_catalog_json = Column(JSON)
    selected_fields_json = Column(JSON)
    filters_json = Column(JSON)
    schedule_cron = Column(String(80))
    export_format = Column(String(20), default="csv")
    visible_to_roles = Column(String(250))
    is_active = Column(Boolean, default=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReportRun(Base):
    __tablename__ = "report_runs"

    id = Column(Integer, primary_key=True, index=True)
    report_definition_id = Column(Integer, ForeignKey("report_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(30), default="Queued", index=True)
    row_count = Column(Integer, default=0)
    file_url = Column(String(500))
    error_message = Column(Text)
    requested_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReportSchedule(Base):
    __tablename__ = "report_schedules"

    id = Column(Integer, primary_key=True, index=True)
    report_definition_id = Column(Integer, ForeignKey("report_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    cron_expression = Column(String(80), nullable=False)
    recipients_json = Column(JSON)
    export_format = Column(String(20), default="csv")
    status = Column(String(30), default="Active", index=True)
    last_run_at = Column(DateTime(timezone=True))
    next_run_at = Column(DateTime(timezone=True))
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class IntegrationCredential(Base):
    __tablename__ = "integration_credentials"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(100), nullable=False, index=True)
    credential_name = Column(String(150), nullable=False)
    auth_type = Column(String(50), default="API Key")
    secret_ref = Column(String(255), nullable=False)
    scopes = Column(String(500))
    status = Column(String(30), default="Active", index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    event_type = Column(String(120), nullable=False, index=True)
    target_url = Column(String(500), nullable=False)
    secret_ref = Column(String(255))
    is_active = Column(Boolean, default=True, index=True)
    retry_policy_json = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class IntegrationEvent(Base):
    __tablename__ = "integration_events"
    __table_args__ = (
        Index("idx_integration_event_type_status_retry", "event_type", "status", "next_retry_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("webhook_subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(120), nullable=False, index=True)
    payload_json = Column(JSON)
    status = Column(String(30), default="Queued", index=True)
    attempts = Column(Integer, default=0)
    last_error = Column(Text)
    next_retry_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    consent_type = Column(String(80), nullable=False, index=True)
    status = Column(String(30), default="Granted", index=True)
    purpose = Column(Text)
    channel = Column(String(50), default="Web")
    evidence_url = Column(String(500))
    captured_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    captured_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked_at = Column(DateTime(timezone=True))


class DataPrivacyRequest(Base):
    __tablename__ = "data_privacy_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True)
    request_type = Column(String(60), nullable=False, index=True)
    status = Column(String(30), default="Open", index=True)
    requested_by_email = Column(String(150))
    due_date = Column(DateTime(timezone=True))
    resolution_notes = Column(Text)
    processing_result_json = Column(JSON)
    assigned_to = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))


class DataRetentionPolicy(Base):
    __tablename__ = "data_retention_policies"

    id = Column(Integer, primary_key=True, index=True)
    module = Column(String(80), nullable=False, index=True)
    record_type = Column(String(100), nullable=False)
    retention_days = Column(Integer, nullable=False)
    action = Column(String(40), default="Archive")
    legal_basis = Column(Text)
    last_run_at = Column(DateTime(timezone=True))
    last_run_summary_json = Column(JSON)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LegalHold(Base):
    __tablename__ = "legal_holds"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    module = Column(String(80), nullable=False, index=True)
    entity_type = Column(String(80))
    entity_id = Column(Integer)
    reason = Column(Text)
    status = Column(String(30), default="Active", index=True)
    placed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    placed_at = Column(DateTime(timezone=True), server_default=func.now())
    released_at = Column(DateTime(timezone=True))


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    code = Column(String(80), nullable=False, unique=True, index=True)
    module = Column(String(80), nullable=False, index=True)
    formula_json = Column(JSON)
    owner_role = Column(String(80))
    refresh_frequency = Column(String(50), default="Daily")
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DomainPackRegistry(Base):
    __tablename__ = "domain_pack_registry"
    __table_args__ = (
        Index("idx_domain_pack_company_key", "company_id", "pack_key", unique=True),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    pack_key = Column(String(80), nullable=False, index=True)
    pack_name = Column(String(150), nullable=False)
    status = Column(String(30), default="Enabled", index=True)
    config_json = Column(JSON)
    enabled_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    enabled_at = Column(DateTime(timezone=True), server_default=func.now())
    disabled_at = Column(DateTime(timezone=True))


class ManufacturingSafetyIncident(Base):
    __tablename__ = "manufacturing_safety_incidents"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True)
    incident_date = Column(Date, nullable=False, index=True)
    location = Column(String(150))
    incident_type = Column(String(80), nullable=False, index=True)
    severity = Column(String(30), default="Low", index=True)
    description = Column(Text)
    lost_time_hours = Column(Numeric(8, 2), default=0)
    corrective_action = Column(Text)
    status = Column(String(30), default="Open", index=True)
    reported_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ManufacturingPPEIssuance(Base):
    __tablename__ = "manufacturing_ppe_issuances"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    ppe_item = Column(String(120), nullable=False, index=True)
    issued_on = Column(Date, nullable=False, index=True)
    quantity = Column(Integer, default=1)
    expiry_date = Column(Date)
    condition = Column(String(40), default="New")
    acknowledgement_status = Column(String(30), default="Pending", index=True)
    issued_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ManufacturingMedicalFitnessRecord(Base):
    __tablename__ = "manufacturing_medical_fitness_records"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    exam_date = Column(Date, nullable=False, index=True)
    fitness_status = Column(String(40), nullable=False, index=True)
    valid_until = Column(Date, index=True)
    restrictions = Column(Text)
    provider_name = Column(String(150))
    document_url = Column(String(500))
    recorded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ManufacturingContractLaborBatch(Base):
    __tablename__ = "manufacturing_contract_labor_batches"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    vendor_name = Column(String(180), nullable=False, index=True)
    batch_code = Column(String(80), nullable=False, index=True)
    work_order_number = Column(String(100))
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date)
    headcount = Column(Integer, default=0)
    compliance_status = Column(String(40), default="Pending", index=True)
    document_url = Column(String(500))
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
