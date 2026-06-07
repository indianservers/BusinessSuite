from app.apps.crm.models import CRMLead
from app.apps.saas.models import PortalAccessGrant, PortalActivityLog
from phase10_test_utils import auth_headers, invite_portal


def test_partner_portal_submit_and_track_only_submitted_leads(client, db):
    headers = auth_headers(client, db)
    invited = invite_portal(client, headers, "partner", "partner@example.com", partner_id=901)
    portal_headers = {"X-Portal-Session": invited["one_time_session_token"]}

    create = client.post("/api/v1/partner-portal/leads", json={"company_name": "Partner Co", "contact_name": "Priya Partner", "email": "lead@example.com", "value": 50000}, headers=portal_headers)
    assert create.status_code == 201, create.text
    assert create.json()["source"] == "Partner Portal"

    leads = client.get("/api/v1/partner-portal/leads", headers=portal_headers)
    assert leads.status_code == 200
    assert leads.json()["total"] == 1
    assert db.query(CRMLead).filter(CRMLead.email == "lead@example.com").count() == 1
    assert db.query(PortalAccessGrant).filter(PortalAccessGrant.resource_type == "partner_lead").count() == 1
    assert db.query(PortalActivityLog).filter(PortalActivityLog.event_type == "partner_lead_submitted").count() == 1
