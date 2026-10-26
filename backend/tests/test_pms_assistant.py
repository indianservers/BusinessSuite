from uuid import uuid4
from datetime import datetime, timedelta
import pytest
from tests.test_ai_operator import isolate_generic_http_audit
from app.apps.srm.models import SRMInvoice, SRMSalesOrder, SRMSalesOrderLine
from app.apps.srm.commercial_models import ProjectCommercial
from app.ai_operator.assistant_models import AssistantMessage
from app.ai_agents.models import AiAuditLog
from tests.test_connected_commercial import setup_business, link

BASE = "/api/v1/ai-operator/assistant"


@pytest.fixture(autouse=True)
def reset_limits():
    from app.ai_agents.services.rate_limit import AiRateLimitService

    AiRateLimitService._hits.clear()


def setup(client, db, headers):
    buyer, contact, project, team = setup_business(db)
    link(client, headers, buyer, contact, project, team)
    order = SRMSalesOrder(
        organization_id=1,
        order_number="ASSIST-ORDER",
        title="Implementation",
        customer_id=buyer.id,
        currency="INR",
        status="confirmed",
    )
    db.add(order)
    db.flush()
    db.add(
        SRMSalesOrderLine(
            sales_order_id=order.id,
            description="Service",
            quantity=1,
            unit_price=500000,
            tax_amount=90000,
            line_total=590000,
        )
    )
    db.get(ProjectCommercial, project.id).sales_order_id = order.id
    db.commit()
    response = client.post(BASE + "/conversations", headers=headers, json={})
    assert response.status_code == 201, response.text
    return buyer, project, response.json()["id"]


def prepare(client, headers, conversation, project, **extra):
    return client.post(
        f"{BASE}/conversations/{conversation}/messages",
        headers=headers,
        json={
            "request_key": str(uuid4()),
            "text": "Create an invoice for this project: 40% remaining, due in 15 days",
            "project_id": project.id,
            "intent": {
                "tool": "invoices.prepare",
                "project_id": project.id,
                "percentage": 40,
                **extra,
            },
        },
    )


def confirm(client, headers, conversation, message):
    return client.post(
        f"{BASE}/conversations/{conversation}/messages/{message['id']}/confirm",
        headers=headers,
        json={"approval_hash": message["approval_hash"]},
    )


def test_assistant_invoice_preview_confirm_replay_pdf_and_audit(
    client, db, superuser_headers
):
    buyer, project, conversation = setup(client, db, superuser_headers)
    response = prepare(client, superuser_headers, conversation, project)
    assert response.status_code == 200, response.text
    message = response.json()
    assert message["card"]["total"] == "236000.00"
    assert db.query(SRMInvoice).count() == 0
    saved = confirm(client, superuser_headers, conversation, message)
    assert saved.status_code == 200, saved.text
    assert saved.json()["status"] == "completed"
    invoice_id = saved.json()["card"]["id"]
    assert db.query(SRMInvoice).count() == 1
    assert (
        confirm(client, superuser_headers, conversation, message).json()["card"]["id"]
        == invoice_id
    )
    assert (
        client.get(
            f"/api/v1/srm/invoices/{invoice_id}", headers=superuser_headers
        ).status_code
        == 200
    )
    assert client.get(
        f"/api/v1/srm/invoices/{invoice_id}/pdf", headers=superuser_headers
    ).content.startswith(b"%PDF")
    assert (
        db.query(AiAuditLog).filter(AiAuditLog.action == "assistant.completed").count()
        == 1
    )
    assert (
        client.get(
            f"{BASE}/conversations/{conversation}", headers=superuser_headers
        ).json()["messages"][0]["card"]["id"]
        == invoice_id
    )
    second = prepare(client, superuser_headers, conversation, project).json()
    assert (
        second["card"]["previously_invoiced"] == "200000.00"
        and second["card"]["total"] == "141600.00"
    )


def test_assistant_stale_expired_and_unapproved_proposals(
    client, db, superuser_headers
):
    buyer, project, conversation = setup(client, db, superuser_headers)
    m = prepare(client, superuser_headers, conversation, project).json()
    assert (
        client.post(
            f"{BASE}/conversations/{conversation}/messages/{m['id']}/confirm",
            headers=superuser_headers,
            json={"approval_hash": "x" * 64},
        ).status_code
        == 409
    )
    row = db.get(AssistantMessage, m["id"])
    row.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    assert confirm(client, superuser_headers, conversation, m).status_code == 409
    m = prepare(client, superuser_headers, conversation, project).json()
    db.get(ProjectCommercial, project.id).contact_id = None
    db.commit()
    assert confirm(client, superuser_headers, conversation, m).status_code == 409
    assert db.query(SRMInvoice).count() == 0


