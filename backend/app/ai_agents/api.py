from __future__ import annotations
from app.access.catalog import permission_objects

import csv
import io
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.ai_agents.models import (
    AiActionApproval,
    AiAgent,
    AiAgentPermission,
    AiAuditLog,
    AiConversation,
    AiCostLog,
    AiHandoffNote,
    AiMessage,
    AiMessageFeedback,
    AiSecuritySetting,
    AiUsageEvent,
    AiUsageLimit,
)
from app.ai_agents.schemas import (
    AiAgentRead,
    AiAgentStatusUpdate,
    AiApprovalRead,
    AiApprovalReject,
    AiChatRequest,
    AiChatResponse,
    AiConfigUpdate,
    AiConversationCreate,
    AiConversationDetail,
    AiConversationRead,
    AiFeedbackCreate,
    AiHandoffCreate,
    AiHandoffStatusUpdate,
    AiMessageCreate,
    AiMessageRead,
    AiMessageSaveResponse,
    AiPermissionPayload,
    AiSecuritySettingsPayload,
    AiToolExecutionResponse,
    AiToolTestRequest,
    AiUsageLimitPayload,
)
from app.ai_agents.services.advanced_security import (
    AiAgentPermissionService,
    AiDataRedactionService,
    AiSecuritySettingsService,
    AiUsageService,
)
from app.ai_agents.services.approvals import AiApprovalService
from app.ai_agents.services.approval_executor import AiApprovalExecutorService
from app.ai_agents.services.audit import AiAuditService
from app.ai_agents.services.orchestrator import AiAgentOrchestratorService
from app.ai_agents.services.rate_limit import AiRateLimitService
from app.ai_agents.services.registry import AiAgentRegistryService
from app.ai_agents.services.settings import AiAgentSettingsService
from app.ai_agents.tools.ai_tool_execution_service import AiToolExecutionService
from app.core.deps import get_current_user, get_db
from app.models.user import User

router = APIRouter(prefix="/ai-agents", tags=["AI Agents"])

AI_ENGINE_PLACEHOLDER = "AI engine is not connected yet. Message saved successfully."


def _request_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _company_id(user: User) -> int | None:
    employee = getattr(user, "employee", None)
    return getattr(employee, "organization_id", None) or getattr(user, "company_id", None)


def _can_access_ai_agents(user: User) -> bool:
    if not user or not getattr(user, "is_active", True):
        return False
    if user.is_superuser:
        return True
    permissions = {permission.name for permission in (permission_objects(user))}
    return bool(permissions.intersection({"ai_assistant", "settings_manage"}))


def _require_ai_access(user: User) -> None:
    if not _can_access_ai_agents(user):
        raise HTTPException(status_code=403, detail="You do not have permission to access AI Agents")


def _is_ai_tool_tester(user: User) -> bool:
    if user.is_superuser:
        return True
    role_name = (user.role.name if user.role else "").lower().replace(" ", "_")
    if role_name in {"admin", "super_admin", "developer"}:
        return True
    permissions = {permission.name for permission in (permission_objects(user))}
    return bool(permissions.intersection({"settings_view", "settings_manage"}))


def _is_ai_admin(user: User) -> bool:
    if user.is_superuser:
        return True
    role_name = (user.role.name if user.role else "").lower().replace(" ", "_")
    if role_name in {"admin", "super_admin", "developer"}:
        return True
    permissions = {permission.name for permission in (permission_objects(user))}
    return bool(permissions.intersection({"settings_manage"}))


def _require_ai_admin(user: User) -> None:
    if not _is_ai_admin(user):
        raise HTTPException(status_code=403, detail="Only admin users can manage AI Agent configuration")


