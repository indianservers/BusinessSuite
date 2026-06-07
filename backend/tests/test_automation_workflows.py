from app.apps.automation.models import AutomationAction, AutomationCondition, AutomationExecutionLog, AutomationWorkflow
from tests.automation_test_utils import automation_headers, create_workflow


def test_workflow_create_activate_test_and_log(client, db):
    headers = automation_headers(client, db)
    workflow = create_workflow(client, headers)
    assert workflow["is_active"] is True
    assert db.query(AutomationWorkflow).count() == 1
    assert db.query(AutomationCondition).count() == 1
    assert db.query(AutomationAction).count() == 1

    response = client.post(f"/api/v1/automation/workflows/{workflow['id']}/test", headers=headers, json={"record": {"discount_percent": 20}, "record_id": 101})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "success"
    assert db.query(AutomationExecutionLog).count() == 1

    response = client.post(f"/api/v1/automation/workflows/{workflow['id']}/deactivate", headers=headers)
    assert response.status_code == 200
    assert response.json()["is_active"] is False

