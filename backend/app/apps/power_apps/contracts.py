"""Versioned declarative contracts. Phase 1 deliberately has no executor."""
from typing import Literal, Protocol
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.apps.power_apps.graph import VisualWorkflowDefinition

class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class Trigger(Contract):
    type: Literal["manual", "event", "scheduled", "webhook"] = "manual"
    event_name: str | None = Field(default=None, max_length=160)
    schedule: str | None = Field(default=None, max_length=120)

class Node(Contract):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    type: Literal["condition", "branch", "action", "delay", "approval", "webhook"]
    component: str | None = Field(default=None, max_length=120)
    next: list[str] = Field(default_factory=list, max_length=50)
    # Secrets and arbitrary request bodies are excluded from Phase 1 definitions.
    credential_reference: str | None = Field(default=None, max_length=120, pattern=r"^[a-zA-Z0-9_-]+$")
    delay_seconds: int | None = Field(default=None, ge=0, le=2592000)

class WorkflowDefinition(Contract):
    schema_version: Literal[1] = 1
    trigger: Trigger = Field(default_factory=Trigger)
    nodes: list[Node] = Field(default_factory=list, max_length=200)
    entry: str | None = Field(default=None, max_length=80)
    max_attempts: int = Field(default=3, ge=1, le=10)
    retry_backoff_seconds: int = Field(default=60, ge=1, le=86400)
    idempotency: Literal["event_id", "request_id"] = "request_id"
    execution_identity: Literal["owner"] = "owner"

    @model_validator(mode="after")
    def valid_graph(self):
        ids = {node.id for node in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("Node IDs must be unique")
        if self.entry is not None and self.entry not in ids:
            raise ValueError("Entry must reference a node")
        if any(target not in ids for node in self.nodes for target in node.next):
            raise ValueError("Edges must reference existing nodes")
        return self

class DraftCreate(Contract):
    name: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=2000)
    definition: WorkflowDefinition | VisualWorkflowDefinition = Field(default_factory=WorkflowDefinition)

class DraftUpdate(DraftCreate):
    expected_version: int = Field(ge=1)

class EnvironmentUpdate(Contract):
    enabled: bool

class ExecutionContext(Contract):
    organization_id: int
    environment: Literal["development", "testing", "production"]
    workflow_id: int
    version: int
    actor_user_id: int
    idempotency_key: str = Field(min_length=1, max_length=180)
    correlation_id: str

class ConnectorAdapter(Protocol):
    def authorize(self, context: ExecutionContext, credential_reference: str) -> None: ...
    def execute(self, context: ExecutionContext, node: Node) -> dict: ...


class EventEnvelope(Contract):
    """Future producers must provide explicit tenant and environment context."""
    event_id: str = Field(min_length=1, max_length=180)
    name: str = Field(min_length=1, max_length=160)
    source: str = Field(min_length=1, max_length=80)
    organization_id: int
    environment: Literal["development", "testing", "production"]
    actor_user_id: int
    occurred_at: datetime
    correlation_id: str
    resource_type: str | None = None
    resource_id: str | None = None


class ExecutionResult(Contract):
    status: Literal["succeeded", "failed", "waiting", "retry_pending"]
    attempt: int = Field(ge=1, le=10)
    node_id: str
    next_attempt_at: datetime | None = None
    error_code: str | None = None
    # Results must never expose decrypted credentials or full connector responses.
