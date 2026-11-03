"""CRM CRUD and recovery preserve metadata and never resurrect merged sources."""
import pytest
from app.apps.crm.models import CRMContact
from tests.test_crm_associations_merge import superuser_headers, post
from tests.test_crm_rest_api import _crm_user_headers


def create_record(client, headers, entity):
    company = post(client, headers, "crm/companies", {"name": "Customer company", "industry": "Software", "city": "Hyderabad"})
    if entity == "companies":
        return company
    person = {"first_name": "Customer", "full_name": "Customer Person", "company_id": company["id"], "email": "customer@example.com"}
    if entity in {"contacts", "leads"}:
        if entity == "leads":
            person.pop("company_id")
            person["company_name"] = company["name"]
        return post(client, headers, f"crm/{entity}", person)
    contact = post(client, headers, "crm/contacts", person)
    pipeline = post(client, headers, "crm/pipelines", {"name": "Management pipeline"})
    stage = post(client, headers, f"crm/pipelines/{pipeline['id']}/stages", {"name": "Discovery", "probability": 20})
    return post(client, headers, "crm/deals", {"name": "Customer opportunity", "company_id": company["id"], "contact_id": contact["id"], "pipeline_id": pipeline["id"], "stage_id": stage["id"], "amount": 1000})


@pytest.mark.parametrize("entity", ["contacts", "leads", "companies", "deals"])
def test_crud_metadata_and_restore(client, superuser_headers, entity):
    h = superuser_headers
    record = create_record(client, h, entity)
    path = f"/api/v1/crm/{entity}/{record['id']}"
    field = post(client, h, "crm/custom-fields", {"entityType": entity, "fieldName": "Customer segment", "fieldKey": "customer_segment", "fieldType": "text"})
    notes_key = "description" if entity == "deals" else "notes"
    updated = client.patch(path, headers=h, json={notes_key: "Verified business details", "custom_fields": {"customer_segment": "Enterprise"}})
    assert updated.status_code == 200, updated.text
    detail = client.get(path, headers=h)
    assert detail.status_code == 200, detail.text
    assert detail.json()[notes_key] == "Verified business details"
    custom = next(item for item in detail.json()["customFields"] if item["id"] == field["id"])
    assert custom["value"] == "Enterprise"
    assert client.delete(path, headers=h).status_code == 200
    assert client.get(path, headers=h).status_code == 404
    active = client.get(f"/api/v1/crm/{entity}", headers=h).json()
    assert record["id"] not in [item["id"] for item in active["items"]]
    deleted = client.get(f"/api/v1/crm/{entity}?deleted_only=true", headers=h)
    assert deleted.status_code == 200, deleted.text
    assert record["id"] in [item["id"] for item in deleted.json()["items"]]
    restored = client.post(path + "/restore", headers=h)
    assert restored.status_code == 200, restored.text
    assert restored.json()["deleted_at"] is None
    detail = client.get(path, headers=h).json()
    assert detail[notes_key] == "Verified business details"
    assert next(item for item in detail["customFields"] if item["id"] == field["id"])["value"] == "Enterprise"
    assert client.post(path + "/restore", headers=h).status_code == 200
    assert not client.get(f"/api/v1/crm/{entity}?deleted_only=true", headers=h).json()["items"]


def test_restore_rejects_merged_contact(client, superuser_headers):
    h = superuser_headers
    first = create_record(client, h, "contacts")
    second = create_record(client, h, "contacts")
    post(client, h, "crm/duplicates/merge", {"entityType": "contact", "winnerId": first["id"], "loserIds": [second["id"]], "allowUndetected": True})
    response = client.post(f"/api/v1/crm/contacts/{second['id']}/restore", headers=h)
    assert response.status_code == 409, response.text
    assert "merged" in response.json()["detail"].lower()
    assert client.get(f"/api/v1/crm/contacts/{second['id']}", headers=h).status_code == 404


def test_restore_rejects_deleted_parent_and_foreign_tenant(client, db, superuser_headers):
    h = superuser_headers
    record = create_record(client, h, "contacts")
    path = f"/api/v1/crm/contacts/{record['id']}"
    assert client.delete(path, headers=h).status_code == 200
    assert client.delete(f"/api/v1/crm/companies/{record['company_id']}", headers=h).status_code == 200
    assert client.post(path + "/restore", headers=h).status_code == 404
    assert client.post(f"/api/v1/crm/companies/{record['company_id']}/restore", headers=h).status_code == 200
    assert client.post(path + "/restore", headers=h).status_code == 200
    row = db.get(CRMContact, record["id"])
    row.organization_id = 999
    db.commit()
    assert client.post(path + "/restore", headers=h).status_code == 404


def test_recovery_requires_auth_and_supported_resource(client, superuser_headers):
    assert client.post("/api/v1/crm/contacts/1/restore").status_code in (401, 403)
    assert client.post("/api/v1/crm/tasks/1/restore", headers=superuser_headers).status_code == 422


def test_view_only_user_cannot_restore_or_list_recycle_bin(client, db, superuser_headers):
    h = superuser_headers
    record = create_record(client, h, "contacts")
    path = f"/api/v1/crm/contacts/{record['id']}"
    assert client.delete(path, headers=h).status_code == 200
    viewer, _ = _crm_user_headers(client, db, "record-viewer@example.com", "CRM record viewer", ["crm_view"])
    viewer["X-Suite-Branch"] = h["X-Suite-Branch"]
    assert client.post(path + "/restore", headers=viewer).status_code == 403
    assert client.get("/api/v1/crm/contacts?deleted_only=true", headers=viewer).status_code == 403
    assert client.get(path, headers=h).status_code == 404
