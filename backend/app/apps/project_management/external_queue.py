"""PMS external actions: transactional enqueue, bounded retry and ambiguous-outcome hold."""
import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.apps.automation.models import AutomationScheduledJob as Job
from app.shared import integrations
from .models import PMSWorkspaceEntry, PMSProject, PMSTask

router = APIRouter()

class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(max_length=500)
    secret: str = Field(min_length=24, max_length=120)
    receiver_deduplicates_delivery_id: bool


def connection(db, workspace_id, identity):
    row = db.query(PMSWorkspaceEntry).filter_by(id=identity, workspace_id=workspace_id, kind="ext_hook").first()
    if not row: raise HTTPException(422, "Choose a workspace webhook connection")
    return row, json.loads(row.body)


@router.get("/workspaces/{workspace_id}/external-connections")
def connections(workspace_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    from .automations import _manage
    _manage(db, workspace_id, user)
    return [{"id": r.id, "name": json.loads(r.body)["name"], "url": json.loads(r.body)["url"], "enabled": json.loads(r.body).get("enabled", True)} for r in db.query(PMSWorkspaceEntry).filter_by(workspace_id=workspace_id, kind="ext_hook").all()]


@router.post("/workspaces/{workspace_id}/external-connections", status_code=201)
def create_connection(workspace_id: int, data: ConnectionInput, db=Depends(get_db), user=Depends(get_current_user)):
    from .automations import _manage
    _manage(db, workspace_id, user)
    if not data.receiver_deduplicates_delivery_id: raise HTTPException(422, "Receiver must deduplicate the stable delivery_id before retries can be enabled")
    if not data.name.strip(): raise HTTPException(422, "Enter a connection name")
    integrations.destination(data.url)
    if db.query(PMSWorkspaceEntry).filter_by(workspace_id=workspace_id, kind="ext_hook").count() >= 25: raise HTTPException(422, "Connection limit reached")
    row = PMSWorkspaceEntry(workspace_id=workspace_id, author_id=user.id, kind="ext_hook", body=json.dumps({"name": data.name.strip(), "url": data.url, "secret": integrations.protect(data.secret), "enabled": True}))
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "name": data.name.strip(), "url": data.url, "enabled": True}


@router.post("/workspaces/{workspace_id}/external-connections/{identity}/disable")
def disable_connection(workspace_id: int, identity: int, db=Depends(get_db), user=Depends(get_current_user)):
    from .automations import _manage
    _manage(db, workspace_id, user); row, raw = connection(db, workspace_id, identity)
    raw["enabled"] = False; row.body = json.dumps(raw); db.commit()
    return {"enabled": False}


def enqueue(db, rule_row, rule, task, project):
    _, config = connection(db, project.workspace_id, rule.get("connection_id"))
    if not config.get("enabled", True): return False
    delivery_id = str(uuid.uuid4())
    db.add(Job(organization_id=project.organization_id, module_name="project_management", job_type="pms_external", record_type="task", record_id=task.id, created_by=rule_row.author_id, status="scheduled", attempts=0, run_at=datetime.now(timezone.utc), payload_json={"delivery_id": delivery_id, "workspace_id": project.workspace_id, "project_id": project.id, "connection_id": rule["connection_id"], "rule_id": rule_row.id,
        "event": {"delivery_id": delivery_id, "event": rule["trigger"], "task": {"id": task.id, "key": task.task_key, "status": task.status, "priority": task.priority}, "project_id": project.id}}))
    return True


def _query(db, workspace_id):
    # IDs are restricted through visible projects as well as workspace management.
    return db.query(Job).filter(Job.job_type == "pms_external", Job.module_name == "project_management", Job.record_id.in_(db.query(PMSTask.id).join(PMSProject).filter(PMSProject.workspace_id == workspace_id)))


