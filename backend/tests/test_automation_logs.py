from tests.automation_test_utils import automation_headers, create_workflow


def test_logs_list_detail_and_retry_failed_execution(client, db):
    headers = automation_headers(client, db)
    workflow = create_workflow(client, headers)
    failed = client.post(f"/api/v1/automation/workflows/{workflow['id']}/test", headers=headers, json={"record": {"discount_percent": 20}, "depth": 99})
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    log_id = failed.json()["id"]

    response = client.get("/api/v1/automation/logs", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] >= 1

    response = client.get(f"/api/v1/automation/logs/{log_id}", headers=headers)
    assert response.status_code == 200

    response = client.post(f"/api/v1/automation/logs/{log_id}/retry", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "failed"

