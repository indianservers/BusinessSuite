from sqlalchemy import Column, String, Integer, Text, JSON, DateTime, Boolean, ForeignKey, UniqueConstraint
from app.db.base_class import Base

class SyncConnection(Base):
    __tablename__ = "accounting_sync_connections"
    id = Column(String(36), primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String(20), nullable=False)
    account_id = Column(String(120), nullable=False)
    source_connection_id = Column(String(36), nullable=True)
    sandbox = Column(Boolean, nullable=False, default=True)
    enabled = Column(Boolean, nullable=False, default=True)
    last_success_at = Column(DateTime(timezone=True))
    lease_until = Column(DateTime(timezone=True))
    active_token = Column(String(36))
    bridge_secret = Column(Text)
    __table_args__ = (UniqueConstraint("organization_id", "branch_id", "provider", "account_id", name="uq_accounting_sync_account"),)

class SyncRecord(Base):
    __tablename__ = "accounting_sync_records"
    id = Column(String(36), primary_key=True)
    connection_id = Column(String(36), ForeignKey("accounting_sync_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    entity = Column(String(20), nullable=False)
    external_id = Column(String(160), nullable=False)
    data = Column(JSON, nullable=False)
    fingerprint = Column(String(64), nullable=False)
    present = Column(Boolean, nullable=False, default=True)
    seen_run_id = Column(String(36), nullable=False)
    __table_args__ = (UniqueConstraint("connection_id", "entity", "external_id", name="uq_accounting_sync_record"),)

class SyncRun(Base):
    __tablename__ = "accounting_sync_runs"
    id = Column(String(36), primary_key=True)
    connection_id = Column(String(36), ForeignKey("accounting_sync_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    counts = Column(JSON, nullable=False, default=dict)
    error = Column(String(300))
