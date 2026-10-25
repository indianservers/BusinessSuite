"""Tenant-owned configuration and per-lead operating state."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, UniqueConstraint
from sqlalchemy.sql import func
from app.db.base_class import Base


class CRMLeadManagementConfig(Base):
    __tablename__ = "crm_lead_management_config"
    organization_id = Column(Integer, primary_key=True)
    settings_json = Column(JSON, nullable=False, default=dict)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CRMLeadOperatingState(Base):
    __tablename__ = "crm_lead_operating_states"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "lead_id", name="uq_crm_lead_operating_state"
        ),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    lead_id = Column(
        Integer,
        ForeignKey("crm_leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    data_json = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
