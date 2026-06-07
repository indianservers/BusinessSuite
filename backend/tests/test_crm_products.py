from app.apps.crm.models import CRMProduct


def test_crm_product_crud_api_database_and_validation(client, db, superuser_headers):
    response = client.post("/api/v1/crm/products", headers=superuser_headers, json={
        "name": "CRM Enterprise",
        "productCode": "CRM-ENT",
        "category": "Software",
        "listPrice": 125000,
        "costPrice": 40000,
        "active": True,
    })
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["productCode"] == "CRM-ENT"
    row = db.query(CRMProduct).filter(CRMProduct.id == body["id"]).one()
    assert row.product_code == "CRM-ENT"
    assert float(row.list_price) == 125000

    update = client.patch(f"/api/v1/crm/products/{body['id']}", headers=superuser_headers, json={"listPrice": 130000})
    assert update.status_code == 200, update.text
    db.refresh(row)
    assert float(row.list_price) == 130000

    invalid = client.post("/api/v1/crm/products", headers=superuser_headers, json={"sku": "MISSING-NAME"})
    assert invalid.status_code == 422
