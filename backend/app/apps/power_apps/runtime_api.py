"""Runtime API: all user controls share suite authentication, RBAC and scoped resources."""

import copy
import hashlib
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, case, select
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.apps.power_apps.router import find_draft
from app.apps.power_apps.models import (
    PowerResource,
    PowerVersion,
    PowerExecution,
    PowerEnvironment,
)
from app.apps.power_apps.runtime_models import (
    AutomationDeployment as Deployment,
    AutomationRun as Run,
    AutomationStep as Step,
    AutomationJob as Job,
    AutomationWait as Wait,
    AutomationTrigger as Trigger,
    AutomationEvent as Event,
    AutomationDeadLetter as DeadLetter,
    AutomationWorker as Worker,
)
from app.apps.power_apps.runtime_contracts import (
    LifecycleRequest,
    RunRequest,
    TriggerRequest,
    ResumeRequest,
)
from app.apps.power_apps.service import scoped, validate_environment, serialize
from app.apps.power_apps.runtime import (
    lifecycle,
    deployment,
    enqueue,
    now,
    utc,
    scope_values,
    finish,
    authority,
    advance,
    TERMINAL,
)
from app.apps.power_apps.authoring import redact_debug
from app.apps.power_apps.runtime_executors import capabilities, EXECUTORS
from app.apps.power_apps.runtime_triggers import configure, webhook
from app.ai_operator.providers import cipher
from app.core.middleware.audit import client_addresses

router = APIRouter(prefix="/power-apps", tags=["Automation Runtime"])
view = RequirePermission("power_apps_view")


def export_allowed(db, user):
    if user.is_superuser:
        return True
    from app.access.service import legacy_grants

    grant = (getattr(user, "_suite_grants", None) or {}).get("power_apps")
    if grant is None:
        grant = legacy_grants(db, user, user.organization_id).get("power_apps", {})
    return "export" in grant.get("actions", [])


def visible(db, user, environment, run_id, approval_participant_read=False):
    validate_environment(db, user, environment)
    root = scoped(db, PowerExecution, user, environment).filter_by(id=run_id).first()
    if not root and approval_participant_read:
        from app.apps.power_apps.approvals.service import visible_ids
        from app.apps.power_apps.approvals.models import RequestState
        linked=db.query(RequestState.run_id).filter(RequestState.organization_id==user.organization_id,RequestState.environment==environment,RequestState.id.in_(visible_ids(db,user,environment)))
        root=db.query(PowerExecution).filter(PowerExecution.id==run_id,PowerExecution.organization_id==user.organization_id,PowerExecution.environment==environment,PowerExecution.id.in_(linked)).first()
    if not root:
        raise HTTPException(404, "Execution not found")
    run = (
        db.query(Run)
        .filter_by(
            id=root.id, organization_id=root.organization_id, environment=environment
        )
        .first()
    )
    if not run:
        raise HTTPException(404, "Runtime history unavailable")
    return root, run


@router.get("/automations/runtime/capabilities")
def runtime_capabilities(user=Depends(view)):
    return {
        "executors": capabilities(),
        "queue": "postgresql",
        "external_actions": False,
        "internal_event_providers": [],
        "loop_limits": {"items": 1000, "steps": 5000, "depth": 2},
    }


@router.get("/automations/{resource_id}/runtime")
def get_deployment(
    resource_id: int,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(view),
):
    row = find_draft(db, user, environment, resource_id)
    state = (
        db.query(Deployment)
        .filter_by(
            resource_id=row.id,
            organization_id=row.organization_id,
            environment=environment,
        )
        .first()
    )
    return (
        serialize(state)
        if state
        else {
            "status": "draft",
            "validated_version": None,
            "version_id": None,
            "policy": {},
            "revision": 0,
        }
    )


@router.post("/automations/{resource_id}/runtime/{action}")
def transition(
    resource_id: int,
    action: str,
    data: LifecycleRequest,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_publish")),
):
    RequirePermission("power_apps_view")(user)
    row = find_draft(db, user, environment, resource_id)
    result = lifecycle(
        db,
        row,
        user,
        action,
        data.expected_version,
        data.policy.model_dump() if action == "publish" else None,
    )
    db.commit()
    return serialize(result)


