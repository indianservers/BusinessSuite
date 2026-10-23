from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.ai_agents.models import AiActionApproval, AiAgent, AiConversation
from app.models.user import User


class AiApprovalService:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        conversation: AiConversation,
        agent: AiAgent,
        user: User,
        module: str,
        action_type: str,
        proposed_action: dict[str, Any],
        related_entity_type: str | None = None,
        related_entity_id: str | None = None,
    ) -> AiActionApproval:
        approval = AiActionApproval(
            conversation_id=conversation.id,
            agent_id=agent.id,
            user_id=user.id,
            module=module,
            action_type=action_type,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            proposed_action_json=proposed_action,
            status="pending",
        )
        self.db.add(approval)
        self.db.flush()
        return approval

    def approve(self, approval_id: int, user: User) -> AiActionApproval:
        approval = self.db.query(AiActionApproval).filter(AiActionApproval.id == approval_id).first()
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
        if approval.status != "pending":
            raise HTTPException(status_code=400, detail="Approval is not pending")
        approval.status = "approved"
        approval.approved_by = user.id
        approval.approved_at = datetime.utcnow()
        approval.updated_at = datetime.utcnow()
        self.db.flush()
        return approval

    def reject(self, approval_id: int, reason: str, user: User) -> AiActionApproval:
        approval = self.db.query(AiActionApproval).filter(AiActionApproval.id == approval_id).with_for_update().first()
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
        if not user.is_superuser and approval.user_id != user.id:
            raise HTTPException(status_code=403, detail="You do not have permission to reject this AI action")
        if approval.status != "pending":
            raise HTTPException(status_code=400, detail="Approval is not pending")
        approval.status = "rejected"
        approval.rejected_reason = reason
        approval.updated_at = datetime.utcnow()
        if approval.action_type == "EXECUTE_PMS_OPERATOR_PLAN":
            from app.ai_operator.models import OperatorRun
            run = self.db.query(OperatorRun).filter_by(approval_id=approval.id).with_for_update().first()
            if run and run.status == "awaiting_approval":
                run.status = "cancelled"
        self.db.flush()
        return approval
