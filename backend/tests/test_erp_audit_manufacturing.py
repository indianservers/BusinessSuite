from decimal import Decimal

import pytest

from app.apps.srm.models import SRMProductionOrder, SRMInventoryMovement, SRMInventoryBalance, SRMBOMComponent
from tests.test_erp_audit_procurement import procurement


@pytest.fixture
def production(client, db, procurement):
    headers, component, _ = procurement
    base = "/api/v1/srm/inventory"
    finished = client.post(base + "/items", headers=headers, json={"sku": "AUDIT-KIT", "item_name": "Audit kit", "default_warehouse_id": component["warehouse_id"]})
    assert finished.status_code == 201, finished.text
    opening = client.post(base + "/opening-stock", headers=headers, json={"product_id": component["product_id"], "warehouse_id": component["warehouse_id"], "quantity": 20, "rate": 5})
    assert opening.status_code == 201, opening.text
    bom = client.post(base + "/manufacturing/bom", headers=headers, json={"bom_name": "Audit kit assembly", "finished_product_id": finished.json()["id"], "output_quantity": 1, "components": [{"component_product_id": component["product_id"], "warehouse_id": component["warehouse_id"], "quantity": 4, "unit_cost": 5}]})
    assert bom.status_code == 201, bom.text
    order = client.post(base + "/manufacturing/orders", headers=headers, json={"bom_id": bom.json()["id"], "warehouse_id": component["warehouse_id"], "planned_quantity": 2})
    assert order.status_code == 201, order.text
    return headers, component, finished.json(), bom.json(), order.json()


@pytest.mark.parametrize("quantity", [0, -1])
def test_production_invalid_completion_never_consumes_stock(client, db, production, quantity):
    headers, component, _, _, order = production
    before = db.query(SRMInventoryMovement).count()
    response = client.post(f"/api/v1/srm/inventory/manufacturing/orders/{order['id']}/post", headers=headers, json={"completed_quantity": quantity})
    assert response.status_code in {400, 422}, response.text
    row = db.get(SRMProductionOrder, order["id"])
    db.refresh(row)
    assert row.status == "planned" and row.completed_quantity == 0
    assert db.query(SRMInventoryMovement).count() == before
    assert db.query(SRMInventoryBalance).filter_by(product_id=component["product_id"]).one().quantity == 20


def test_cancelled_production_cannot_post(client, db, production):
    headers, _, _, _, order = production
    row = db.get(SRMProductionOrder, order["id"])
    row.status = "cancelled"
    db.commit()
    before = db.query(SRMInventoryMovement).count()
    response = client.post(f"/api/v1/srm/inventory/manufacturing/orders/{row.id}/post", headers=headers, json={"completed_quantity": 1})
    assert response.status_code == 409, response.text
    db.refresh(row)
    assert row.status == "cancelled" and row.completed_quantity == 0
    assert db.query(SRMInventoryMovement).count() == before


def test_partial_completion_and_omitted_remaining_quantity_are_preserved(client, db, production):
    headers, component, finished, _, order = production
    endpoint = f"/api/v1/srm/inventory/manufacturing/orders/{order['id']}/post"
    first = client.post(endpoint, headers=headers, json={"completed_quantity": 1})
    assert first.status_code == 200, first.text
    assert first.json()["production_order"]["status"] == "partially_completed"
    second = client.post(endpoint, headers=headers, json={})
    assert second.status_code == 200, second.text
    assert second.json()["production_order"]["status"] == "completed"
    assert second.json()["production_order"]["completed_quantity"] == 2
    assert db.query(SRMInventoryBalance).filter_by(product_id=component["product_id"]).one().quantity == 12
    assert db.query(SRMInventoryBalance).filter_by(product_id=finished["id"]).one().quantity == 2
    assert db.get(SRMProductionOrder, order["id"]).total_component_cost == Decimal("40")
    before = db.query(SRMInventoryMovement).count()
    assert client.post(endpoint, headers=headers, json={}).status_code == 409
    assert db.query(SRMInventoryMovement).count() == before