def _require_ai_rate_limit(db: Session, request: Request, user: User, *, bucket: str) -> None:
    limit = AiRateLimitService.limit_for_user(user)
    if AiRateLimitService.check(user=user, bucket=bucket, limit=limit):
        return
    _audit(
        db,
        request,
        user,
        action="AI_RATE_LIMIT_EXCEEDED",
        module="CROSS",
        input_json={"bucket": bucket, "limit": limit},
        output_json={"success": False, "error_code": "RATE_LIMIT_EXCEEDED"},
        status="failed",
    )
    db.commit()
    raise HTTPException(
        status_code=429,
        detail={
            "success": False,
            "error_code": "RATE_LIMIT_EXCEEDED",
            "message": "AI usage limit reached. Please try again later.",
        },
    )


def _audit(
    db: Session,
    request: Request,
    user: User,
    *,
    action: str,
    module: str = "CROSS",
    agent_id: int | None = None,
    input_json: dict | None = None,
    output_json: dict | None = None,
    status: str = "success",
    related_entity_type: str | None = None,
    related_entity_id: str | None = None,
) -> None:
    AiAuditService(db).log(
        user=user,
        agent_id=agent_id,
        module=module,
        action=action,
        input_json=input_json,
        output_json=output_json,
        status=status,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        ip_address=_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


@router.get("", response_model=list[AiAgentRead])
def list_agents(
    request: Request,
    module: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_ai_access(current_user)
    agents = AiAgentRegistryService(db).list_agents(module)
    _audit(
        db,
        request,
        current_user,
        action="agent.list_viewed",
        module=module.upper() if module else "CROSS",
        input_json={"module": module},
        output_json={"count": len(agents)},
    )
    db.commit()
    return agents


@router.get("/config")
def ai_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    company_id = _company_id(current_user)
    agents = AiAgentRegistryService(db).list_agents()
    settings_by_agent = {row.agent_id: row for row in AiAgentSettingsService(db).list_for_company(company_id)}
    return [
        {
            "agent": AiAgentRead.model_validate(agent),
            "setting": {
                "is_enabled": settings_by_agent.get(agent.id).is_enabled if settings_by_agent.get(agent.id) else True,
                "auto_action_enabled": settings_by_agent.get(agent.id).auto_action_enabled if settings_by_agent.get(agent.id) else False,
                "approval_required": settings_by_agent.get(agent.id).approval_required if settings_by_agent.get(agent.id) else True,
                "data_access_scope": settings_by_agent.get(agent.id).data_access_scope if settings_by_agent.get(agent.id) else "own_records",
            },
        }
        for agent in agents
    ]


@router.put("/config/{agent_id}")
def update_ai_config(
    agent_id: int,
    payload: AiConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    agent = db.query(AiAgent).filter(AiAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    company_id = _company_id(current_user)
    setting = AiAgentSettingsService(db).get_or_create(agent_id=agent_id, company_id=company_id)

    for field in ("is_enabled", "auto_action_enabled", "approval_required", "data_access_scope"):
        value = getattr(payload, field)
        if value is not None:
            setattr(setting, field, value)

    _audit(
        db,
        request,
        current_user,
        agent_id=agent.id,
        module=agent.module,
        action="agent.config_updated",
        input_json=payload.model_dump(exclude_none=True),
        output_json={"status": "updated"},
    )
    db.commit()
    return {"status": "updated"}


@router.post("/conversations", response_model=AiConversationRead)
def create_conversation(
    payload: AiConversationCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_ai_access(current_user)
    agent = AiAgentRegistryService(db).get_agent(payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="AI agent not found")
    if agent.module != payload.module:
        raise HTTPException(status_code=400, detail="Conversation module does not match the selected agent")

    conversation = AiConversation(
        user_id=current_user.id,
        agent_id=agent.id,
        module=payload.module,
        title=payload.title or agent.name,
        related_entity_type=payload.related_entity_type,
        related_entity_id=payload.related_entity_id,
        status="active",
    )
    db.add(conversation)
    db.flush()
    _audit(
        db,
        request,
        current_user,
        agent_id=agent.id,
        module=agent.module,
        action="conversation.created",
        input_json=payload.model_dump(exclude_none=True),
        output_json={"conversation_id": conversation.id},
        related_entity_type=conversation.related_entity_type,
        related_entity_id=conversation.related_entity_id,
    )
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/conversations", response_model=list[AiConversationRead])
def list_conversations(
    agent_id: int | None = None,
    module: str | None = None,
    related_entity_type: str | None = None,
    related_entity_id: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_ai_access(current_user)
    query = db.query(AiConversation).filter(AiConversation.user_id == current_user.id)
    if agent_id:
        query = query.filter(AiConversation.agent_id == agent_id)
    if module:
        query = query.filter(AiConversation.module == module.upper())
    if related_entity_type:
        query = query.filter(AiConversation.related_entity_type == related_entity_type)
    if related_entity_id:
        query = query.filter(AiConversation.related_entity_id == related_entity_id)
    if status:
        query = query.filter(AiConversation.status == status)
    return query.order_by(AiConversation.updated_at.desc().nullslast(), AiConversation.created_at.desc()).limit(100).all()


@router.post("/tools/test", response_model=AiToolExecutionResponse)
def test_ai_tool(
    payload: AiToolTestRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_ai_access(current_user)
    if not _is_ai_tool_tester(current_user):
        raise HTTPException(status_code=403, detail="Only admin/developer users can test AI tools")
    _require_ai_rate_limit(db, request, current_user, bucket="ai_tool_test")
    result = AiToolExecutionService(db).execute_tool(
        user=current_user,
        agent_code=payload.agent_code,
        tool_name=payload.tool_name,
        input=payload.input,
        conversation_id=payload.conversation_id,
        related_entity_type=payload.related_entity_type,
        related_entity_id=payload.related_entity_id,
        ip_address=_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return result


@router.get("/conversations/{conversation_id}", response_model=AiConversationDetail)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_ai_access(current_user)
    row = (
        db.query(AiConversation)
        .options(joinedload(AiConversation.messages))
        .filter(AiConversation.id == conversation_id, AiConversation.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return row


@router.get("/conversations/{conversation_id}/messages", response_model=list[AiMessageRead])
def get_conversation_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_ai_access(current_user)
    conversation = db.query(AiConversation).filter(AiConversation.id == conversation_id, AiConversation.user_id == current_user.id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return db.query(AiMessage).filter(AiMessage.conversation_id == conversation.id).order_by(AiMessage.created_at.asc(), AiMessage.id.asc()).all()


@router.post("/conversations/{conversation_id}/messages", response_model=AiMessageSaveResponse)
def save_conversation_message(
    conversation_id: int,
    payload: AiMessageCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_ai_access(current_user)
    conversation = db.query(AiConversation).filter(AiConversation.id == conversation_id, AiConversation.user_id == current_user.id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    message = AiMessage(conversation_id=conversation.id, role="user", content=payload.content)
    db.add(message)
    db.flush()
    _audit(
        db,
        request,
        current_user,
        agent_id=conversation.agent_id,
        module=conversation.module,
        action="message.saved",
        input_json={"content_length": len(payload.content)},
        output_json={"message_id": message.id, "placeholder": True},
        related_entity_type=conversation.related_entity_type,
        related_entity_id=conversation.related_entity_id,
    )
    db.commit()
    db.refresh(message)
    return AiMessageSaveResponse(conversation_id=conversation.id, message_id=message.id, response=AI_ENGINE_PLACEHOLDER)


@router.get("/approvals/pending", response_model=list[AiApprovalRead])
def pending_approvals(
    module: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_ai_access(current_user)
    query = db.query(AiActionApproval).filter(AiActionApproval.status == "pending")
    if module:
        query = query.filter(AiActionApproval.module == module.upper())
    if not current_user.is_superuser:
        query = query.filter(AiActionApproval.user_id == current_user.id)
    return query.order_by(AiActionApproval.created_at.desc()).limit(100).all()


@router.post("/approvals/{approval_id}/approve", response_model=AiApprovalRead)
def approve_ai_action(
    approval_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_ai_access(current_user)
    row = AiApprovalExecutorService(db).execute_approved_action(
        user=current_user,
        approval_id=approval_id,
        ip_address=_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _audit(
        db,
        request,
        current_user,
        agent_id=row.agent_id,
        module=row.module,
        action="approval.approved",
        input_json={"approval_id": approval_id},
        output_json={"status": row.status, "execution_result": row.execution_result_json},
        related_entity_type=row.related_entity_type,
        related_entity_id=row.related_entity_id,
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/approvals/{approval_id}/reject", response_model=AiApprovalRead)
def reject_ai_action(
    approval_id: int,
    payload: AiApprovalReject,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_ai_access(current_user)
    row = AiApprovalService(db).reject(approval_id, payload.rejected_reason, current_user)
    _audit(
        db,
        request,
        current_user,
        agent_id=row.agent_id,
        module=row.module,
        action="approval.rejected",
        input_json={"approval_id": approval_id, "rejected_reason": payload.rejected_reason},
        output_json={"status": row.status},
        related_entity_type=row.related_entity_type,
        related_entity_id=row.related_entity_id,
    )
    db.commit()
    db.refresh(row)
    return row


@router.get("/logs")
def ai_logs(
    module: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_ai_access(current_user)
    query = db.query(AiAuditLog)
    if module:
        query = query.filter(AiAuditLog.module == module.upper())
    if not current_user.is_superuser:
        query = query.filter(AiAuditLog.user_id == current_user.id)
    rows = query.order_by(AiAuditLog.created_at.desc()).limit(200).all()
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "agent_id": row.agent_id,
            "module": row.module,
            "action": row.action,
            "status": row.status,
            "related_entity_type": row.related_entity_type,
            "related_entity_id": row.related_entity_id,
            "input_json": row.input_json,
            "output_json": row.output_json,
            "created_at": row.created_at,
        }
        for row in rows
    ]


def _json_ready(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _limit_payload(row: AiUsageLimit) -> dict:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "user_id": row.user_id,
        "agent_id": row.agent_id,
        "module": row.module,
        "limit_type": row.limit_type,
        "max_requests": row.max_requests,
        "period": row.period,
        "is_active": row.is_active,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _company_filter(query, model, current_user: User):
    company_id = _company_id(current_user)
    if current_user.is_superuser:
        return query
    if hasattr(model, "company_id"):
        return query.filter(model.company_id == company_id)
    return query


@router.get("/usage/limits")
def get_usage_limits(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    company_id = _company_id(current_user)
    rows = db.query(AiUsageLimit).filter(AiUsageLimit.company_id == company_id).order_by(AiUsageLimit.created_at.desc()).all()
    return [_limit_payload(row) for row in rows]


@router.put("/usage/limits")
def update_usage_limits(
    payload: list[AiUsageLimitPayload],
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    company_id = _company_id(current_user)
    saved = []
    for item in payload:
        row = db.query(AiUsageLimit).filter(AiUsageLimit.id == item.id, AiUsageLimit.company_id == company_id).first() if item.id else None
        if not row:
            row = AiUsageLimit(company_id=company_id)
            db.add(row)
        for field, value in item.model_dump(exclude={"id"}).items():
            setattr(row, field, value)
        saved.append(row)
    _audit(db, request, current_user, action="AI_USAGE_LIMITS_UPDATED", input_json={"count": len(payload)}, output_json={"status": "updated"})
    db.commit()
    return {"status": "updated", "count": len(saved)}


@router.get("/usage/summary")
def usage_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    company_id = _company_id(current_user)
    since = datetime.utcnow() - timedelta(days=30)
    query = db.query(
        AiUsageEvent.event_type,
        func.count(AiUsageEvent.id),
        func.coalesce(func.sum(AiUsageEvent.token_input), 0),
        func.coalesce(func.sum(AiUsageEvent.token_output), 0),
        func.coalesce(func.sum(AiUsageEvent.estimated_cost), 0),
    ).filter(AiUsageEvent.created_at >= since)
    if not current_user.is_superuser:
        query = query.filter(AiUsageEvent.company_id == company_id)
    rows = query.group_by(AiUsageEvent.event_type).all()
    return {"period_days": 30, "events": [{"event_type": row[0], "count": row[1], "token_input": int(row[2] or 0), "token_output": int(row[3] or 0), "estimated_cost": float(row[4] or 0)} for row in rows]}


@router.get("/security/settings")
def get_security_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    row = AiSecuritySettingsService(db).get_or_create(_company_id(current_user))
    return {
        "ai_enabled": row.ai_enabled,
        "crm_ai_enabled": row.crm_ai_enabled,
        "pms_ai_enabled": row.pms_ai_enabled,
        "hrms_ai_enabled": row.hrms_ai_enabled,
        "cross_ai_enabled": row.cross_ai_enabled,
        "emergency_message": row.emergency_message,
        "updated_by": row.updated_by,
        "updated_at": row.updated_at,
    }


@router.put("/security/settings")
def update_security_settings(
    payload: AiSecuritySettingsPayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    row = AiSecuritySettingsService(db).get_or_create(_company_id(current_user))
    for field, value in payload.model_dump().items():
        setattr(row, field, value)
    row.updated_by = current_user.id
    _audit(db, request, current_user, action="AI_SECURITY_SETTINGS_UPDATED", input_json=payload.model_dump(), output_json={"status": "updated"})
    db.commit()
    return {"status": "updated"}


@router.get("/security/summary")
def security_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    events = [
        "AI_PROMPT_INJECTION_DETECTED",
        "AI_UNSAFE_PROMPT_BLOCKED",
        "AI_RESPONSE_BLOCKED_BY_SAFETY_FILTER",
        "AI_TOOL_FAILED",
        "AI_RATE_LIMIT_EXCEEDED",
        "AI_CONTEXT_SANITIZED",
        "AI_APPROVED_ACTION_FAILED",
    ]
    query = db.query(AiAuditLog.action, func.count(AiAuditLog.id)).filter(AiAuditLog.action.in_(events))
    if not current_user.is_superuser:
        query = query.filter(AiAuditLog.user_id == current_user.id)
    rows = query.group_by(AiAuditLog.action).all()
    settings = AiSecuritySettingsService(db).get_or_create(_company_id(current_user))
    return {"events": {row[0]: row[1] for row in rows}, "kill_switch": {"ai_enabled": settings.ai_enabled, "crm_ai_enabled": settings.crm_ai_enabled, "pms_ai_enabled": settings.pms_ai_enabled, "hrms_ai_enabled": settings.hrms_ai_enabled, "cross_ai_enabled": settings.cross_ai_enabled}}


@router.get("/security/events")
def security_events(module: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    actions = ["AI_PROMPT_INJECTION_DETECTED", "AI_UNSAFE_PROMPT_BLOCKED", "AI_RESPONSE_BLOCKED_BY_SAFETY_FILTER", "AI_TOOL_FAILED", "AI_RATE_LIMIT_EXCEEDED", "AI_CONTEXT_SANITIZED", "AI_APPROVED_ACTION_FAILED"]
    query = db.query(AiAuditLog).filter(AiAuditLog.action.in_(actions))
    if not current_user.is_superuser:
        query = query.filter(AiAuditLog.user_id == current_user.id)
    if module:
        query = query.filter(AiAuditLog.module == module.upper())
    rows = query.order_by(AiAuditLog.created_at.desc()).limit(200).all()
    return [{"id": row.id, "action": row.action, "module": row.module, "status": row.status, "created_at": row.created_at, "input_json": row.input_json, "output_json": row.output_json} for row in rows]


@router.get("/security/permissions")
def get_permissions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    rows = db.query(AiAgentPermission).filter(AiAgentPermission.company_id == _company_id(current_user)).all()
    return [{"id": row.id, "agent_id": row.agent_id, "role_id": row.role_id, "user_id": row.user_id, "can_use": row.can_use, "can_configure": row.can_configure, "can_approve_actions": row.can_approve_actions, "can_view_logs": row.can_view_logs, "can_export_conversations": row.can_export_conversations} for row in rows]


@router.put("/security/permissions")
def update_permissions(
    payload: list[AiPermissionPayload],
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    company_id = _company_id(current_user)
    for item in payload:
        row = db.query(AiAgentPermission).filter(AiAgentPermission.id == item.id, AiAgentPermission.company_id == company_id).first() if item.id else None
        if not row:
            row = AiAgentPermission(company_id=company_id)
            db.add(row)
        for field, value in item.model_dump(exclude={"id"}).items():
            setattr(row, field, value)
    _audit(db, request, current_user, action="AI_PERMISSION_MATRIX_UPDATED", input_json={"count": len(payload)}, output_json={"status": "updated"})
    db.commit()
    return {"status": "updated", "count": len(payload)}


@router.get("/analytics/summary")
def analytics_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    company_id = _company_id(current_user)
    conversation_query = db.query(func.count(AiConversation.id))
    approval_query = db.query(func.count(AiActionApproval.id))
    feedback_query = db.query(func.count(AiMessageFeedback.id))
    failed_query = db.query(func.count(AiAuditLog.id)).filter(AiAuditLog.action == "AI_TOOL_FAILED")
    if not current_user.is_superuser:
        conversation_query = conversation_query.filter(AiConversation.user_id == current_user.id)
        approval_query = approval_query.filter(AiActionApproval.user_id == current_user.id)
        feedback_query = feedback_query.filter(AiMessageFeedback.user_id == current_user.id)
        failed_query = failed_query.filter(AiAuditLog.user_id == current_user.id)
    conversation_ids = db.query(AiConversation.id)
    if not current_user.is_superuser:
        conversation_ids = conversation_ids.filter(AiConversation.user_id == current_user.id)
    return {
        "company_id": company_id,
        "conversations": conversation_query.scalar() or 0,
        "messages": db.query(func.count(AiMessage.id)).filter(AiMessage.conversation_id.in_(conversation_ids)).scalar() or 0,
        "approvals": approval_query.scalar() or 0,
        "feedback": feedback_query.scalar() or 0,
        "failed_tool_calls": failed_query.scalar() or 0,
    }


@router.get("/analytics/by-agent")
def analytics_by_agent(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    join_condition = AiConversation.agent_id == AiAgent.id
    query = db.query(AiAgent.id, AiAgent.name, func.count(AiConversation.id)).outerjoin(AiConversation, join_condition)
    if not current_user.is_superuser:
        query = query.filter((AiConversation.user_id == current_user.id) | (AiConversation.id.is_(None)))
    rows = query.group_by(AiAgent.id, AiAgent.name).all()
    return [{"agent_id": row[0], "agent": row[1], "conversations": row[2]} for row in rows]


@router.get("/analytics/by-module")
def analytics_by_module(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    query = db.query(AiConversation.module, func.count(AiConversation.id))
    if not current_user.is_superuser:
        query = query.filter(AiConversation.user_id == current_user.id)
    rows = query.group_by(AiConversation.module).all()
    return [{"module": row[0], "conversations": row[1]} for row in rows]


@router.get("/analytics/by-user")
def analytics_by_user(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    query = db.query(AiConversation.user_id, func.count(AiConversation.id))
    if not current_user.is_superuser:
        query = query.filter(AiConversation.user_id == current_user.id)
    rows = query.group_by(AiConversation.user_id).limit(100).all()
    return [{"user_id": row[0], "conversations": row[1]} for row in rows]


@router.get("/analytics/cost")
@router.get("/cost/summary")
def analytics_cost(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    query = db.query(AiCostLog.model, func.coalesce(func.sum(AiCostLog.total_tokens), 0), func.coalesce(func.sum(AiCostLog.estimated_cost), 0))
    if not current_user.is_superuser:
        query = query.filter(AiCostLog.company_id == _company_id(current_user))
    rows = query.group_by(AiCostLog.model).all()
    return [{"model": row[0], "total_tokens": int(row[1] or 0), "estimated_cost": float(row[2] or 0)} for row in rows]


@router.get("/cost/by-agent")
def cost_by_agent(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    query = db.query(AiCostLog.agent_id, func.coalesce(func.sum(AiCostLog.total_tokens), 0), func.coalesce(func.sum(AiCostLog.estimated_cost), 0))
    if not current_user.is_superuser:
        query = query.filter(AiCostLog.company_id == _company_id(current_user))
    rows = query.group_by(AiCostLog.agent_id).all()
    return [{"agent_id": row[0], "total_tokens": int(row[1] or 0), "estimated_cost": float(row[2] or 0)} for row in rows]


@router.get("/cost/by-user")
def cost_by_user(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    query = db.query(AiCostLog.user_id, func.coalesce(func.sum(AiCostLog.total_tokens), 0), func.coalesce(func.sum(AiCostLog.estimated_cost), 0))
    if not current_user.is_superuser:
        query = query.filter(AiCostLog.company_id == _company_id(current_user))
    rows = query.group_by(AiCostLog.user_id).all()
    return [{"user_id": row[0], "total_tokens": int(row[1] or 0), "estimated_cost": float(row[2] or 0)} for row in rows]


@router.post("/messages/{message_id}/feedback")
def create_feedback(message_id: int, payload: AiFeedbackCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_ai_access(current_user)
    message = db.query(AiMessage).filter(AiMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    conversation = db.query(AiConversation).filter(AiConversation.id == message.conversation_id, AiConversation.user_id == current_user.id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    row = AiMessageFeedback(message_id=message.id, conversation_id=conversation.id, user_id=current_user.id, agent_id=conversation.agent_id, **payload.model_dump())
    db.add(row)
    db.commit()
    return {"status": "saved", "id": row.id}


@router.get("/feedback")
def list_feedback(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    rows = db.query(AiMessageFeedback).order_by(AiMessageFeedback.created_at.desc()).limit(200).all()
    return [{"id": row.id, "message_id": row.message_id, "conversation_id": row.conversation_id, "user_id": row.user_id, "agent_id": row.agent_id, "rating": row.rating, "feedback_type": row.feedback_type, "feedback_text": row.feedback_text, "created_at": row.created_at} for row in rows]


@router.post("/handoff-notes")
def create_handoff(payload: AiHandoffCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_ai_access(current_user)
    row = AiHandoffNote(created_by=current_user.id, **payload.model_dump())
    db.add(row)
    db.commit()
    return {"status": "created", "id": row.id}


@router.get("/handoff-notes")
def list_handoff(status: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_ai_access(current_user)
    query = db.query(AiHandoffNote)
    if not _is_ai_admin(current_user):
        query = query.filter((AiHandoffNote.created_by == current_user.id) | (AiHandoffNote.assigned_to == current_user.id))
    if status:
        query = query.filter(AiHandoffNote.status == status)
    rows = query.order_by(AiHandoffNote.created_at.desc()).limit(200).all()
    return [{"id": row.id, "conversation_id": row.conversation_id, "agent_id": row.agent_id, "module": row.module, "related_entity_type": row.related_entity_type, "related_entity_id": row.related_entity_id, "assigned_to": row.assigned_to, "priority": row.priority, "summary": row.summary, "reason": row.reason, "recommended_action": row.recommended_action, "status": row.status, "created_by": row.created_by, "created_at": row.created_at} for row in rows]


@router.patch("/handoff-notes/{note_id}/status")
def update_handoff_status(note_id: int, payload: AiHandoffStatusUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_ai_access(current_user)
    row = db.query(AiHandoffNote).filter(AiHandoffNote.id == note_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Handoff note not found")
    if not _is_ai_admin(current_user) and row.assigned_to != current_user.id and row.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have permission to update this handoff note")
    row.status = payload.status
    db.commit()
    return {"status": "updated"}


@router.get("/conversations/{conversation_id}/export")
def export_conversation(conversation_id: int, format: str = "json", db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_ai_access(current_user)
    if not AiAgentPermissionService(db).can_export_conversation(current_user, conversation_id):
        raise HTTPException(status_code=403, detail="You do not have permission to export this conversation")
    conversation = db.query(AiConversation).filter(AiConversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = db.query(AiMessage).filter(AiMessage.conversation_id == conversation.id).order_by(AiMessage.created_at.asc()).all()
    redactor = AiDataRedactionService()
    export_rows = [
        {
            "role": msg.role,
            "content": redactor.redact_text(msg.content or ""),
            "tool_call_summary": redactor.redact_for_ai(current_user, conversation.module, msg.tool_call_json or {}),
            "tool_result_summary": redactor.redact_for_ai(current_user, conversation.module, msg.tool_result_json or {}),
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        }
        for msg in messages
    ]
    payload = {"conversation": {"id": conversation.id, "title": conversation.title, "module": conversation.module, "agent_id": conversation.agent_id, "created_at": conversation.created_at.isoformat() if conversation.created_at else None}, "messages": export_rows}
    fmt = format.lower()
    if fmt == "json":
        return JSONResponse(payload, headers={"Content-Disposition": f"attachment; filename=ai-conversation-{conversation.id}.json"})
    if fmt == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["created_at", "role", "content"])
        writer.writeheader()
        for row in export_rows:
            writer.writerow({"created_at": row["created_at"], "role": row["role"], "content": row["content"]})
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=ai-conversation-{conversation.id}.csv"})
    if fmt == "pdf":
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        y = 800
        pdf.drawString(40, y, f"AI Conversation: {conversation.title}")
        y -= 30
        for row in export_rows:
            text = f"{row['created_at']} {row['role']}: {row['content']}"[:110]
            pdf.drawString(40, y, text)
            y -= 18
            if y < 60:
                pdf.showPage()
                y = 800
        pdf.save()
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=ai-conversation-{conversation.id}.pdf"})
    raise HTTPException(status_code=400, detail="format must be json, csv, or pdf")


@router.post("/{agent_id}/chat", response_model=AiChatResponse)
def chat_with_agent(
    agent_id: int,
    payload: AiChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_ai_access(current_user)
    _require_ai_rate_limit(db, request, current_user, bucket="ai_chat")
    result = AiAgentOrchestratorService(db).send_message(
        user=current_user,
        agent_id=agent_id,
        payload=payload,
        ip_address=_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return result


@router.get("/{agent_id}", response_model=AiAgentRead)
def get_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_ai_access(current_user)
    agent = AiAgentRegistryService(db).get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="AI agent not found")
    return agent


@router.patch("/{agent_id}/status", response_model=AiAgentRead)
def update_agent_status(
    agent_id: int,
    payload: AiAgentStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_ai_access(current_user)
    _require_ai_admin(current_user)
    agent = AiAgentRegistryService(db).set_status(agent_id, payload.is_active)
    if not agent:
        raise HTTPException(status_code=404, detail="AI agent not found")
    _audit(
        db,
        request,
        current_user,
        agent_id=agent.id,
        module=agent.module,
        action="agent.status_changed",
        input_json=payload.model_dump(),
        output_json={"is_active": agent.is_active},
    )
    db.commit()
    db.refresh(agent)
    return agent
