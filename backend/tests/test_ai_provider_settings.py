from ai_test_utils import auth_headers, create_mock_provider


def test_ai_provider_settings_crud_and_test(client, db):
    headers, _ = auth_headers(client, db)
    provider = create_mock_provider(client, headers)
    listed = client.get("/api/v1/ai/provider-settings", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["provider_name"] == "mock"
    tested = client.post(f"/api/v1/ai/provider-settings/{provider['id']}/test", headers=headers)
    assert tested.status_code == 200
    assert tested.json()["provider_configured"] is True

