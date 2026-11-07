"""Durable calendar checkpoints and per-account event mappings."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from app.db.base_class import Base


class CalendarSyncState(Base):
    __tablename__ = "calendar_sync_states"
    integration_id = Column(Integer, ForeignKey("calendar_integrations.id", ondelete="CASCADE"), primary_key=True)
    enabled = Column(Boolean, nullable=False, default=True)
    import_target = Column(String(12), nullable=False, default="crm")
    account_key = Column(String(64))
    cursor_encrypted = Column(Text)
    window_start = Column(DateTime(timezone=True))
    window_end = Column(DateTime(timezone=True))
    last_synced_at = Column(DateTime(timezone=True))
    next_run_at = Column(DateTime(timezone=True), index=True)
    failures = Column(Integer, nullable=False, default=0)
    last_error = Column(String(240))
    lease_owner = Column(String(36))
    lease_until = Column(DateTime(timezone=True))
    counts = Column(JSON, nullable=False, default=dict)


class CalendarEventLink(Base):
    __tablename__ = "calendar_event_links"
    __table_args__ = (
        UniqueConstraint("integration_id", "module", "local_id", name="uq_calendar_link_local"),
        UniqueConstraint("integration_id", "remote_id", name="uq_calendar_link_remote"),
    )
    id = Column(Integer, primary_key=True)
    integration_id = Column(Integer, ForeignKey("calendar_integrations.id", ondelete="CASCADE"), nullable=False, index=True)
    module = Column(String(12), nullable=False)
    local_id = Column(Integer, nullable=False)
    remote_id = Column(String(1024), nullable=False)
    # The last agreed local/remote values detect independent edits without comparing clocks.
    local_snapshot = Column(JSON, nullable=False, default=dict)
    remote_snapshot = Column(JSON, nullable=False, default=dict)
    remote_etag = Column(String(512))
    remote_metadata = Column(JSON, nullable=False, default=dict)
    conflict = Column(Boolean, nullable=False, default=False)
    conflict_remote = Column(JSON)
    resolution = Column(String(12))
    deleted = Column(Boolean, nullable=False, default=False)
    last_synced_at = Column(DateTime(timezone=True))
