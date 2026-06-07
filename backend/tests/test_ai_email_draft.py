from ai_test_utils import auth_headers, create_mock_provider


def test_ai_email_draft_requires_review_not_direct_send(client, db):
    headers, _ = auth_headers(client, db)
    create_mock_provider(client, headers)
    response = client.post("/api/v1/ai/email-draft", headers=headers, json={"module_name": "crm", "record_type": "deal", "tone": "polite"})
    assert response.status_code == 200, response.text
    assert response.json()["requires_user_review_before_send"] is True
    assert response.json()["output"]["draft"]["requires_review"] is True

