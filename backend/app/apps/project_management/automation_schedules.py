"""Bounded PMS clock adapter: existing rules, actions, cron ledger and access scopes.

Rule locks serialize durable per-task receipts. The action, receipt and scan cursor
commit together; retries and overlapping cron calls cannot apply a period twice.
"""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from app.models.deployment import ScheduledJobRun
from app.models.user import User
from app.branches.models import BranchOwnership
from app.access.service import background_scope, activate_run_context, release_run_context
from .models import PMSWorkspaceEntry, PMSProject, PMSTask
from .automations import RuleInput, _manage, _matches, _apply_rule
from .access import can_access_project


def _run_rule(db, rule_id, now, task_limit, expected_project=None):
    row = db.get(PMSWorkspaceEntry, rule_id)
    raw = json.loads(row.body)
    if expected_project is not None and raw.get("project_id") != expected_project:
        return 0
    if not raw.get("enabled") or raw.get("trigger") not in {"schedule.daily", "task.due_date"}:
        return 0
    project = db.get(PMSProject, raw["project_id"])
    if not project or project.deleted_at or project.is_archived or project.workspace_id != row.workspace_id:
        return 0
    # Resolve authorization only after lock waits, so revocations during a wait
    # cannot survive in either the actor or the effective module/branch policy.
    project = db.query(PMSProject).filter_by(id=project.id).with_for_update().populate_existing().one()
    row = db.query(PMSWorkspaceEntry).filter_by(id=rule_id, kind="auto_rule").with_for_update().populate_existing().one()
    # Discover the persisted branch, then execute with the author's current rights.
    owner = db.query(BranchOwnership).filter_by(resource_table="pms_projects", resource_key=str(project.id), company_id=project.organization_id).first()
    if not owner:
        raise HTTPException(409, "Scheduled project branch cannot be verified")
    actor = db.query(User).filter_by(id=row.author_id).populate_existing().first()
    if not actor or not actor.is_active:
        raise HTTPException(403, "Rule author is inactive")
    activate_run_context(db, actor, SimpleNamespace(scope_key=f"company:{project.organization_id}"))
    try:
        with background_scope(db, actor, "project_management", "edit", branch_id=owner.branch_id):
            raw = json.loads(row.body)
            rule = RuleInput.model_validate({k: v for k, v in raw.items() if not k.startswith("_")})
            if not rule.enabled or rule.trigger not in {"schedule.daily", "task.due_date"}:
                return 0
            if rule.project_id != project.id or row.workspace_id != project.workspace_id or project.deleted_at or project.is_archived:
                return 0
            _manage(db, row.workspace_id, actor)
            if not can_access_project(db, project, actor, "manage_tasks"):
                raise HTTPException(403, "Rule author no longer manages project tasks")
            local = now.astimezone(ZoneInfo(rule.schedule.timezone))
            if local.strftime("%H:%M") < rule.schedule.at:
                return 0
            today = local.date()
            tasks = db.query(PMSTask).filter(PMSTask.project_id == project.id,
                PMSTask.deleted_at.is_(None), PMSTask.id > int(raw.get("_cursor", 0)))
            tasks = tasks.order_by(PMSTask.id).with_for_update().populate_existing().limit(task_limit).all()
            processed = 0
            for task in tasks:
                if task.status in {"Done", "Cancelled", "Closed"} or not _matches(raw, task):
                    continue
                if rule.trigger == "task.due_date":
                    if not task.due_date or task.due_date + timedelta(days=rule.schedule.due_offset_days) > today:
                        continue
                    period = task.due_date.isoformat()
                else:
                    period = today.isoformat()
                kind = f"ar{row.id:x}"
                receipt = db.query(PMSWorkspaceEntry).filter_by(workspace_id=row.workspace_id, kind=kind, task_id=task.id).first()
                if receipt:
                    saved = json.loads(receipt.body)
                    same_period = saved.get("period") == period if rule.trigger == "task.due_date" else saved.get("period", "") >= period
                    if same_period and saved.get("revision", 1) == raw.get("_revision", 1):
                        continue
                if _apply_rule(db, row, raw, task, project, actor):
                    marker = json.dumps({"period": period, "revision": raw.get("_revision", 1)})
                    if receipt:
                        receipt.body = marker
                    else:
                        db.add(PMSWorkspaceEntry(workspace_id=row.workspace_id, task_id=task.id,
                            author_id=actor.id, kind=kind, body=marker))
                    processed += 1
            raw["_cursor"] = tasks[-1].id if len(tasks) == task_limit else 0
            row.body = json.dumps(raw)
            db.flush()
            return processed
    finally:
        release_run_context(db)


def dispatch_due(db, *, now=None, rule_limit=25, task_limit=50):
    """Called only by authenticated cron; no caller-supplied clock or company."""
    now = now or datetime.now(timezone.utc)
    if now.utcoffset() is None:
        raise ValueError("Scheduler clock must include a timezone")
    rule_limit, task_limit = max(1, min(rule_limit, 100)), max(1, min(task_limit, 100))
    # Reuse the scheduler's unique ledger and a locked cursor for fair rule scans.
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    if not db.query(ScheduledJobRun.id).filter_by(job_name="pms_automation", period="dispatch").first():
        db.execute(insert(ScheduledJobRun).values(job_name="pms_automation", period="dispatch", status="pending",
            cursor=0, attempts=0, updated_at=now).on_conflict_do_nothing(index_elements=["job_name", "period"]))
    ledger = db.query(ScheduledJobRun).filter_by(job_name="pms_automation", period="dispatch").with_for_update(skip_locked=True).first()
    if not ledger:
        db.rollback()
        return {"processed": 0, "failed_rule_ids": [], "scanned": 0, "status": "already_running"}
    ids = list(db.scalars(select(PMSWorkspaceEntry.id).where(PMSWorkspaceEntry.kind == "auto_rule",
        PMSWorkspaceEntry.id > ledger.cursor).order_by(PMSWorkspaceEntry.id).limit(rule_limit)))
    processed, failures = 0, []
    ordered = []
    for rule_id in ids:
        try:
            ordered.append((int(json.loads(db.get(PMSWorkspaceEntry, rule_id).body)["project_id"]), rule_id))
        except (ValueError, TypeError, KeyError):
            failures.append(rule_id)
    for project_id, rule_id in sorted(ordered):
        try:
            with db.begin_nested():
                db.expire_all()
                processed += _run_rule(db, rule_id, now, task_limit, expected_project=project_id)
        except Exception:
            # A failed rule rolls back its action and receipt, not other rules.
            failures.append(rule_id)
    ledger.cursor = ids[-1] if len(ids) == rule_limit else 0
    ledger.updated_at = now
    ledger.attempts += 1
    ledger.result = {"processed": processed, "failed_rule_ids": failures, "scanned": len(ids)}
    db.commit()
    return ledger.result
