"""Contact payment details and recorded transactions; no payment execution."""
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, CheckConstraint, UniqueConstraint
from sqlalchemy.sql import func
from app.db.base_class import Base


class ContactFinancialProfile(Base):
    __tablename__ = "crm_contact_financial_profiles"
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="RESTRICT"), primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    gst_number = Column(String(15))
    bank_accounts = Column(JSON, nullable=False, default=list)
    upi_ids = Column(JSON, nullable=False, default=list)
    version = Column(Integer, nullable=False, default=1)


class ContactFinancialTransaction(Base):
    __tablename__ = "crm_contact_financial_transactions"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_contact_transaction_positive"), UniqueConstraint("organization_id", "request_id", name="uq_contact_transaction_request"))
    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="RESTRICT"), nullable=False, index=True)
    organization_id = Column(Integer, nullable=False, index=True)
    request_id = Column(String(36))
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(15), nullable=False, default="recorded")
    void_reason = Column(String(500))
    direction = Column(String(10), nullable=False)
    amount = Column(Numeric(16, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    transaction_date = Column(Date, nullable=False)
    method = Column(String(20), nullable=False)
    reference = Column(String(120))
    notes = Column(Text)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
