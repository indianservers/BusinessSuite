"""Persistent, tenant-scoped import staging and reversible change receipts."""
from sqlalchemy import Column, Integer, String, JSON, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.base_class import Base


class ImportBatch(Base):
    __tablename__ = "suite_import_batches"
    id = Column(String(36), primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=False, index=True)
    module = Column(String(20), nullable=False, index=True)
    entity = Column(String(40), nullable=False)
    filename = Column(String(220), nullable=False)
    source = Column(String(40), nullable=False, default="spreadsheet")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), nullable=False, default="uploaded")
    version = Column(Integer, nullable=False, default=1)
    table_json = Column(JSON, nullable=False)
    mapping_json = Column(JSON, nullable=True)
    options_json = Column(JSON, nullable=True)
    preview_json = Column(JSON, nullable=True)
    changes_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    committed_at = Column(DateTime(timezone=True))
    revoked_at = Column(DateTime(timezone=True))
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}


class ImportConnection(Base):
    __tablename__ = "suite_import_connections"
    id = Column(String(36), primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String(30), nullable=False)
    account_id = Column(String(120), nullable=False)
    region = Column(String(10), nullable=False, default="com")
    secret = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
