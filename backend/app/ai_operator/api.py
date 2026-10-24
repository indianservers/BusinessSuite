import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.ai_agents.api import _require_ai_access, _require_ai_admin, _require_ai_rate_limit
from app.ai_agents.models import AiActionApproval, AiAgent, AiAgentSetting
from app.ai_agents.services.approval_executor import AiApprovalExecutorService
from app.ai_agents.services.audit import AiAuditService
from app.ai_agents.services.registry import AiAgentRegistryService
from app.ai_agents.services.advanced_security import AiAgentPermissionService, AiDataRedactionService, AiUsageService
from app.ai_operator.models import OperatorApiLog, OperatorProvider, OperatorRun, OperatorJob, OperatorStep, OperatorEvent
from app.ai_operator.providers import encrypt_key, generate_json
from app.ai_operator.schemas import ApproveInput, CommandInput, Provider, ProviderUpdate, TaskPlan, RevisionInput, ResumeInput
from app.ai_operator.service import context_for, digest, require_enabled, scope_key, validate_plan
from app.apps.project_management.access import get_project_for_action

router = APIRouter(prefix="/ai-operator", tags=["AI Operator"])
from app.ai_operator.extensions import router as extensions_router
router.include_router(extensions_router)
from app.ai_operator.assistant_api import router as assistant_router
router.include_router(assistant_router)


def public_provider(row):
    return {"provider": row.provider, "model": row.model, "enabled": row.enabled,
        "data_sharing_allowed": row.data_sharing_allowed, "has_key": bool(row.encrypted_key),
        "max_tokens": row.max_tokens, "input_price": row.input_price, "output_price": row.output_price}


def public_run(row):
    return {name: getattr(row, name) for name in (
        "id", "project_id", "command", "input_mode", "provider", "status", "selection", "plan", "plan_hash",
        "approval_id", "result", "error_code", "created_at", "updated_at", "background", "execution_mode", "parent_run_id", "revision", "timezone")}


def owned_run(db, user, run_id, lock=False):
    query = db.query(OperatorRun).filter_by(id=run_id, user_id=user.id)
    row = (query.with_for_update() if lock else query).first()
    if not row:
        raise HTTPException(404, "Run not found")
    project = get_project_for_action(db, row.project_id, user, "manage_tasks")
    if row.scope_key != scope_key(db, user, project.workspace_id):
        raise HTTPException(403, "Run scope changed")
    return row


