from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.ai_agents.models import AiAgent, AiConversation, AiMessage
from app.models.user import User


class AiConversationService:
    def __init__(self, db: Session):
        self.db = db

    def create_or_get(
        self,
        *,
        user: User,
        agent: AiAgent,
        conversation_id: int | None,
        message: str,
        module: str | None = None,
        related_entity_type: str | None = None,
        related_entity_id: str | None = None,
    ) -> AiConversation:
        if conversation_id:
            conversation = self.db.query(AiConversation).filter(
                AiConversation.id == conversation_id,
                AiConversation.user_id == user.id,
            ).first()
            if not conversation or conversation.agent_id!=agent.id:
                from fastapi import HTTPException
                raise HTTPException(404,"Conversation not found")
            from app.ai_agents.security import history_guard
            history_guard(self.db,user,conversation)
            return conversation
        title = message.strip().replace("\n", " ")[:80] or f"{agent.name} chat"
        conversation = AiConversation(
            user_id=user.id,
            agent_id=agent.id,
            module=module or agent.module,
            title=title,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            status="active",
        )
        self.db.add(conversation)
        self.db.flush()
        return conversation

    def add_message(
        self,
        conversation: AiConversation,
        role: str,
        content: str | None = None,
        tool_call_json: dict[str, Any] | None = None,
        tool_result_json: dict[str, Any] | None = None,
    ) -> AiMessage:
        row = AiMessage(
            conversation_id=conversation.id,
            role=role,
            content=content,
            tool_call_json=tool_call_json,
            tool_result_json=tool_result_json,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def list_recent_messages(self, conversation: AiConversation, limit: int = 12) -> list[AiMessage]:
        rows = (
            self.db.query(AiMessage)
            .filter(AiMessage.conversation_id == conversation.id)
            .order_by(AiMessage.created_at.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(rows))
