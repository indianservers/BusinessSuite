"""Payment requests are separate from receipts and accounting postings."""
from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime, ForeignKey, UniqueConstraint, Index, CheckConstraint
from sqlalchemy.sql import func
from app.db.base_class import Base
from app.shared.payment_schema import SOURCE_CHECK


class PaymentRequest(Base):
    __tablename__ = "suite_payment_requests"
    __table_args__ = (
        UniqueConstraint("organization_id", "request_id", name="uq_suite_payment_request_id"),
        Index("ix_suite_payment_source", "organization_id", "source_type", "source_id"),
        CheckConstraint("amount > 0", name="ck_suite_payment_positive"),
        CheckConstraint(SOURCE_CHECK, name="ck_suite_payment_source"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    request_id = Column(String(36), nullable=False)
    source_type = Column(String(30), nullable=False)
    source_id = Column(Integer, nullable=False)
    deal_id = Column(Integer, ForeignKey("crm_deals.id", ondelete="RESTRICT"))
    quotation_id = Column(Integer, ForeignKey("crm_quotations.id", ondelete="RESTRICT"))
    sales_order_id = Column(Integer, ForeignKey("srm_sales_orders.id", ondelete="RESTRICT"))
    invoice_id = Column(Integer, ForeignKey("srm_invoices.id", ondelete="RESTRICT"))
    reference = Column(String(180), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    instructions = Column(Text, nullable=False, default="")
    status = Column(String(40), nullable=False, default="awaiting_gateway")
    provider = Column(String(30))
    provider_account = Column(String(64))
    provider_id = Column(String(100))
    payment_url = Column(String(500))
    amount_paid = Column(Numeric(14, 2), nullable=False, default=0)
    receipt_id = Column(Integer, ForeignKey("srm_receipts.id", ondelete="RESTRICT"), unique=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
