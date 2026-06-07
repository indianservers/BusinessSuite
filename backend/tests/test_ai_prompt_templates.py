from ai_test_utils import auth_headers, create_mock_provider


def test_ai_prompt_template_create_and_test(client, db):
    headers, _ = auth_headers(client, db)
    create_mock_provider(client, headers)
    created = client.post(
        "/api/v1/ai/prompt-templates",
        headers=headers,
        json={
            "name": "Summary",
            "use_case": "summary",
            "module_name": "crm",
            "system_prompt": "Use sanitized context only.",
            "user_prompt_template": "Summarize with evidence.",
            "output_schema_json": {"summary": "string"},
            "active": True,
        },
    )
    assert created.status_code == 201, created.text
    response = client.post(f"/api/v1/ai/prompt-templates/{created.json()['id']}/test", headers=headers, json={"module_name": "crm", "record_type": "lead"})
    assert response.status_code == 200, response.text
    assert response.json()["provider_configured"] is True

