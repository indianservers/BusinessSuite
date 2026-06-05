from app.apps.srm.models import SRMAuditLog, SRMEngagement, SRMEngagementLink


def test_srm_engagement_create_persists(client, db, superuser_headers):
    response = client.post("/api/v1/srm/engagements", headers=superuser_headers, json={
        "name": "Implementation engagement",
        "customer_id": 44,
        "billing_type": "milestone",
        "budget_amount": 450000,
    })
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["engagement_number"].startswith("ENG-")
    assert body["status"] == "created"
    assert db.query(SRMEngagement).filter(SRMEngagement.id == body["id"]).first() is not None

    link = client.post(f"/api/v1/srm/engagements/{body['id']}/links", headers=superuser_headers, json={
        "linked_module": "crm",
        "linked_entity_type": "deal",
        "linked_entity_id": 501,
        "label": "CRM deal",
    })
    assert link.status_code == 201, link.text
    duplicate_link = client.post(f"/api/v1/srm/engagements/{body['id']}/links", headers=superuser_headers, json={
        "linked_module": "crm",
        "linked_entity_type": "deal",
        "linked_entity_id": 501,
    })
    assert duplicate_link.status_code == 409

    status = client.post(f"/api/v1/srm/engagements/{body['id']}/status/delivery_in_progress", headers=superuser_headers)
    assert status.status_code == 200, status.text
    assert status.json()["status"] == "delivery_in_progress"
    timeline = client.get(f"/api/v1/srm/engagements/{body['id']}/timeline", headers=superuser_headers)
    assert timeline.status_code == 200
    assert len(timeline.json()["links"]) == 1
    assert db.query(SRMEngagementLink).filter(SRMEngagementLink.engagement_id == body["id"]).count() == 1
    assert db.query(SRMAuditLog).filter(SRMAuditLog.entity_type == "engagement", SRMAuditLog.entity_id == body["id"]).count() >= 2
