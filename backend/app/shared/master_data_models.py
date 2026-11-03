"""Business extensions to existing canonical CRM/HR identities, not new identities."""
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.sql import func
from app.db.base_class import Base


class ContactChannel(Base):
    __tablename__ = "suite_contact_channels"
    __table_args__ = (CheckConstraint("(CASE WHEN contact_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN account_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN person_id IS NOT NULL THEN 1 ELSE 0 END) = 1", name="ck_contact_channel_owner"),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="RESTRICT"), index=True)
    account_id = Column(Integer, ForeignKey("crm_companies.id", ondelete="RESTRICT"), index=True)
    person_id = Column(Integer, ForeignKey("common_people.id", ondelete="RESTRICT"), index=True)
    kind = Column(String(10), nullable=False)
    label = Column(String(50), nullable=False, default="Work")
    value = Column(String(254), nullable=False)
    normalized_value = Column(String(254), nullable=False, index=True)
    country_code = Column(String(5))
    is_primary = Column(Boolean, nullable=False, default=False)
    whatsapp = Column(Boolean, nullable=False, default=False)
    # Verification is integration-owned; ordinary edits cannot assert verification.
    verification_status = Column(String(20), nullable=False, default="unverified")
    notes = Column(String(500))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BusinessRelationship(Base):
    __tablename__ = "suite_business_relationships"
    __table_args__ = (
        CheckConstraint("(CASE WHEN contact_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN account_id IS NOT NULL THEN 1 ELSE 0 END) = 1", name="ck_business_relationship_owner"),
        UniqueConstraint("contact_id", "role", name="uq_contact_business_role"),
        UniqueConstraint("account_id", "role", name="uq_account_business_role"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="RESTRICT"), index=True)
    account_id = Column(Integer, ForeignKey("crm_companies.id", ondelete="RESTRICT"), index=True)
    role = Column(String(30), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="Active")
    category = Column(String(100))
    payment_terms = Column(String(250))
    credit_limit = Column(Numeric(14, 2))
    follow_up_at = Column(DateTime(timezone=True))
    notes = Column(Text)


class CompanyMasterDetails(Base):
    __tablename__ = "suite_company_master_details"
    account_id = Column(Integer, ForeignKey("crm_companies.id", ondelete="RESTRICT"), primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    legal_name = Column(String(180))
    trade_name = Column(String(180))
    business_type = Column(String(100))
    addresses = Column(JSON, nullable=False, default=list)
    tax_registrations = Column(JSON, nullable=False, default=list)
    primary_contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="RESTRICT"))
    version = Column(Integer, nullable=False, default=1)


class CompanyContactLink(Base):
    __tablename__ = "suite_company_contact_links"
    account_id = Column(Integer, ForeignKey("crm_companies.id", ondelete="RESTRICT"), primary_key=True)
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="RESTRICT"), primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    relationship = Column(String(100), default="Contact person")


class ContactBirthday(Base):
    __tablename__ = "suite_contact_birthdays"
    __table_args__ = (
        CheckConstraint("(CASE WHEN contact_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN person_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN employee_id IS NOT NULL THEN 1 ELSE 0 END) = 1", name="ck_contact_birthday_owner"),
        CheckConstraint("(birth_day IS NULL AND birth_month IS NULL AND birth_year IS NULL) OR (birth_day BETWEEN 1 AND 31 AND birth_month BETWEEN 1 AND 12 AND (birth_year IS NULL OR birth_year BETWEEN 1900 AND 9999))", name="ck_contact_birthday_parts"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="RESTRICT"), unique=True)
    person_id = Column(Integer, ForeignKey("common_people.id", ondelete="RESTRICT"), unique=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="RESTRICT"), unique=True)
    birth_day = Column(Integer)
    birth_month = Column(Integer)
    birth_year = Column(Integer)
    email_opt_in = Column(Boolean, nullable=False, default=False)
    whatsapp_opt_in = Column(Boolean, nullable=False, default=False)
    sms_opt_in = Column(Boolean, nullable=False, default=False)
    reminders_enabled = Column(Boolean, nullable=False, default=False)
    version = Column(Integer, nullable=False, default=1)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class GreetingReservation(Base):
    __tablename__ = "suite_contact_greeting_reservations"
    __table_args__ = (UniqueConstraint("birthday_id", "year", "channel", name="uq_contact_annual_greeting"),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    birthday_id = Column(Integer, ForeignKey("suite_contact_birthdays.id", ondelete="RESTRICT"), nullable=False)
    year = Column(Integer, nullable=False)
    channel = Column(String(15), nullable=False)
    status = Column(String(20), nullable=False, default="prepared")
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