def test_invalid_output_warehouse_never_consumes_components(client, db, production):
    headers, component, _, _, order = production
    before = db.query(SRMInventoryMovement).count()
    response = client.post(f"/api/v1/srm/inventory/manufacturing/orders/{order['id']}/post", headers=headers, json={"completed_quantity": 1, "warehouse_id": 999999})
    assert response.status_code == 404
    assert db.query(SRMInventoryMovement).count() == before
    assert db.query(SRMInventoryBalance).filter_by(product_id=component["product_id"]).one().quantity == 20
    assert db.get(SRMProductionOrder, order["id"]).completed_quantity == 0


def test_production_lookup_reaches_older_orders_and_matches_literal_numbers(client, db, production):
    headers, _, _, bom, original = production
    seed = db.get(SRMProductionOrder, original["id"])
    seed.production_number = "OLD_%\\ORDER"
    added = []
    for index in range(105):
        added.append(SRMProductionOrder(organization_id=seed.organization_id, production_number=f"AUDIT-{index}", bom_id=bom["id"], finished_product_id=seed.finished_product_id, warehouse_id=seed.warehouse_id, planned_quantity=1, order_date=seed.order_date, status="completed" if index == 0 else "planned"))
    db.add_all(added)
    from test_identity_utils import own_workflow_records
    own_workflow_records(db, *added, company_id=seed.organization_id)
    db.commit()
    db.expire_all()
    base = "/api/v1/srm/inventory/manufacturing/orders"
    first = client.get(base, headers=headers, params={"per_page": 100, "open_only": True}).json()
    second = client.get(base, headers=headers, params={"page": 2, "per_page": 100, "open_only": True}).json()
    assert first["total"] == 105 and first["has_more"]
    assert len(second["items"]) == 5 and not second["has_more"]
    assert original["id"] in [item["id"] for item in second["items"]]
    for term in ("%", "_", "\\"):
        result = client.get(base, headers=headers, params={"search": term}).json()
        assert [item["id"] for item in result["items"]] == [original["id"]]
    assert client.get(base, headers=headers, params={"page": 0}).status_code == 422


def test_later_component_shortage_rolls_back_earlier_consumption(client, db, production):
    headers, component, _, bom, order = production
    missing = client.post("/api/v1/srm/inventory/items", headers=headers, json={"sku": "AUDIT-MISSING", "item_name": "Unstocked component", "default_warehouse_id": component["warehouse_id"]})
    assert missing.status_code == 201
    extra = SRMBOMComponent(bom_id=bom["id"], component_product_id=missing.json()["id"], warehouse_id=component["warehouse_id"], quantity=1, unit_cost=1)
    db.add(extra)
    from test_identity_utils import own_workflow_records
    own_workflow_records(db, extra, company_id=order["organization_id"])
    db.commit()
    db.expire_all()
    before = db.query(SRMInventoryMovement).count()
    response = client.post(f"/api/v1/srm/inventory/manufacturing/orders/{order['id']}/post", headers=headers, json={"completed_quantity": 1})
    assert response.status_code == 409
    assert db.query(SRMInventoryMovement).count() == before
    assert db.query(SRMInventoryBalance).filter_by(product_id=component["product_id"]).one().quantity == 20
    assert db.get(SRMProductionOrder, order["id"]).completed_quantity == 0


@pytest.mark.parametrize("change", [{"warehouse_id": 999999}, {"unit_cost": -1}, {"line_total": -1}, {"scrap_percent": -1}, {"scrap_percent": 101}])
def test_bom_rejects_invalid_component_without_saving(client, db, production, change):
    headers, component, finished, _, _ = production
    from app.apps.srm.models import SRMBillOfMaterial
    before = db.query(SRMBillOfMaterial).count()
    response = client.post("/api/v1/srm/inventory/manufacturing/bom", headers=headers, json={"bom_name": "Invalid assembly", "finished_product_id": finished["id"], "components": [{"component_product_id": component["product_id"], "warehouse_id": component["warehouse_id"], "quantity": 1, "unit_cost": 5, **change}]})
    assert response.status_code in {404, 422}
    assert db.query(SRMBillOfMaterial).count() == before


