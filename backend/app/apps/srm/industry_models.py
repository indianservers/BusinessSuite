"""Specialist operational records; money and stock remain in their native ledgers."""
from sqlalchemy import Column, Integer, String, ForeignKey, JSON, DateTime, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.db.base_class import Base


class IndustryRecord(Base):
    __tablename__ = "srm_industry_records"
    __table_args__ = (
        UniqueConstraint("organization_id", "branch_id", "request_id", name="uq_industry_request"),
        Index("ix_industry_scope_kind", "organization_id", "branch_id", "kind"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    kind = Column(String(40), nullable=False)
    title = Column(String(220), nullable=False)
    status = Column(String(30), nullable=False, default="draft")
    revision = Column(Integer, nullable=False, default=1)
    request_id = Column(String(36), nullable=False)
    customer_id = Column(Integer, ForeignKey("crm_companies.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id"), nullable=True)
    parent_id = Column(Integer, ForeignKey("srm_industry_records.id"), nullable=True)
    invoice_id = Column(Integer, ForeignKey("srm_invoices.id"), nullable=True)
    stock_movement_id = Column(Integer, ForeignKey("srm_inventory_movements.id"), nullable=True, unique=True)
    starts_at = Column(DateTime(timezone=True), nullable=True, index=True)
    ends_at = Column(DateTime(timezone=True), nullable=True, index=True)
    data = Column(JSON, nullable=False, default=dict)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