@router.post("/automations/{resource_id}/publish")
def publish(
    resource_id: int,
    data: LifecycleRequest,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_publish")),
):
    return transition(resource_id, "publish", data, environment, db, user)


@router.post("/automations/{resource_id}/execute", status_code=202)
def execute(
    resource_id: int,
    data: RunRequest,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_execute")),
):
    RequirePermission("power_apps_view")(user)
    row = find_draft(db, user, environment, resource_id)
    root = enqueue(db, row, user, data.input, data.idempotency_key)
    db.commit()
    return {
        "id": root.id,
        "status": root.status,
        "workflow_version": root.workflow_version,
    }


@router.get("/automations/{resource_id}/triggers")
def triggers(
    resource_id: int,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(view),
):
    row = find_draft(db, user, environment, resource_id)
    items = (
        db.query(Trigger)
        .filter_by(
            resource_id=row.id,
            organization_id=row.organization_id,
            environment=environment,
        )
        .all()
    )
    return {
        "items": [
            {k: v for k, v in serialize(t).items() if k != "encrypted_secret"}
            for t in items
        ]
    }


@router.put("/automations/{resource_id}/triggers/{kind}")
def configure_trigger(
    resource_id: int,
    kind: str,
    data: TriggerRequest,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_publish")),
):
    RequirePermission("power_apps_view")(user)
    row = find_draft(db, user, environment, resource_id)
    db.query(PowerResource).filter_by(id=row.id).with_for_update().one()
    trigger, secret = configure(db, row, user, kind, data.enabled, data.config)
    db.commit()
    return {
        "id": trigger.id,
        "enabled": trigger.enabled,
        "endpoint": (
            f"/api/v1/power-apps/hooks/{trigger.endpoint}"
            if kind == "webhook"
            else None
        ),
        "secret": secret,
        "secret_version": trigger.secret_version,
        "next_at": trigger.next_at,
    }


@router.post("/automations/{resource_id}/triggers/webhook/rotate")
def rotate(
    resource_id: int,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_publish")),
):
    RequirePermission("power_apps_view")(user)
    row = find_draft(db, user, environment, resource_id)
    if user.id != row.owner_user_id:
        raise HTTPException(403, "Only the delegated owner may rotate webhook secrets")
    db.query(PowerResource).filter_by(id=row.id).with_for_update().one()
    trigger = (
        db.query(Trigger)
        .filter_by(
            resource_id=row.id, kind="webhook", organization_id=row.organization_id
        )
        .with_for_update()
        .first()
    )
    if not trigger:
        raise HTTPException(404, "Webhook not configured")
    secret = secrets.token_urlsafe(32)
    trigger.encrypted_secret = cipher().encrypt(secret.encode()).decode()
    trigger.secret_version += 1
    db.add(
        Event(
            **scope_values(row),
            resource_id=row.id,
            kind="webhook_secret_rotated",
            details={
                "actor_user_id": user.id,
                "secret_version": trigger.secret_version,
            },
        )
    )
    db.commit()
    return {"secret": secret, "secret_version": trigger.secret_version}


@router.post("/hooks/{endpoint}", status_code=202)
async def ingress(endpoint: str, request: Request, db: Session = Depends(get_db)):
    # Streaming bound prevents allocating an unbounded request body before checking.
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 32768:
            raise HTTPException(413, "Webhook payload exceeds 32 KB")
    root = webhook(
        db,
        endpoint,
        bytes(body),
        request.headers.get("x-power-timestamp", ""),
        request.headers.get("x-power-nonce", ""),
        request.headers.get("x-power-signature", ""),
        client_addresses(request)[0] or "",
    )
    request.state.observed_company_id = root.organization_id
    db.commit()
    return {"id": root.id, "status": root.status}


