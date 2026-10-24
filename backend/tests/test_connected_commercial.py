from datetime import date
from uuid import uuid4
from decimal import Decimal

from app.apps.crm.models import CRMCompany, CRMContact, CRMTeam, CRMOwner
from app.apps.project_management.models import PMSProject, PMSTimeLog
from app.apps.srm.models import SRMInvoice, SRMInvoiceLine
from app.apps.srm.commercial_models import InvoiceContext, TimeBillingAllocation
from app.models.company import Company
from app.models.user import User
from app.common.models import CommonPerson
from app.core.config import settings
from tests.srm_test_utils import auth_headers_for


def setup_business(db):
    owner = db.query(User).first()
    if not db.get(Company, 1):
        db.add(
            Company(
                id=1,
                name="Test seller",
                legal_name="Seller Pvt Ltd",
                address="Seller address",
            )
        )
    buyer = CRMCompany(
        organization_id=1,
        name="Shared buyer",
        email="billing@example.invalid",
        address="Original address",
        owner_user_id=owner.id,
    )
    team = CRMTeam(organization_id=1, name="Shared delivery team", status="Active")
    db.add_all([buyer, team])
    db.flush()
    contact = CRMContact(
        organization_id=1,
        company_id=buyer.id,
        first_name="Test",
        full_name="Test billing",
        email="billing@example.invalid",
    )
    p = PMSProject(
        organization_id=1,
        name="Connected project",
        project_key="CONNECTED",
        manager_user_id=owner.id,
    )
    db.add_all([contact, p])
    db.flush()
    db.add(
        CRMOwner(
            organization_id=1,
            user_id=owner.id,
            team_id=team.id,
            full_name="Owner",
            email=owner.email,
            status="Active",
        )
    )
    db.commit()
    return buyer, contact, p, team


def link(client, headers, buyer, contact, project, team):
    response = client.put(
        f"/api/v1/project-management/projects/{project.id}/commercial",
        headers=headers,
        json={
            "customer_id": buyer.id,
            "contact_id": contact.id,
            "seller_id": 1,
            "team_id": team.id,
            "currency": "INR",
        },
    )
    assert response.status_code == 200, response.text


