"""Durable edit history and workspace recovery checkpoints."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.sql import func
from app.db.base_class import Base


class RecoveryChange(Base):
    __tablename__ = "pms_recovery_changes"
    id = Column(Integer, primary_key=True)
    workspace_id = Column(
        Integer, ForeignKey("pms_workspaces.id"), index=True, nullable=False
    )
    task_id = Column(Integer, ForeignKey("pms_tasks.id"), index=True, nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    before = Column(JSON, nullable=False)
    after = Column(JSON, nullable=False)
    state = Column(String(16), nullable=False, default="applied")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class RecoveryPoint(Base):
    __tablename__ = "pms_recovery_points"
    id = Column(Integer, primary_key=True)
    workspace_id = Column(
        Integer, ForeignKey("pms_workspaces.id"), index=True, nullable=False
    )
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(160), nullable=False)
    automatic = Column(Boolean, default=False, nullable=False)
    payload = Column(JSON, nullable=False)
    checksum = Column(String(64), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class RecoveryPolicy(Base):
    __tablename__ = "pms_recovery_policies"
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id"), primary_key=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    enabled = Column(Boolean, default=False, nullable=False)
    interval_hours = Column(Integer, default=24, nullable=False)
    retain_automatic = Column(Integer, default=14, nullable=False)
    last_success_at = Column(DateTime)
