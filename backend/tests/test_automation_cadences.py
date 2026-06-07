from app.apps.automation.models import AutomationScheduledJob
from tests.automation_test_utils import automation_headers


def test_cadence_create_enroll_pause_resume(client, db):
    headers = automation_headers(client, db)
    response = client.post("/api/v1/automation/cadences", headers=headers, json={
        "name": "Lead nurture",
        "module_name": "crm",
        "target_type": "lead",
        "stop_rules_json": {"stop_on": ["won", "lost", "converted"]},
        "steps": [{"step_type": "email", "delay_hours": 1, "payload_json": {"template_id": "intro"}}],
    })
    assert response.status_code == 201, response.text
    cadence_id = response.json()["id"]
    response = client.post(f"/api/v1/automation/cadences/{cadence_id}/enroll", headers=headers, json={"record_type": "lead", "record_id": 15})
    assert response.status_code == 200
    assert db.query(AutomationScheduledJob).count() == 1
    assert client.post(f"/api/v1/automation/cadences/{cadence_id}/pause", headers=headers).json()["status"] == "paused"
    assert client.post(f"/api/v1/automation/cadences/{cadence_id}/resume", headers=headers).json()["status"] == "active"
    assert client.post(f"/api/v1/automation/cadences/{cadence_id}/complete", headers=headers).json()["status"] == "completed"
