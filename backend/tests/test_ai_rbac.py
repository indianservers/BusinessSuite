from ai_test_utils import auth_headers


def test_ai_backend_blocks_user_without_ai_permission(client, db):
    headers, _ = auth_headers(client, db, email="no-ai@example.com", permissions=["crm_view"])
    response = client.post("/api/v1/ai/summary", headers=headers, json={"module_name": "crm", "record_type": "lead"})
    assert response.status_code == 403


def test_ai_backend_blocks_crm_context_without_crm_permission(client, db):
    headers, _ = auth_headers(client, db, email="ai-no-crm@example.com", permissions=["ai_view", "ai_use"])
    response = client.post("/api/v1/ai/summary", headers=headers, json={"module_name": "crm", "record_type": "lead"})
    assert response.status_code == 403

