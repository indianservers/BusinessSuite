"""Versioned, organization-owned visual CRM templates."""
from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.base_class import Base


class CRMVisualTemplate(Base):
    __tablename__ = "crm_visual_templates"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(180), nullable=False)
    category = Column(String(24), nullable=False)
    document_type = Column(String(40), nullable=False)
    module = Column(String(24), nullable=False)
    subject = Column(Text, nullable=False, default="")
    folder = Column(String(100), nullable=False, default="General")
    status = Column(String(16), nullable=False, default="draft")
    design = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    email_template_id = Column(Integer, ForeignKey("communication_email_templates.id", ondelete="SET NULL"))
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
