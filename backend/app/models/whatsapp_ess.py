from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class WhatsAppESSConfig(Base):
    __tablename__ = "whatsapp_ess_configs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(80), default="WhatsApp Business")
    business_phone_number = Column(String(30), nullable=False)
    business_phone_number_country_code = Column(String(5), nullable=True)
    webhook_url = Column(String(500))
    access_token_ref = Column(String(200))
    app_secret_ref = Column(String(200))
    verify_token_ref = Column(String(200))
    default_language = Column(String(20), default="en")
    is_active = Column(Boolean, default=True, index=True)
    opt_in_required = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WhatsAppESSSession(Base):
    __tablename__ = "whatsapp_ess_sessions"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    phone_number = Column(String(30), nullable=False, index=True)
    phone_number_country_code = Column(String(5), nullable=True)
    status = Column(String(30), default="Active", index=True)
    last_intent = Column(String(80))
    last_message_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    employee = relationship("Employee")


class WhatsAppESSMessage(Base):
    __tablename__ = "whatsapp_ess_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("whatsapp_ess_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    direction = Column(String(20), nullable=False, index=True)  # Inbound, Outbound
    phone_number = Column(String(30), nullable=False)
    phone_number_country_code = Column(String(5), nullable=True)
    message_text = Column(Text, nullable=False)
    intent = Column(String(80))
    status = Column(String(30), default="Received", index=True)
    provider_message_id = Column(String(150))
    response_text = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("WhatsAppESSSession")
    employee = relationship("Employee")


class WhatsAppESSTemplate(Base):
    __tablename__ = "whatsapp_ess_templates"

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("whatsapp_ess_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    template_name = Column(String(120), nullable=False)
    intent = Column(String(80), nullable=False, index=True)
    language = Column(String(20), default="en")
    body_text = Column(Text, nullable=False)
    provider_template_id = Column(String(150))
    status = Column(String(30), default="Draft", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    config = relationship("WhatsAppESSConfig")


class WhatsAppESSOptIn(Base):
    __tablename__ = "whatsapp_ess_opt_ins"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    phone_number = Column(String(30), nullable=False, index=True)
    phone_number_country_code = Column(String(5), nullable=True)
    status = Column(String(30), default="Opted In", index=True)
    source = Column(String(80), default="ESS")
    consent_text = Column(Text)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    employee = relationship("Employee")


class WhatsAppESSDeliveryEvent(Base):
    __tablename__ = "whatsapp_ess_delivery_events"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("whatsapp_ess_messages.id", ondelete="CASCADE"), nullable=True, index=True)
    provider_message_id = Column(String(150), index=True)
    status = Column(String(30), nullable=False, index=True)
    raw_payload = Column(Text)
    received_at = Column(DateTime(timezone=True), server_default=func.now())

    message = relationship("WhatsAppESSMessage")