def test_assistant_customer_ambiguity_and_unauthorized_history(
    client, db, superuser_headers
):
    from app.apps.crm.models import CRMCompany
    from app.core.security import create_access_token
    from app.models.user import User

    buyer, project, conversation = setup(client, db, superuser_headers)
    db.add(CRMCompany(organization_id=1, name=buyer.name))
    db.commit()
    result = client.post(
        f"{BASE}/conversations/{conversation}/messages",
        headers=superuser_headers,
        json={
            "request_key": str(uuid4()),
            "text": "Find shared buyer",
            "intent": {"tool": "customers.search", "query": "Shared"},
        },
    )
    assert result.status_code == 200, result.text
    assert len(result.json()["card"]["items"]) == 2
    user = User(
        email="not-owner@audit.invalid",
        hashed_password="unused",
        is_superuser=True,
        is_active=True,
    )
    db.add(user)
    db.commit()
    from app.models.user import UserSession
    from datetime import datetime,timedelta,timezone
    session=UserSession(user_id=user.id,session_token_hash="isolated-test-session",status="Active",expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
    db.add(session);db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(user.id,session_id=session.id)}"}
    assert (
        client.get(f"{BASE}/conversations/{conversation}", headers=headers).status_code
        == 404
    )


@pytest.mark.parametrize("query", ["Shared buyer", "Shared", "buyer", "Shared byer"])
def test_exact_partial_and_spelling_safe_customer_selection(
    client, db, superuser_headers, query
):
    buyer, project, conv = setup(client, db, superuser_headers)
    result = client.post(
        f"{BASE}/conversations/{conv}/messages",
        headers=superuser_headers,
        json={
            "request_key": str(uuid4()),
            "text": f"Find {query}",
            "intent": {"tool": "customers.search", "query": query},
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["card"]["items"][0]["id"] == buyer.id
    assert db.query(SRMInvoice).count() == 0


def test_mismatched_customer_tax_and_currency_are_rejected(
    client, db, superuser_headers
):
    from app.apps.crm.models import CRMCompany

    buyer, project, conv = setup(client, db, superuser_headers)
    other = CRMCompany(organization_id=1, name="Other customer")
    db.add(other)
    db.commit()
    assert (
        prepare(
            client, superuser_headers, conv, project, customer_id=other.id
        ).status_code
        == 422
    )
    ctx = db.get(ProjectCommercial, project.id)
    ctx.sales_order_id = None
    db.commit()
    assert prepare(client, superuser_headers, conv, project).status_code == 422
    data = {"tool": "invoices.prepare", "project_id": project.id, "amount": 100}
    response = client.post(
        f"{BASE}/conversations/{conv}/messages",
        headers=superuser_headers,
        json={
            "request_key": str(uuid4()),
            "text": "Create invoice plus GST",
            "intent": data,
        },
    )
    assert response.status_code == 422 and "tax" in response.text
    ctx.currency = "KWD"
    db.commit()
    assert (
        prepare(
            client,
            superuser_headers,
            conv,
            project,
            percentage=None,
            amount=100,
            tax_amount=0,
        ).status_code
        == 422
    )


def test_stream_and_edited_request_key_validation(client, db, superuser_headers):
    buyer, project, conv = setup(client, db, superuser_headers)
    payload = {
        "request_key": str(uuid4()),
        "text": "Create invoice for this project: 40% remaining",
        "project_id": project.id,
    }
    result = client.post(
        f"{BASE}/conversations/{conv}/messages/stream",
        headers=superuser_headers,
        json=payload,
    )
    assert (
        result.status_code == 200
        and "event: status" in result.text
        and "event: result" in result.text
    )
    assert db.query(SRMInvoice).count() == 0
    assert (
        client.post(
            f"{BASE}/conversations/{conv}/messages",
            headers=superuser_headers,
            json={
                **payload,
                "intent": {"tool": "projects.create", "title": "Changed request"},
            },
        ).status_code
        == 409
    )


def test_project_and_task_tools_use_normal_pms_records(client, db, superuser_headers):
    from app.apps.project_management.models import PMSProject, PMSTask

    buyer, project, conv = setup(client, db, superuser_headers)
    for intent in [
        {"tool": "projects.create", "title": "Assistant-created project"},
        {
            "tool": "tasks.create",
            "project_id": project.id,
            "title": "Assistant-created task",
        },
    ]:
        response = client.post(
            f"{BASE}/conversations/{conv}/messages",
            headers=superuser_headers,
            json={
                "request_key": str(uuid4()),
                "text": "Prepare reviewed action",
                "intent": intent,
            },
        )
        assert response.status_code == 200, response.text
        message = response.json()
        assert message["status"] == "awaiting_approval"
        result = confirm(client, superuser_headers, conv, message)
        assert result.status_code == 200, result.text
        assert confirm(client, superuser_headers, conv, message).status_code == 200
    assert db.query(PMSProject).filter_by(name="Assistant-created project").count() == 1
    assert db.query(PMSTask).filter_by(title="Assistant-created task").count() == 1


def test_invoice_issue_and_send_each_require_separate_approval(
    client, db, superuser_headers, monkeypatch
):
    from app.core.config import settings

    buyer, project, conv = setup(client, db, superuser_headers)
    m = prepare(client, superuser_headers, conv, project).json()
    saved = confirm(client, superuser_headers, conv, m).json()
    invoice_id = saved["card"]["id"]
    monkeypatch.setattr(settings, "COMMUNICATION_EMAIL_PROVIDER", "stub")
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    for tool in ["invoices.issue", "invoices.send"]:
        response = client.post(
            f"{BASE}/conversations/{conv}/messages",
            headers=superuser_headers,
            json={
                "request_key": str(uuid4()),
                "text": f"Review {tool}",
                "intent": {"tool": tool, "invoice_id": invoice_id},
            },
        )
        assert response.status_code == 200, response.text
        db.expire_all()
        assert db.get(SRMInvoice, invoice_id).sent_at is None
        done = confirm(client, superuser_headers, conv, response.json())
        assert done.status_code == 200, done.text
    db.expire_all()
    assert db.get(SRMInvoice, invoice_id).sent_at is not None


def test_revoked_financial_permission_and_changed_tenant_cannot_use_history(
    client, db, superuser_headers
):
    from ai_test_utils import auth_headers
    from app.common.models import CommonPerson

    buyer, project, _ = setup(client, db, superuser_headers)
    headers, user = auth_headers(
        client,
        db,
        email="assistant-limited@example.com",
        permissions=["ai_assistant", "pms_view", "srm_invoice_create"],
    )
    conv = client.post(BASE + "/conversations", headers=headers, json={}).json()["id"]
    response = prepare(client, headers, conv, project)
    assert response.status_code == 200, response.text
    m = response.json()
    user.role.permissions = [
        p for p in user.role.permissions if p.name != "srm_invoice_create"
    ]
    db.commit()
    assert confirm(client, headers, conv, m).status_code == 404
    history = client.get(f"{BASE}/conversations/{conv}", headers=headers)
    assert history.status_code == 404
    from app.models.company import Company
    if not db.get(Company,2):db.add(Company(id=2,name="Other isolated tenant"));db.flush()
    db.add(
        CommonPerson(
            user_id=user.id, organization_id=2, display_name="Tenant reassigned"
        )
    )
    db.commit()
    assert (
        client.get(f"{BASE}/conversations/{conv}", headers=headers).status_code == 404
    )


def test_assistant_migrations_replay_without_changing_business_ids(tmp_path):
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine, inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.db.base_class import Base

    engine = create_engine("sqlite:///" + str(tmp_path / "assistant-upgrade.db"))
    Base.metadata.create_all(
        engine,
        tables=[
            table
            for name, table in Base.metadata.tables.items()
            if not name.startswith("pms_assistant_")
        ],
    )
    for folder, name in [
        ("alembic", "20261024_007_assistant.py"),
        ("alembic_postgresql", "pg_20261024_007_assistant.py"),
    ]:
        spec = importlib.util.spec_from_file_location(
            "assistant_migration",
            Path(__file__).parents[1] / folder / "versions" / name,
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
                module.upgrade()
        assert {"pms_assistant_conversations", "pms_assistant_messages"}.issubset(
            set(inspect(engine).get_table_names())
        )
    engine.dispose()


def test_natural_invoice_request_resolves_customer_then_project_before_creating(
    client, db, superuser_headers
):
    buyer, project, conv = setup(client, db, superuser_headers)
    url = f"{BASE}/conversations/{conv}/messages"
    request = {
        "request_key": str(uuid4()),
        "text": "Create an invoice for Shared buyer for the Connected project for INR 75000 plus GST",
    }
    found = client.post(url, headers=superuser_headers, json=request)
    assert found.status_code == 200, found.text
    assert (
        found.json()["card"]["kind"] == "selection"
        and db.query(SRMInvoice).count() == 0
    )
    intent = found.json()["card"]["next"]
    intent.update(customer_id=buyer.id, query="")
    selected = client.post(
        url,
        headers=superuser_headers,
        json={
            "request_key": str(uuid4()),
            "text": "Selected customer",
            "intent": intent,
        },
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["card"]["kind"] == "invoice_preview"
    assert selected.json()["card"]["project_id"] == project.id
    assert selected.json()["card"]["total"] == "88500.00"
    assert confirm(client, superuser_headers, conv, selected.json()).status_code == 200
    assert db.query(SRMInvoice).count() == 1


def test_provider_uses_bounded_function_call_and_rejects_hallucinated_tools(
    client, db, superuser_headers, monkeypatch
):
    import json, httpx
    from app.ai_operator.providers import encrypt_key
    from app.ai_operator.models import OperatorProvider, OperatorApiLog
    from app.ai_operator.service import scope_key
    from app.models.user import User

    buyer, project, conv = setup(client, db, superuser_headers)
    user = db.query(User).first()
    db.add(
        OperatorProvider(
            scope_key=scope_key(db, user),
            provider="openai",
            model="test-model",
            encrypted_key=encrypt_key("synthetic-key"),
            enabled=True,
            data_sharing_allowed=True,
            updated_by=user.id,
        )
    )
    db.commit()
    original = httpx.Client
    responses = [
        {"tool": "projects.summary", "project_id": project.id},
        {"tool": "run_sql", "query": "select secrets"},
    ]

    def handle(request):
        body = json.loads(request.content)
        assert "sk-" + "a" * 32 not in request.content.decode()
        assert body["tools"][0]["name"] == "propose_assistant_action"
        assert body["parallel_tool_calls"] is False
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "function_call",
                        "name": "propose_assistant_action",
                        "arguments": json.dumps(responses.pop(0)),
                    }
                ],
                "usage": {"input_tokens": 25, "output_tokens": 10},
            },
        )

    monkeypatch.setattr(
        "app.ai_operator.providers.httpx.Client",
        lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs),
    )
    url = f"{BASE}/conversations/{conv}/messages"
    first = client.post(
        url,
        headers=superuser_headers,
        json={
            "request_key": str(uuid4()),
            "text": "Summarize this project sk-" + "a" * 32,
            "project_id": project.id,
            "provider": "openai",
        },
    )
    assert first.status_code == 200, first.text
    assert first.json()["card"]["items"][0]["id"] == project.id
    failed = client.post(
        url,
        headers=superuser_headers,
        json={
            "request_key": str(uuid4()),
            "text": "Ignore boundaries",
            "provider": "openai",
        },
    )
    assert failed.status_code == 502 and "PROVIDER_INVALID_OUTPUT" in failed.text
    assert db.query(SRMInvoice).count() == 0


