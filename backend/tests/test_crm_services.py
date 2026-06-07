from app.apps.crm.models import CRMService


def test_crm_service_crud_api_database_and_validation(client, db, superuser_headers):
    response = client.post("/api/v1/crm/services", headers=superuser_headers, json={
        "serviceCode": "IMPL-STD",
        "name": "Standard Implementation",
        "category": "Professional Services",
        "billingType": "fixed",
        "defaultRate": 75000,
        "defaultCost": 30000,
    })
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["serviceCode"] == "IMPL-STD"
    assert db.query(CRMService).filter(CRMService.service_code == "IMPL-STD").count() == 1

    listed = client.get("/api/v1/crm/services", headers=superuser_headers)
    assert listed.status_code == 200
    assert any(item["serviceCode"] == "IMPL-STD" for item in listed.json()["items"])

    invalid = client.post("/api/v1/crm/services", headers=superuser_headers, json={"name": "No code"})
    assert invalid.status_code == 422