def test_one_invoice_customer_snapshot_payment_and_truthful_delivery(
    client, db, superuser_headers, monkeypatch
):
    buyer, contact, project, team = setup_business(db)
    link(client, superuser_headers, buyer, contact, project, team)
    payload = {
        "request_id": str(uuid4()),
        "lines": [
            {
                "description": "Consulting",
                "quantity": "2",
                "unit_price": "100.10",
                "tax_amount": "36.04",
            }
        ],
    }
    url = f"/api/v1/project-management/projects/{project.id}/invoices"
    draft = client.post(url, headers=superuser_headers, json=payload)
    assert draft.status_code == 201, draft.text
    invoice = draft.json()
    ident = invoice["id"]
    assert invoice["total_amount"] == 236.24
    assert (
        client.post(url, headers=superuser_headers, json=payload).json()["id"] == ident
    )
    assert db.query(SRMInvoice).count() == 1
    assert (
        client.get("/api/v1/srm/invoices", headers=superuser_headers).json()[0]["id"]
        == ident
    )
    assert (
        client.get(
            f"/api/v1/srm/business/customers/{buyer.id}/history",
            headers=superuser_headers,
        ).json()["invoices"][0]["invoice_number"]
        == invoice["invoice_number"]
    )
    assert (
        client.post(
            f"/api/v1/srm/invoices/{ident}/approve", headers=superuser_headers
        ).status_code
        == 200
    )
    buyer.address = "Changed current address"
    db.commit()
    assert (
        db.get(InvoiceContext, ident).customer_snapshot["address"] == "Original address"
    )
    assert (
        client.patch(
            f"/api/v1/srm/invoices/{ident}",
            headers=superuser_headers,
            json={"total_amount": 1},
        ).status_code
        == 409
    )
    monkeypatch.setattr(settings, "COMMUNICATION_EMAIL_PROVIDER", "")
    failed = client.post(
        f"/api/v1/srm/invoices/{ident}/send", headers=superuser_headers
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()["delivery"]["status"] == "blocked"
    assert failed.json()["status"] == "approved"
    monkeypatch.setattr(settings, "COMMUNICATION_EMAIL_PROVIDER", "stub")
    sent = client.post(f"/api/v1/srm/invoices/{ident}/send", headers=superuser_headers)
    assert sent.json()["delivery"]["status"] == "sent", sent.text
    again = client.post(f"/api/v1/srm/invoices/{ident}/send", headers=superuser_headers)
    assert again.json()["delivery"]["id"] == sent.json()["delivery"]["id"]
    pdf = client.get(f"/api/v1/srm/invoices/{ident}/pdf", headers=superuser_headers)
    assert pdf.content.startswith(b"%PDF-") and b"xref" in pdf.content
    receipt = client.post(
        "/api/v1/srm/receipts",
        headers=superuser_headers,
        json={"customer_id": buyer.id, "amount": 100, "currency": "INR"},
    ).json()
    payment = client.post(
        f"/api/v1/srm/receipts/{receipt['id']}/allocate",
        headers=superuser_headers,
        json={"invoice_id": ident, "amount": 100},
    )
    assert payment.status_code == 200, payment.text
    summary = client.get(
        f"/api/v1/project-management/projects/{project.id}/billing",
        headers=superuser_headers,
    ).json()
    assert summary["invoices"][0]["balance_amount"] == 136.24
    assert summary["invoices"][0]["payment_status"] == "partially_paid"
    assert summary["customer"]["address"] == "Changed current address"
    assert client.get(
        "/api/v1/project-management/business/teams", headers=superuser_headers
    ).json()[0]["members"][0]["active"]


def test_partial_time_reservations_and_server_totals(client, db, superuser_headers):
    buyer, contact, project, team = setup_business(db)
    link(client, superuser_headers, buyer, contact, project, team)
    log = PMSTimeLog(
        project_id=project.id,
        user_id=project.manager_user_id,
        log_date=date.today(),
        duration_minutes=120,
        is_billable=True,
        approval_status="Approved",
    )
    db.add(log)
    db.commit()

    def bill(minutes):
        return client.post(
            f"/api/v1/project-management/projects/{project.id}/invoices",
            headers=superuser_headers,
            json={
                "request_id": str(uuid4()),
                "time_log_ids": [log.id],
                "time_minutes": {str(log.id): minutes},
                "hourly_rate": "100.10",
            },
        )

    first = bill(30)
    assert first.status_code == 201, first.text
    assert first.json()["total_amount"] == 50.05
    assert bill(100).status_code == 409
    assert bill(90).status_code == 201
    assert bill(1).status_code == 409
    assert db.query(TimeBillingAllocation).count() == 2
    bad = client.post(
        f"/api/v1/project-management/projects/{project.id}/invoices",
        headers=superuser_headers,
        json={
            "request_id": str(uuid4()),
            "lines": [
                {
                    "description": "Spoof",
                    "unit_price": 100,
                    "quantity": 1,
                    "line_total": 1,
                }
            ],
        },
    )
    assert bad.status_code == 422


def test_financial_permissions_and_tenant_boundaries(client, db, superuser_headers):
    buyer, contact, project, team = setup_business(db)
    link(client, superuser_headers, buyer, contact, project, team)
    inv = client.post(
        f"/api/v1/project-management/projects/{project.id}/invoices",
        headers=superuser_headers,
        json={
            "request_id": str(uuid4()),
            "lines": [{"description": "Fee", "unit_price": 10}],
        },
    ).json()
    headers = auth_headers_for(
        client,
        db,
        "tasks@example.com",
        "srm_viewer",
        permissions=["pms_manage_tasks", "srm_view"],
    )
    assert (
        client.get(
            f"/api/v1/project-management/projects/{project.id}/billing", headers=headers
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/srm/invoices/{inv['id']}/approve", headers=headers
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/srm/invoices/{inv['id']}/send", headers=headers
        ).status_code
        == 403
    )
    other = auth_headers_for(
        client,
        db,
        "finance2@example.com",
        "srm_finance_manager",
        permissions=["srm_invoice_view", "srm_invoice_create", "srm_invoice_approve"],
    )
    u = db.query(User).filter_by(email="finance2@example.com").one()
    db.add(CommonPerson(user_id=u.id, organization_id=2, display_name="Other tenant"))
    db.commit()
    assert (
        client.get(f"/api/v1/srm/invoices/{inv['id']}", headers=other).status_code
        == 404
    )
    assert client.get("/api/v1/srm/invoices", headers=other).json() == []
    assert (
        client.get(f"/api/v1/srm/invoices/{inv['id']}/pdf", headers=other).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/srm/business/customers/{buyer.id}/history", headers=other
        ).status_code
        == 404
    )
    denied = client.put(
        f"/api/v1/project-management/projects/{project.id}/commercial",
        headers=superuser_headers,
        json={"customer_id": buyer.id, "seller_id": 999, "currency": "INR"},
    )
    assert denied.status_code == 403


