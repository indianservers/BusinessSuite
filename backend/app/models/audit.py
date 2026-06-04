from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, DateTime, Text, Index, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_log_entity", "entity_type", "entity_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    method = Column(String(10), nullable=False)
    endpoint = Column(String(500))
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    status_code = Column(Integer)
    duration_ms = Column(Integer)
    entity_type = Column(String(100))
    entity_id = Column(Integer)
    action = Column(String(50))  # CREATE, UPDATE, DELETE, LOGIN, LOGOUT
    old_values = Column(Text)  # JSON
    new_values = Column(Text)  # JSON
    description = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User", back_populates="audit_logs")


class FieldAuditEvent(Base):
    __tablename__ = "field_audit_events"
    __table_args__ = (
        Index("idx_field_audit_employee_field", "employee_id", "field_name", "created_at"),
        Index("idx_field_audit_module_actor", "module", "actor_user_id", "created_at"),
        Index("idx_field_audit_hash", "new_value_hash"),
    )

    id = Column(Integer, primary_key=True, index=True)
    module = Column(String(80), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True)
    field_name = Column(String(120), nullable=False, index=True)
    action = Column(String(50), default="updated", index=True)
    old_value_masked = Column(String(500))
    new_value_masked = Column(String(500))
    old_value_hash = Column(String(128), index=True)
    new_value_hash = Column(String(128), index=True)
    old_value_plaintext = Column(Text)
    new_value_plaintext = Column(Text)
    is_sensitive = Column(Boolean, default=True, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    reason = Column(Text)
    request_id = Column(String(120))
    ip_address = Column(String(50))
    metadata_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