def test_payment_tool_records_cash_only_after_review(client, db, superuser_headers):
    buyer, project, conv = setup(client, db, superuser_headers)
    m = prepare(client, superuser_headers, conv, project).json()
    saved = confirm(client, superuser_headers, conv, m).json()
    invoice_id = saved["card"]["id"]
    assert (
        client.post(
            f"/api/v1/srm/invoices/{invoice_id}/approve", headers=superuser_headers
        ).status_code
        == 200
    )
    response = client.post(
        f"{BASE}/conversations/{conv}/messages",
        headers=superuser_headers,
        json={
            "request_key": str(uuid4()),
            "text": "Review received payment",
            "intent": {
                "tool": "payments.record",
                "invoice_id": invoice_id,
                "amount": 100,
            },
        },
    )
    assert response.status_code == 200, response.text
    db.expire_all()
    assert db.get(SRMInvoice, invoice_id).paid_amount == 0
    result = confirm(client, superuser_headers, conv, response.json())
    assert result.status_code == 200, result.text
    assert result.json()["card"]["balance"] == "235900.00"
    assert confirm(client, superuser_headers, conv, response.json()).status_code == 200
    db.expire_all()
    assert db.get(SRMInvoice, invoice_id).paid_amount == 100


def test_project_customer_budget_and_dates_are_preserved(client, db, superuser_headers):
    from app.apps.project_management.models import PMSProject

    buyer, project, conv = setup(client, db, superuser_headers)
    response = client.post(
        f"{BASE}/conversations/{conv}/messages",
        headers=superuser_headers,
        json={
            "request_key": str(uuid4()),
            "text": "Prepare linked project",
            "intent": {
                "tool": "projects.create",
                "title": "Linked AI project",
                "customer_id": buyer.id,
                "seller_id": 1,
                "currency": "INR",
                "amount": 300000,
                "start_date": "2026-11-01",
                "due_date": "2026-12-01",
            },
        },
    )
    assert response.status_code == 200, response.text
    result = confirm(client, superuser_headers, conv, response.json())
    assert result.status_code == 200, result.text
    ident = result.json()["card"]["project_id"]
    db.expire_all()
    assert db.get(ProjectCommercial, ident).customer_id == buyer.id
    assert db.get(PMSProject, ident).budget_amount == 300000
    assert str(db.get(PMSProject, ident).start_date) == "2026-11-01"