def test_crm_account_customer_projection_and_reviewed_legacy_mapping(
    client, db, superuser_headers
):
    from app.apps.project_management.models import PMSClient
    from app.apps.srm.commercial_models import CustomerLink

    response = client.post(
        "/api/v1/crm/account-registry",
        headers=superuser_headers,
        json={
            "account_name": "Created in CRM",
            "billing_address": "Account billing address",
        },
    )
    assert response.status_code == 201, response.text
    account = response.json()
    shared_id = account["shared_customer_id"]
    assert (
        client.get("/api/v1/srm/business/customers", headers=superuser_headers).json()[
            "items"
        ][0]["id"]
        == shared_id
    )
    assert (
        client.get(
            "/api/v1/project-management/business/customers", headers=superuser_headers
        ).json()["items"][0]["id"]
        == shared_id
    )
    legacy = PMSClient(organization_id=None, name="Old client spelling")
    db.add(legacy)
    db.commit()
    linked = client.put(
        f"/api/v1/project-management/clients/{legacy.id}/shared-customer",
        headers=superuser_headers,
        json={"customer_id": shared_id},
    )
    assert linked.status_code == 200, linked.text
    changed = client.patch(
        "/api/v1/crm/accounts/" + str(shared_id),
        headers=superuser_headers,
        json={"name": "Updated canonical buyer", "address": "Updated current address"},
    )
    assert changed.status_code == 200, changed.text
    directory = client.get(
        "/api/v1/srm/business/customers", headers=superuser_headers
    ).json()
    assert directory["items"][0]["name"] == "Updated canonical buyer"
    db.refresh(legacy)
    assert legacy.name == "Updated canonical buyer"
    assert db.query(CustomerLink).count() == 2
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "reconcile_commercial",
        Path(__file__).parents[1] / "scripts/reconcile_commercial_identity.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    count = db.query(CustomerLink).count()
    report = module.reconcile(db, 1)
    assert report["dry_run"] and db.query(CustomerLink).count() == count