def test_production_creation_rejects_unknown_warehouse(client, db, production):
    headers, _, _, bom, _ = production
    before = db.query(SRMProductionOrder).count()
    response = client.post("/api/v1/srm/inventory/manufacturing/orders", headers=headers, json={"bom_id": bom["id"], "warehouse_id": 999999, "planned_quantity": 1})
    assert response.status_code == 404
    assert db.query(SRMProductionOrder).count() == before


@pytest.mark.parametrize("name", ["   ", "X" * 181])
def test_bom_rejects_invalid_name(client, production, name):
    headers, component, finished, _, _ = production
    response = client.post("/api/v1/srm/inventory/manufacturing/bom", headers=headers, json={"bom_name": name, "finished_product_id": finished["id"], "components": [{"component_product_id": component["product_id"], "quantity": 1}]})
    assert response.status_code == 422


def test_manufacturing_identity_trim_and_zero_cost_auto_pricing(client, db, production):
    headers, component, finished, _, _ = production
    base = "/api/v1/srm/inventory/manufacturing"
    payload = {"bom_number": " QA-BOM ", "bom_name": " Audit BOM ", "finished_product_id": finished["id"], "components": [{"component_product_id": component["product_id"], "quantity": 1, "unit_cost": 0, "scrap_percent": 0}]}
    bom = client.post(base + "/bom", headers=headers, json=payload)
    assert bom.status_code == 201
    assert bom.json()["bom_name"] == "Audit BOM" and bom.json()["bom_number"] == "QA-BOM"
    assert bom.json()["components"][0]["unit_cost"] == 5
    assert client.post(base + "/bom", headers=headers, json=payload).status_code == 409
    order = client.post(base + "/orders", headers=headers, json={"bom_id": bom.json()["id"], "production_number": " QA-ORDER ", "planned_quantity": 1})
    assert order.status_code == 201
    assert order.json()["production_number"] == "QA-ORDER"
    assert client.post(base + "/orders", headers=headers, json={"bom_id": bom.json()["id"], "production_number": "QA-ORDER", "planned_quantity": 1}).status_code == 409


@pytest.mark.parametrize("field", ["unit_cost", "quantity", "output_quantity"])
def test_invalid_historical_bom_cannot_corrupt_stock(client, db, production, field):
    headers, component, _, bom, order = production
    from app.apps.srm.models import SRMBillOfMaterial
    row = db.get(SRMBillOfMaterial, bom["id"])
    if field == "output_quantity":
        row.output_quantity = -1
    else:
        setattr(row.components[0], field, -1)
    db.commit()
    before = db.query(SRMInventoryMovement).count()
    response = client.post(f"/api/v1/srm/inventory/manufacturing/orders/{order['id']}/post", headers=headers, json={"completed_quantity": 1})
    assert response.status_code == 409
    assert db.query(SRMInventoryMovement).count() == before
    assert db.query(SRMInventoryBalance).filter_by(product_id=component["product_id"]).one().quantity == 20
    assert db.get(SRMProductionOrder, order["id"]).completed_quantity == 0



def test_bom_lookup_pages_and_literal_name_or_number_search(client, db, production):
    headers, _, finished, original, _ = production
    from app.apps.srm.models import SRMBillOfMaterial
    from test_identity_utils import own_workflow_records
    lots = [SRMBillOfMaterial(organization_id=original["organization_id"], bom_number=f"PAGE-{index}", bom_name="Old_%\\assembly" if index == 0 else f"Assembly {index}", finished_product_id=finished["id"], output_quantity=1) for index in range(105)]
    db.add_all(lots)
    own_workflow_records(db, *lots, company_id=original["organization_id"])
    db.commit()
    base = "/api/v1/srm/inventory/manufacturing/bom"
    first = client.get(base, headers=headers).json()
    second = client.get(base, headers=headers, params={"page": 2}).json()
    assert first["total"] == 106 and len(first["items"]) == 100 and first["has_more"]
    assert len(second["items"]) == 6 and not second["has_more"]
    assert original["id"] in {row["id"] for row in second["items"]}
    for term in ["%", "_", "\\", "PAGE-0"]:
        found = client.get(base, headers=headers, params={"search": term}).json()
        assert [row["id"] for row in found["items"]] == [lots[0].id]
    for params in [{"page": 0}, {"per_page": 101}]:
        assert client.get(base, headers=headers, params=params).status_code == 422