def test_invoice_service_can_join_confirmation_transaction(
    client, db, superuser_headers
):
    from app.apps.srm.commercial_api import draft_project_invoice_service, DraftInput
    from app.models.user import User

    buyer, project, conv = setup(client, db, superuser_headers)
    user = db.query(User).first()
    with db.begin_nested() as nested:
        result = draft_project_invoice_service(
            project.id,
            DraftInput(
                request_id=uuid4(),
                lines=[{"description": "Atomic preview approval", "unit_price": 100}],
            ),
            db,
            user,
            commit=False,
        )
        assert db.query(SRMInvoice).filter_by(id=result["id"]).count() == 1
        nested.rollback()
    assert db.query(SRMInvoice).count() == 0


def test_history_management_and_stream_failure_are_truthful(
    client, db, superuser_headers
):
    buyer, project, conv = setup(client, db, superuser_headers)
    response = client.post(
        f"{BASE}/conversations/{conv}/messages/stream",
        headers=superuser_headers,
        json={
            "request_key": str(uuid4()),
            "text": "Summarize this project",
            "project_id": project.id,
            "provider": "openai",
        },
    )
    assert "event: failure" in response.text and "not configured" in response.text
    assert db.query(SRMInvoice).count() == 0
    renamed = client.patch(
        f"{BASE}/conversations/{conv}",
        headers=superuser_headers,
        json={"title": "Billing review"},
    )
    assert renamed.status_code == 200
    assert (
        client.get(BASE + "/conversations?q=Billing", headers=superuser_headers).json()[
            0
        ]["id"]
        == conv
    )
    assert (
        client.delete(
            f"{BASE}/conversations/{conv}", headers=superuser_headers
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"{BASE}/conversations/{conv}", headers=superuser_headers
        ).status_code
        == 404
    )


