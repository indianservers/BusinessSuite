from tests.automation_test_utils import automation_headers, create_workflow


def test_automation_execution_depth_is_limited(client, db):
    headers = automation_headers(client, db)
    workflow = create_workflow(client, headers)
    response = client.post(f"/api/v1/automation/workflows/{workflow['id']}/test", headers=headers, json={"record": {"discount_percent": 20}, "depth": 6})
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert "depth" in response.json()["error_message"]