@router.get("/workspaces/{workspace_id}/external-deliveries")
def deliveries(workspace_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    from .automations import _manage
    from .access import accessible_project_query
    _manage(db, workspace_id, user)
    projects = accessible_project_query(db, user).with_entities(PMSProject.id)
    return [{"id": j.id, "status": j.status, "attempts": j.attempts, "next_attempt": j.run_at, "error": j.last_error, "delivery_id": j.payload_json["delivery_id"]} for j in _query(db, workspace_id).filter(Job.record_id.in_(db.query(PMSTask.id).filter(PMSTask.project_id.in_(projects)))).order_by(Job.id.desc()).limit(100)]


@router.post("/workspaces/{workspace_id}/external-deliveries/{identity}/{action}")
def control(workspace_id: int, identity: int, action: str, db=Depends(get_db), user=Depends(get_current_user)):
    from .automations import _manage
    from .access import get_project_for_action
    _manage(db, workspace_id, user)
    job = _query(db, workspace_id).filter(Job.id == identity).with_for_update().first()
    if not job: raise HTTPException(404, "Delivery not found")
    get_project_for_action(db, job.payload_json["project_id"], user, "manage_tasks")
    if action == "cancel" and job.status in {"scheduled", "dead_letter"}: job.status = "cancelled"
    elif action == "retry" and job.status == "dead_letter":
        job.status = "scheduled"; job.attempts = 0; job.run_at = datetime.now(timezone.utc)
    else: raise HTTPException(409, "Only confirmed failures can be retried; ambiguous outcomes require reconciliation")
    db.commit(); return {"status": job.status}


def dispatch(db, now=None, limit=10):
    from app.access.service import activate_run_context, release_run_context, background_scope
    from app.branches.models import BranchOwnership
    from .access import get_project_for_action
    from .automations import _manage
    now = now or datetime.now(timezone.utc); count = 0
    for _ in range(min(limit, 25)):
        job = db.query(Job).filter(Job.job_type == "pms_external", Job.status == "scheduled", Job.run_at <= now).order_by(Job.run_at, Job.id).with_for_update(skip_locked=True).first()
        if not job: break
        raw = job.payload_json
        try:
            actor = db.query(User).filter_by(id=job.created_by).populate_existing().first()
            if not actor or not actor.is_active: raise HTTPException(403, "Delivery owner is unavailable")
            branch = db.query(BranchOwnership).filter_by(resource_table="pms_projects", resource_key=str(raw["project_id"]), company_id=job.organization_id).first()
            if not branch: raise HTTPException(403, "Delivery project scope cannot be verified")
            activate_run_context(db, actor, SimpleNamespace(scope_key=f"company:{job.organization_id}"))
            with background_scope(db, actor, "project_management", "edit", branch_id=branch.branch_id):
                project = get_project_for_action(db, raw["project_id"], actor, "manage_tasks")
                _manage(db, raw["workspace_id"], actor)
                task = db.get(PMSTask, job.record_id)
                rule = db.query(PMSWorkspaceEntry).filter_by(id=raw["rule_id"], kind="auto_rule", workspace_id=raw["workspace_id"]).first()
                if not task or task.deleted_at or task.project_id != project.id or project.is_archived or not rule or not json.loads(rule.body).get("enabled"):
                    raise HTTPException(403, "Delivery source is unavailable or paused")
                _, config = connection(db, raw["workspace_id"], raw["connection_id"])
                if not config.get("enabled", True): raise HTTPException(403, "Connection is disabled")
                # Validate and decrypt before reserving an external attempt.
                integrations.destination(config["url"]); secret = integrations.reveal(config["secret"])
                job.status = "reconciliation_required"; job.attempts += 1
                db.commit()  # A crash after this point must never trigger an automatic duplicate.
                try:
                    integrations.send(config["url"], secret, raw["event"])
                    job.status = "accepted"; job.last_error = None
                except HTTPException as error:
                    code = getattr(error, "connector_status", None)
                    if code in {429, 500, 502, 503, 504}:
                        job.status = "scheduled" if job.attempts < 5 else "dead_letter"
                        job.run_at = now + timedelta(seconds=min(3600, 60 * 2 ** (job.attempts - 1)))
                        job.last_error = f"Receiver rejected attempt (HTTP {code})"
                    elif code is not None:
                        job.status = "dead_letter"; job.last_error = f"Receiver rejected attempt (HTTP {code})"
                    else: job.last_error = "Outcome unconfirmed; reconcile using delivery ID"
                except Exception:
                    job.last_error = "Outcome unconfirmed; reconcile using delivery ID"
        except Exception:
            job.status = "dead_letter"; job.last_error = "Delivery authorization or connection validation failed"
        finally:
            release_run_context(db)
        db.commit(); count += 1
    return {"processed": count}
