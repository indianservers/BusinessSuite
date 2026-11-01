import pytest
from app.apps.crm.models import CRMDeal, CRMProduct
from app.models.company import Company


def seed(client, db, headers):
    if not db.get(Company, 1):
        db.add(Company(id=1, name="Deal catalog tenant"))
        db.commit()
    pipeline = client.post("/api/v1/crm/pipelines", headers=headers, json={"name": "Catalog pipeline"})
    assert pipeline.status_code == 201, pipeline.text
    stage = client.post(f"/api/v1/crm/pipelines/{pipeline.json()['id']}/stages", headers=headers, json={"name": "Discovery", "probability": 20})
    assert stage.status_code == 201, stage.text
    product = client.post("/api/v1/crm/products", headers=headers, json={"name": "License", "listPrice": 100.25})
    service = client.post("/api/v1/crm/services", headers=headers, json={"name": "Setup", "serviceCode": "SETUP", "defaultRate": 50})
    assert product.status_code == service.status_code == 201
    return {"name": "Catalog deal", "pipeline_id": pipeline.json()["id"], "stage_id": stage.json()["id"]}, product.json()["id"], service.json()["id"]


def test_catalog_round_trip_update_clear_and_server_total(client, db, superuser_headers):
    payload, product, service = seed(client, db, superuser_headers)
    payload.update(amount=1, catalog_items=[
        {"kind": "product", "item_id": product, "quantity": 2, "unit_price": 100.25, "discount": 10},
        {"kind": "service", "item_id": service, "quantity": 1, "unit_price": 50, "discount": 0}])
    result = client.post("/api/v1/crm/deals", headers=superuser_headers, json=payload)
    assert result.status_code == 201, result.text
    body = result.json()
    assert body["amount"] == 230.45
    assert [line["name"] for line in body["catalog_items"]] == ["License", "Setup"]
    row = db.get(CRMDeal, body["id"])
    assert len(row.catalog_items) == 2
    related = client.get(f"/api/v1/crm/deals/{row.id}/related", headers=superuser_headers)
    assert related.status_code == 200, related.text
    assert len(related.json()["related"]["products"]) == 2
    update = client.patch(f"/api/v1/crm/deals/{row.id}", headers=superuser_headers, json={"name": "Renamed"})
    assert update.status_code == 200, update.text
    assert len(update.json()["catalog_items"]) == 2
    clear = client.patch(f"/api/v1/crm/deals/{row.id}", headers=superuser_headers, json={"catalog_items": [], "amount": 25})
    assert clear.status_code == 200, clear.text
    assert clear.json()["catalog_items"] == []
    assert clear.json()["amount"] == 25


@pytest.mark.parametrize("override", [{"quantity": 0}, {"quantity": 1.5}, {"unit_price": -1}, {"discount": 101}, {"kind": "other"}])
def test_catalog_rejects_invalid_lines(client, db, superuser_headers, override):
    payload, product, _ = seed(client, db, superuser_headers)
    payload["catalog_items"] = [{"kind": "product", "item_id": product, "quantity": 1, "unit_price": 100, **override}]
    response = client.post("/api/v1/crm/deals", headers=superuser_headers, json=payload)
    assert response.status_code == 422, response.text
    assert not db.query(CRMDeal).filter(CRMDeal.name == "Catalog deal").first()


def test_catalog_rejects_foreign_and_inactive_items(client, db, superuser_headers):
    payload, product, _ = seed(client, db, superuser_headers)
    foreign = CRMProduct(name="Other tenant product", organization_id=999, active=True)
    db.add(foreign)
    db.commit()
    payload["catalog_items"] = [{"kind": "product", "item_id": foreign.id, "quantity": 1, "unit_price": 100}]
    response = client.post("/api/v1/crm/deals", headers=superuser_headers, json=payload)
    assert response.status_code == 404, response.text
    own = db.get(CRMProduct, product)
    own.active = False
    db.commit()
    payload["catalog_items"][0]["item_id"] = product
    response = client.post("/api/v1/crm/deals", headers=superuser_headers, json=payload)
    assert response.status_code == 422, response.text
