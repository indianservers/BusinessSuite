"""Central governance endpoints; existing corporate authentication is reused."""

import json
import time
import hmac
import hashlib
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from pydantic import Field
from sqlalchemy.orm import Session
from app.access.api import (
    Strict,
    admin,
    company_access,
    check_step,
    authority,
    serialize,
)
from app.access import service
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.company import Company
from app.models.platform import IntegrationCredential, IntegrationEvent
from app.models.notification import Notification, NotificationDeliveryLog
from app.apps.automation.models import (
    AutomationWorkflow,
    AutomationScheduledJob,
    AutomationExecutionLog,
    AutomationWebhookEndpoint,
)
from app.shared.models import (
    ServicePolicy,
    ServiceEvent,
    WorkflowVersion,
    ServiceDocument,
)
from app.shared import runtime, integrations
from app.shared.contracts import describe, authorize, service_identity
from app.shared.gateway import digest, read_record
from app.shared.settings import effective, validate as validate_settings
from app.shared.communications import provider_status

router = APIRouter(prefix="/access/services", tags=["Shared Service Governance"])


def audit(db, actor, company, operation, request, reason, after=None, before=None):
    service.audit(
        db,
        actor,
        company,
        "shared." + operation,
        reason,
        request=request,
        after=after,
        before=before,
    )


def change(db, actor, company, request):
    company_access(db, actor, company)
    from app.access.control import mutate

    mutate(request, actor)


def inspect_identity(db, actor, company, identifier):
    if actor.is_superuser:
        return True
    user = db.get(User, identifier) if identifier else None
    policy = service.policy_for(db, user, company) if user else None
    if not policy:
        return False
    try:
        authority(actor, service.resolved_grants(db, policy))
        return True
    except HTTPException:
        return False


@router.get("/catalog")
def catalog(
    companyId: int = 1, db: Session = Depends(get_db), actor: User = Depends(admin)
):
    company_access(db, actor, companyId)
    from app.ai_operator.suite_tools import catalog as tools

    return {
        "modules": describe(db),
        "nodes": sorted(runtime.NODES),
        "tools": tools(),
        "channels": provider_status(),
        "navigation": [
            {"label": "Approval Center", "route": "/hrms/approvals"},
            {"label": "Automations", "route": "/admin/automation"},
            {"label": "Email & templates", "route": "/crm/communication-hub"},
            {"label": "AI Providers", "route": "/ai/provider-settings"},
            {"label": "AI Tool Registry", "route": "/ai-agents/config"},
            {"label": "Custom Fields", "route": "/admin/customization/fields"},
            {"label": "Form Builder", "route": "/pms/forms"},
        ],
    }


@router.get("/overview")
def overview(
    companyId: int = 1, db: Session = Depends(get_db), actor: User = Depends(admin)
):
    company_access(db, actor, companyId)
    jobs = (
        db.query(AutomationScheduledJob)
        .filter_by(organization_id=companyId, job_type="shared_workflow")
        .order_by(AutomationScheduledJob.id.desc())
        .limit(100)
        .all()
    )
    return {
        "workflows": db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == companyId,
            AutomationWorkflow.graph_json.isnot(None),
        )
        .count(),
        "pendingEvents": db.query(ServiceEvent)
        .filter_by(organization_id=companyId, status="pending")
        .count(),
        "executions": [serialize(j) for j in jobs],
        "providers": provider_status(),
        "settings": effective(db, companyId, "*"),
    }


class PolicyInput(Strict):
    companyId: int = Field(gt=0)
    module: str = "*"
    platform: bool = False
    version: int = Field(ge=0)
    values: dict
    reason: str = Field(min_length=3, max_length=500)


@router.get("/settings")
def settings(
    companyId: int = 1,
    module: str = "*",
    platform: bool = False,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, companyId)
    if platform and not actor.is_superuser:
        raise HTTPException(403, "Global policy requires global administration")
    if module != "*":
        authorize(db, actor, companyId, module)
    key = (
        "platform"
        if platform
        else f"company:{companyId}" + (f":module:{module}" if module != "*" else "")
    )
    row = db.query(ServicePolicy).filter_by(scope_key=key, kind="settings").first()
    return {
        "effective": effective(db, companyId, module),
        "override": serialize(row) if row else None,
    }