@router.get("/executions")
def executions(
    environment: str = "development",
    workflow: int | None = None,
    status: str | None = Query(None, max_length=30, pattern=r"^[a-z_]+$"),
    identity: int | None = None,
    initiator: int | None = None,
    error_type: str | None = Query(None, max_length=100, pattern=r"^[A-Za-z0-9_.]+$"),
    start: datetime | None = None,
    end: datetime | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(view),
):
    validate_environment(db, user, environment)
    query = scoped(db, PowerExecution, user, environment).join(
        Run, Run.id == PowerExecution.id
    )
    if workflow:
        query = query.filter(PowerExecution.resource_id == workflow)
    if status:
        query = query.filter(PowerExecution.status == status)
    if identity:
        query = query.filter(Run.effective_user_id == identity)
    if initiator:
        query = query.filter(PowerExecution.actor_user_id == initiator)
    if error_type:
        query = query.filter(Run.error_type == error_type)
    if start:
        query = query.filter(PowerExecution.created_at >= start)
    if end:
        query = query.filter(PowerExecution.created_at <= end)
    counts = {
        key: query.filter(PowerExecution.status == key).count()
        for key in [
            "queued",
            "running",
            "waiting",
            "retry_scheduled",
            "completed",
            "failed",
            "cancelled",
        ]
    }
    total = query.count()
    duration = func.extract("epoch", Run.finished_at) - func.extract(
        "epoch", Run.started_at
    )
    average = (
        query.with_entities(func.avg(duration))
        .filter(Run.finished_at.is_not(None), Run.started_at.is_not(None))
        .scalar()
    )
    queue = (
        scoped(db, Job, user, environment)
        .filter(Job.status.in_({"queued", "running"}))
        .count()
    )
    items = []
    for root in query.order_by(PowerExecution.id.desc()).offset(offset).limit(limit):
        run = db.get(Run, root.id)
        items.append(
            {
                **serialize(root),
                "correlation_id": run.correlation_id,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "effective_user_id": run.effective_user_id,
                "error_type": run.error_type,
            }
        )
    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "metrics": {
            "total": total,
            **counts,
            "average_duration_seconds": average,
            "failure_rate": counts["failed"] / total if total else 0,
            "queue_depth": queue,
        },
    }


@router.get("/executions/{run_id}")
def history(
    run_id: int,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(view),
):
    root, run = visible(db, user, environment, run_id,approval_participant_read=True)
    version = (
        db.query(PowerVersion)
        .filter_by(
            id=run.version_id,
            organization_id=root.organization_id,
            resource_id=root.resource_id,
        )
        .one()
    )
    steps = (
        db.query(Step)
        .filter_by(
            run_id=root.id,
            organization_id=root.organization_id,
            environment=environment,
        )
        .order_by(Step.id)
        .all()
    )
    events = (
        db.query(Event)
        .filter_by(
            run_id=root.id,
            organization_id=root.organization_id,
            environment=environment,
        )
        .order_by(Event.id)
        .limit(2000)
        .all()
    )
    jobs = (
        db.query(Job)
        .filter_by(
            run_id=root.id,
            organization_id=root.organization_id,
            environment=environment,
        )
        .all()
    )
    return redact_debug(
        {
            "execution": {
                **serialize(root),
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "effective_user_id": run.effective_user_id,
                "correlation_id": run.correlation_id,
            },
            "run": {k: v for k, v in serialize(run).items() if k != "plan"},
            "definition": version.snapshot["definition"],
            "steps": [serialize(s) for s in steps],
            "events": [serialize(e) for e in events],
            "jobs": [
                {k: v for k, v in serialize(j).items() if k not in {"lease_token"}}
                for j in jobs
            ],
            "history_immutable": True,
            "can_export": export_allowed(db, user),
        }
    )