@router.get("/providers")
def providers(workspace_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    scope = scope_key(db, user, workspace_id)
    return {"items": [public_provider(r) for r in db.query(OperatorProvider).filter_by(scope_key=scope).all()]}


@router.put("/providers/{provider}")
def save_provider(provider: Provider, payload: ProviderUpdate, workspace_id: int | None = None,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_admin(user)
    scope = scope_key(db, user, workspace_id, manage=True)
    row = db.query(OperatorProvider).filter_by(scope_key=scope, provider=provider).with_for_update().first()
    if not row:
        if not payload.api_key:
            raise HTTPException(422, "API key is required for a new provider")
        row = OperatorProvider(scope_key=scope, provider=provider)
        db.add(row)
    if payload.api_key is not None:
        row.encrypted_key = encrypt_key(payload.api_key.get_secret_value())
    for name, value in payload.model_dump(exclude={"api_key"}).items():
        setattr(row, name, value)
    row.updated_by = user.id
    AiAuditService(db).log(user=user, agent_id=None, module="PMS", action="operator.provider.updated",
        input_json={"provider": provider, "scope": scope, "key_rotated": payload.api_key is not None},
        output_json={"model": row.model, "enabled": row.enabled}, status="success")
    db.commit()
    return public_provider(row)


@router.post("/providers/{provider}/test")
def test_provider(provider: Provider, request: Request, workspace_id: int | None = None,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_admin(user)
    _require_ai_rate_limit(db, request, user, bucket="operator_provider_test")
    scope = scope_key(db, user, workspace_id, manage=True)
    config = db.query(OperatorProvider).filter_by(scope_key=scope, provider=provider).first()
    if not config:
        raise HTTPException(404, "Provider not configured")
    try:
        generate_json(db, user, config, prompt="Connectivity test. Return summary 'Connection verified', clarification null, steps []. No business data.",
            schema=TaskPlan.model_json_schema(), purpose="test")
    except HTTPException:
        db.commit()  # Preserve sanitized failure telemetry too.
        raise
    db.commit()
    return {"success": True, "provider": provider, "model": config.model}


@router.get("/capabilities")
def capabilities(user: User = Depends(get_current_user)):
    _require_ai_access(user)
    return {"tools": ["update_task", "add_checklist", "move_to_sprint", "schedule_task", "add_dependency", "remove_dependency", "update_checklist", "remove_checklist", "add_comment"], "max_tasks": 25, "max_steps": 75,
        "approval_required": True, "execution": ["atomic_synchronous", "atomic_background", "checkpointed_background"], "voice": "browser_transcription",
        "progress": "durable_cursor_events", "revisions": True,
        "local_planning": {"supported": True, "server_validated": True, "provider_required": False, "approval_required": True},
        "providers": ["openai", "gemini", "claude"]}


@router.post("/commands")
def command(payload: CommandInput, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    request_hash = digest(payload.model_dump(exclude={"request_key"}))
    previous = db.query(OperatorRun).filter_by(user_id=user.id, request_key=payload.request_key).first()
    if previous:
        owned_run(db, user, previous.id)
        if previous.request_hash != request_hash:
            raise HTTPException(409, "Idempotency key was already used for a different command")
        return public_run(previous)
    _require_ai_rate_limit(db, request, user, bucket="operator_command")
    require_enabled(db, user)
    AiAgentRegistryService(db).ensure_seed_data()
    agent = db.query(AiAgent).filter_by(code="pms_task_planning", is_active=True).first()
    if not agent or not AiAgentPermissionService(db).can_use_agent(user, agent.id):
        raise HTTPException(403, "Task planning agent is unavailable")
    AiUsageService(db).check_limits(user=user, agent=agent, module="PMS")
    from app.ai_agents.services.advanced_security import company_id_for
    agent_setting = db.query(AiAgentSetting).filter_by(agent_id=agent.id, company_id=company_id_for(user)).first()
    if agent_setting and not agent_setting.is_enabled:
        raise HTTPException(403, "Task planning agent is disabled")
    project, tasks, context = context_for(db, user, payload.project_id, payload.task_ids)
    scope = scope_key(db, user, project.workspace_id)
    config = db.query(OperatorProvider).filter_by(scope_key=scope, provider=payload.provider, enabled=True, data_sharing_allowed=True).first()
    if not config and not payload.local_plan:
        raise HTTPException(409, "Configure and enable this provider for the project's workspace in AI settings")
    parent = None
    if payload.parent_run_id:
        parent = owned_run(db, user, payload.parent_run_id)
        if parent.approval_id:
            db.query(AiActionApproval).filter_by(id=parent.approval_id).with_for_update().first()
        parent = owned_run(db, user, parent.id, lock=True)
        if parent.project_id != payload.project_id or sorted(set(payload.task_ids)) != parent.selection:
            raise HTTPException(422, "Follow-up must retain the original project and selection")
        if parent.status in {"queued_planning", "planning", "queued", "executing", "retrying", "superseded"}:
            raise HTTPException(409, "Cancel active work or wait before revising")
        if payload.parent_plan_hash != parent.plan_hash:
            raise HTTPException(409, "Follow-up refers to an outdated preview")
        if parent.status in {"awaiting_approval", "needs_clarification", "paused"}:
            parent.status = "superseded"
            if parent.approval_id:
                previous_approval = db.get(AiActionApproval, parent.approval_id)
                if previous_approval.status == "pending":
                    previous_approval.status = "cancelled"
                elif previous_approval.execution_status in {"queued", "executing", "paused"}:
                    previous_approval.execution_status = "cancelled"
            db.query(OperatorJob).filter_by(run_id=parent.id).update({"status": "cancelled", "lease_token": None, "lease_until": None}, synchronize_session=False)
    run = OperatorRun(scope_key=scope, user_id=user.id, project_id=project.id, request_key=payload.request_key,
        request_hash=request_hash, command=payload.command, input_mode=payload.input_mode, provider=payload.provider,
        status="queued_planning" if payload.background and not payload.local_plan else "planning", selection=sorted(set(payload.task_ids)),
        snapshots={str(t.id): digest(s) for t, s in zip(tasks, context["tasks"])},
        background=payload.background, execution_mode=payload.execution_mode, timezone=payload.timezone,
        parent_run_id=parent.id if parent else None, revision=parent.revision + 1 if parent else 1)
    db.add(run)
    try:
        db.flush()
        if payload.local_plan:
            validate_plan(db, user, run, payload.local_plan)
            from app.ai_operator.planner import publish_plan
            publish_plan(db, user, run, payload.local_plan, run.snapshots)
            from app.ai_operator.jobs import emit
            emit(db, run, "plan.local", source="browser_tensorflow")
            AiAuditService(db).log(user=user, agent_id=agent.id, module="PMS", action="operator.local.plan",
                input_json={"run_id": run.id, "task_count": len(run.selection)}, output_json={"status": run.status}, status="success")
        elif payload.background:
            from app.ai_operator.jobs import emit, enqueue
            enqueue(db, run, "plan")
            emit(db, run, "run.queued")
            if parent:
                emit(db, parent, "run.revised", child_run_id=run.id)
        db.commit()  # Persist intent before the external model call; no domain changes yet.
    except IntegrityError:
        db.rollback()
        existing = db.query(OperatorRun).filter_by(user_id=user.id, request_key=payload.request_key).first()
        if not existing or existing.request_hash != request_hash:
            raise HTTPException(409, "Conflicting command request") from None
        return public_run(existing)
    if payload.background or payload.local_plan:
        return public_run(run)
    try:
        outbound = AiDataRedactionService().redact_for_ai(user, "PMS", {"command": payload.command, "authorized_context": context})
        output = generate_json(db, user, config,
            prompt=json.dumps(outbound),
            schema=TaskPlan.model_json_schema(), run_id=run.id)
        run = db.query(OperatorRun).filter_by(id=run.id).populate_existing().with_for_update().one()
        if run.status == "cancelled":
            db.commit()
            return public_run(run)
        plan = TaskPlan.model_validate(output)
        validate_plan(db, user, run, plan)
        run.plan = plan.model_dump(mode="json", exclude_none=True)
        run.plan_hash = digest(run.plan)
        if plan.clarification:
            run.status = "needs_clarification"
        else:
            approval = AiActionApproval(user_id=user.id, agent_id=agent.id, module="PMS",
                action_type="EXECUTE_PMS_OPERATOR_PLAN", related_entity_type="operator_run", related_entity_id=str(run.id),
                proposed_action_json={"input": {"run_id": run.id, "plan_hash": run.plan_hash},
                    "preview": run.plan, "task_ids": run.selection}, status="pending", execution_status="pending",
                idempotency_key=f"operator:{run.id}:{run.plan_hash}")
            db.add(approval)
            db.flush()
            run.approval_id = approval.id
            run.status = "awaiting_approval"
        AiUsageService(db).record_event(user=user, agent_id=agent.id, module="PMS", event_type="operator_planned")
    except HTTPException as exc:
        run = db.query(OperatorRun).filter_by(id=run.id).populate_existing().with_for_update().one()
        if run.status != "cancelled":
            run.status = "failed"
            run.error_code = str(exc.detail)[:60] if isinstance(exc.detail, str) and str(exc.detail).startswith("PROVIDER_") else "PLAN_VALIDATION_FAILED"
    AiAuditService(db).log(user=user, agent_id=agent.id, module="PMS", action="operator.plan",
        input_json={"run_id": run.id, "task_count": len(run.selection), "input_mode": run.input_mode},
        output_json={"status": run.status, "plan_hash": run.plan_hash}, status="failed" if run.status == "failed" else "success")
    db.commit()
    return public_run(run)


@router.get("/runs")
def runs(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    project = get_project_for_action(db, project_id, user, "manage_tasks")
    scope = scope_key(db, user, project.workspace_id)
    return {"items": [public_run(r) for r in db.query(OperatorRun).filter_by(user_id=user.id, project_id=project_id, scope_key=scope).order_by(OperatorRun.id.desc()).limit(50).all()]}


@router.get("/runs/{run_id}")
def run_detail(run_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    return public_run(owned_run(db, user, run_id))


@router.post("/runs/{run_id}/approve")
def approve(run_id: int, payload: ApproveInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    row = owned_run(db, user, run_id)
    if payload.plan_hash != row.plan_hash or not row.approval_id:
        raise HTTPException(409, "Preview does not match this plan")
    # Existing approval executor owns locking, authorization and replay detection.
    AiApprovalExecutorService(db).execute_approved_action(user=user, approval_id=row.approval_id)
    db.commit()
    db.refresh(row)
    return public_run(row)


@router.post("/runs/{run_id}/cancel")
def cancel(run_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    row = owned_run(db, user, run_id)
    # Lock approval first, matching the executor's lock order.
    if row.approval_id:
        approval = db.query(AiActionApproval).filter_by(id=row.approval_id).with_for_update().first()
    else:
        approval = None
    row = owned_run(db, user, run_id, lock=True)
    if row.status in {"succeeded", "failed"}:
        raise HTTPException(409, "This run has already finished")
    row.status = "cancelled"
    if approval and approval.status == "pending":
        approval.status = "cancelled"
    if approval and approval.execution_status in {"queued", "executing", "paused"}:
        approval.execution_status = "cancelled"
    db.query(OperatorJob).filter_by(run_id=row.id).update({"status": "cancelled", "lease_token": None, "lease_until": None}, synchronize_session=False)
    from app.ai_operator.jobs import emit
    emit(db, row, "run.cancelled", partial=bool((row.result or {}).get("receipts")))
    AiAuditService(db).log(user=user, agent_id=None, module="PMS", action="operator.cancel",
        input_json={"run_id": row.id}, output_json={"status": row.status}, status="success")
    db.commit()
    return public_run(row)


@router.get("/analytics")
def analytics(workspace_id: int | None = None, days: int = Query(30, ge=1, le=365),
              db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_admin(user)
    scope = scope_key(db, user, workspace_id, manage=True)
    start = datetime.now(timezone.utc) - timedelta(days=days)
    base = db.query(OperatorApiLog).filter(OperatorApiLog.scope_key == scope, OperatorApiLog.created_at >= start)
    groups = db.query(OperatorApiLog.provider, OperatorApiLog.model, OperatorApiLog.status,
        func.count(OperatorApiLog.id).label("requests"), func.sum(OperatorApiLog.input_tokens).label("input_tokens"),
        func.sum(OperatorApiLog.output_tokens).label("output_tokens"), func.sum(OperatorApiLog.estimated_cost).label("estimated_cost"),
        func.count(OperatorApiLog.estimated_cost).label("priced_requests"), func.avg(OperatorApiLog.duration_ms).label("average_latency_ms")
        ).filter(OperatorApiLog.scope_key == scope, OperatorApiLog.created_at >= start).group_by(OperatorApiLog.provider, OperatorApiLog.model, OperatorApiLog.status).all()
    fields = ("id", "user_id", "run_id", "provider", "model", "purpose", "status", "error_code", "http_status",
              "provider_request_id", "input_tokens", "output_tokens", "estimated_cost", "duration_ms", "created_at")
    local_plans = db.query(func.count(OperatorEvent.id)).join(OperatorRun, OperatorRun.id == OperatorEvent.run_id).filter(
        OperatorRun.scope_key == scope, OperatorEvent.event_type == "plan.local", OperatorEvent.created_at >= start).scalar()
    return {"days": days, "local_plans": local_plans, "groups": [dict(g._mapping) for g in groups],
        "logs": [{f: getattr(r, f) for f in fields} for r in base.order_by(OperatorApiLog.id.desc()).limit(200).all()],
        "cost_note": "USD estimates use administrator-supplied rates per million tokens. Null means unknown; not a provider invoice. Logs exclude prompts, responses and credentials."}


@router.post("/runs/{run_id}/revise")
def revise(run_id: int, payload: RevisionInput, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    parent = owned_run(db, user, run_id)
    return command(CommandInput(project_id=parent.project_id, task_ids=parent.selection, command=payload.command,
        provider=parent.provider, request_key=payload.request_key, input_mode=payload.input_mode, background=True,
        execution_mode=parent.execution_mode, timezone=parent.timezone, parent_run_id=parent.id, parent_plan_hash=payload.plan_hash), request, db, user)


@router.post("/runs/{run_id}/resume")
def resume(run_id: int, payload: ResumeInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    row = owned_run(db, user, run_id)
    approval = db.query(AiActionApproval).filter_by(id=row.approval_id).with_for_update().first()
    row = owned_run(db, user, run_id, lock=True)
    if row.status != "paused" or not approval or approval.status != "approved" or row.plan_hash != payload.plan_hash:
        raise HTTPException(409, "Only an approved, unchanged paused run can resume")
    from app.ai_operator.jobs import authorize, check_snapshots, emit, now_utc
    authorize(db, user, row)
    check_snapshots(db, user, row)
    job = db.query(OperatorJob).filter_by(run_id=row.id, kind="execute").with_for_update().first()
    if not job or job.status != "failed":
        raise HTTPException(409, "Run has no failed execution job")
    job.status, job.failures, job.available_at = "queued", 0, now_utc()
    job.lease_token, job.lease_until, job.error_code = None, None, None
    row.status, row.error_code, approval.execution_status = "queued", None, "queued"
    emit(db, row, "run.resumed")
    db.commit()
    return public_run(row)


@router.get("/runs/{run_id}/steps")
def steps(run_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    owned_run(db, user, run_id)
    return {"items": [{"position": s.position, "depends_on": s.depends_on, "payload": s.payload,
                       "status": s.status, "receipt": s.receipt, "error_code": s.error_code}
                      for s in db.query(OperatorStep).filter_by(run_id=run_id).order_by(OperatorStep.position).all()]}


@router.get("/runs/{run_id}/events")
def events(run_id: int, after_id: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_ai_access(user)
    run = owned_run(db, user, run_id)
    rows = db.query(OperatorEvent).filter(OperatorEvent.run_id == run_id, OperatorEvent.id > after_id).order_by(OperatorEvent.id).limit(limit + 1).all()
    page = rows[:limit]
    return {"items": [{"id": e.id, "type": e.event_type, "payload": e.payload, "created_at": e.created_at} for e in page],
        "next_cursor": page[-1].id if page else after_id, "has_more": len(rows) > limit, "run": public_run(run)}
