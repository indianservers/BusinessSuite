from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.ai_agents.models import AiAuditLog
from app.models.user import User


class AiAuditService:
    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        *,
        user: User | None,
        agent_id: int | None,
        module: str,
        action: str,
        input_json: dict[str, Any] | None = None,
        output_json: dict[str, Any] | None = None,
        status: str = "success",
        related_entity_type: str | None = None,
        related_entity_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AiAuditLog:
        from app.ai_agents.security import company,metadata
        from uuid import uuid4
        info=self.db.info.get("ai_request_context") or {}
        row = AiAuditLog(
            event_key=uuid4().hex,
            organization_id=company(user) if user else None,
            session_id=info.get("session_id") or getattr(user,"_suite_session_id",None),
            correlation_id=info.get("correlation_id") or uuid4().hex,
            user_id=user.id if user else None,
            agent_id=agent_id,
            module=module,
            action=action,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            input_json=metadata(input_json),
            output_json=metadata(output_json),
            status=status,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        from app.core.audit_context import context
        request=context.get()
        if request is not None:
            request.setdefault("ai_events",[]).append({column.name:getattr(row,column.name) for column in row.__table__.columns if column.name not in {"id","created_at"}})
        self.db.add(row)
        self.db.flush()
        return row