@router.put("/settings")
def save_settings(
    data: PolicyInput,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(db, actor, data.companyId, request)
    if data.platform and not actor.is_superuser:
        raise HTTPException(403, "Only global administrators may set platform policy")
    if data.module != "*":
        authorize(db, actor, data.companyId, data.module)
    validate_settings(data.values)
    db.query(Company).filter_by(id=data.companyId).with_for_update().one()
    key = (
        "platform"
        if data.platform
        else f"company:{data.companyId}"
        + (f":module:{data.module}" if data.module != "*" else "")
    )
    row = (
        db.query(ServicePolicy)
        .filter_by(scope_key=key, kind="settings")
        .with_for_update()
        .populate_existing()
        .first()
    )
    if (row.version if row else 0) != data.version:
        raise HTTPException(409, "Settings changed; reload before saving")
    before = dict(row.values_json) if row else {}
    if not row:
        row = ServicePolicy(
            scope_key=key,
            organization_id=None if data.platform else data.companyId,
            module_key=data.module,
            kind="settings",
            updated_by=actor.id,
            version=0,
        )
        db.add(row)
    row.values_json, row.version, row.updated_by = (
        data.values,
        row.version + 1,
        actor.id,
    )
    audit(
        db,
        actor,
        data.companyId,
        "settings.updated",
        request,
        data.reason,
        data.values,
        before,
    )
    db.commit()
    return {
        "version": row.version,
        "effective": effective(db, data.companyId, data.module),
    }


class WorkflowInput(Strict):
    companyId: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=180)
    module: str = Field(min_length=1, max_length=80)
    entity: str = Field(min_length=1, max_length=80)
    event: str = Field(min_length=1, max_length=120)
    runAsUserId: int = Field(gt=0)
    graph: dict
    version: int = Field(0, ge=0)
    reason: str = Field(min_length=3, max_length=500)


@router.get("/workflows")
def workflows(
    companyId: int = 1, db: Session = Depends(get_db), actor: User = Depends(admin)
):
    company_access(db, actor, companyId)
    return [
        serialize(w)
        for w in db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == companyId,
            AutomationWorkflow.graph_json.isnot(None),
        )
        .order_by(AutomationWorkflow.id.desc())
        if inspect_identity(db, actor, companyId, w.run_as_user_id)
    ]