def test_assignment_proposal_targets_only_current_project_collaborators(
    client, db, superuser_headers
):
    from app.apps.project_management.models import PMSTask
    from app.models.user import User

    buyer, project, conv = setup(client, db, superuser_headers)
    user = db.query(User).first()
    task = PMSTask(
        project_id=project.id, task_key="ASSIST-ASSIGN", title="Assign reviewed task"
    )
    db.add(task)
    db.commit()
    response = client.post(
        f"{BASE}/conversations/{conv}/messages",
        headers=superuser_headers,
        json={
            "request_key": str(uuid4()),
            "text": "Review assignment",
            "intent": {
                "tool": "tasks.assign",
                "project_id": project.id,
                "task_id": task.id,
                "assignee_id": user.id,
            },
        },
    )
    assert response.status_code == 200, response.text
    assert confirm(client, superuser_headers, conv, response.json()).status_code == 200
    db.refresh(task)
    assert task.assignee_user_ids == [user.id]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Create invoice for this project for INR 8 lakh", 800000),
        ("Create invoice for this project for INR 75k", 75000),
    ],
)
def test_guided_currency_multipliers_are_not_treated_as_single_units(text, expected):
    from app.ai_operator.assistant_api import parse_local

    assert parse_local(text, 1).amount == expected
