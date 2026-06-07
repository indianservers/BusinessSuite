from app.apps.saas.models import PortalActivityLog, PortalCustomerLink, PortalUser
from phase10_test_utils import auth_headers, invite_portal


def test_customer_portal_invite_profile_and_safe_empty_records(client, db):
    headers = auth_headers(client, db)
    invited = invite_portal(client, headers, "customer", "cust1@example.com", customer_id=501)
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