@router.post("/workflows", status_code=201)
@router.put("/workflows/{workflow_id}")
def save_workflow(
    data: WorkflowInput,
    request: Request,
    workflow_id: int | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(db, actor, data.companyId, request)
    runtime.validate_graph(data.graph)
    if (
        len(data.graph["nodes"])
        > effective(db, data.companyId, data.module)["values"]["workflow_max_nodes"]
    ):
        raise HTTPException(422, "Graph exceeds the effective module node limit")
    execution_actor = service_identity(
        db, db.get(User, data.runAsUserId), data.companyId, data.module
    )
    authority(
        actor,
        service.resolved_grants(
            db, service.policy_for(db, execution_actor, data.companyId)
        ),
    )
    row = (
        db.query(AutomationWorkflow)
        .filter_by(id=workflow_id, organization_id=data.companyId)
        .with_for_update()
        .populate_existing()
        .first()
        if workflow_id
        else None
    )
    if workflow_id and not row:
        raise HTTPException(404, "Workflow not found")
    if (row.draft_version if row else 0) != data.version:
        raise HTTPException(409, "Workflow changed; reload before editing")
    if row and (row.module_name, row.record_type, row.trigger_type) != (
        data.module,
        data.entity,
        data.event,
    ):
        raise HTTPException(422, "Duplicate the workflow to change its source contract")
    if not row:
        row = AutomationWorkflow(
            organization_id=data.companyId,
            module_name=data.module,
            record_type=data.entity,
            trigger_type=data.event,
            created_by=actor.id,
            draft_version=0,
            is_active=False,
        )
        db.add(row)
    row.name, row.graph_json, row.run_as_user_id, row.draft_version, row.updated_by = (
        data.name,
        data.graph,
        data.runAsUserId,
        row.draft_version + 1,
        actor.id,
    )
    audit(
        db,
        actor,
        data.companyId,
        "workflow.saved",
        request,
        data.reason,
        {"name": data.name, "version": row.draft_version},
    )
    db.commit()
    return serialize(row)


class Command(Strict):
    companyId: int = Field(gt=0)
    version: int | None = None
    reason: str = Field(min_length=3, max_length=500)


@router.post("/workflows/{workflow_id}/publish")
def publish(
    workflow_id: int,
    data: Command,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(db, actor, data.companyId, request)
    row = (
        db.query(AutomationWorkflow)
        .filter_by(id=workflow_id, organization_id=data.companyId)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not row or row.draft_version != data.version:
        raise HTTPException(409, "Workflow is missing or draft version changed")
    runtime.validate_graph(row.graph_json)
    if (
        len(row.graph_json["nodes"])
        > effective(db, data.companyId, row.module_name)["values"]["workflow_max_nodes"]
    ):
        raise HTTPException(422, "Graph exceeds the effective module node limit")
    execution_actor = service_identity(
        db, db.get(User, row.run_as_user_id), data.companyId, row.module_name
    )
    authority(
        actor,
        service.resolved_grants(
            db, service.policy_for(db, execution_actor, data.companyId)
        ),
    )
    if (
        db.query(WorkflowVersion)
        .filter_by(workflow_id=row.id, version=row.draft_version)
        .first()
    ):
        raise HTTPException(409, "This version is already published; save a new draft")
    db.add(
        WorkflowVersion(
            organization_id=data.companyId,
            workflow_id=row.id,
            version=row.draft_version,
            graph_json=row.graph_json,
            digest=digest(row.graph_json),
            published_by=actor.id,
            run_as_user_id=row.run_as_user_id,
        )
    )
    row.published_version, row.is_active = row.draft_version, True
    audit(
        db,
        actor,
        data.companyId,
        "workflow.published",
        request,
        data.reason,
        {"workflowId": row.id, "version": row.draft_version},
    )
    db.commit()
    return serialize(row)


@router.get("/workflows/{workflow_id}/versions")
def versions(
    workflow_id: int,
    companyId: int = 1,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, companyId)
    return [
        serialize(r)
        for r in db.query(WorkflowVersion)
        .filter_by(workflow_id=workflow_id, organization_id=companyId)
        .order_by(WorkflowVersion.version.desc())
        if inspect_identity(db, actor, companyId, r.run_as_user_id)
    ]


@router.post("/graph/validate")
def preview_graph(data: dict, actor: User = Depends(admin)):
    runtime.validate_graph(data)
    return {
        "valid": True,
        "nodeCount": len(data["nodes"]),
        "message": "Graph valid. No business action was executed.",
    }


class EventInput(Strict):
    companyId: int = Field(gt=0)
    module: str
    entity: str
    entityId: int = Field(gt=0)
    event: str
    requestKey: str = Field(min_length=8, max_length=180)
    data: dict = Field(default_factory=dict)
    reason: str = Field(min_length=3, max_length=500)


@router.post("/events")
def event_input(
    data: EventInput,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(db, actor, data.companyId, request)
    read_record(db, actor, data.companyId, data.module, data.entity, data.entityId)
    row = runtime.emit(
        db,
        actor,
        data.companyId,
        data.module,
        data.event,
        data.entity,
        data.entityId,
        data.requestKey,
        data.data,
    )
    audit(
        db,
        actor,
        data.companyId,
        "event.submitted",
        request,
        data.reason,
        {"eventId": row.id, "module": data.module},
    )
    db.commit()
    return serialize(row)


@router.get("/events")
def events(
    companyId: int = 1, db: Session = Depends(get_db), actor: User = Depends(admin)
):
    company_access(db, actor, companyId)
    return [
        {
            **serialize(r),
            "payload_json": {
                key: value
                for key, value in r.payload_json.items()
                if key not in {"snapshot", "data"}
            },
        }
        for r in db.query(ServiceEvent)
        .filter_by(organization_id=companyId)
        .order_by(ServiceEvent.id.desc())
        .limit(100)
    ]


@router.get("/executions")
def executions(
    companyId: int = 1, db: Session = Depends(get_db), actor: User = Depends(admin)
):
    company_access(db, actor, companyId)
    return [
        serialize(j)
        for j in db.query(AutomationScheduledJob)
        .filter_by(organization_id=companyId, job_type="shared_workflow")
        .order_by(AutomationScheduledJob.id.desc())
        .limit(100)
    ]


@router.post("/executions/{job_id}/{operation}")
def execution_command(
    job_id: int,
    operation: str,
    data: Command,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(db, actor, data.companyId, request)
    row = (
        db.query(AutomationScheduledJob)
        .filter_by(
            id=job_id, organization_id=data.companyId, job_type="shared_workflow"
        )
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not row:
        raise HTTPException(404, "Execution not found")
    if not inspect_identity(db, actor, data.companyId, row.payload_json["actorId"]):
        raise HTTPException(403, "Execution identity exceeds your authority")
    if operation == "pause" and row.status == "scheduled":
        row.status = "paused"
    elif operation == "cancel" and row.status in {"scheduled", "paused", "dead_letter"}:
        row.status = "cancelled"
    elif operation in {"resume", "retry"} and row.status in {"paused", "dead_letter"}:
        service_identity(
            db,
            db.get(User, row.payload_json["actorId"]),
            data.companyId,
            row.module_name,
        )
        row.status, row.run_at, row.attempts = "scheduled", runtime.now(), 0
    else:
        raise HTTPException(
            409,
            "Operation is not permitted in the current execution state; uncertain writes require reconciliation",
        )
    audit(
        db,
        actor,
        data.companyId,
        "execution." + operation,
        request,
        data.reason,
        {"jobId": job_id},
    )
    db.commit()
    return serialize(row)


@router.post("/worker/tick")
def tick(
    data: Command,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(db, actor, data.companyId, request)
    if not actor.is_superuser:
        raise HTTPException(403, "Global scheduler administrator required")
    result = runtime.process_batch(db, 20)
    audit(db, actor, data.companyId, "worker.tick", request, data.reason, result)
    db.commit()
    return result


class ConnectionInput(Strict):
    companyId: int
    name: str = Field(min_length=1, max_length=150)
    provider: str = Field(min_length=1, max_length=100)
    modules: list[str] = Field(min_length=1, max_length=30)
    operations: dict
    secret: str = Field(min_length=16, max_length=4000, repr=False)
    reason: str = Field(min_length=3, max_length=500)


@router.post("/connections", status_code=201)
def connection(
    data: ConnectionInput,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(db, actor, data.companyId, request)
    if not actor.is_superuser:
        raise HTTPException(403, "Only global administrators may approve destinations")
    if not 1 <= len(data.operations) <= 20:
        raise HTTPException(422, "Choose a bounded operation catalog")
    for module in data.modules:
        authorize(db, actor, data.companyId, module)
    for name, config in data.operations.items():
        if (
            not isinstance(config, dict)
            or set(config) - {"url", "fields"}
            or not isinstance(config.get("fields"), list)
        ):
            raise HTTPException(
                422, "Each operation requires a fixed URL and field allowlist"
            )
        integrations.destination(config.get("url", ""))
    row = IntegrationCredential(
        organization_id=data.companyId,
        provider=data.provider,
        credential_name=data.name,
        auth_type="Signed HTTPS",
        secret_ref=integrations.protect(data.secret),
        module_keys=data.modules,
        config_json={"operations": data.operations},
        created_by=actor.id,
        status="Active",
    )
    db.add(row)
    db.flush()
    audit(
        db,
        actor,
        data.companyId,
        "connection.created",
        request,
        data.reason,
        {"id": row.id, "modules": data.modules, "provider": data.provider},
    )
    db.commit()
    return {"id": row.id, "status": "configured-unverified"}


@router.get("/connections")
def connections(
    companyId: int = 1, db: Session = Depends(get_db), actor: User = Depends(admin)
):
    company_access(db, actor, companyId)
    return [
        {
            "id": r.id,
            "name": r.credential_name,
            "provider": r.provider,
            "modules": r.module_keys,
            "status": r.status,
            "ownerId": r.created_by,
            "version": r.version,
            "operations": list((r.config_json or {}).get("operations", {})),
            "verification": "unverified",
        }
        for r in db.query(IntegrationCredential).filter_by(organization_id=companyId)
    ]


@router.post("/connections/{connection_id}/revoke")
def revoke_connection(
    connection_id: int,
    data: Command,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(db, actor, data.companyId, request)
    row = (
        db.query(IntegrationCredential)
        .filter_by(id=connection_id, organization_id=data.companyId)
        .with_for_update()
        .first()
    )
    if not row:
        raise HTTPException(404, "Connection not found")
    row.status, row.version = "Revoked", row.version + 1
    audit(
        db,
        actor,
        data.companyId,
        "connection.revoked",
        request,
        data.reason,
        {"id": row.id},
    )
    db.commit()
    return {"status": row.status}


@router.get("/delivery")
def delivery(
    companyId: int = 1, db: Session = Depends(get_db), actor: User = Depends(admin)
):
    company_access(db, actor, companyId)
    rows = (
        db.query(NotificationDeliveryLog, Notification)
        .join(Notification, Notification.id == NotificationDeliveryLog.notification_id)
        .filter(Notification.company_id == companyId)
        .order_by(NotificationDeliveryLog.id.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": log.id,
            "notificationId": notification.id,
            "module": notification.module,
            "userId": notification.user_id,
            "channel": log.channel,
            "status": log.status,
            "error": log.error_message,
            "at": log.attempted_at,
        }
        for log, notification in rows
    ]


class WebhookInput(Strict):
    companyId: int = Field(gt=0)
    module: str
    entity: str
    events: list[str] = Field(min_length=1, max_length=20)
    runAsUserId: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=150)
    secret: str = Field(min_length=24, max_length=32, repr=False)
    reason: str = Field(min_length=3, max_length=500)


@router.post("/webhooks", status_code=201)
def create_webhook(
    data: WebhookInput,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(db, actor, data.companyId, request)
    if not actor.is_superuser:
        raise HTTPException(403, "Global administrator must approve webhook identities")
    service_identity(db, db.get(User, data.runAsUserId), data.companyId, data.module)
    row = AutomationWebhookEndpoint(
        organization_id=data.companyId,
        name=data.name,
        target_url="internal:" + data.module,
        event_types_json={
            "module": data.module,
            "entity": data.entity,
            "events": data.events,
            "runAsUserId": data.runAsUserId,
        },
        secret_ref=integrations.protect(data.secret),
        created_by=actor.id,
        is_active=True,
    )
    db.add(row)
    db.flush()
    audit(
        db,
        actor,
        data.companyId,
        "webhook.created",
        request,
        data.reason,
        {"id": row.id, "module": data.module},
    )
    db.commit()
    return {"id": row.id, "path": f"/api/v1/access/services/webhooks/{row.id}/receive"}


@router.get("/webhooks")
def webhooks(
    companyId: int = 1, db: Session = Depends(get_db), actor: User = Depends(admin)
):
    company_access(db, actor, companyId)
    return [
        {
            "id": w.id,
            "name": w.name,
            "active": w.is_active,
            "subscription": w.event_types_json,
            "path": f"/api/v1/access/services/webhooks/{w.id}/receive",
        }
        for w in db.query(AutomationWebhookEndpoint).filter(
            AutomationWebhookEndpoint.organization_id == companyId,
            AutomationWebhookEndpoint.target_url.startswith("internal:"),
        )
    ]


@router.post("/webhooks/{endpoint_id}/receive")
async def receive_webhook(
    endpoint_id: int, request: Request, db: Session = Depends(get_db)
):
    from starlette.concurrency import run_in_threadpool

    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 64000:
            raise HTTPException(413, "Webhook payload is too large")
    raw = bytes(content)
    return await run_in_threadpool(
        receive_signed_event, endpoint_id, raw, dict(request.headers), db
    )


def receive_signed_event(endpoint_id, raw, headers, db):
    row = (
        db.query(AutomationWebhookEndpoint)
        .filter_by(id=endpoint_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not row or not row.is_active or not row.target_url.startswith("internal:"):
        raise HTTPException(404, "Webhook not found")
    if len(raw) > 64000:
        raise HTTPException(413, "Webhook payload is too large")
    stamp = headers.get("x-suite-timestamp", "")
    try:
        valid_time = abs(int(stamp) - int(time.time())) <= 300
    except ValueError:
        valid_time = False
    signature = hmac.new(
        integrations.reveal(row.secret_ref).encode(),
        stamp.encode() + b"." + raw,
        hashlib.sha256,
    ).hexdigest()
    if not valid_time or not hmac.compare_digest(
        signature, headers.get("x-suite-signature", "")
    ):
        raise HTTPException(401, "Webhook signature is invalid or expired")
    try:
        data = json.loads(raw)
        if (
            not isinstance(data, dict)
            or set(data) - {"id", "entityId", "event", "data"}
            or not isinstance(data.get("id"), str)
            or not 8 <= len(data["id"]) <= 100
        ):
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(422, "Invalid signed event payload") from None
    config = row.event_types_json
    if data.get("event") not in config["events"]:
        raise HTTPException(422, "Event is not subscribed")
    key = f"webhook:{row.id}:{data['id']}"
    if (
        db.query(ServiceEvent)
        .filter_by(organization_id=row.organization_id, request_key=key)
        .first()
    ):
        raise HTTPException(409, "Webhook replay rejected")
    cutoff = runtime.now() - timedelta(minutes=5)
    if (
        db.query(ServiceEvent)
        .filter(
            ServiceEvent.organization_id == row.organization_id,
            ServiceEvent.request_key.startswith(f"webhook:{row.id}:"),
            ServiceEvent.created_at >= cutoff,
        )
        .count()
        >= 100
    ):
        raise HTTPException(429, "Webhook rate limit exceeded")
    actor = service_identity(
        db, db.get(User, config["runAsUserId"]), row.organization_id, config["module"]
    )
    read_record(
        db,
        actor,
        row.organization_id,
        config["module"],
        config["entity"],
        data.get("entityId"),
    )
    result = runtime.emit(
        db,
        actor,
        row.organization_id,
        config["module"],
        data["event"],
        config["entity"],
        data["entityId"],
        key,
        data.get("data", {}),
    )
    db.commit()
    return {"eventId": result.id, "status": "queued"}


@router.get("/documents")
def documents(
    companyId: int = 1,
    module: str | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    if not actor.is_superuser and companyId not in service.companies_for(db, actor):
        raise HTTPException(403, "Company membership required")
    query = db.query(ServiceDocument).filter_by(organization_id=companyId)
    if module:
        query = query.filter_by(module_key=module)
    result = []
    for row in query.order_by(ServiceDocument.id.desc()).limit(50):
        try:
            read_record(
                db, actor, companyId, row.module_key, row.entity_type, row.entity_id
            )
        except HTTPException:
            continue
        result.append({k: v for k, v in serialize(row).items() if k != "storage_path"})
    return result


@router.get("/ai")
def ai_governance(
    companyId: int = 1, db: Session = Depends(get_db), actor: User = Depends(admin)
):
    company_access(db, actor, companyId)
    from app.ai_operator.models import OperatorProvider
    from app.ai_agents.models import AiUsageEvent, AiUsageLimit
    from app.ai_agents.tools.definitions import ALL_TOOL_DEFINITIONS

    events = (
        db.query(AiUsageEvent)
        .filter_by(company_id=companyId)
        .order_by(AiUsageEvent.id.desc())
        .limit(500)
        .all()
    )
    providers = (
        db.query(OperatorProvider).filter_by(scope_key=f"company:{companyId}").all()
    )
    return {
        "providers": [
            {
                "provider": p.provider,
                "model": p.model,
                "enabled": p.enabled,
                "dataSharingAllowed": p.data_sharing_allowed,
                "credentialConfigured": bool(p.encrypted_key),
                "status": (
                    "configured-unverified"
                    if p.enabled and p.encrypted_key
                    else "disabled-or-unconfigured"
                ),
            }
            for p in providers
        ],
        "tools": [
            {
                "id": t.tool_name,
                "module": t.module,
                "description": t.description,
                "schema": t.input_schema,
                "requiredPermission": t.required_permission,
                "risk": t.risk_level,
                "humanApprovalRequired": t.requires_approval,
            }
            for t in ALL_TOOL_DEFINITIONS
        ],
        "usage": [
            {
                "id": e.id,
                "module": e.module,
                "userId": e.user_id,
                "type": e.event_type,
                "inputTokens": e.token_input,
                "outputTokens": e.token_output,
                "estimatedCost": (
                    str(e.estimated_cost) if e.estimated_cost is not None else None
                ),
                "at": e.created_at,
            }
            for e in events
        ],
        "limits": [
            serialize(l) for l in db.query(AiUsageLimit).filter_by(company_id=companyId)
        ],
        "costSemantics": "Estimates only; billed costs are not available from this ledger",
        "localModels": "Existing TensorFlow.js inference remains separate from the conversational provider registry",
    }


@router.post("/documents", status_code=201)
def upload_document(
    request: Request,
    companyId: int = Form(...),
    module: str = Form(...),
    entity: str = Form(...),
    entityId: int = Form(...),
    folder: str = Form("/"),
    documentKey: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    authorize(db, actor, companyId, module, "edit")
    read_record(db, actor, companyId, module, entity, entityId)
    from app.core.config import settings as config
    from app.core.storage import persist_file

    raw = file.file.read(
        min(
            config.MAX_UPLOAD_SIZE_MB,
            effective(db, companyId, module)["values"]["upload_limit_mb"],
        )
        * 1024
        * 1024
        + 1
    )
    if (
        len(raw)
        > min(
            config.MAX_UPLOAD_SIZE_MB,
            effective(db, companyId, module)["values"]["upload_limit_mb"],
        )
        * 1024
        * 1024
        or not raw
    ):
        raise HTTPException(413, "File is empty or exceeds the effective upload limit")
    extension = Path(file.filename or "").suffix.lower()
    signatures = {
        ".pdf": (b"%PDF-", "application/pdf"),
        ".png": (b"\x89PNG\r\n\x1a\n", "image/png"),
        ".jpg": (b"\xff\xd8\xff", "image/jpeg"),
        ".jpeg": (b"\xff\xd8\xff", "image/jpeg"),
    }
    if extension not in signatures or not raw.startswith(signatures[extension][0]):
        raise HTTPException(
            422, "Only verified PDF, PNG and JPEG files are currently supported"
        )
    key = documentKey or str(uuid.uuid4())
    previous = (
        db.query(ServiceDocument)
        .filter_by(document_key=key)
        .order_by(ServiceDocument.version.desc())
        .with_for_update()
        .first()
    )
    if previous and (
        previous.organization_id,
        previous.module_key,
        previous.entity_type,
        previous.entity_id,
    ) != (companyId, module, entity, entityId):
        raise HTTPException(403, "Document belongs to another record")
    if ".." in folder or len(folder) > 240:
        raise HTTPException(422, "Invalid folder")
    from app.enterprise.controls import quota

    quota(db, companyId, "storage_mb", len(raw))
    path = (
        Path(config.UPLOAD_DIR)
        / "shared"
        / str(companyId)
        / module
        / (str(uuid.uuid4()) + extension)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    persist_file(str(path))
    row = ServiceDocument(
        organization_id=companyId,
        module_key=module,
        entity_type=entity,
        entity_id=entityId,
        document_key=key,
        version=(previous.version + 1 if previous else 1),
        name=Path(file.filename).name[:240],
        folder=folder,
        mime_type=signatures[extension][1],
        size_bytes=len(raw),
        storage_path=str(path),
        content_hash=hashlib.sha256(raw).hexdigest(),
        owner_id=actor.id,
    )
    db.add(row)
    audit(
        db,
        actor,
        companyId,
        "document.uploaded",
        request,
        "Authorized record document upload",
        {"module": module, "entityId": entityId, "version": row.version},
    )
    db.commit()
    return {k: v for k, v in serialize(row).items() if k != "storage_path"}


@router.get("/documents/{document_id}/download")
def download(
    document_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    row = db.get(ServiceDocument, document_id)
    if not row:
        raise HTTPException(404, "Document not found")
    read_record(
        db, actor, row.organization_id, row.module_key, row.entity_type, row.entity_id
    )
    from app.core.storage import materialize_file
    from fastapi.responses import FileResponse

    # Authenticated streaming keeps record-level revocation authoritative on every download.
    return FileResponse(
        materialize_file(row.storage_path),
        filename=row.name,
        media_type=row.mime_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "sandbox",
        },
    )
