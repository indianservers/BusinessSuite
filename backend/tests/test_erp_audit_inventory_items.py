from tests.fam_inventory_test_utils import create_stock_item, inventory_headers
from tests.test_erp_audit_procurement import procurement


def test_audit_finance_item_rejects_foreign_and_inactive_master_references(client, db):
    from app.apps.fam.models import FAMStockGroup, FAMUnitOfMeasure, FAMWarehouse
    from app.models.company import Company

    headers = inventory_headers(client, db)
    item, warehouse = create_stock_item(client, headers, "AUD-SCOPE")
    company_id = db.get(FAMWarehouse, warehouse["id"]).company_id
    other = Company(name="Other inventory company")
    db.add(other)
    db.flush()
    models = [("stock_group_id", FAMStockGroup, {"group_code": "AUD", "group_name": "Audit group"}), ("unit_id", FAMUnitOfMeasure, {"unit_code": "AUD", "unit_name": "Audit unit"}), ("default_warehouse_id", FAMWarehouse, {"warehouse_code": "AUD", "warehouse_name": "Audit warehouse"})]
    bad = []
    for field, model, values in models:
        for owner, active in [(other.id, True), (company_id, False)]:
            row = model(company_id=owner, active=active, **values)
            db.add(row)
            db.flush()
            bad.append((field, row.id))
    db.commit()
    base = "/api/v1/fam/inventory/items"
    before = client.get(base, headers=headers).json()["total"]
    for field, value in bad:
        response = client.post(base, headers=headers, json={"sku": "AUD-REJECT", "item_name": "Rejected item", field: value})
        assert response.status_code == 422, response.text
        assert client.get(base, headers=headers).json()["total"] == before


def test_audit_finance_item_rejects_invalid_values_and_master_references(client, db):
    headers = inventory_headers(client, db)
    item, warehouse = create_stock_item(client, headers, "AUD-ITEM")
    base = "/api/v1/fam/inventory/items"
    before = client.get(base, headers=headers).json()["total"]
    payload = {"sku": "AUD-NEW", "item_name": "Office paper", "stock_group_id": item["stock_group_id"], "unit_id": item["unit_id"], "default_warehouse_id": warehouse["id"]}
    changes = [{field: -1} for field in ["purchase_rate", "sales_rate", "reorder_level", "min_stock", "max_stock"]]
    changes += [{"sku": "  "}, {"item_name": "  "}, {"sku": "X" * 81}]
    changes += [{field: 999999} for field in ["stock_group_id", "unit_id", "default_warehouse_id"]]
    for change in changes:
        response = client.post(base, headers=headers, json={**payload, **change})
        assert response.status_code == 422, response.text
        assert client.get(base, headers=headers).json()["total"] == before
    response = client.post(base, headers=headers, json={**payload, "sku": "  AUD-NEW  ", "item_name": "  Office paper  ", "purchase_rate": 25})
    assert response.status_code == 201, response.text
    assert response.json()["sku"] == "AUD-NEW"
    assert response.json()["item_name"] == "Office paper"
    assert response.json()["stock_group_id"] == payload["stock_group_id"]
    assert response.json()["unit_id"] == payload["unit_id"]


def test_audit_sales_item_rejects_negative_amounts_and_invalid_gst(client, procurement):
    headers, line, _ = procurement
    base = "/api/v1/srm/inventory/items"
    before = client.get(base, headers=headers).json()["total"]
    changes = [{field: -1} for field in ["purchase_rate", "sales_rate", "reorder_level", "min_stock", "max_stock", "mrp", "gst_rate"]]
    changes += [{"gst_rate": 101}, {"sku": "  "}, {"item_name": "  "}]
    for change in changes:
        response = client.post(base, headers=headers, json={"sku": "AUD-NEW", "item_name": "Office paper", **change})
        assert response.status_code == 422, response.text
        assert client.get(base, headers=headers).json()["total"] == before
    for change in [{"purchase_rate": -1}, {"gst_rate": 101}]:
        response = client.put(f"{base}/{line['product_id']}", headers=headers, json=change)
        assert response.status_code == 422, response.text
    response = client.post(base, headers=headers, json={"sku": "  AUD-NEW  ", "item_name": "  Office paper  ", "purchase_rate": 25, "gst_rate": 18})
    assert response.status_code == 201, response.text
    assert response.json()["sku"] == "AUD-NEW"
    assert response.json()["item_name"] == "Office paper"
    assert response.json()["gst_rate"] == 18
