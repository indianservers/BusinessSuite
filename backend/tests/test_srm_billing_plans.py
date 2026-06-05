from app.apps.srm.models import SRMAuditLog, SRMBillingMilestone, SRMBillingPlan

from tests.srm_test_utils import create_engagement_via_confirm


def test_srm_billing_plan_lifecycle_and_milestones(client, db, superuser_headers):
    engagement, _order = create_engagement_via_confirm(client, superuser_headers)

    response = client.post("/api/v1/srm/billing-plans", headers=superuser_headers, json={
        "engagement_id": engagement["id"],
        "name": "Hybrid delivery billing",
        "billing_type": "hybrid",
        "currency": "INR",
        "total_amount": 147500,
        "milestones": [
            {"name": "Kickoff", "amount": 50000},
            {"name": "Go live", "amount": 97500},
        ],
    })
    assert response.status_code == 201, response.text
    plan = response.json()
    assert plan["status"] == "draft"
    assert len(plan["milestones"]) == 2

    extra = client.post(f"/api/v1/srm/billing-plans/{plan['id']}/milestones", headers=superuser_headers, json={
        "name": "Support period",
        "amount": 25000,
    })
    assert extra.status_code == 201, extra.text

    active = client.post(f"/api/v1/srm/billing-plans/{plan['id']}/activate", headers=superuser_headers)
    assert active.status_code == 200, active.text
    assert active.json()["status"] == "active"
    paused = client.post(f"/api/v1/srm/billing-plans/{plan['id']}/pause", headers=superuser_headers)
    assert paused.status_code == 200, paused.text
    resumed = client.post(f"/api/v1/srm/billing-plans/{plan['id']}/activate", headers=superuser_headers)
    assert resumed.status_code == 200, resumed.text
    completed = client.post(f"/api/v1/srm/billing-plans/{plan['id']}/complete", headers=superuser_headers)
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"

    saved = db.query(SRMBillingPlan).filter(SRMBillingPlan.id == plan["id"]).first()
    assert saved is not None
    assert db.query(SRMBillingMilestone).filter(SRMBillingMilestone.billing_plan_id == plan["id"]).count() == 3
    assert db.query(SRMAuditLog).filter(SRMAuditLog.entity_type == "billing_plan", SRMAuditLog.entity_id == plan["id"]).count() >= 4


def test_srm_billing_plan_rejects_invalid_type(client, db, superuser_headers):
    engagement, _order = create_engagement_via_confirm(client, superuser_headers)
    response = client.post("/api/v1/srm/billing-plans", headers=superuser_headers, json={
        "engagement_id": engagement["id"],
        "name": "Invalid plan",
        "billing_type": "random",
    })
    assert response.status_code == 400
