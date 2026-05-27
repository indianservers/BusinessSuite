from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class CRMCompany(Base):
    __tablename__ = "crm_companies"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    territory_id = Column(Integer, ForeignKey("crm_territories.id", ondelete="SET NULL"), nullable=True, index=True)
    parent_company_id = Column(Integer, ForeignKey("crm_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    industry = Column(String(120), index=True)
    website = Column(String(200))
    phone = Column(String(40))
    email = Column(String(150), index=True)
    address = Column(Text)
    city = Column(String(100), index=True)
    state = Column(String(100))
    country = Column(String(100), default="India")
    employee_count = Column(Integer)
    annual_revenue = Column(Numeric(14, 2))
    account_type = Column(String(40), default="Prospect", index=True)
    status = Column(String(40), default="Active", index=True)
    tags_text = Column(String(500))
    notes = Column(Text)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    contacts = relationship("CRMContact", back_populates="company", foreign_keys="CRMContact.company_id")
    deals = relationship("CRMDeal", back_populates="company", foreign_keys="CRMDeal.company_id")


class CRMContact(Base):
    __tablename__ = "crm_contacts"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    company_id = Column(Integer, ForeignKey("crm_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100))
    full_name = Column(String(220), nullable=False, index=True)
    email = Column(String(150), index=True)
    phone = Column(String(40))
    alternate_phone = Column(String(40))
    job_title = Column(String(120))
    department = Column(String(120))
    lifecycle_stage = Column(String(60), default="Lead", index=True)
    source = Column(String(80), index=True)
    date_of_birth = Column(Date)
    company_name = Column(String(180), index=True)
    company_website = Column(String(200))
    industry = Column(String(120), index=True)
    employee_count = Column(Integer)
    website = Column(String(200))
    linkedin_url = Column(String(300))
    twitter_url = Column(String(300))
    email_verification_status = Column(String(40), index=True)
    social_profiles_json = Column(JSON)
    city = Column(String(100), index=True)
    state = Column(String(100))
    country = Column(String(100), default="India")
    address = Column(Text)
    status = Column(String(40), default="Active", index=True)
    customer_since = Column(Date)
    last_contacted_at = Column(DateTime(timezone=True))
    next_follow_up_at = Column(DateTime(timezone=True), index=True)
    tags_text = Column(String(500))
    notes = Column(Text)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    company = relationship("CRMCompany", back_populates="contacts", foreign_keys=[company_id])
    deals = relationship("CRMDeal", back_populates="contact", foreign_keys="CRMDeal.contact_id")
    deal_links = relationship("CRMDealContact", back_populates="contact", cascade="all, delete-orphan")


class CRMLead(Base):
    __tablename__ = "crm_leads"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_team_id = Column(Integer, nullable=True, index=True)
    territory_id = Column(Integer, ForeignKey("crm_territories.id", ondelete="SET NULL"), nullable=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100))
    full_name = Column(String(220), nullable=False, index=True)
    email = Column(String(150), index=True)
    phone = Column(String(40), index=True)
    alternate_phone = Column(String(40))
    company_name = Column(String(180), index=True)
    job_title = Column(String(120))
    source = Column(String(80), default="Other", index=True)
    status = Column(String(40), default="New", index=True)
    rating = Column(String(20), default="Warm", index=True)
    lead_score = Column(Integer, default=0, index=True)
    lead_score_label = Column(String(20), default="Cold", index=True)
    lead_score_mode = Column(String(20), default="automatic", index=True)
    last_score_calculated_at = Column(DateTime(timezone=True))
    industry = Column(String(120), index=True)
    website = Column(String(200))
    linkedin_url = Column(String(300))
    company_website = Column(String(200))
    employee_count = Column(Integer)
    email_verification_status = Column(String(40), index=True)
    social_profiles_json = Column(JSON)
    city = Column(String(100), index=True)
    state = Column(String(100))
    country = Column(String(100), default="India")
    address = Column(Text)
    estimated_value = Column(Numeric(12, 2))
    expected_close_date = Column(Date, index=True)
    last_contacted_at = Column(DateTime(timezone=True))
    next_follow_up_at = Column(DateTime(timezone=True), index=True)
    is_converted = Column(Boolean, default=False, index=True)
    converted_at = Column(DateTime(timezone=True))
    converted_contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="SET NULL"), nullable=True)
    converted_company_id = Column(Integer, ForeignKey("crm_companies.id", ondelete="SET NULL"), nullable=True)
    converted_deal_id = Column(Integer, ForeignKey("crm_deals.id", ondelete="SET NULL"), nullable=True)
    tags_text = Column(String(500))
    notes = Column(Text)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    converted_contact = relationship("CRMContact", foreign_keys=[converted_contact_id])
    converted_company = relationship("CRMCompany", foreign_keys=[converted_company_id])
    converted_deal = relationship("CRMDeal", foreign_keys=[converted_deal_id])


class CRMLeadScoringRule(Base):
    __tablename__ = "crm_lead_scoring_rules"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_crm_lead_scoring_rule_org_name"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    name = Column(String(160), nullable=False, index=True)
    field = Column(String(100), nullable=False, index=True)
    operator = Column(String(40), nullable=False, index=True)
    value = Column(String(240))
    points = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class CRMPipeline(Base):
    __tablename__ = "crm_pipelines"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    name = Column(String(160), nullable=False)
    description = Column(Text)
    is_default = Column(Boolean, default=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    stages = relationship("CRMPipelineStage", back_populates="pipeline", cascade="all, delete-orphan")
    deals = relationship("CRMDeal", back_populates="pipeline")


class CRMPipelineStage(Base):
    __tablename__ = "crm_pipeline_stages"
    __table_args__ = (UniqueConstraint("pipeline_id", "name", name="uq_crm_pipeline_stage_name"),)

    id = Column(Integer, primary_key=True, index=True)
    pipeline_id = Column(Integer, ForeignKey("crm_pipelines.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    probability = Column(Integer, default=0)
    position = Column(Integer, default=0)
    color = Column(String(30))
    is_won = Column(Boolean, default=False)
    is_lost = Column(Boolean, default=False)
    organization_id = Column(Integer, nullable=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    pipeline = relationship("CRMPipeline", back_populates="stages")
    deals = relationship("CRMDeal", back_populates="stage")


class CRMDeal(Base):
    __tablename__ = "crm_deals"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    territory_id = Column(Integer, ForeignKey("crm_territories.id", ondelete="SET NULL"), nullable=True, index=True)
    company_id = Column(Integer, ForeignKey("crm_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    pipeline_id = Column(Integer, ForeignKey("crm_pipelines.id", ondelete="CASCADE"), nullable=False, index=True)
    stage_id = Column(Integer, ForeignKey("crm_pipeline_stages.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(180), nullable=False, index=True)
    description = Column(Text)
    amount = Column(Numeric(12, 2), default=0)
    currency = Column(String(10), default="INR")
    probability = Column(Integer, default=0)
    expected_revenue = Column(Numeric(12, 2))
    expected_close_date = Column(Date, index=True)
    actual_close_date = Column(Date)
    status = Column(String(30), default="Open", index=True)
    loss_reason = Column(Text)
    lost_reason = Column(Text)
    lead_source = Column(String(80), index=True)
    source = Column(String(80), index=True)
    won_at = Column(DateTime(timezone=True), index=True)
    lost_at = Column(DateTime(timezone=True), index=True)
    closed_at = Column(DateTime(timezone=True), index=True)
    discount_amount = Column(Numeric(12, 2))
    position = Column(Integer, default=0)
    next_follow_up_at = Column(DateTime(timezone=True), index=True)
    last_activity_at = Column(DateTime(timezone=True))
    tags_text = Column(String(500))
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    company = relationship("CRMCompany", back_populates="deals", foreign_keys=[company_id])
    contact = relationship("CRMContact", back_populates="deals", foreign_keys=[contact_id])
    pipeline = relationship("CRMPipeline", back_populates="deals")
    stage = relationship("CRMPipelineStage", back_populates="deals")
    contact_links = relationship("CRMDealContact", back_populates="deal", cascade="all, delete-orphan")


class CRMDealContact(Base):
    __tablename__ = "crm_deal_contacts"
    __table_args__ = (UniqueConstraint("deal_id", "contact_id", name="uq_crm_deal_contact"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    deal_id = Column(Integer, ForeignKey("crm_deals.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(80), default="Stakeholder", index=True)
    influence_level = Column(String(40), nullable=True, index=True)
    is_primary = Column(Boolean, default=False, index=True)
    notes = Column(Text)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    deal = relationship("CRMDeal", back_populates="contact_links")
    contact = relationship("CRMContact", back_populates="deal_links")


class CRMProduct(Base):
    __tablename__ = "crm_products"
    __table_args__ = (UniqueConstraint("organization_id", "sku", name="uq_crm_product_org_sku"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    sku = Column(String(80), index=True)
    category = Column(String(120), index=True)
    description = Column(Text)
    unit_price = Column(Numeric(12, 2), default=0)
    currency = Column(String(10), default="INR")
    tax_rate = Column(Numeric(5, 2))
    image_url = Column(String(500))
    status = Column(String(30), default="Active", index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class CRMDealProduct(Base):
    __tablename__ = "crm_deal_products"

    id = Column(Integer, primary_key=True, index=True)
    deal_id = Column(Integer, ForeignKey("crm_deals.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("crm_products.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity = Column(Integer, default=1)
    unit_price = Column(Numeric(12, 2), default=0)
    discount_amount = Column(Numeric(12, 2))
    tax_rate = Column(Numeric(5, 2))
    total_amount = Column(Numeric(12, 2), default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CRMQuotation(Base):
    __tablename__ = "crm_quotations"
    __table_args__ = (UniqueConstraint("organization_id", "quote_number", name="uq_crm_quote_org_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    deal_id = Column(Integer, ForeignKey("crm_deals.id", ondelete="SET NULL"), nullable=True, index=True)
    company_id = Column(Integer, ForeignKey("crm_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    quote_number = Column(String(60), nullable=False, index=True)
    issue_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=False, index=True)
    status = Column(String(30), default="Draft", index=True)
    currency = Column(String(10), default="INR")
    subtotal = Column(Numeric(12, 2), default=0)
    discount_amount = Column(Numeric(12, 2))
    tax_amount = Column(Numeric(12, 2))
    total_amount = Column(Numeric(12, 2), default=0)
    terms = Column(Text)
    notes = Column(Text)
    pdf_url = Column(String(500))
    pdf_file_name = Column(String(180))
    pdf_status = Column(String(30))
    pdf_generated_at = Column(DateTime(timezone=True))
    pdf_generated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CRMQuotationItem(Base):
    __tablename__ = "crm_quotation_items"

    id = Column(Integer, primary_key=True, index=True)
    quotation_id = Column(Integer, ForeignKey("crm_quotations.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("crm_products.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(180), nullable=False)
    description = Column(Text)
    quantity = Column(Integer, default=1)
    unit_price = Column(Numeric(12, 2), default=0)
    discount_amount = Column(Numeric(12, 2))
    tax_rate = Column(Numeric(5, 2))
    total_amount = Column(Numeric(12, 2), default=0)


class CRMActivity(Base):
    __tablename__ = "crm_activities"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    entity_type = Column(String(40), index=True)
    entity_id = Column(Integer, index=True)
    lead_id = Column(Integer, ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="CASCADE"), nullable=True, index=True)
    company_id = Column(Integer, ForeignKey("crm_companies.id", ondelete="CASCADE"), nullable=True, index=True)
    deal_id = Column(Integer, ForeignKey("crm_deals.id", ondelete="CASCADE"), nullable=True, index=True)
    activity_type = Column(String(40), nullable=False, index=True)
    title = Column(String(220))
    subject = Column(String(180), nullable=False)
    body = Column(Text)
    description = Column(Text)
    metadata_json = Column(JSON)
    status = Column(String(30), default="Pending", index=True)
    priority = Column(String(30), default="Medium", index=True)
    activity_date = Column(DateTime(timezone=True), index=True)
    due_date = Column(DateTime(timezone=True), index=True)
    completed_at = Column(DateTime(timezone=True))
    outcome = Column(Text)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CRMTask(Base):
    __tablename__ = "crm_tasks"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    lead_id = Column(Integer, ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="CASCADE"), nullable=True, index=True)
    company_id = Column(Integer, ForeignKey("crm_companies.id", ondelete="CASCADE"), nullable=True, index=True)
    deal_id = Column(Integer, ForeignKey("crm_deals.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String(220), nullable=False)
    description = Column(Text)
    status = Column(String(30), default="To Do", index=True)
    priority = Column(String(30), default="Medium", index=True)
    due_date = Column(DateTime(timezone=True), index=True)
    reminder_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class CRMNote(Base):
    __tablename__ = "crm_notes"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    author_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    lead_id = Column(Integer, ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="CASCADE"), nullable=True, index=True)
    company_id = Column(Integer, ForeignKey("crm_companies.id", ondelete="CASCADE"), nullable=True, index=True)
    deal_id = Column(Integer, ForeignKey("crm_deals.id", ondelete="CASCADE"), nullable=True, index=True)
    ticket_id = Column(Integer, ForeignKey("crm_tickets.id", ondelete="CASCADE"), nullable=True, index=True)
    body = Column(Text, nullable=False)
    is_pinned = Column(Boolean, default=False)
    is_internal = Column(Boolean, default=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class CRMNoteMention(Base):
    __tablename__ = "crm_note_mentions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    note_id = Column(Integer, ForeignKey("crm_notes.id", ondelete="CASCADE"), nullable=True, index=True)
    activity_id = Column(Integer, ForeignKey("crm_activities.id", ondelete="CASCADE"), nullable=True, index=True)
    mentioned_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mentioned_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    entity_type = Column(String(40), index=True)
    entity_id = Column(Integer, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    read_at = Column(DateTime(timezone=True))


class CRMEnrichmentLog(Base):
    __tablename__ = "crm_enrichment_logs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    entity_type = Column(String(40), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    provider = Column(String(80), nullable=False, index=True)
    old_values_json = Column(JSON)
    new_values_json = Column(JSON)
    applied_fields_json = Column(JSON)
    status = Column(String(30), default="previewed", index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class CRMEmailLog(Base):
    __tablename__ = "crm_email_logs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    entity_type = Column(String(40), index=True)
    entity_id = Column(Integer, index=True)
    subject = Column(String(220), nullable=False)
    body = Column(Text)
    from_email = Column(String(150))
    to_email = Column(String(150), nullable=False, index=True)
    cc = Column(String(500))
    bcc = Column(String(500))
    direction = Column(String(20), default="Outbound", index=True)
    status = Column(String(30), default="draft", index=True)
    provider_message_id = Column(String(160))
    failure_reason = Column(Text)
    sent_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    lead_id = Column(Integer, ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="CASCADE"), nullable=True, index=True)
    company_id = Column(Integer, ForeignKey("crm_companies.id", ondelete="CASCADE"), nullable=True, index=True)
    deal_id = Column(Integer, ForeignKey("crm_deals.id", ondelete="CASCADE"), nullable=True, index=True)
    sent_at = Column(DateTime(timezone=True))
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class CRMEmailTemplate(Base):
    __tablename__ = "crm_email_templates"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_crm_email_template_org_name"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    name = Column(String(160), nullable=False, index=True)
    subject = Column(String(220), nullable=False)
    body = Column(Text, nullable=False)
    entity_type = Column(String(40), index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class CRMMessage(Base):
    __tablename__ = "crm_messages"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    entity_type = Column(String(40), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    channel = Column(String(20), nullable=False, index=True)
    to = Column(String(40), nullable=False, index=True)
    body = Column(Text, nullable=False)
    status = Column(String(30), default="queued", index=True)
    provider = Column(String(80), nullable=False, default="mock", index=True)
    provider_message_id = Column(String(160))
    failure_reason = Column(Text)
    template_id = Column(Integer, ForeignKey("crm_message_templates.id", ondelete="SET NULL"), nullable=True, index=True)
    sent_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sent_at = Column(DateTime(timezone=True), index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class CRMMessageTemplate(Base):
    __tablename__ = "crm_message_templates"
    __table_args__ = (UniqueConstraint("organization_id", "name", "channel", name="uq_crm_message_template_org_name_channel"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    name = Column(String(160), nullable=False, index=True)
    channel = Column(String(20), nullable=False, default="sms", index=True)
    body = Column(Text, nullable=False)
    entity_type = Column(String(40), index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class CRMCalendarIntegration(Base):
    __tablename__ = "calendar_integrations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(40), nullable=False, index=True)
    access_token_encrypted = Column(Text)
    refresh_token_encrypted = Column(Text)
    expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class CRMCallLog(Base):
    __tablename__ = "crm_call_logs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    direction = Column(String(20), nullable=False, index=True)
    phone_number = Column(String(40), nullable=False)
    duration_seconds = Column(Integer)
    outcome = Column(String(160))
    notes = Column(Text)
    lead_id = Column(Integer, ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="CASCADE"), nullable=True, index=True)
    company_id = Column(Integer, ForeignKey("crm_companies.id", ondelete="CASCADE"), nullable=True, index=True)
    deal_id = Column(Integer, ForeignKey("crm_deals.id", ondelete="CASCADE"), nullable=True, index=True)
    call_time = Column(DateTime(timezone=True), nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class CRMMeeting(Base):
    __tablename__ = "crm_meetings"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(180), nullable=False)
    description = Column(Text)
    location = Column(String(240))
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False)
    outcome = Column(Text)
    status = Column(String(30), default="Scheduled", index=True)
    external_provider = Column(String(40), index=True)
    external_event_id = Column(String(180), index=True)
    sync_status = Column(String(30), default="not_synced", index=True)
    last_synced_at = Column(DateTime(timezone=True))
    lead_id = Column(Integer, ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="CASCADE"), nullable=True, index=True)
    company_id = Column(Integer, ForeignKey("crm_companies.id", ondelete="CASCADE"), nullable=True, index=True)
    deal_id = Column(Integer, ForeignKey("crm_deals.id", ondelete="CASCADE"), nullable=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class CRMTicket(Base):
    __tablename__ = "crm_tickets"
    __table_args__ = (UniqueConstraint("organization_id", "ticket_number", name="uq_crm_ticket_org_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    company_id = Column(Integer, ForeignKey("crm_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    ticket_number = Column(String(60), nullable=False, index=True)
    subject = Column(String(220), nullable=False)
    description = Column(Text)
    priority = Column(String(30), default="Medium", index=True)
    status = Column(String(50), default="Open", index=True)
    category = Column(String(100), index=True)
    source = Column(String(40), default="Manual", index=True)
    due_date = Column(DateTime(timezone=True), index=True)
    resolved_at = Column(DateTime(timezone=True))
    satisfaction_rating = Column(Integer)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class CRMCampaign(Base):
    __tablename__ = "crm_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    campaign_type = Column(String(50), nullable=False, index=True)
    status = Column(String(30), default="Planned", index=True)
    start_date = Column(Date)
    end_date = Column(Date)
    budget_amount = Column(Numeric(12, 2))
    actual_cost = Column(Numeric(12, 2))
    expected_revenue = Column(Numeric(12, 2))
    description = Column(Text)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class CRMCampaignLead(Base):
    __tablename__ = "crm_campaign_leads"
    __table_args__ = (UniqueConstraint("campaign_id", "lead_id", name="uq_crm_campaign_lead"),)

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("crm_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CRMFileAsset(Base):
    __tablename__ = "crm_file_assets"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    lead_id = Column(Integer, ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="CASCADE"), nullable=True, index=True)
    company_id = Column(Integer, ForeignKey("crm_companies.id", ondelete="CASCADE"), nullable=True, index=True)
    deal_id = Column(Integer, ForeignKey("crm_deals.id", ondelete="CASCADE"), nullable=True, index=True)
    ticket_id = Column(Integer, ForeignKey("crm_tickets.id", ondelete="CASCADE"), nullable=True, index=True)
    file_name = Column(String(240), nullable=False)
    original_name = Column(String(240), nullable=False)
    mime_type = Column(String(120))
    size_bytes = Column(Integer, default=0)
    storage_path = Column(String(500), nullable=False)
    visibility = Column(String(40), default="Internal", index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class CRMTag(Base):
    __tablename__ = "crm_tags"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_crm_tag_org_name"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    name = Column(String(100), nullable=False)
    color = Column(String(30))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CRMTerritory(Base):
    __tablename__ = "crm_territories"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_crm_territory_org_name"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(160), nullable=False, index=True)
    code = Column(String(40), index=True)
    country = Column(String(100), default="India")
    state = Column(String(100), index=True)
    city = Column(String(100), index=True)
    description = Column(Text)
    rules_json = Column(JSON)
    priority = Column(Integer, default=100, index=True)
    is_active = Column(Boolean, default=True, index=True)
    status = Column(String(30), default="Active", index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class CRMTerritoryUser(Base):
    __tablename__ = "crm_territory_users"
    __table_args__ = (UniqueConstraint("territory_id", "user_id", name="uq_crm_territory_user"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    territory_id = Column(Integer, ForeignKey("crm_territories.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CRMTeam(Base):
    __tablename__ = "crm_teams"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_crm_team_org_name"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(160), nullable=False, index=True)
    team_type = Column(String(60), default="Sales", index=True)
    description = Column(Text)
    status = Column(String(30), default="Active", index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class CRMOwner(Base):
    __tablename__ = "crm_owners"
    __table_args__ = (UniqueConstraint("organization_id", "email", name="uq_crm_owner_org_email"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    team_id = Column(Integer, ForeignKey("crm_teams.id", ondelete="SET NULL"), nullable=True, index=True)
    territory_id = Column(Integer, ForeignKey("crm_territories.id", ondelete="SET NULL"), nullable=True, index=True)
    full_name = Column(String(180), nullable=False, index=True)
    email = Column(String(150), nullable=False, index=True)
    phone = Column(String(40))
    role = Column(String(80), default="Sales Executive", index=True)
    status = Column(String(30), default="Active", index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class CRMCustomField(Base):
    __tablename__ = "crm_custom_fields"
    __table_args__ = (UniqueConstraint("organization_id", "entity", "field_key", name="uq_crm_custom_field_org_entity_key"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    entity = Column(String(80), nullable=False, index=True)
    field_key = Column(String(100), nullable=False, index=True)
    field_name = Column(String(160))
    label = Column(String(160), nullable=False)
    field_type = Column(String(40), default="text", index=True)
    options_json = Column(JSON)
    is_required = Column(Boolean, default=False)
    is_unique = Column(Boolean, default=False, index=True)
    is_visible = Column(Boolean, default=True, index=True)
    is_filterable = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    position = Column(Integer, default=0)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    values = relationship("CRMCustomFieldValue", back_populates="custom_field", cascade="all, delete-orphan")


class CRMCustomFieldValue(Base):
    __tablename__ = "crm_custom_field_values"
    __table_args__ = (UniqueConstraint("organization_id", "custom_field_id", "entity", "record_id", name="uq_crm_custom_field_value_record"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    custom_field_id = Column(Integer, ForeignKey("crm_custom_fields.id", ondelete="CASCADE"), nullable=False, index=True)
    entity = Column(String(80), nullable=False, index=True)
    record_id = Column(Integer, nullable=False, index=True)
    value_text = Column(Text)
    value_number = Column(Numeric(18, 4))
    value_date = Column(Date)
    value_datetime = Column(DateTime(timezone=True))
    value_boolean = Column(Boolean)
    value_json = Column(JSON)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    custom_field = relationship("CRMCustomField", back_populates="values")


class CRMWebhook(Base):
    __tablename__ = "crm_webhooks"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    url = Column(String(500), nullable=False)
    secret = Column(String(160), nullable=False)
    events = Column(JSON)
    is_active = Column(Boolean, default=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class CRMWebhookDelivery(Base):
    __tablename__ = "crm_webhook_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    webhook_id = Column(Integer, ForeignKey("crm_webhooks.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    payload = Column(JSON)
    status = Column(String(30), default="pending", index=True)
    response_code = Column(Integer)
    response_body = Column(Text)
    attempt_count = Column(Integer, default=0)
    next_retry_at = Column(DateTime(timezone=True), index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    webhook = relationship("CRMWebhook")


class CRMApprovalWorkflow(Base):
    __tablename__ = "crm_approval_workflows"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    entity_type = Column(String(40), nullable=False, index=True)
    trigger_type = Column(String(80), nullable=False, index=True)
    conditions = Column(JSON)
    is_active = Column(Boolean, default=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    steps = relationship("CRMApprovalStep", back_populates="workflow", cascade="all, delete-orphan", order_by="CRMApprovalStep.step_order")


class CRMApprovalStep(Base):
    __tablename__ = "crm_approval_steps"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("crm_approval_workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    step_order = Column(Integer, nullable=False, default=1, index=True)
    approver_type = Column(String(30), nullable=False, default="user", index=True)
    approver_id = Column(Integer, nullable=True, index=True)
    action_on_reject = Column(String(30), default="stop", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    workflow = relationship("CRMApprovalWorkflow", back_populates="steps")


class CRMApprovalRequest(Base):
    __tablename__ = "crm_approval_requests"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    workflow_id = Column(Integer, ForeignKey("crm_approval_workflows.id", ondelete="SET NULL"), nullable=True, index=True)
    entity_type = Column(String(40), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    status = Column(String(30), default="pending", nullable=False, index=True)
    submitted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True))

    workflow = relationship("CRMApprovalWorkflow")
    steps = relationship("CRMApprovalRequestStep", back_populates="request", cascade="all, delete-orphan", order_by="CRMApprovalRequestStep.id")


class CRMApprovalRequestStep(Base):
    __tablename__ = "crm_approval_request_steps"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("crm_approval_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id = Column(Integer, ForeignKey("crm_approval_steps.id", ondelete="SET NULL"), nullable=True, index=True)
    approver_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(30), default="pending", nullable=False, index=True)
    comments = Column(Text)
    acted_at = Column(DateTime(timezone=True))

    request = relationship("CRMApprovalRequest", back_populates="steps")
    step = relationship("CRMApprovalStep")
