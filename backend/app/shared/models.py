from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    JSON,
    ForeignKey,
    DateTime,
    UniqueConstraint,
    event,
)
from sqlalchemy.sql import func
from app.db.base_class import Base


class ServicePolicy(Base):
    __tablename__ = "suite_service_policies"
    id = Column(Integer, primary_key=True)
    scope_key = Column(String(180), unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("companies.id"), index=True)
    module_key = Column(String(80), nullable=False, default="*")
    kind = Column(String(40), nullable=False)
    values_json = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ServiceEvent(Base):
    __tablename__ = "suite_service_events"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "request_key", name="uq_suite_event_request"
        ),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("companies.id"), nullable=False, index=True
    )
    module_key = Column(String(80), nullable=False, index=True)
    event_type = Column(String(120), nullable=False, index=True)
    entity_type = Column(String(80), nullable=False)
    entity_id = Column(Integer, nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    request_key = Column(String(180), nullable=False)
    payload_json = Column(JSON, nullable=False, default=dict)
    status = Column(String(30), nullable=False, default="pending", index=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WorkflowVersion(Base):
    __tablename__ = "suite_workflow_versions"
    __table_args__ = (
        UniqueConstraint("workflow_id", "version", name="uq_suite_workflow_version"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("companies.id"), nullable=False, index=True
    )
    workflow_id = Column(
        Integer, ForeignKey("automation_workflows.id"), nullable=False, index=True
    )
    version = Column(Integer, nullable=False)
    graph_json = Column(JSON, nullable=False)
    digest = Column(String(64), nullable=False)
    published_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    run_as_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ServiceDocument(Base):
    __tablename__ = "suite_service_documents"
    __table_args__ = (
        UniqueConstraint("document_key", "version", name="uq_suite_document_version"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("companies.id"), nullable=False, index=True
    )
    module_key = Column(String(80), nullable=False, index=True)
    entity_type = Column(String(80), nullable=False)
    entity_id = Column(Integer, nullable=False)
    document_key = Column(String(100), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    name = Column(String(240), nullable=False)
    folder = Column(String(240), nullable=False, default="/")
    mime_type = Column(String(120), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    storage_path = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


@event.listens_for(WorkflowVersion, "before_update")
@event.listens_for(WorkflowVersion, "before_delete")
def immutable_version(*args):
    raise ValueError("Published workflow versions are immutable")
