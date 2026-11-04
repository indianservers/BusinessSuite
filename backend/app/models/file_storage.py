"""Company storage routing and durable locators; existing business file URLs stay stable."""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, UniqueConstraint
from sqlalchemy.sql import func
from app.db.base_class import Base


class StorageConnection(Base):
    __tablename__ = "file_storage_connections"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    provider = Column(String(30), nullable=False)
    label = Column(String(160), nullable=False)
    account = Column(String(250))
    encrypted_value = Column(Text)
    expires_at = Column(DateTime(timezone=True))
    connected = Column(Boolean, nullable=False, default=False)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StoragePolicy(Base):
    __tablename__ = "file_storage_policies"
    organization_id = Column(Integer, primary_key=True)
    enabled = Column(Boolean, nullable=False, default=False)
    default_provider = Column(String(30), nullable=False, default="google_drive")
    routes = Column(JSON, nullable=False, default=dict)
    revision = Column(Integer, nullable=False, default=1)


class StorageOAuthState(Base):
    __tablename__ = "file_storage_oauth_states"
    id = Column(String(64), primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    connection_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)
    encrypted_value = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True))


class StorageObject(Base):
    __tablename__ = "file_storage_objects"
    __table_args__ = (UniqueConstraint("organization_id", "relative_path", name="uq_file_storage_locator"),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    module = Column(String(30), nullable=False)
    relative_path = Column(String(1000), nullable=False)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(160), nullable=False)
    size = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    connection_id = Column(Integer)
    provider = Column(String(30), nullable=False)
    folder_id = Column(String(250))
    remote_id = Column(String(500))
    status = Column(String(30), nullable=False, default="local")
    error = Column(String(250))
    versions = Column(JSON, nullable=False, default=list)
    uploaded_by = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
