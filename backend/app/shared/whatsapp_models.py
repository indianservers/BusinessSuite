"""Customer-owned WhatsApp assets. Tokens are encrypted and never serialized."""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint, JSON, func
from app.db.base_class import Base


class WhatsAppConnection(Base):
    __tablename__ = "suite_whatsapp_connections"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=False, unique=True, index=True)
    waba_id = Column(String(100), nullable=False, index=True)
    phone_number_id = Column(String(100), nullable=False, index=True)
    routing_key = Column(String(100), unique=True, nullable=True)
    display_number = Column(String(80))
    business_name = Column(String(250))
    token_ciphertext = Column(Text)
    source = Column(String(30), nullable=False, default="manual")
    status = Column(String(30), nullable=False, default="connected")
    subscribed = Column(Boolean, nullable=False, default=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class WhatsAppOnboarding(Base):
    __tablename__ = "suite_whatsapp_onboarding"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    state_digest = Column(String(64), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True))


class WhatsAppContact(Base):
    __tablename__ = "suite_whatsapp_contacts"
    __table_args__ = (UniqueConstraint("organization_id", "recipient", name="uq_suite_wa_contact"),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    recipient = Column(String(80), nullable=False, index=True)
    name = Column(String(250))
    entity_type = Column(String(20))
    entity_id = Column(Integer)
    consent = Column(String(20), nullable=False, default="unknown")
    consent_source = Column(String(250))
    consent_at = Column(DateTime(timezone=True))
    last_inbound_at = Column(DateTime(timezone=True))
    last_message_at = Column(DateTime(timezone=True), index=True)
    erased_at = Column(DateTime(timezone=True))


class WhatsAppMessage(Base):
    __tablename__ = "suite_whatsapp_messages"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_suite_wa_request"),
        UniqueConstraint("connection_id", "provider_message_id", name="uq_suite_wa_provider_message"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    connection_id = Column(Integer, ForeignKey("suite_whatsapp_connections.id"), nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey("suite_whatsapp_contacts.id"), nullable=False, index=True)
    crm_message_id = Column(Integer, ForeignKey("crm_messages.id"), nullable=True)
    direction = Column(String(10), nullable=False)
    kind = Column(String(30), nullable=False, default="text")
    body = Column(Text, nullable=False, default="")
    template_json = Column(JSON)
    status = Column(String(40), nullable=False, index=True)
    provider_message_id = Column(String(200), index=True)
    idempotency_key = Column(String(100))
    payload_digest = Column(String(64))
    error_code = Column(String(40))
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class WhatsAppReceipt(Base):
    __tablename__ = "suite_whatsapp_receipts"
    __table_args__ = (UniqueConstraint("connection_id", "provider_message_id", "status", name="uq_suite_wa_receipt"),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    connection_id = Column(Integer, ForeignKey("suite_whatsapp_connections.id"), nullable=False)
    provider_message_id = Column(String(200), nullable=False, index=True)
    status = Column(String(40), nullable=False)
    error_code = Column(String(40))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