def test_parallel_requests_keep_one_invoice_and_unique_numbers(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db.base_class import Base
    from app.apps.srm.commercial_models import ProjectCommercial
    from app.apps.srm.commercial_api import draft, DraftInput

    engine = create_engine(
        "sqlite:///" + str(tmp_path / "concurrent.db"), connect_args={"timeout": 20}
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        user = User(
            email="synthetic@example.com",
            hashed_password="unused",
            is_superuser=True,
            is_active=True,
        )
        buyer = CRMCompany(organization_id=1, name="Concurrent synthetic customer")
        db.add_all([user, buyer, Company(id=1, name="Synthetic seller")])
        db.flush()
        p = PMSProject(
            organization_id=1,
            name="Concurrent project",
            project_key="CONCUR",
            manager_user_id=user.id,
        )
        db.add(p)
        db.flush()
        db.add(
            ProjectCommercial(
                project_id=p.id, customer_id=buyer.id, seller_id=1, currency="INR"
            )
        )
        db.commit()
        project_id, user_id = p.id, user.id
    key = str(uuid4())

    def create(key):
        with sessions() as db:
            user = db.get(User, user_id)
            return draft(
                project_id,
                DraftInput(
                    request_id=key,
                    lines=[
                        {
                            "description": "Concurrent fee",
                            "quantity": 1,
                            "unit_price": 10,
                        }
                    ],
                ),
                db,
                user,
            )

    with ThreadPoolExecutor(max_workers=6) as workers:
        repeated = list(workers.map(create, [key] * 6))
        separate = list(workers.map(create, [str(uuid4()) for _ in range(6)]))
    assert len({r["id"] for r in repeated}) == 1
    assert len({r["invoice_number"] for r in separate}) == 6
    with sessions() as db:
        assert db.query(SRMInvoice).count() == 7
    engine.dispose()


def test_migration_replay_preserves_legacy_documents_and_expands_precision(tmp_path):
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine, inspect, text
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.db.base_class import Base

    engine = create_engine("sqlite:///" + str(tmp_path / "legacy.db"))
    Base.metadata.create_all(
        engine,
        tables=[
            t
            for t in Base.metadata.tables.values()
            if not t.name.startswith("business_") and t.name != "srm_invoice_lines"
        ],
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE srm_invoice_lines (id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL REFERENCES srm_invoices(id), source_type VARCHAR(60), source_id INTEGER, description TEXT NOT NULL, quantity NUMERIC(12,2), unit_price NUMERIC(14,2), tax_amount NUMERIC(14,2), line_total NUMERIC(14,2), CONSTRAINT uq_srm_invoice_line_source UNIQUE(source_type,source_id))"
            )
        )
        connection.execute(
            text(
                "INSERT INTO srm_invoices (id, invoice_number, status, currency, total_amount, paid_amount, balance_amount) VALUES (123, 'INV-004321', 'paid', 'INR', 12.12,12.12,0)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO srm_invoice_lines (id,invoice_id,source_type,source_id,description,quantity,unit_price,tax_amount,line_total) VALUES (321,123,'legacy',45,'Historical line',12.12,1,0,12.12)"
            )
        )
        root = Path(__file__).parents[1]
        for folder, name in [
            ("alembic/versions", "20261024_006_commercial.py"),
            ("alembic_postgresql/versions", "pg_20261024_006_commercial.py"),
        ]:
            spec = importlib.util.spec_from_file_location(
                name.replace(".", "_"), root / folder / name
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
                module.upgrade()
        row = connection.execute(
            text(
                "SELECT invoice_number,status,total_amount,paid_amount FROM srm_invoices WHERE id=123"
            )
        ).one()
        assert tuple(row) == ("INV-004321", "paid", 12.12, 12.12)
        line = connection.execute(
            text(
                "SELECT id,source_id,quantity,line_total,discount_amount FROM srm_invoice_lines WHERE id=321"
            )
        ).one()
        assert tuple(line) == (321, 45, 12.12, 12.12, 0)
        columns = {
            c["name"]: c for c in inspect(connection).get_columns("srm_invoice_lines")
        }
        assert columns["quantity"]["type"].scale == 10
    engine.dispose()


def test_configured_smtp_path_uses_shared_delivery_and_does_not_send_twice(
    client, db, superuser_headers, monkeypatch
):
    buyer, contact, project, team = setup_business(db)
    link(client, superuser_headers, buyer, contact, project, team)
    invoice = client.post(
        f"/api/v1/project-management/projects/{project.id}/invoices",
        headers=superuser_headers,
        json={
            "request_id": str(uuid4()),
            "lines": [{"description": "SMTP synthetic verification", "unit_price": 10}],
        },
    ).json()
    assert (
        client.post(
            f"/api/v1/srm/invoices/{invoice['id']}/approve", headers=superuser_headers
        ).status_code
        == 200
    )
    calls = []

    class SandboxSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def starttls(self):
            pass

        def login(self, *args):
            pass

        def send_message(self, message, to_addrs):
            calls.append(message)
            assert to_addrs == [contact.email]
            attachments = list(message.iter_attachments())
            assert len(attachments) == 1 and attachments[0].get_payload(
                decode=True
            ).startswith(b"%PDF")
            return {}

    import smtplib

    monkeypatch.setattr(smtplib, "SMTP", SandboxSMTP)
    for key, value in {
        "COMMUNICATION_EMAIL_PROVIDER": "smtp",
        "MAIL_USERNAME": "synthetic",
        "MAIL_PASSWORD": "synthetic-test-value",
        "MAIL_FROM": "sender@example.invalid",
        "MAIL_SSL_TLS": False,
    }.items():
        monkeypatch.setattr(settings, key, value)
    response = client.post(
        f"/api/v1/srm/invoices/{invoice['id']}/send", headers=superuser_headers
    )
    assert response.json()["delivery"]["status"] == "sent", response.text
    client.post(f"/api/v1/srm/invoices/{invoice['id']}/send", headers=superuser_headers)
    assert len(calls) == 1
    message_id = response.json()["delivery"]["message_id"]
    headers = auth_headers_for(
        client,
        db,
        "communications@example.com",
        "srm_viewer",
        permissions=["communication_view", "communication_email_send"],
    )
    assert (
        client.get(
            f"/api/v1/communication/emails/{message_id}", headers=headers
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/v1/communication/timeline/srm_invoice/{invoice['id']}",
            headers=headers,
        ).status_code
        == 403
    )
    logs = client.get("/api/v1/communication/delivery-logs", headers=headers)
    assert logs.status_code == 200
    assert all(row["related_message_id"] != message_id for row in logs.json()["items"])
    assert (
        client.post(
            "/api/v1/communication/emails/send",
            headers=headers,
            json={
                "related_record_type": "srm_invoice",
                "related_record_id": invoice["id"],
                "to_email": "blocked@example.com",
                "subject": "Forged invoice send",
                "body": "Must use invoice service",
            },
        ).status_code
        == 409
    )


def test_milestone_and_whole_order_cannot_bill_same_obligation(
    client, db, superuser_headers
):
    from tests.srm_test_utils import create_engagement_via_confirm
    from app.apps.srm.models import SRMBillingMilestone

    engagement, order = create_engagement_via_confirm(client, superuser_headers)
    milestone = db.query(SRMBillingMilestone).first()
    milestone.status = "approved"
    db.commit()
    first = client.post(
        f"/api/v1/srm/invoices/draft-from-billing-milestone/{milestone.id}",
        headers=superuser_headers,
    )
    assert first.status_code == 201, first.text
    assert (
        client.post(
            f"/api/v1/srm/invoices/draft-from-sales-order/{order['id']}",
            headers=superuser_headers,
        ).status_code
        == 409
    )


def test_atomic_payment_retry_reversal_and_cancellation(client, db, superuser_headers):
    from app.apps.srm.models import SRMReceipt
    buyer, contact, project, team = setup_business(db)
    link(client, superuser_headers, buyer, contact, project, team)
    invoice = client.post(f"/api/v1/project-management/projects/{project.id}/invoices", headers=superuser_headers, json={"request_id": str(uuid4()), "lines": [{"description": "Receipt workflow", "unit_price": 100}]}).json()
    assert client.post(f"/api/v1/srm/invoices/{invoice['id']}/approve", headers=superuser_headers).status_code == 200
    data = {"request_id": str(uuid4()), "amount": "40", "reference": "Synthetic transaction"}
    url = f"/api/v1/srm/business/invoices/{invoice['id']}/payments"
    first = client.post(url, headers=superuser_headers, json=data)
    assert first.status_code == 201, first.text
    repeated = client.post(url, headers=superuser_headers, json=data)
    assert repeated.json()["receipt_id"] == first.json()["receipt_id"]
    assert db.query(SRMReceipt).count() == 1
    billing = client.get(f"/api/v1/project-management/projects/{project.id}/billing", headers=superuser_headers).json()
    assert billing["invoices"][0]["balance_amount"] == 60
    assert client.post(f"/api/v1/srm/business/invoices/{invoice['id']}/cancel", headers=superuser_headers, json={"reason": "Paid invoice must not cancel"}).status_code == 409
    receipt_id = first.json()["receipt_id"]
    reverse = client.post(f"/api/v1/srm/business/payments/{receipt_id}/reverse", headers=superuser_headers, json={"reason": "Synthetic payment entered in error"})
    assert reverse.status_code == 200, reverse.text
    assert reverse.json()["invoice"]["balance_amount"] == 100
    assert client.post(f"/api/v1/srm/business/payments/{receipt_id}/reverse", headers=superuser_headers, json={"reason": "Retry"}).json()["invoice"]["balance_amount"] == 100
    cancel = client.post(f"/api/v1/srm/business/invoices/{invoice['id']}/cancel", headers=superuser_headers, json={"reason": "Synthetic cancellation after reversal"})
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["document_status"] == "cancelled"
    assert cancel.json()["payment_status"] == "not_payable"
    assert db.query(SRMInvoice).one().total_amount == Decimal("100")


def test_commercial_handoff_carries_customer_contact_team_and_origin(client, db, superuser_headers):
    from tests.test_srm_crm_won_handoff import create_won_deal_with_quote
    from app.apps.srm.commercial_models import ProjectCommercial, MilestoneBillingSource
    buyer, contact, independent, team = setup_business(db)
    deal, quote = create_won_deal_with_quote(db, "Canonical handoff")
    deal.company_id, deal.contact_id = buyer.id, contact.id
    buyer.assigned_team_id = team.id
    db.commit()
    handoff = client.post(f"/api/v1/srm/from-crm/deals/{deal.id}/create-sales-order", headers=superuser_headers)
    assert handoff.status_code == 201, handoff.text
    order = handoff.json()["sales_order"]
    engagement = handoff.json()["engagement"]
    client.post(f"/api/v1/srm/sales-orders/{order['id']}/submit", headers=superuser_headers)
    client.post(f"/api/v1/srm/sales-orders/{order['id']}/approve", headers=superuser_headers)
    assert client.post(f"/api/v1/srm/sales-orders/{order['id']}/confirm", headers=superuser_headers).status_code == 200
    created = client.post(f"/api/v1/srm/engagements/{engagement['id']}/create-pms-project", headers=superuser_headers)
    assert created.status_code == 200, created.text
    project_id = created.json()["project"]["id"]
    ctx = db.get(ProjectCommercial, project_id)
    assert (ctx.customer_id, ctx.contact_id, ctx.team_id, ctx.seller_id) == (buyer.id, contact.id, team.id, 1)
    assert (ctx.opportunity_id, ctx.sales_order_id, ctx.engagement_id) == (deal.id, order["id"], engagement["id"])
    assert db.query(CRMCompany).count() == 1
    assert db.query(MilestoneBillingSource).count() > 0
    again = client.post(f"/api/v1/srm/engagements/{engagement['id']}/create-pms-project", headers=superuser_headers)
    assert again.json()["project"]["id"] == project_id
    related = client.get(f"/api/v1/srm/business/related-projects?engagement_id={engagement['id']}", headers=superuser_headers)
    assert related.json()[0]["id"] == project_id
