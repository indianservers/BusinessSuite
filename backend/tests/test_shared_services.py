import copy
import hashlib
import hmac
import json
import time
import pytest
from fastapi import HTTPException
from app.access.models import AccessPolicy
from app.apps.crm.models import CRMLead
from app.models.user import User, Role
from app.models.company import Company
from app.models.approval_os import ApprovalRequest
from app.models.notification import Notification
from app.apps.automation.models import AutomationScheduledJob
from app.shared.models import (
    ServiceEvent,
    WorkflowVersion,
    ServiceDocument,
    ServicePolicy,
)
from app.shared import runtime, integrations
from app.shared.gateway import ModuleServices
from tests.test_suite_access import access_account, login, secure, grant, apply
from app.core.security import get_password_hash
from app.common.models import CommonPerson

ROOT = "/api/v1/access/services"


@pytest.fixture
def shared_setup(client, db, access_account, superuser_headers):
    headers = secure(client, superuser_headers)
    crm = grant(client, headers, "crm", "admin")
    assert apply(client, headers, access_account, {"crm": crm}).status_code == 200
    lead = CRMLead(
        organization_id=1,
        owner_user_id=access_account.id,
        first_name="Service",
        full_name="Shared Service Lead",
        status="New",
    )
    db.add(lead)
    db.commit()
    return headers, access_account, lead


def graph(*nodes):
    rows = [
        {"id": "start", "type": "start", "config": {}, "x": 0, "y": 0},
        *nodes,
        {"id": "end", "type": "end", "config": {}, "x": 600, "y": 0},
    ]
    return {
        "nodes": rows,
        "edges": [
            {"source": a["id"], "target": b["id"]} for a, b in zip(rows, rows[1:])
        ],
    }


def create_workflow(client, headers, user, definition, **extra):
    body = {
        "companyId": 1,
        "name": "Shared service workflow",
        "module": "crm",
        "entity": "lead",
        "event": "test.event",
        "runAsUserId": user.id,
        "graph": definition,
        "version": 0,
        "reason": "Create verified workflow",
        **extra,
    }
    response = client.post(ROOT + "/workflows", headers=headers, json=body)
    assert response.status_code == 201, response.text
    row = response.json()
    published = client.post(
        ROOT + f"/workflows/{row['id']}/publish",
        headers=headers,
        json={
            "companyId": 1,
            "version": row["draft_version"],
            "reason": "Publish verified workflow",
        },
    )
    assert published.status_code == 200, published.text
    return row


def test_shared_catalog_and_unauthorized_control(client, db, shared_setup):
    headers, user, lead = shared_setup
    data = client.get(ROOT + "/catalog", headers=headers)
    assert data.status_code == 200, data.text
    assert all(
        set(m["services"])
        >= {"authentication", "approvals", "ai", "documents", "integrations"}
        for m in data.json()["modules"]
    )
    assert client.get(ROOT + "/workflows", headers=login(client)).status_code == 403
    assert (
        client.get(
            ROOT + "/settings", headers=headers, params={"companyId": 99999}
        ).status_code
        == 404
    )


def test_publish_persistence_idempotent_event_and_real_notification(
    client, db, shared_setup
):
    headers, user, lead = shared_setup
    row = create_workflow(
        client,
        headers,
        user,
        graph(
            {
                "id": "notice",
                "type": "notification",
                "config": {
                    "recipientId": user.id,
                    "title": "Shared engine alert",
                    "message": "Real in-app delivery",
                },
            }
        ),
    )
    sdk = ModuleServices(db, user, 1, "crm")
    event = sdk.emit("test.event", "lead", lead.id, "shared-event-0001")
    assert sdk.emit("test.event", "lead", lead.id, "shared-event-0001").id == event.id
    db.commit()
    result = runtime.process_batch(db, 10)
    assert result["processed"] == 3
    job = db.query(AutomationScheduledJob).filter_by(job_type="shared_workflow").one()
    assert job.status == "completed", job.last_error
    assert (
        db.query(Notification)
        .filter_by(title="Shared engine alert", user_id=user.id, company_id=1)
        .count()
        == 1
    )
    assert runtime.process_batch(db, 10)["processed"] == 0
    assert db.query(WorkflowVersion).filter_by(workflow_id=row["id"]).count() == 1


