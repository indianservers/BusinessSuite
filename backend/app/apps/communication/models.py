from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base_class import Base


class CommunicationEmailTemplate(Base):
    __tablename__ = "communication_email_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    subject = Column(String(240), nullable=False)
    body_html = Column(Text)
    body_text = Column(Text)
    module_name = Column(String(80), nullable=False, index=True)
    template_type = Column(String(60), default="email", index=True)
    active = Column(Boolean, default=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CommunicationEmailMessage(Base):
    __tablename__ = "communication_email_messages"

    id = Column(Integer, primary_key=True, index=True)
    related_record_type = Column(String(80), nullable=False, index=True)
    related_record_id = Column(Integer, nullable=False, index=True)
    to_email = Column(String(180), nullable=False, index=True)
    cc = Column(Text)
    bcc = Column(Text)
    subject = Column(String(240), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(40), default="draft", nullable=False, index=True)
    provider_message_id = Column(String(180), index=True)
    error_message = Column(Text)
    sent_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class CommunicationEmailAttachment(Base):
    __tablename__ = "communication_email_attachments"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("communication_email_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String(240), nullable=False)
    file_url = Column(Text)
    mime_type = Column(String(120))
    size_bytes = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CommunicationWebform(Base):
    __tablename__ = "communication_webforms"
    __table_args__ = (UniqueConstraint("public_slug", name="uq_communication_webform_slug"),)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    target_module = Column(String(40), nullable=False, index=True)
    public_slug = Column(String(140), nullable=False, index=True)
    fields_json = Column(JSON)
    mapping_json = Column(JSON)
    active = Column(Boolean, default=True, index=True)
    auto_response_rule_id = Column(Integer, ForeignKey("communication_auto_response_rules.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class CommunicationWebformField(Base):
    __tablename__ = "communication_webform_fields"

    id = Column(Integer, primary_key=True, index=True)
    webform_id = Column(Integer, ForeignKey("communication_webforms.id", ondelete="CASCADE"), nullable=False, index=True)
    field_key = Column(String(120), nullable=False)
    label = Column(String(160), nullable=False)
    field_type = Column(String(40), default="text")
    required = Column(Boolean, default=False)
    order_index = Column(Integer, default=0)


class CommunicationWebformSubmission(Base):
    __tablename__ = "communication_webform_submissions"

    id = Column(Integer, primary_key=True, index=True)
    webform_id = Column(Integer, ForeignKey("communication_webforms.id", ondelete="CASCADE"), nullable=False, index=True)
    payload_json = Column(JSON, nullable=False)
    created_record_type = Column(String(60), index=True)
    created_record_id = Column(Integer, index=True)
    duplicate_detected = Column(Boolean, default=False, index=True)
    ip_address = Column(String(80))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class CommunicationAutoResponseRule(Base):
    __tablename__ = "communication_auto_response_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    trigger_type = Column(String(80), default="webform_submission", index=True)
    template_id = Column(Integer, ForeignKey("communication_email_templates.id", ondelete="SET NULL"), nullable=True)
    active = Column(Boolean, default=True, index=True)
    condition_json = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class CommunicationCampaign(Base):
    __tablename__ = "communication_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    type = Column(String(40), default="email", nullable=False, index=True)
    segment_json = Column(JSON)
    template_id = Column(Integer, ForeignKey("communication_email_templates.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(40), default="draft", nullable=False, index=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True, index=True)
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    blocked_count = Column(Integer, default=0)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class CommunicationCampaignMember(Base):
    __tablename__ = "communication_campaign_members"
    __table_args__ = (UniqueConstraint("campaign_id", "record_type", "record_id", name="uq_communication_campaign_member_record"),)

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("communication_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    record_type = Column(String(60), nullable=False, index=True)
    record_id = Column(Integer, nullable=False, index=True)
    email = Column(String(180), nullable=False, index=True)
    status = Column(String(40), default="pending", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CommunicationCampaignSend(Base):
    __tablename__ = "communication_campaign_sends"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("communication_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey("communication_campaign_members.id", ondelete="SET NULL"), nullable=True, index=True)
    email_message_id = Column(Integer, ForeignKey("communication_email_messages.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(40), nullable=False, index=True)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class CommunicationConsent(Base):
    __tablename__ = "communication_consents"
    __table_args__ = (UniqueConstraint("email", "phone", "record_type", "record_id", "consent_type", name="uq_communication_consent_subject"),)

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(180), index=True)
    phone = Column(String(60), index=True)
    record_type = Column(String(60), index=True)
    record_id = Column(Integer, index=True)
    consent_type = Column(String(60), default="email", index=True)
    status = Column(String(40), default="opted_in", nullable=False, index=True)
    source = Column(String(120))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)


class CommunicationOptOut(Base):
    __tablename__ = "communication_opt_outs"
    __table_args__ = (UniqueConstraint("email", "channel", name="uq_communication_opt_out_email_channel"),)

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(180), nullable=False, index=True)
    channel = Column(String(40), default="email", nullable=False, index=True)
    reason = Column(Text)
    source = Column(String(120), default="manual")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class CommunicationWhatsAppTemplate(Base):
    __tablename__ = "communication_whatsapp_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    template_key = Column(String(140), nullable=False, index=True)
    body_text = Column(Text, nullable=False)
    provider_status = Column(String(80), default="placeholder_only", index=True)
    active = Column(Boolean, default=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class CommunicationTimelineEvent(Base):
    __tablename__ = "communication_timeline_events"

    id = Column(Integer, primary_key=True, index=True)
    record_type = Column(String(80), nullable=False, index=True)
    record_id = Column(Integer, nullable=False, index=True)
    channel = Column(String(40), nullable=False, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    subject = Column(String(240))
    summary = Column(Text)
    metadata_json = Column(JSON)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class CommunicationDeliveryLog(Base):
    __tablename__ = "communication_delivery_logs"

    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String(40), nullable=False, index=True)
    related_message_id = Column(Integer, nullable=True, index=True)
    provider = Column(String(80), nullable=False, index=True)
    status = Column(String(40), nullable=False, index=True)
    request_json = Column(JSON)
    response_json = Column(JSON)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

