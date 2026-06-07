from ai_test_utils import auth_headers, create_mock_provider
from app.apps.crm.models import CRMCustomField, CRMCustomFieldValue, CRMLead


def test_ai_context_excludes_hidden_custom_fields(client, db):
    headers, user = auth_headers(client, db)
    create_mock_provider(client, headers)
    lead = CRMLead(first_name="Asha", full_name="Asha Lead", company_name="Acme", status="New", owner_user_id=user.id, organization_id=1)
    db.add(lead)
    db.flush()
    field = CRMCustomField(organization_id=1, entity="leads", field_key="secret_budget", label="Secret Budget", is_visible=False, is_active=True)
    db.add(field)
    db.flush()
    db.add(CRMCustomFieldValue(organization_id=1, custom_field_id=field.id, entity="leads", record_id=lead.id, value_text="Top Secret"))
    db.commit()
    response = client.post("/api/v1/ai/summary", headers=headers, json={"module_name": "crm", "record_type": "lead", "record_id": lead.id})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source_data_summary"]["custom_field_count"] == 0
    assert "Top Secret" not in str(payload)