def test_version_staleness_and_non_super_execution_identity(client, db, shared_setup):
    headers, user, lead = shared_setup
    row = create_workflow(client, headers, user, graph())
    stale = client.put(
        ROOT + f"/workflows/{row['id']}",
        headers=headers,
        json={
            "companyId": 1,
            "name": "Stale",
            "module": "crm",
            "entity": "lead",
            "event": "test.event",
            "runAsUserId": user.id,
            "graph": graph(),
            "version": 0,
            "reason": "Check optimistic locking",
        },
    )
    assert stale.status_code == 409
    admin_id = db.query(User).filter_by(is_superuser=True).first().id
    forbidden = client.post(
        ROOT + "/workflows",
        headers=headers,
        json={
            "companyId": 1,
            "name": "Unsafe identity",
            "module": "crm",
            "entity": "lead",
            "event": "test.event",
            "runAsUserId": admin_id,
            "graph": graph(),
            "version": 0,
            "reason": "Reject unrestricted execution",
        },
    )
    assert forbidden.status_code == 422


def test_graph_cycles_injection_and_unreachable_nodes(client, db, shared_setup):
    headers, _, _ = shared_setup
    cycle = graph()
    cycle["edges"].append({"source": "end", "target": "start"})
    assert (
        client.post(ROOT + "/graph/validate", headers=headers, json=cycle).status_code
        == 422
    )
    unsafe = graph(
        {
            "id": "run",
            "type": "create_record",
            "config": {"tool": "run_python", "code": "unsafe"},
        }
    )
    assert (
        client.post(ROOT + "/graph/validate", headers=headers, json=unsafe).status_code
        == 422
    )
    disconnected = graph()
    disconnected["nodes"].append({"id": "orphan", "type": "end", "config": {}})
    assert (
        client.post(
            ROOT + "/graph/validate", headers=headers, json=disconnected
        ).status_code
        == 422
    )


def test_revocation_denies_queued_work_and_retains_dead_letter(
    client, db, shared_setup
):
    headers, user, lead = shared_setup
    create_workflow(client, headers, user, graph())
    ModuleServices(db, user, 1, "crm").emit(
        "test.event", "lead", lead.id, "revoked-work-0001"
    )
    db.commit()
    runtime.dispatch_events(db)
    policy = db.query(AccessPolicy).filter_by(user_id=user.id, company_id=1).one()
    policy.grants = {"crm": {**policy.grants["crm"], "enabled": False}}
    db.commit()
    runtime.process_batch(db, 10)
    job = db.query(AutomationScheduledJob).filter_by(job_type="shared_workflow").one()
    assert job.status == "dead_letter"
    assert "denied" in job.last_error.lower()


def test_approval_snapshot_self_approval_and_real_decision(client, db, shared_setup):
    headers, user, lead = shared_setup
    role = Role(name="shared_reviewer", permissions=list(user.role.permissions))
    reviewer = User(
        email="shared.reviewer@example.com",
        hashed_password=get_password_hash("Sales@123456"),
        role=role,
        is_active=True,
    )
    db.add(reviewer)
    db.flush()
    db.add(
        CommonPerson(user_id=reviewer.id, organization_id=1, display_name="Reviewer")
    )
    db.add(
        AccessPolicy(
            user_id=reviewer.id,
            company_id=1,
            grants=copy.deepcopy(
                db.query(AccessPolicy)
                .filter_by(user_id=user.id, company_id=1)
                .one()
                .grants
            ),
            status="active",
        )
    )
    db.commit()
    with pytest.raises(HTTPException):
        ModuleServices(db, user, 1, "crm").approval(
            "lead", lead.id, [user.id], "Self approval", "self-approval-0001"
        )
    event = ModuleServices(db, user, 1, "crm").approval(
        "lead", lead.id, [reviewer.id], "Review record", "independent-approval-0001"
    )
    db.commit()
    request = db.query(ApprovalRequest).filter_by(approval_type="shared.workflow").one()
    assert (
        runtime.decide_approval(
            db, reviewer, request.id, "approve", "Reviewed the immutable snapshot"
        ).status
        == "Approved"
    )
    db.commit()
    assert db.get(ServiceEvent, event.id).status == "approved"