@router.post("/executions/{run_id}/cancel")
def cancel(
    run_id: int,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_execute")),
):
    RequirePermission("power_apps_view")(user)
    root, run = visible(db, user, environment, run_id)
    from app.apps.power_apps.runtime import quota_lock

    quota_lock(db, root.organization_id, environment)
    root = (
        db.query(PowerExecution)
        .filter_by(id=root.id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    if root.status in TERMINAL:
        raise HTTPException(409, "Execution already finished")
    finish(db, run, "cancelled")
    db.add(
        Event(
            **scope_values(run),
            run_id=run.id,
            resource_id=root.resource_id,
            kind="cancel_requested",
            details={"actor_user_id": user.id},
        )
    )
    db.commit()
    return {"status": "cancelled"}


@router.post("/executions/{run_id}/retry")
def retry(
    run_id: int,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_execute")),
):
    RequirePermission("power_apps_view")(user)
    root, run = visible(db, user, environment, run_id)
    from app.apps.power_apps.approvals.models import RequestState
    if db.query(RequestState).filter_by(run_id=run_id).first():raise HTTPException(409,'Approval failures require administrative resolution and a new request, not a generic retry')
    from app.apps.power_apps.runtime import quota_lock

    quota_lock(db, root.organization_id, environment)
    root = (
        db.query(PowerExecution)
        .filter_by(id=root.id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    if root.status != "failed":
        raise HTTPException(409, "Only failed executions can be retried")
    authority(
        db, run.effective_user_id, run.organization_id, environment, run.owner_user_id
    )
    failed = db.query(Step).filter_by(run_id=root.id, status="failed").all()
    if not failed or any(s.output is not None for s in failed):
        raise HTTPException(
            409,
            "This failure requires reconciliation; cannot retry after downstream routing",
        )
    if utc(run.deadline) <= now() or run.payloads_purged_at:
        raise HTTPException(
            409,
            "Workflow deadline expired or payloads were purged; explicitly re-run instead",
        )
    nodes = {n["id"]: n for n in run.plan["nodes"]}
    if any(
        nodes[s.node_id]["type"] not in EXECUTORS
        or EXECUTORS[nodes[s.node_id]["type"]].idempotency != "transactional"
        for s in failed
    ):
        raise HTTPException(409, "Executor is not safe to retry")
    from app.apps.power_apps.runtime import new_job

    for step in failed:
        if step.attempt >= 10:
            raise HTTPException(409, "Manual retry safety limit reached")
        new_job(db, run, step)
    db.query(Step).filter_by(run_id=root.id, status="cancelled").update(
        {"status": "pending", "finished_at": None}, synchronize_session="fetch"
    )
    db.query(DeadLetter).filter_by(run_id=root.id, resolved_at=None).update(
        {"resolved_at": now()}, synchronize_session="fetch"
    )
    # Preserve an already persisted wait when retrying a failed sibling branch.
    for wait in db.query(Wait).filter_by(run_id=root.id, status="cancelled").all():
        step = db.get(Step, wait.step_id)
        if step.status == "pending":
            wait.status = "waiting"
            step.status = "waiting"
    root.status = "queued"
    run.finished_at = None
    run.error = None
    run.error_type = None
    if utc(run.deadline) <= now():
        raise HTTPException(409, "Workflow deadline expired; explicitly re-run instead")
    db.add(
        Event(
            **scope_values(run),
            run_id=run.id,
            resource_id=root.resource_id,
            kind="manual_retry",
            details={"actor_user_id": user.id},
        )
    )
    db.commit()
    return {"status": "queued"}


@router.post("/executions/{run_id}/rerun", status_code=202)
def rerun(
    run_id: int,
    data: RunRequest,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_execute")),
):
    RequirePermission("power_apps_view")(user)
    root, run = visible(db, user, environment, run_id)
    if not data.confirm:
        raise HTTPException(
            422,
            "Explicit re-run confirmation is required; the current active publication will be used",
        )
    row = find_draft(db, user, environment, root.resource_id)
    new = enqueue(db, row, user, data.input, data.idempotency_key)
    db.commit()
    return {
        "id": new.id,
        "status": new.status,
        "workflow_version": new.workflow_version,
    }


@router.get("/runtime/health")
def health(
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_manage_environment")),
):
    RequirePermission("power_apps_view")(user)
    validate_environment(db, user, environment)
    # Aggregate system-owned liveness only; ordinary ORM reads of this internal table stay denied.
    workers = (
        db.connection()
        .execute(
            select(
                Worker.__table__.c.status,
                Worker.__table__.c.heartbeat_at,
                Worker.__table__.c.scheduler_at,
            )
        )
        .all()
    )
    dead = (
        scoped(db, DeadLetter, user, environment)
        .filter_by(resolved_at=None)
        .order_by(DeadLetter.id.desc())
        .limit(100)
        .all()
    )
    queues = scoped(db, Job, user, environment)
    oldest = (
        queues.filter_by(status="queued")
        .with_entities(func.min(Job.available_at))
        .scalar()
    )
    return {
        "workers_alive": sum(
            w.status == "running"
            and utc(w.heartbeat_at) > now() - timedelta(seconds=60)
            for w in workers
        ),
        "scheduler_last_at": max(
            (utc(w.scheduler_at) for w in workers if w.scheduler_at), default=None
        ),
        "queue_depth": queues.filter_by(status="queued").count(),
        "leased": queues.filter_by(status="running").count(),
        "oldest_due_seconds": (
            max(0, (now() - utc(oldest)).total_seconds()) if oldest else 0
        ),
        "dead_letters": [serialize(d) for d in dead],
    }


@router.post("/executions/{run_id}/resume")
def resume(
    run_id: int,
    data: ResumeRequest,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_execute")),
):
    RequirePermission("power_apps_view")(user)
    root, run = visible(db, user, environment, run_id)
    from app.apps.power_apps.runtime import quota_lock

    quota_lock(db, root.organization_id, environment)
    root = (
        db.query(PowerExecution)
        .filter_by(id=root.id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    if root.status in TERMINAL:
        raise HTTPException(409, "Execution has already finished")
    matches = (
        db.query(Wait)
        .filter_by(run_id=root.id, status="waiting", event_key=data.event_key)
        .filter(Wait.kind != "approval")
        .with_for_update()
        .all()
    )
    if not matches:
        raise HTTPException(404, "Authorized wait condition not found")
    for wait in matches:
        if utc(wait.wake_at) <= now():
            raise HTTPException(409, "Wait condition has expired")
        wait.event_key = None
        wait.wake_at = now()
    db.add(
        Event(
            **scope_values(run),
            run_id=run.id,
            resource_id=root.resource_id,
            kind="authorized_resume_requested",
            details={"actor_user_id": user.id, "wait_count": len(matches)},
        )
    )
    db.commit()
    return {"status": "resume_scheduled"}


@router.put("/automations/{resource_id}/runtime-limits")
def configure_limits(
    resource_id: int,
    data: LifecycleRequest,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_manage_environment")),
):
    RequirePermission("power_apps_view")(user)
    row = find_draft(db, user, environment, resource_id)
    row = (
        db.query(PowerResource)
        .filter_by(id=row.id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    if row.version != data.expected_version:
        raise HTTPException(409, "Draft changed; reload limits")
    state = deployment(db, row, True)
    # Runtime administration may adjust capacity, never switch an execution identity.
    policy = dict(state.policy)
    policy.update(
        {
            key: getattr(data.policy, key)
            for key in ["concurrency", "overflow", "max_queued"]
        }
    )
    state.policy = policy
    state.revision += 1
    db.add(
        Event(
            **scope_values(row),
            resource_id=row.id,
            kind="runtime_limits_changed",
            details={
                "actor_user_id": user.id,
                "concurrency": policy["concurrency"],
                "overflow": policy["overflow"],
                "max_queued": policy["max_queued"],
            },
        )
    )
    db.commit()
    return serialize(state)


@router.get("/executions/{run_id}/export")
def export_report(
    run_id: int,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(view),
):
    if not export_allowed(db, user):
        raise HTTPException(
            403, "Current module policy does not permit execution exports"
        )
    return history(run_id, environment, db, user)
