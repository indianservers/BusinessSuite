"""Database queue with leases, fenced claims and transactionally committed checkpoints."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import or_, case
from fastapi import HTTPException
from app.models.user import User
from app.ai_agents.models import AiActionApproval
from app.ai_agents.services.audit import AiAuditService
from app.ai_operator.models import OperatorRun, OperatorJob, OperatorStep, OperatorEvent
from app.ai_operator.schemas import TaskPlan, PlanStep
from app.ai_operator.service import digest, task_snapshot, perform_step, scope_key, OperatorExecutor
from app.apps.project_management.access import get_project_for_action, get_task_project_for_action, has_any_permission, PMS_GLOBAL_MANAGE_TASKS
from app.apps.project_management.models import PMSTask


def now_utc():
    return datetime.now(timezone.utc)


def emit(db, run, kind, **payload):
    db.add(OperatorEvent(run_id=run.id, event_type=kind, payload={"status": run.status, "revision": run.revision, **payload}))


def enqueue(db, run, kind):
    key = f"operator:{run.id}:{kind}"
    job = db.query(OperatorJob).filter_by(dedupe_key=key).first()
    if job:
        return job
    job = OperatorJob(run_id=run.id, kind=kind, dedupe_key=key, status="queued", attempts=0, failures=0, available_at=now_utc())
    db.add(job)
    return job


def authorize(db, user, run):
    from app.access.service import check_background_access
    if user:
        check_background_access(db, user, "project_management", "edit")
        check_background_access(db, user, "ai", "create")
    from app.ai_agents.api import _require_ai_access
    from app.ai_operator.planner import planning_agent
    if not user or not user.is_active or run.user_id != user.id:
        raise HTTPException(403, "Initiator unavailable")
    _require_ai_access(user)
    project = get_project_for_action(db, run.project_id, user, "manage_tasks")
    if scope_key(db, user, project.workspace_id) != run.scope_key:
        raise HTTPException(403, "Run scope changed")
    if not has_any_permission(user, PMS_GLOBAL_MANAGE_TASKS):
        raise HTTPException(403, "Task management permission required")
    planning_agent(db, user)
    from app.ai_operator.workbench import check_standing_consent
    check_standing_consent(db,user,run)


def queue_approved_plan(db, user, approval):
    # The caller holds the approval lock; keep approval -> run -> job ordering.
    run_id = (approval.proposed_action_json or {}).get("input", {}).get("run_id")
    run = db.query(OperatorRun).filter_by(id=run_id, user_id=user.id).with_for_update().first()
    if not run:
        raise HTTPException(404, "Run not found")
    authorize(db, user, run)
    if run.status in {"cancelled", "superseded"}:
        raise HTTPException(409, "Plan is no longer active")
    if approval.execution_status == "executed":
        return approval
    if approval.status == "approved" and approval.execution_status in {"queued", "executing", "paused"}:
        return approval
    if approval.status != "pending" or run.status != "awaiting_approval" or run.approval_id != approval.id:
        raise HTTPException(409, "Plan is no longer pending")
    if (digest(run.plan) != run.plan_hash or digest(approval.proposed_action_json.get("preview")) != run.plan_hash
            or approval.proposed_action_json.get("execution_mode") != run.execution_mode):
        raise HTTPException(409, "Plan changed")
    approval.status, approval.execution_status = "approved", "queued"
    approval.approved_by, approval.approved_at = user.id, now_utc()
    run.status = "queued"
    for position, step in enumerate(TaskPlan.model_validate(run.plan).steps, 1):
        db.add(OperatorStep(run_id=run.id, position=position,
            depends_on=step.depends_on if step.depends_on is not None else list(range(1, position)),
            payload=step.model_dump(mode="json", exclude_none=True), status="pending"))
    enqueue(db, run, "execute")
    emit(db, run, "run.approved", mode=run.execution_mode)
    AiAuditService(db).log(user=user, agent_id=approval.agent_id, module="PMS", action="operator.queued",
        input_json={"run_id": run.id, "plan_hash": run.plan_hash}, output_json={"status": "queued"}, status="success")
    db.flush()
    return approval


def claim(db, *, now=None):
    now = now or now_utc()
    # CAS works on SQLite too; PostgreSQL avoids waiting on other workers.
    eligible = or_((OperatorJob.status == "queued") & (OperatorJob.available_at <= now),
                   (OperatorJob.status == "running") & (OperatorJob.lease_until < now))
    for _ in range(5):
        job_id = db.query(OperatorJob.id).filter(eligible).order_by(OperatorJob.available_at, OperatorJob.id).with_for_update(skip_locked=True).limit(1).scalar()
        if job_id is None:
            db.commit()
            return None
        token = uuid4().hex
        changed = db.query(OperatorJob).filter(OperatorJob.id == job_id, eligible).update({
            OperatorJob.failures: case((OperatorJob.status == "running", OperatorJob.failures + 1), else_=OperatorJob.failures),
            OperatorJob.status: "running", OperatorJob.lease_token: token, OperatorJob.lease_until: now + timedelta(seconds=120),
            OperatorJob.attempts: OperatorJob.attempts + 1}, synchronize_session=False)
        db.commit()
        if changed:
            return job_id, token
    return None


def lock_claim(db, job_id, token):
    # Read IDs without holding a job lock, then use the shared lock order.
    meta = db.query(OperatorJob.run_id).filter_by(id=job_id).scalar()
    approval_id = db.query(OperatorRun.approval_id).filter_by(id=meta).scalar()
    approval = db.query(AiActionApproval).filter_by(id=approval_id).populate_existing().with_for_update().first() if approval_id else None
    run = db.query(OperatorRun).filter_by(id=meta).populate_existing().with_for_update().first()
    job = db.query(OperatorJob).filter_by(id=job_id, lease_token=token, status="running").populate_existing().with_for_update().first()
    if not job or not run:
        return None, None, None
    expiry = job.lease_until.replace(tzinfo=timezone.utc) if job.lease_until.tzinfo is None else job.lease_until
    if expiry <= now_utc():
        return None, None, None
    return job, run, approval


def check_snapshots(db, user, run):
    tasks = db.query(PMSTask).filter(PMSTask.id.in_(run.selection)).order_by(PMSTask.id).populate_existing().with_for_update().all()
    if len(tasks) != len(run.selection):
        raise HTTPException(409, "STALE_PLAN")
    for task in tasks:
        get_task_project_for_action(db, task.id, user, "manage_tasks")
        if task.deleted_at or digest(task_snapshot(db, task)) != run.snapshots.get(str(task.id)):
            raise HTTPException(409, "STALE_PLAN")
    return tasks


def receipts_for(db, run):
    return [s.receipt for s in db.query(OperatorStep).filter_by(run_id=run.id, status="succeeded").order_by(OperatorStep.position).all()]


def finish(db, job, run, approval):
    run.status = "succeeded"
    run.result = {"success": True, "run_id": run.id, "receipts": receipts_for(db, run)}
    from app.ai_operator.workbench import remember_run_after
    remember_run_after(db, run)
    approval.execution_status, approval.executed_at = "executed", now_utc()
    approval.execution_result_json = {"success": True, "result": run.result}
    job.status, job.lease_token, job.lease_until = "completed", None, None
    emit(db, run, "run.succeeded", completed=len(run.result["receipts"]))
    user = db.get(User, run.user_id)
    AiAuditService(db).log(user=user, agent_id=approval.agent_id, module="PMS", action="operator.background.succeeded",
        input_json={"run_id": run.id, "plan_hash": run.plan_hash}, output_json={"completed_steps": len(run.result["receipts"])}, status="success")
    if run.execution_mode == "checkpointed":
        from app.ai_agents.services.advanced_security import AiUsageService
        AiUsageService(db).record_event(user=user, agent_id=approval.agent_id, module="PMS", event_type="operator_executed")


def execute_checkpoint(db, job, run, approval, user):
    if (not approval or approval.status != "approved" or approval.execution_status not in {"queued", "executing", "paused"}
        or digest(run.plan) != run.plan_hash or digest(approval.proposed_action_json.get("preview")) != run.plan_hash):
        raise HTTPException(409, "APPROVAL_CHANGED")
    authorize(db, user, run)
    tasks = check_snapshots(db, user, run)
    steps = db.query(OperatorStep).filter_by(run_id=run.id).order_by(OperatorStep.position).all()
    complete = {s.position for s in steps if s.status == "succeeded"}
    pending = next((s for s in steps if s.status != "succeeded" and set(s.depends_on) <= complete), None)
    if pending is None:
        if len(complete) != len(steps):
            raise HTTPException(409, "STEP_GRAPH_BLOCKED")
        finish(db, job, run, approval)
        return
    if pending.payload != TaskPlan.model_validate(run.plan).steps[pending.position - 1].model_dump(mode="json", exclude_none=True):
        raise HTTPException(409, "PLAN_CHANGED")
    receipt = perform_step(db, user, PlanStep.model_validate(pending.payload), pending.position)
    pending.status, pending.receipt, pending.error_code = "succeeded", receipt, None
    db.flush()
    run.snapshots = {str(t.id): digest(task_snapshot(db, t)) for t in tasks}
    run.status, run.error_code = "executing", None
    run.result = {"success": False, "partial": True, "receipts": receipts_for(db, run)}
    approval.execution_status = "executing"
    emit(db, run, "step.succeeded", step=pending.position, receipt=receipt)
    job.failures, job.error_code = 0, None
    job.status, job.lease_token, job.lease_until, job.available_at = "queued", None, None, now_utc()
    if len(complete) + 1 == len(steps):
        finish(db, job, run, approval)


def process_claim(db, job_id, token):
    savepoint = None
    try:
        job, run, approval = lock_claim(db, job_id, token)
        if not job:
            db.commit()
            return "lost_lease"
        if run.status in {"cancelled", "superseded", "succeeded"}:
            job.status, job.lease_token, job.lease_until = "completed", None, None
            db.commit()
            return "finished"
        if job.failures >= 3:
            raise HTTPException(409, "RETRY_LIMIT_REACHED")
        user = db.get(User, run.user_id)
        authorize(db, user, run)
        if job.kind == "plan":
            run.status = "planning"
            emit(db, run, "run.planning")
            db.commit()  # Release all locks before calling the model.
            from app.ai_operator.planner import generate_plan, publish_plan
            plan, snapshots = generate_plan(db, user, run)
            db.expire_all()  # Re-read permissions and cancellation after network I/O.
            job, run, _ = lock_claim(db, job_id, token)
            if not job:
                db.commit()  # Retain telemetry even when the lease was replaced.
                return "lost_lease"
            if run.status not in {"cancelled", "superseded"}:
                user = db.query(User).filter_by(id=run.user_id).populate_existing().one()
                authorize(db, user, run)
                savepoint = db.begin_nested()
                publish_plan(db, user, run, plan, snapshots)
                emit(db, run, "plan.ready", plan_hash=run.plan_hash)
            job.status, job.lease_token, job.lease_until = "completed", None, None
        elif run.execution_mode == "checkpointed":
            savepoint = db.begin_nested()
            execute_checkpoint(db, job, run, approval, user)
        else:
            savepoint = db.begin_nested()
            if not approval or approval.status != "approved":
                raise HTTPException(409, "APPROVAL_CHANGED")
            result = OperatorExecutor(db).execute_run(user, approval.proposed_action_json)
            if not result.get("success"):
                raise HTTPException(409, result.get("error_code", "EXECUTION_FAILED"))
            for step, receipt in zip(db.query(OperatorStep).filter_by(run_id=run.id).order_by(OperatorStep.position).all(), result["receipts"]):
                step.status, step.receipt = "succeeded", receipt
                emit(db, run, "step.succeeded", step=step.position, receipt=receipt)
            db.flush()
            finish(db, job, run, approval)
        if savepoint is not None:
            savepoint.commit()
        db.commit()
        return "processed"
    except Exception as exc:
        if savepoint is not None and savepoint.is_active:
            savepoint.rollback()
        if not db.is_active:
            db.rollback()
        job, run, approval = lock_claim(db, job_id, token)
        if not job:
            db.commit()
            return "lost_lease"
        if run.status in {"cancelled", "superseded"}:
            job.status = "completed"
        else:
            code = str(exc.detail) if isinstance(exc, HTTPException) and isinstance(exc.detail, str) else "OPERATOR_JOB_FAILED"
            code = code if code in {"STALE_PLAN", "APPROVAL_CHANGED", "PLAN_CHANGED", "STEP_GRAPH_BLOCKED", "RETRY_LIMIT_REACHED", "AUTO_POLICY_REVOKED"} or code.startswith("PROVIDER_") else "OPERATOR_JOB_FAILED"
            job.failures += 1
            permanent_provider_error = code in {"PROVIDER_HTTP_400", "PROVIDER_HTTP_401", "PROVIDER_HTTP_403", "PROVIDER_HTTP_404"}
            retry = job.failures < 3 and not permanent_provider_error and not (isinstance(exc, HTTPException) and exc.status_code in {400, 403, 404, 409, 422})
            job.status, job.error_code = ("queued" if retry else "failed"), code
            job.available_at = now_utc() + timedelta(seconds=5 * 2 ** job.failures)
            run.status = "retrying" if retry else "paused" if job.kind == "execute" else "failed"
            run.error_code = code
            run.result = {"success": False, "partial": bool(receipts_for(db, run)), "receipts": receipts_for(db, run), "message": "Review progress before resuming or revising."}
            if approval and job.kind == "execute":
                approval.execution_status = "paused" if not retry else "queued"
                failed_step = db.query(OperatorStep).filter(OperatorStep.run_id == run.id, OperatorStep.status != "succeeded").order_by(OperatorStep.position).first()
                if failed_step:
                    failed_step.status, failed_step.error_code = "failed", code
            emit(db, run, "run.retrying" if retry else "run.paused", error_code=code)
            AiAuditService(db).log(user=db.get(User, run.user_id), agent_id=approval.agent_id if approval else None,
                module="PMS", action="operator.background.retry" if retry else "operator.background.paused",
                input_json={"run_id": run.id, "job_id": job.id}, output_json={"error_code": code, "status": run.status}, status="failed")
        job.lease_token, job.lease_until = None, None
        db.commit()
        return "retry" if job.status == "queued" else "paused"


def process_batch(db, *, limit=20, time_budget=50):
    import time
    start, counts = time.monotonic(), {}
    for _ in range(min(limit, 100)):
        if time.monotonic() - start >= time_budget:
            break
        claimed = claim(db)
        if not claimed:
            break
        result = process_claim(db, *claimed)
        counts[result] = counts.get(result, 0) + 1
    from app.ai_operator.extensions import check_monitors
    monitors = check_monitors(db, limit=min(limit, 20))
    if monitors["checked"]:
        counts["monitors"] = monitors
    from app.ai_operator.workbench import tick_rules
    rules = tick_rules(db, limit=min(limit, 10))
    if rules['checked']:
        counts['assistant_rules'] = rules
    return counts