def test_approval_detects_changed_source_and_tampered_reference(
    client, db, shared_setup
):
    headers, user, lead = shared_setup
    reviewer = db.query(User).filter_by(is_superuser=True).one()
    event = runtime.request_approval(
        db,
        user,
        1,
        "crm",
        "lead",
        lead.id,
        [reviewer.id],
        "Review immutable record",
        "tamper-approval-0001",
    )
    db.commit()
    request = db.query(ApprovalRequest).filter_by(approval_type="shared.workflow").one()
    request.context_json = {"_shared": event.id, "snapshotHash": "forged"}
    db.commit()
    with pytest.raises(HTTPException) as denied:
        runtime.decide_approval(db, reviewer, request.id, "approve", "No tampering")
    assert denied.value.status_code == 409


def test_notification_recipient_and_document_tenant_scope(
    client, db, shared_setup, tmp_path, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    headers, user, lead = shared_setup
    foreign = Company(name="Foreign company")
    db.add(foreign)
    db.flush()
    recipient = User(
        email="foreign.notify@example.com",
        hashed_password=get_password_hash("Sales@123456"),
        role=user.role,
        is_active=True,
    )
    db.add(recipient)
    db.flush()
    db.add(
        CommonPerson(
            user_id=recipient.id,
            organization_id=foreign.id,
            display_name="Foreign recipient",
        )
    )
    db.commit()
    with pytest.raises(HTTPException):
        ModuleServices(db, user, 1, "crm").notify(
            "lead", lead.id, recipient.id, "Private alert", "Must not cross tenant"
        )
    upload = client.post(
        ROOT + "/documents",
        headers=login(client),
        data={
            "companyId": "1",
            "module": "crm",
            "entity": "lead",
            "entityId": str(lead.id),
        },
        files={"file": ("test.pdf", b"%PDF-1.4\nTest document", "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    assert "storage_path" not in upload.json()
    foreign_headers = login(client, "foreign.notify@example.com")
    assert client.get(
        ROOT + f"/documents/{upload.json()['id']}/download", headers=foreign_headers
    ).status_code in {403, 404}
    assert (
        client.get(
            ROOT + f"/documents/{upload.json()['id']}/download", headers=login(client)
        ).status_code
        == 200
    )


def test_ssrf_and_secret_encryption_without_external_delivery():
    for url in (
        "http://example.com",
        "https://127.0.0.1/hook",
        "https://[::1]/hook",
        "https://169.254.169.254/latest",
        "https://user:password@example.com/hook",
    ):
        with pytest.raises(HTTPException):
            integrations.destination(url)
    secret = "a-shared-secret-at-least-24-chars"
    encrypted = integrations.protect(secret)
    assert secret not in encrypted and integrations.reveal(encrypted) == secret
    with pytest.raises(HTTPException):
        integrations.reveal(secret)


def test_signed_webhook_replay_and_tampering(client, db, shared_setup):
    headers, user, lead = shared_setup
    secret = "1234567890abcdefghijklmnop"
    created = client.post(
        ROOT + "/webhooks",
        headers=headers,
        json={
            "companyId": 1,
            "module": "crm",
            "entity": "lead",
            "events": ["webhook.received"],
            "runAsUserId": user.id,
            "name": "Signed test input",
            "secret": secret,
            "reason": "Verify secure webhooks",
        },
    )
    assert created.status_code == 201, created.text
    path = created.json()["path"]
    body = json.dumps(
        {
            "id": "test-webhook-event-0001",
            "entityId": lead.id,
            "event": "webhook.received",
            "data": {},
        }
    ).encode()
    stamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode(), stamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    assert (
        client.post(
            path,
            content=body,
            headers={"X-Suite-Timestamp": stamp, "X-Suite-Signature": "forged"},
        ).status_code
        == 401
    )
    signed = {
        "Content-Type": "application/json",
        "X-Suite-Timestamp": stamp,
        "X-Suite-Signature": signature,
    }
    assert client.post(path, content=body, headers=signed).status_code == 200
    assert client.post(path, content=body, headers=signed).status_code == 409


def test_policy_override_cannot_weaken_limits(client, db, shared_setup):
    headers, user, lead = shared_setup
    first = client.put(
        ROOT + "/settings",
        headers=headers,
        json={
            "companyId": 1,
            "version": 0,
            "values": {"workflow_max_steps": 10},
            "reason": "Set stricter company policy",
        },
    )
    assert first.status_code == 200, first.text
    assert first.json()["effective"]["values"]["workflow_max_steps"] == 10
    stale = client.put(
        ROOT + "/settings",
        headers=headers,
        json={
            "companyId": 1,
            "version": 0,
            "values": {},
            "reason": "Reject stale config",
        },
    )
    assert stale.status_code == 409
    invalid = client.put(
        ROOT + "/settings",
        headers=headers,
        json={
            "companyId": 1,
            "version": 1,
            "values": {"security_notifications_required": False},
            "reason": "Reject weakening",
        },
    )
    assert invalid.status_code == 422


def test_real_native_record_writes_emit_transactional_events(client, db, shared_setup):
    headers, user, _ = shared_setup
    response = client.post(
        "/api/v1/crm/lead-management/leads",
        headers=headers,
        json={"values": {"full_name": "Outbox captured lead"}},
    )
    assert response.status_code == 201, response.text
    assert (
        db.query(ServiceEvent)
        .filter_by(
            module_key="crm",
            entity_type="lead",
            entity_id=response.json()["id"],
            event_type="record.created",
        )
        .count()
        == 1
    )


def test_future_module_uses_existing_auth_workflows_notifications_and_settings(
    client, db, shared_setup
):
    from fastapi import APIRouter, Depends
    from app.main import app
    from app.module_registry import APP_MODULES, AppModule
    from app.core.config import settings
    from app.core.deps import RequirePermission, get_db
    from app.access.catalog import register_routes, MODULES, ROUTES, ENDPOINT_MODULES
    from app.shared.contracts import register_record, RecordContract, RECORDS
    from app.models.user import Permission

    headers, user, _ = shared_setup
    router = APIRouter(prefix="/__future_module")

    @router.get("/records/{record_id}")
    def company_record(
        record_id: int,
        db=Depends(get_db),
        actor=Depends(RequirePermission("future_view")),
    ):
        record = db.get(Company, record_id)
        if not record or record.id != actor.organization_id:
            raise HTTPException(404, "Record not found")
        return {"id": record.id, "name": record.name, "active": record.is_active}

    original_routes = list(app.router.routes)
    installed = list(settings.INSTALLED_APPS)
    try:
        APP_MODULES["future"] = AppModule(key="future", label="Future module")
        settings.INSTALLED_APPS = [*installed, "future"]
        register_routes(router, "app.apps.future.api", "future")
        app.include_router(router, prefix="/api/v1")
        register_record(
            RecordContract(
                "future", "company", "/__future_module/records/{id}", "future_view"
            )
        )
        db.add(Permission(name="future_view", module="future"))
        policy = db.query(AccessPolicy).filter_by(user_id=user.id, company_id=1).one()
        policy.grants = {
            **policy.grants,
            "future": {
                "enabled": True,
                "role": "viewer",
                "permissions": ["future_view"],
                "actions": ["view", "create", "edit", "approve"],
                "scope": "organization",
            },
        }
        db.commit()
        db.info.pop("suite_access_catalog", None)
        sdk = ModuleServices(db, user, 1, "future")
        assert sdk.read("company", 1)["id"] == 1
        assert sdk.settings()["values"]["security_notifications_required"] is True
        create_workflow(
            client,
            headers,
            user,
            graph(
                {
                    "id": "notify",
                    "type": "notification",
                    "config": {
                        "recipientId": user.id,
                        "title": "Future module central notification",
                        "message": "Existing service, new registered module",
                    },
                }
            ),
            module="future",
            entity="company",
        )
        sdk.emit("test.event", "company", 1, "future-event-0001")
        db.commit()
        runtime.process_batch(db, 10)
        assert (
            db.query(Notification)
            .filter_by(module="future", title="Future module central notification")
            .count()
            == 1
        )
        assert (
            db.query(AutomationScheduledJob)
            .filter_by(module_name="future", job_type="shared_workflow")
            .one()
            .status
            == "completed"
        )
    finally:
        app.router.routes[:] = original_routes
        APP_MODULES.pop("future", None)
        settings.INSTALLED_APPS = installed
        MODULES.pop("future", None)
        RECORDS.pop(("future", "company"), None)
        for key, value in list(ROUTES.items()):
            if value == "future":
                ROUTES.pop(key)
        for key, value in list(ENDPOINT_MODULES.items()):
            if value == "future":
                ENDPOINT_MODULES.pop(key)


def test_legacy_service_scope_hides_shared_graph_and_other_company(db, shared_setup):
    from app.shared.tenancy import install
    from app.apps.automation.models import AutomationWorkflow
    from app.apps.communication.models import CommunicationEmailMessage

    headers, user, lead = shared_setup
    other = Company(name="Other shared-service tenant")
    db.add(other)
    db.flush()
    own = CommunicationEmailMessage(
        organization_id=1,
        related_record_type="lead",
        related_record_id=lead.id,
        body="Private",
        subject="Own private message",
        to_email="own@example.test",
        status="draft",
    )
    foreign = CommunicationEmailMessage(
        organization_id=other.id,
        related_record_type="lead",
        related_record_id=lead.id,
        body="Private",
        subject="Foreign private message",
        to_email="other@example.test",
        status="draft",
    )
    db.add_all([own, foreign])
    db.flush()
    foreign_id = foreign.id
    cleanup = install(db, 1, "communication")
    try:
        assert db.get(CommunicationEmailMessage, own.id) is own
        assert db.get(CommunicationEmailMessage, foreign_id) is None
        assert foreign_id not in [
            row.id for row in db.query(CommunicationEmailMessage).all()
        ]
    finally:
        cleanup()
    row = AutomationWorkflow(
        organization_id=1,
        name="Protected versioned workflow",
        module_name="crm",
        record_type="lead",
        trigger_type="record.updated",
        graph_json=graph(),
    )
    db.add(row)
    db.flush()
    workflow_id = row.id
    cleanup = install(db, 1, "automation")
    try:
        assert db.get(AutomationWorkflow, workflow_id) is None
        assert workflow_id not in [
            item.id for item in db.query(AutomationWorkflow).all()
        ]
    finally:
        cleanup()


def test_approval_snapshot_removes_credentials_and_stabilizes_signed_urls():
    from app.shared.gateway import business_snapshot, digest

    first = business_snapshot(
        {
            "name": "Customer",
            "access_token": "secret",
            "nested": {"password": "private"},
            "preview": "https://files.test/1?token=first",
        }
    )
    second = business_snapshot(
        {
            "name": "Customer",
            "access_token": "changed",
            "nested": {"password": "changed"},
            "preview": "https://files.test/1?token=second",
        }
    )
    assert "secret" not in json.dumps(first)
    assert "private" not in json.dumps(first)
    assert digest(first) == digest(second)


def test_date_conditions_respect_offsets_and_module_node_limit(
    client, db, shared_setup
):
    assert (
        runtime.condition(
            {
                "field": "due",
                "operator": "date_before",
                "value": "2026-01-01T08:00:00+00:00",
            },
            {"due": "2026-01-01T10:00:00+05:30"},
        )
        is True
    )
    headers, user, lead = shared_setup
    db.add(
        ServicePolicy(
            scope_key="company:1:module:crm",
            organization_id=1,
            module_key="crm",
            kind="settings",
            values_json={"workflow_max_nodes": 2},
            updated_by=user.id,
            version=1,
        )
    )
    db.commit()
    response = client.post(
        ROOT + "/workflows",
        headers=headers,
        json={
            "companyId": 1,
            "name": "Exceeds configured limit",
            "module": "crm",
            "entity": "lead",
            "event": "test.event",
            "runAsUserId": user.id,
            "graph": graph(
                {
                    "id": "middle",
                    "type": "condition",
                    "config": {
                        "condition": {
                            "field": "status",
                            "operator": "equals",
                            "value": "New",
                        }
                    },
                }
            ),
            "version": 0,
            "reason": "Verify module node budget",
        },
    )
    assert response.status_code == 422, response.text
    assert "node limit" in response.json()["detail"]
