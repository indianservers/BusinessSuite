from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import RequirePermission, get_current_user, get_db
from app.core.masking import user_has_permission
from app.models.approval_os import ApprovalComment, ApprovalHistory, ApprovalRequest
from app.models.user import User
from app.models.workflow_engine import WorkflowInstance, WorkflowStepDefinition, WorkflowTask
from app.schemas.approval_os import (
    ApprovalCommentCreate,
    ApprovalCommentSchema,
    ApprovalDecision,
    ApprovalHistorySchema,
    ApprovalInboxItem,
    ApprovalInboxResponse,
    ApprovalRequestCreate,
    ApprovalRequestSchema,
    ApprovalSummary,
)
from app.schemas.notification import NotificationCreate
from app.services.notifications import create_notification

router = APIRouter(prefix="/approval-os", tags=["Approval OS"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _role_name(user: User) -> str | None:
    return user.role.name if user.role else None


def _can_view_all(user: User) -> bool:
    return (
        user.is_superuser
        or user_has_permission(user, "approval_os_admin")
        or user_has_permission(user, "approval_os_view")
        or user_has_permission(user, "company_manage")
    )


def _can_decide_request(request: ApprovalRequest, user: User) -> bool:
    role_name = _role_name(user)
    return bool(
        user.is_superuser
        or request.assigned_to_user_id == user.id
        or request.assigned_role == role_name
        or request.delegated_to_user_id == user.id
        or request.delegated_role == role_name
        or user_has_permission(user, "approval_os_admin")
    )


def _record_history(
    db: Session,
    request: ApprovalRequest,
    event_type: str,
    actor_user_id: int | None,
    before_status: str | None,
    after_status: str | None,
    reason: str | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        ApprovalHistory(
            request_id=request.id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            before_status=before_status,
            after_status=after_status,
            reason=reason,
            details_json=details or {},
        )
    )


def _notify_assignee(db: Session, request: ApprovalRequest) -> None:
    if not request.assigned_to_user_id:
        return
    create_notification(
        db,
        NotificationCreate(
            user_id=request.assigned_to_user_id,
            title=f"Approval required: {request.title}",
            message=request.ai_summary or request.description or "A Business Suite approval needs your decision.",
            module=request.source_module,
            event_type="approval_os_pending",
            related_entity_type="approval_request",
            related_entity_id=request.id,
            action_url="/hrms/approval-os",
            channels=["in_app"],
        ),
    )


def _request_query(db: Session, user: User, scope: str):
    query = db.query(ApprovalRequest)
    role_name = _role_name(user)
    if scope == "submitted":
        return query.filter(ApprovalRequest.requester_user_id == user.id)
    if scope == "all" and _can_view_all(user):
        return query
    return query.filter(
        or_(
            ApprovalRequest.assigned_to_user_id == user.id,
            ApprovalRequest.assigned_role == role_name,
            ApprovalRequest.delegated_to_user_id == user.id,
            ApprovalRequest.delegated_role == role_name,
            ApprovalRequest.requester_user_id == user.id,
        )
    )


def _native_item(request: ApprovalRequest, user: User) -> ApprovalInboxItem:
    return ApprovalInboxItem(
        id=f"approval:{request.id}",
        source="approval_os",
        source_module=request.source_module,
        approval_type=request.approval_type,
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        title=request.title,
        description=request.description,
        requester_user_id=request.requester_user_id,
        assigned_to_user_id=request.assigned_to_user_id,
        assigned_role=request.assigned_role,
        priority=request.priority,
        status=request.status,
        sla_due_at=request.sla_due_at,
        submitted_at=request.created_at,
        escalated_at=request.escalated_at,
        ai_summary=request.ai_summary,
        mobile_enabled=bool(request.mobile_enabled),
        action_url="/hrms/approval-os",
        can_decide=request.status == "Pending" and _can_decide_request(request, user),
    )


def _workflow_item(task: WorkflowTask, instance: WorkflowInstance | None, step: WorkflowStepDefinition | None, user: User) -> ApprovalInboxItem:
    context = instance.context_json if instance and isinstance(instance.context_json, dict) else {}
    title = context.get("title") or f"{(instance.module if instance else 'Workflow').title()} approval"
    source_module = instance.module if instance else "workflow"
    role_name = _role_name(user)
    return ApprovalInboxItem(
        id=f"workflow:{task.id}",
        source="workflow_engine",
        source_module=source_module,
        approval_type=(step.step_type if step else "Approval") or "Approval",
        entity_type=instance.entity_type if instance else "workflow_task",
        entity_id=instance.entity_id if instance else task.id,
        title=title,
        description=context.get("description"),
        requester_user_id=instance.requester_user_id if instance else None,
        assigned_to_user_id=task.assigned_to_user_id,
        assigned_role=task.assigned_role,
        priority=context.get("priority") or "Normal",
        status=task.status,
        sla_due_at=task.due_at,
        submitted_at=task.created_at,
        escalated_at=task.escalated_at,
        ai_summary=context.get("ai_summary"),
        mobile_enabled=True,
        action_url="/hrms/workflow",
        can_decide=task.status == "Pending" and (user.is_superuser or task.assigned_to_user_id == user.id or task.assigned_role == role_name),
    )


def _workflow_tasks(db: Session, user: User, scope: str) -> list[ApprovalInboxItem]:
    role_name = _role_name(user)
    query = db.query(WorkflowTask, WorkflowInstance, WorkflowStepDefinition).join(
        WorkflowInstance,
        WorkflowTask.instance_id == WorkflowInstance.id,
    ).outerjoin(
        WorkflowStepDefinition,
        WorkflowTask.step_definition_id == WorkflowStepDefinition.id,
    )
    if scope == "submitted":
        query = query.filter(WorkflowInstance.requester_user_id == user.id)
    elif scope != "all" or not _can_view_all(user):
        query = query.filter(or_(WorkflowTask.assigned_to_user_id == user.id, WorkflowTask.assigned_role == role_name))
    rows = query.order_by(WorkflowTask.created_at.desc()).limit(200).all()
    return [_workflow_item(task, instance, step, user) for task, instance, step in rows]


def _summarize(items: list[ApprovalInboxItem]) -> ApprovalSummary:
    now = _now()
    by_module: dict[str, int] = {}
    by_type: dict[str, int] = {}
    pending = overdue = escalated = high_priority = 0
    for item in items:
        by_module[item.source_module] = by_module.get(item.source_module, 0) + 1
        by_type[item.approval_type] = by_type.get(item.approval_type, 0) + 1
        if item.status.lower() == "pending":
            pending += 1
            if item.sla_due_at and item.sla_due_at.replace(tzinfo=item.sla_due_at.tzinfo or timezone.utc) < now:
                overdue += 1
        if item.escalated_at:
            escalated += 1
        if item.priority.lower() in {"high", "urgent", "critical"}:
            high_priority += 1
    return ApprovalSummary(
        total=len(items),
        pending=pending,
        overdue=overdue,
        escalated=escalated,
        high_priority=high_priority,
        by_module=by_module,
        by_type=by_type,
    )


@router.post("/requests", response_model=ApprovalRequestSchema, status_code=201)
def create_request(
    data: ApprovalRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("approval_os_create", "approval_os_admin", "company_manage")),
):
    if not data.assigned_to_user_id and not data.assigned_role:
        raise HTTPException(status_code=400, detail="Approval request requires an assigned user or role")
    request = ApprovalRequest(**data.model_dump(), requester_user_id=current_user.id)
    db.add(request)
    db.flush()
    _record_history(db, request, "created", current_user.id, None, request.status, details={"source_module": request.source_module})
    _notify_assignee(db, request)
    db.commit()
    db.refresh(request)
    return request


@router.get("/inbox", response_model=ApprovalInboxResponse)
def inbox(
    scope: Literal["mine", "all", "submitted"] = Query("mine"),
    status: str | None = Query(None),
    module: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    native = [_native_item(item, current_user) for item in _request_query(db, current_user, scope).order_by(ApprovalRequest.created_at.desc()).limit(200).all()]
    items = native + _workflow_tasks(db, current_user, scope)
    if status:
        items = [item for item in items if item.status.lower() == status.lower()]
    if module:
        items = [item for item in items if item.source_module.lower() == module.lower()]
    items.sort(key=lambda item: (item.sla_due_at or item.submitted_at or _now()), reverse=False)
    return ApprovalInboxResponse(summary=_summarize(items), items=items[:300])


@router.get("/summary", response_model=ApprovalSummary)
def summary(
    scope: Literal["mine", "all", "submitted"] = Query("mine"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return inbox(scope=scope, db=db, current_user=current_user).summary


@router.get("/requests/{request_id}", response_model=ApprovalRequestSchema)
def get_request(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    request = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if not _can_decide_request(request, current_user) and request.requester_user_id != current_user.id and not _can_view_all(current_user):
        raise HTTPException(status_code=403, detail="Cannot view this approval request")
    return request


def _decide(request_id: int, decision: str, data: ApprovalDecision, db: Session, current_user: User) -> ApprovalRequest:
    request = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if request.status != "Pending":
        raise HTTPException(status_code=400, detail="Approval request is not pending")
    if not _can_decide_request(request, current_user):
        raise HTTPException(status_code=403, detail="Approval request is not assigned to the current user")
    before = request.status
    request.status = "Approved" if decision == "approve" else "Rejected"
    request.decision_reason = data.reason
    request.decided_by = current_user.id
    request.decided_at = _now()
    _record_history(db, request, f"{decision}d", current_user.id, before, request.status, data.reason)
    db.commit()
    db.refresh(request)
    return request


@router.put("/requests/{request_id}/approve", response_model=ApprovalRequestSchema)
def approve_request(request_id: int, data: ApprovalDecision, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _decide(request_id, "approve", data, db, current_user)


@router.put("/requests/{request_id}/reject", response_model=ApprovalRequestSchema)
def reject_request(request_id: int, data: ApprovalDecision, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _decide(request_id, "reject", data, db, current_user)


@router.post("/requests/{request_id}/comments", response_model=ApprovalCommentSchema, status_code=201)
def add_comment(request_id: int, data: ApprovalCommentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    request = get_request(request_id, db, current_user)
    comment = ApprovalComment(request_id=request.id, author_user_id=current_user.id, **data.model_dump())
    db.add(comment)
    _record_history(db, request, "commented", current_user.id, request.status, request.status, data.comment, {"is_internal": data.is_internal})
    db.commit()
    db.refresh(comment)
    return comment


@router.get("/requests/{request_id}/history", response_model=list[ApprovalHistorySchema])
def history(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    request = get_request(request_id, db, current_user)
    return db.query(ApprovalHistory).filter(ApprovalHistory.request_id == request.id).order_by(ApprovalHistory.created_at, ApprovalHistory.id).all()


@router.post("/process-escalations", response_model=list[ApprovalRequestSchema])
def process_escalations(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("approval_os_admin", "company_manage")),
):
    now = _now()
    rows = db.query(ApprovalRequest).filter(
        ApprovalRequest.status == "Pending",
        ApprovalRequest.sla_due_at.isnot(None),
        ApprovalRequest.sla_due_at <= now,
        ApprovalRequest.escalated_at.is_(None),
    ).all()
    for request in rows:
        before = request.status
        request.escalated_at = now
        if request.escalation_user_id or request.escalation_role:
            request.assigned_to_user_id = request.escalation_user_id
            request.assigned_role = request.escalation_role
        _record_history(
            db,
            request,
            "escalated",
            current_user.id,
            before,
            request.status,
            details={"escalation_user_id": request.escalation_user_id, "escalation_role": request.escalation_role},
        )
        _notify_assignee(db, request)
    db.commit()
    return rows
