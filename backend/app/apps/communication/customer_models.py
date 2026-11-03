"""Customer journeys: explicit identities, versioned rules and durable intent."""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Date, JSON, ForeignKey, UniqueConstraint, Index, func
from app.db.base_class import Base


class CustomerRecipient(Base):
    __tablename__ = 'communication_customer_recipients'
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('companies.id'), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey('branches.id'), nullable=False)
    crm_contact_id = Column(Integer, ForeignKey('crm_contacts.id'), nullable=True)
    name = Column(String(220), nullable=False)
    email = Column(String(254))
    phone = Column(String(60))
    role = Column(String(30), nullable=False, default='service')
    language = Column(String(20), nullable=False, default='en')
    timezone = Column(String(80), nullable=False, default='Asia/Kolkata')
    preferred_channel = Column(String(20), nullable=False, default='email')
    birthday = Column(Date)
    anniversary = Column(Date)
    active = Column(Boolean, nullable=False, default=True)
    preferences = Column(JSON, nullable=False, default=dict)
    consent_source = Column(String(240))
    consent_at = Column(DateTime(timezone=True))
    consent_history = Column(JSON, nullable=False, default=list)
    assigned_user_id = Column(Integer, ForeignKey('users.id'))
    last_read_at = Column(DateTime(timezone=True))
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CustomerBinding(Base):
    __tablename__ = 'communication_customer_bindings'
    __table_args__ = (UniqueConstraint('organization_id', 'recipient_id', 'source_type', 'source_id', name='uq_customer_binding'),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('companies.id'), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey('branches.id'), nullable=False)
    recipient_id = Column(Integer, ForeignKey('communication_customer_recipients.id'), nullable=False)
    source_type = Column(String(60), nullable=False)
    source_id = Column(Integer, nullable=False)


class CustomerCommunicationSettings(Base):
    __tablename__ = 'communication_customer_settings'
    organization_id = Column(Integer, ForeignKey('companies.id'), primary_key=True)
    paused = Column(Boolean, nullable=False, default=False)
    daily_limit = Column(Integer, nullable=False, default=1000)
    customer_daily_limit = Column(Integer, nullable=False, default=5)
    bulk_approval_threshold = Column(Integer, nullable=False, default=50)
    updated_by = Column(Integer, ForeignKey('users.id'))


class CustomerEmailConnection(Base):
    __tablename__ = 'communication_customer_email_connections'
    organization_id = Column(Integer, ForeignKey('companies.id'), primary_key=True)
    host = Column(String(254), nullable=False)
    port = Column(Integer, nullable=False, default=587)
    username = Column(String(254), nullable=False)
    password_ciphertext = Column(Text, nullable=False)
    inbound_secret_ciphertext = Column(Text)
    from_email = Column(String(254), nullable=False)
    from_name = Column(String(180), nullable=False)
    reply_to = Column(String(254))
    active = Column(Boolean, nullable=False, default=True)
    updated_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CustomerAutomation(Base):
    __tablename__ = 'communication_customer_automations'
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('companies.id'), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey('branches.id'), nullable=False)
    name = Column(String(180), nullable=False)
    trigger = Column(String(100), nullable=False, index=True)
    purpose = Column(String(20), nullable=False, default='transactional')
    channel = Column(String(20), nullable=False, default='email')
    subject = Column(String(240), nullable=False)
    body = Column(Text, nullable=False)
    whatsapp_template = Column(JSON)
    conditions = Column(JSON, nullable=False, default=dict)
    steps = Column(JSON, nullable=False, default=lambda: [0])
    quiet_start = Column(Integer, nullable=False, default=20)
    quiet_end = Column(Integer, nullable=False, default=8)
    weekdays = Column(JSON, nullable=False, default=lambda: list(range(7)))
    stop_on_reply = Column(Boolean, nullable=False, default=True)
    status = Column(String(20), nullable=False, default='draft')
    version = Column(Integer, nullable=False, default=1)
    last_scanned_at = Column(DateTime(timezone=True))
    recipient_cursor = Column(Integer, nullable=False, default=0)
    activation_event_id = Column(Integer, nullable=False, default=0)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CustomerEvent(Base):
    __tablename__ = 'communication_customer_events'
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=True)
    event_key = Column(String(180), nullable=False, unique=True)
    trigger = Column(String(100), nullable=False)
    source_type = Column(String(60), nullable=False)
    source_id = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default='pending', index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CustomerDelivery(Base):
    __tablename__ = 'communication_customer_deliveries'
    __table_args__ = (UniqueConstraint('event_key', name='uq_customer_delivery_event'), Index('ix_customer_delivery_due', 'status', 'due_at'))
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('companies.id'), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey('branches.id'), nullable=False)
    recipient_id = Column(Integer, ForeignKey('communication_customer_recipients.id'), nullable=False)
    automation_id = Column(Integer, ForeignKey('communication_customer_automations.id'))
    rule_version = Column(Integer)
    event_key = Column(String(180), nullable=False)
    source_type = Column(String(60), nullable=False)
    source_id = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False, default=dict)
    purpose = Column(String(20), nullable=False)
    channel = Column(String(20), nullable=False)
    subject = Column(String(240), nullable=False)
    body = Column(Text, nullable=False)
    whatsapp_template = Column(JSON)
    status = Column(String(40), nullable=False, default='queued', index=True)
    error = Column(String(240))
    due_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    attempted_at = Column(DateTime(timezone=True))
    attempts = Column(Integer, nullable=False, default=0)
    email_outbox_id = Column(Integer, ForeignKey('email_outbox.id'))
    whatsapp_message_id = Column(Integer, ForeignKey('suite_whatsapp_messages.id'))
    reminder_id = Column(Integer, ForeignKey('srm_collection_reminders.id'))
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)


class CustomerShipment(Base):
    __tablename__ = 'communication_customer_shipments'
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('companies.id'), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey('branches.id'), nullable=False)
    sales_order_id = Column(Integer, ForeignKey('srm_sales_orders.id'), nullable=False)
    reference = Column(String(120), nullable=False)
    status = Column(String(40), nullable=False, default='ready')
    carrier = Column(String(160))
    tracking_url = Column(String(1000))
    expected_date = Column(Date)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CustomerPreferenceToken(Base):
    __tablename__ = 'communication_customer_preference_tokens'
    digest = Column(String(64), primary_key=True)
    organization_id = Column(Integer, nullable=False)
    recipient_id = Column(Integer, ForeignKey('communication_customer_recipients.id'), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)


class CustomerConversationNote(Base):
    __tablename__ = 'communication_customer_notes'
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('companies.id'), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey('branches.id'), nullable=False)
    recipient_id = Column(Integer, ForeignKey('communication_customer_recipients.id'), nullable=False)
    body = Column(Text, nullable=False)
    assigned_user_id = Column(Integer, ForeignKey('users.id'))
    follow_up_at = Column(DateTime(timezone=True))
    reminded_at = Column(DateTime(timezone=True))
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CustomerEmailReply(Base):
    __tablename__ = 'communication_customer_email_replies'
    __table_args__ = (UniqueConstraint('organization_id', 'provider_event_id', name='uq_customer_email_reply_event'),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('companies.id'), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey('branches.id'), nullable=False)
    recipient_id = Column(Integer, ForeignKey('communication_customer_recipients.id'), nullable=False)
    delivery_id = Column(Integer, ForeignKey('communication_customer_deliveries.id'), nullable=False)
    provider_event_id = Column(String(180), nullable=False)
    subject = Column(String(240), nullable=False)
    body = Column(Text, nullable=False)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
