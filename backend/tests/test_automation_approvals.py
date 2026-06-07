from app.apps.automation.models import AutomationApprovalRequest, AutomationApprovalRule
from tests.automation_test_utils import automation_headers


def test_approval_rule_request_submit_decide(client, db):
    headers = automation_headers(client, db)
    rule = client.post("/api/v1/automation/approvals/rules", headers=headers, json={
        "name": "Quote margin approval",
        "module_name": "crm",
        "record_type": "quote",
        "condition_json": {"field": "margin_percent", "operator": "less_than", "value": 20},
        "steps": [{"approver_role": "crm_sales_manager"}],
    })
    assert rule.status_code == 201, rule.text
    assert db.query(AutomationApprovalRule).count() == 1

    request = client.post("/api/v1/automation/approvals", headers=headers, json={"rule_id": rule.json()["id"], "module_name": "crm", "record_type": "quote", "record_id": 55})
    assert request.status_code == 201, request.text
    request_id = request.json()["id"]
    assert db.query(AutomationApprovalRequest).count() == 1

    assert client.post(f"/api/v1/automation/approvals/{request_id}/submit", headers=headers).json()["status"] == "pending"
    assert client.post(f"/api/v1/automation/approval-requests/{request_id}/approve", headers=headers, json={"comment": "ok"}).json()["status"] == "approved"


def test_approval_request_reject_alias(client, db):
    headers = automation_headers(client, db)
    request = client.post("/api/v1/automation/approvals", headers=headers, json={"module_name": "crm", "record_type": "quote", "record_id": 56})
    assert request.status_code == 201, request.text
    request_id = request.json()["id"]
    assert client.post(f"/api/v1/automation/approvals/{request_id}/submit", headers=headers).json()["status"] == "pending"
    response = client.post(f"/api/v1/automation/approval-requests/{request_id}/reject", headers=headers, json={"comment": "needs changes"})
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
