"""Cross-module references; financial amounts remain in the SRM ledger."""

from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    ForeignKey,
    JSON,
    DateTime,
    UniqueConstraint,
    Boolean,
)
from sqlalchemy.sql import func
from app.db.base_class import Base


class CustomerLink(Base):
    __tablename__ = "business_customer_links"
    __table_args__ = (
        UniqueConstraint(
            "source_type", "source_id", name="uq_business_customer_source"
        ),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    customer_id = Column(
        Integer,
        ForeignKey("crm_companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_type = Column(String(40), nullable=False)
    source_id = Column(Integer, nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ProjectCommercial(Base):
    __tablename__ = "business_project_commercial"
    project_id = Column(
        Integer, ForeignKey("pms_projects.id", ondelete="RESTRICT"), primary_key=True
    )
    customer_id = Column(
        Integer,
        ForeignKey("crm_companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="RESTRICT"))
    seller_id = Column(
        Integer, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    team_id = Column(Integer, ForeignKey("crm_teams.id", ondelete="RESTRICT"))
    currency = Column(String(3), nullable=False, default="INR")
    opportunity_id = Column(
        Integer, ForeignKey("crm_deals.id", ondelete="RESTRICT"), index=True
    )
    sales_order_id = Column(
        Integer, ForeignKey("srm_sales_orders.id", ondelete="RESTRICT"), index=True
    )
    engagement_id = Column(
        Integer, ForeignKey("srm_engagements.id", ondelete="RESTRICT"), index=True
    )
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InvoiceContext(Base):
    __tablename__ = "business_invoice_contexts"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "request_id", name="uq_business_project_invoice_request"
        ),
        UniqueConstraint(
            "seller_id", "request_id", name="uq_business_seller_invoice_request"
        ),
    )
    invoice_id = Column(
        Integer, ForeignKey("srm_invoices.id", ondelete="RESTRICT"), primary_key=True
    )
    project_id = Column(
        Integer, ForeignKey("pms_projects.id", ondelete="RESTRICT"), index=True
    )
    seller_id = Column(
        Integer, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="RESTRICT"))
    request_id = Column(String(64), nullable=False)
    origin = Column(String(20), nullable=False, default="srm")
    customer_snapshot = Column(JSON)
    seller_snapshot = Column(JSON)
    contact_snapshot = Column(JSON)
    issued_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class InvoiceDelivery(Base):
    __tablename__ = "business_invoice_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "invoice_id", "request_id", name="uq_business_invoice_delivery_request"
        ),
    )
    id = Column(Integer, primary_key=True)
    invoice_id = Column(
        Integer,
        ForeignKey("srm_invoices.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    request_id = Column(String(64), nullable=False)
    message_id = Column(
        Integer, ForeignKey("communication_email_messages.id", ondelete="RESTRICT")
    )
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    status = Column(String(30), nullable=False, default="queued")
    error = Column(String(300))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SellerGrant(Base):
    __tablename__ = "business_seller_grants"
    organization_id = Column(Integer, primary_key=True)
    seller_id = Column(
        Integer, ForeignKey("companies.id", ondelete="RESTRICT"), primary_key=True
    )
    # An explicit admin-reviewed grant; legal entities are never inferred by name.
    active = Column(Boolean, nullable=False, default=True)


class TimeBillingAllocation(Base):
    __tablename__ = "business_time_billing_allocations"
    id = Column(Integer, primary_key=True)
    time_log_id = Column(
        Integer,
        ForeignKey("pms_time_logs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    invoice_id = Column(
        Integer,
        ForeignKey("srm_invoices.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    minutes = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SalesTeamAssignment(Base):
    __tablename__ = "business_sales_team_assignments"
    sales_order_id = Column(
        Integer,
        ForeignKey("srm_sales_orders.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    team_id = Column(
        Integer, ForeignKey("crm_teams.id", ondelete="RESTRICT"), nullable=False
    )
    assigned_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    assigned_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MilestoneBillingSource(Base):
    __tablename__ = "business_milestone_billing_sources"
    pms_milestone_id = Column(
        Integer, ForeignKey("pms_milestones.id", ondelete="RESTRICT"), primary_key=True
    )
    billing_milestone_id = Column(
        Integer,
        ForeignKey("srm_billing_milestones.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )


class CommercialNumberSequence(Base):
    __tablename__ = "business_number_sequences"
    series = Column(String(80), primary_key=True)
    last_number = Column(BigInteger, nullable=False, default=0)


class ReceiptContext(Base):
    __tablename__ = "business_receipt_contexts"
    __table_args__ = (UniqueConstraint("invoice_id", "request_id", name="uq_business_invoice_payment_request"),)
    receipt_id = Column(Integer, ForeignKey("srm_receipts.id", ondelete="RESTRICT"), primary_key=True)
    seller_id = Column(Integer, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    invoice_id = Column(Integer, ForeignKey("srm_invoices.id", ondelete="RESTRICT"), index=True)
    request_id = Column(String(64))
    reversed_at = Column(DateTime(timezone=True))
    reversal_reason = Column(String(500))
