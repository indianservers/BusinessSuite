from app.apps.crm.models import CRMLeadConversionLog, CRMTimelineEvent
from app.core.security import get_password_hash
from app.models.user import Permission, Role, User


def _headers_for_permissions(client, db, email: str, permissions: list[str]):
    role = Role(name=f"role_{email}", description=email, is_system=False)
    db.add(role)
    db.flush()
    for name in permissions:
        permission = db.query(Permission).filter(Permission.name == name).first()
        if not permission:
            permission = Permission(name=name, module="crm", description=name)
            db.add(permission)
            db.flush()
        role.permissions.append(permission)
    user = User(email=email, hashed_password=get_password_hash("Sales@123456"), is_active=True, role_id=role.id)
    db.add(user)
    db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "Sales@123456"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_crm_phase_1_lead_qualification_conversion_timeline_and_dashboard(client, db, superuser_headers):
    pipeline = client.post("/api/v1/crm/pipelines", headers=superuser_headers, json={"name": "Core CRM", "isDefault": True})
    assert pipeline.status_code == 201
    stage = client.post(
        f"/api/v1/crm/pipelines/{pipeline.json()['id']}/stages",
        headers=superuser_headers,
        json={"name": "Qualification", "position": 1, "probability": 30},
    )
    assert stage.status_code == 201

    lead = client.post(
        "/api/v1/crm/leads",
        headers=superuser_headers,
        json={
            "firstName": "Phase",
            "lastName": "One",
            "fullName": "Phase One",
            "companyName": "Foundation Labs",
            "email": "phase-one@example.com",
            "source": "Website",
            "estimatedValue": 250000,
        },
    )
    assert lead.status_code == 201
    lead_id = lead.json()["id"]

    qualified = client.post(f"/api/v1/crm/leads/{lead_id}/qualify", headers=superuser_headers)
    assert qualified.status_code == 200
    assert qualified.json()["status"] == "Qualified"

    converted = client.post(
        f"/api/v1/crm/leads/{lead_id}/convert",
        headers=superuser_headers,
        json={"pipelineId": pipeline.json()["id"], "stageId": stage.json()["id"]},
    )
    assert converted.status_code == 200
    assert converted.json()["lead"]["is_converted"] is True
    assert converted.json()["company"]["name"] == "Foundation Labs"
    assert converted.json()["contact"]["email"] == "phase-one@example.com"
    assert converted.json()["deal"]["status"] == "Open"
    assert db.query(CRMLeadConversionLog).filter(CRMLeadConversionLog.lead_id == lead_id).count() == 1
    assert db.query(CRMTimelineEvent).filter(CRMTimelineEvent.record_type == "lead", CRMTimelineEvent.record_id == lead_id).count() >= 2

    timeline = client.get(f"/api/v1/crm/timeline/lead/{lead_id}", headers=superuser_headers)
    assert timeline.status_code == 200
    assert any(item["type"] in {"qualification", "conversion"} for item in timeline.json()["items"])

    dashboard = client.get("/api/v1/crm/dashboard", headers=superuser_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["summary"]["leads"] >= 1
    assert "nextBestAction" in dashboard.json()


def test_crm_phase_1_deal_actions_activity_completion_and_srm_readiness(client, superuser_headers):
    pipeline = client.post("/api/v1/crm/pipelines", headers=superuser_headers, json={"name": "Deal Actions"})
    assert pipeline.status_code == 201
    stage_open = client.post(f"/api/v1/crm/pipelines/{pipeline.json()['id']}/stages", headers=superuser_headers, json={"name": "Open", "position": 1, "probability": 20})
    stage_won = client.post(f"/api/v1/crm/pipelines/{pipeline.json()['id']}/stages", headers=superuser_headers, json={"name": "Closed Won", "position": 2, "probability": 100, "isWon": True})
    assert stage_open.status_code == 201
    assert stage_won.status_code == 201

    deal = client.post(
        "/api/v1/crm/deals",
        headers=superuser_headers,
        json={"name": "Phase 1 Deal", "pipelineId": pipeline.json()["id"], "stageId": stage_open.json()["id"], "amount": 125000},
    )
    assert deal.status_code == 201
    deal_id = deal.json()["id"]

    moved = client.post(f"/api/v1/crm/deals/{deal_id}/move-stage", headers=superuser_headers, json={"stageId": stage_won.json()["id"], "probability": 100})
    assert moved.status_code == 200
    assert moved.json()["stageId"] == stage_won.json()["id"]

    activity = client.post(
        "/api/v1/crm/activities",
        headers=superuser_headers,
        json={"recordType": "deal", "recordId": deal_id, "activityType": "task", "subject": "Send commercial handoff checklist"},
    )
    assert activity.status_code == 201
    completed = client.post(f"/api/v1/crm/activities/{activity.json()['id']}/complete", headers=superuser_headers)
    assert completed.status_code == 200
    assert completed.json()["status"] == "Completed"

    won = client.post(f"/api/v1/crm/deals/{deal_id}/mark-won", headers=superuser_headers)
    assert won.status_code == 200
    assert won.json()["status"] == "Won"
    detail = client.get(f"/api/v1/crm/deals/{deal_id}", headers=superuser_headers)
    assert detail.status_code == 200
    assert "srm" in detail.json().get("related", {})

    lost_deal = client.post(
        "/api/v1/crm/deals",
        headers=superuser_headers,
        json={"name": "Phase 1 Lost Deal", "pipelineId": pipeline.json()["id"], "stageId": stage_open.json()["id"], "amount": 50000},
    )
    assert lost_deal.status_code == 201
    missing_reason = client.post(f"/api/v1/crm/deals/{lost_deal.json()['id']}/mark-lost", headers=superuser_headers, json={})
    assert missing_reason.status_code == 422
    lost = client.post(f"/api/v1/crm/deals/{lost_deal.json()['id']}/mark-lost", headers=superuser_headers, json={"lostReason": "Budget frozen"})
    assert lost.status_code == 200
    assert lost.json()["status"] == "Lost"
    assert lost.json()["lostReason"] == "Budget frozen"


def test_crm_phase_1_granular_rbac_blocks_unrelated_entities(client, db):
    headers = _headers_for_permissions(client, db, "lead-viewer@example.com", ["crm_leads_view"])
    visible = client.get("/api/v1/crm/leads", headers=headers)
    assert visible.status_code == 200

    blocked_view = client.get("/api/v1/crm/deals", headers=headers)
    assert blocked_view.status_code == 403

    blocked_create = client.post("/api/v1/crm/leads", headers=headers, json={"firstName": "No", "fullName": "No Create"})
    assert blocked_create.status_code == 403

    manage_headers = _headers_for_permissions(client, db, "lead-manager@example.com", ["crm_leads_manage"])
    created = client.post("/api/v1/crm/leads", headers=manage_headers, json={"firstName": "Can", "fullName": "Can Create"})
    assert created.status_code == 201
