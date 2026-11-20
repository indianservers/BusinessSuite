from datetime import date, datetime, timedelta, timezone

from app.apps.crm.models import CRMAccount, CRMCompany, CRMQuotation
from app.apps.project_management.models import PMSProject
from app.apps.saas.models import PortalActivityLog, PortalCustomerLink, PortalUser
from app.apps.srm.models import SRMEngagement, SRMInvoice
from phase10_test_utils import auth_headers, invite_portal
from test_identity_utils import own_workflow_records


def test_customer_portal_invite_profile_and_safe_empty_records(client, db):
    headers = auth_headers(client, db)
    invited = invite_portal(client, db, headers, "customer", "cust1@example.com", customer_id=501)
    portal_headers = {"X-Portal-Session": invited["one_time_session_token"]}

    me = client.get("/api/v1/customer-portal/me", headers=portal_headers)
    assert me.status_code == 200, me.text
    assert me.json()["customer_ids"] == [501]

    quotes = client.get("/api/v1/customer-portal/quotes", headers=portal_headers)
    invoices = client.get("/api/v1/customer-portal/invoices", headers=portal_headers)
    projects = client.get("/api/v1/customer-portal/projects", headers=portal_headers)
    assert quotes.status_code == invoices.status_code == projects.status_code == 200
    assert db.query(PortalUser).filter(PortalUser.email == "cust1@example.com").count() == 1
    assert db.query(PortalCustomerLink).count() == 1
    assert db.query(PortalActivityLog).filter(PortalActivityLog.portal_type == "customer").count() >= 3


def test_customer_portal_refuses_ambiguous_legacy_customer_links(client, db):
    headers = auth_headers(client, db)
    invited = invite_portal(client, db, headers, customer_id=503)
    portal_headers = {"X-Portal-Session": invited["one_time_session_token"]}
    registry_account = CRMAccount(id=503, organization_id=1, account_name="Separate registry account")
    db.add(registry_account)
    own_workflow_records(db, registry_account)
    db.commit()

    me = client.get("/api/v1/customer-portal/me", headers=portal_headers)
    assert me.status_code == 200, me.text
    assert me.json()["customer_ids"] == [503]

    link = db.query(PortalCustomerLink).filter_by(portal_user_id=invited["id"]).one()
    link.srm_customer_id = None
    db.commit()

    me = client.get("/api/v1/customer-portal/me", headers=portal_headers)
    assert me.status_code == 200, me.text
    assert me.json()["customer_ids"] == []


def test_customer_portal_projects_only_customer_visible_fields_and_records(client, db):
    headers = auth_headers(client, db)
    invited = invite_portal(client, db, headers, customer_id=502)
    portal_headers = {"X-Portal-Session": invited["one_time_session_token"]}
    today = date.today()
    quote = CRMQuotation(account_id=502, quote_number="PORTAL-Q", status="Sent",
                         issue_date=today, expiry_date=today, expected_margin=123, sent_at=datetime.now(timezone.utc))
    internal_quote = CRMQuotation(account_id=502, quote_number="REJECTED-Q", status="Rejected",
                               issue_date=today, expiry_date=today)
    invoice = SRMInvoice(customer_id=502, invoice_number="PORTAL-I", status="sent",
                         collection_hold_reason="Internal review")
    draft_invoice = SRMInvoice(customer_id=502, invoice_number="DRAFT-I", status="draft")
    project = PMSProject(name="Shared project", project_key="PORTAL-P", is_client_visible=True, actual_cost=456)
    private = PMSProject(name="Private project", project_key="PRIVATE-P")
    db.add_all([quote, internal_quote, invoice, draft_invoice, project, private])
    own_workflow_records(db, quote, internal_quote, invoice, draft_invoice, project, private)
    for target in (project, private):
        engagement = SRMEngagement(customer_id=502, pms_project_id=target.id,
                                   engagement_number=target.project_key, name=target.name)
        db.add(engagement)
        own_workflow_records(db, engagement)
    db.commit()

    for section, key, expected, internal in (
        ("quotes", "quote_number", "PORTAL-Q", "expected_margin"),
        ("invoices", "invoice_number", "PORTAL-I", "collection_hold_reason"),
        ("projects", "project_key", "PORTAL-P", "actual_cost"),
    ):
        response = client.get(f"/api/v1/customer-portal/{section}", headers=portal_headers)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["total"] == 1
        assert result["items"][0][key] == expected
        assert internal not in result["items"][0]


def test_customer_quote_acceptance_checks_status_expiry_and_records_timestamp(client, db):
    headers = auth_headers(client, db)
    customer = CRMCompany(name="Quote customer", organization_id=1)
    db.add(customer)
    own_workflow_records(db, customer)
    today = date.today()
    sent_at = datetime.now(timezone.utc)
    quotes = [
        CRMQuotation(account_id=customer.id, quote_number="SHARED", status="Sent", issue_date=today,
                     expiry_date=today + timedelta(days=1), sent_at=sent_at),
        CRMQuotation(account_id=customer.id, quote_number="DRAFT", status="Draft", issue_date=today,
                     expiry_date=today + timedelta(days=1)),
        CRMQuotation(account_id=customer.id, quote_number="EXPIRED", status="Sent", issue_date=today - timedelta(days=2),
                     expiry_date=today - timedelta(days=1), sent_at=sent_at - timedelta(days=2)),
    ]
    db.add_all(quotes)
    own_workflow_records(db, *quotes)
    db.commit()
    invited = client.post("/api/v1/portals/invite", headers=headers, json={
        "email": "quote-portal@example.com", "display_name": "Quote customer", "portal_type": "customer",
        "customer_id": customer.id, "permissions": ["view", "accept_quote"],
    })
    assert invited.status_code == 201, invited.text
    portal_headers = {"X-Portal-Session": invited.json()["one_time_session_token"]}

    for quote, expected in zip(quotes, (200, 404, 409), strict=True):
        result = client.post(f"/api/v1/customer-portal/quotes/{quote.id}/accept", headers=portal_headers)
        assert result.status_code == expected, result.text

    db.refresh(quotes[0])
    assert quotes[0].status == "Accepted"
    assert quotes[0].accepted_at is not None
    accepted_at = quotes[0].accepted_at
    repeat = client.post(f"/api/v1/customer-portal/quotes/{quotes[0].id}/accept", headers=portal_headers)
    assert repeat.status_code == 200, repeat.text
    db.refresh(quotes[0])
    assert quotes[0].accepted_at == accepted_at
