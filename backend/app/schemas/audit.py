from datetime import datetime
from typing import Optional
from typing import Any
from pydantic import BaseModel, ConfigDict


class AuditLogSchema(BaseModel):
    id: int
    user_id: Optional[int] = None
    method: str
    endpoint: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status_code: Optional[int] = None
    duration_ms: Optional[int] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    action: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FieldAuditEventSchema(BaseModel):
    id: int
    module: str
    entity_type: str
    entity_id: int
    employee_id: Optional[int] = None
    field_name: str
    action: Optional[str] = None
    old_value_masked: Optional[str] = None
    new_value_masked: Optional[str] = None
    old_value_hash: Optional[str] = None
    new_value_hash: Optional[str] = None
    is_sensitive: bool = True
    actor_user_id: Optional[int] = None
    reason: Optional[str] = None
    request_id: Optional[str] = None
    ip_address: Optional[str] = None
    metadata_json: Optional[dict[str, Any]] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
