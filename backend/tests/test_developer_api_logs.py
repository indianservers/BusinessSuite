from phase10_test_utils import auth_headers


def test_developer_api_logs_capture_key_actions(client, db):
    headers = auth_headers(client, db, permissions=["developer_manage"])
    client.post("/api/v1/developer/api-keys", json={"name": "Log Key", "scopes": ["crm.read"]}, headers=headers)
    logs = client.get("/api/v1/developer/api-logs", headers=headers)
    assert logs.status_code == 200
    assert logs.json()["total"] >= 1
    assert logs.json()["items"][0]["endpoint"].startswith("/api/v1/developer")
