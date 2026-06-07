from tests.fam_test_utils import fam_admin_headers


def inventory_headers(client, db, email="fam-inventory-admin@example.com"):
    return fam_admin_headers(client, db, email=email)


def create_inventory_master_set(client, headers, suffix="1"):
    group = client.post("/api/v1/fam/inventory/stock-groups", headers=headers, json={"group_code": f"GRP-{suffix}", "group_name": f"Group {suffix}"})
    assert group.status_code == 201, group.text
    unit = client.post("/api/v1/fam/inventory/units", headers=headers, json={"unit_code": f"PCS-{suffix}", "unit_name": "Pieces", "symbol": "pcs"})
    assert unit.status_code == 201, unit.text
    warehouse = client.post("/api/v1/fam/inventory/warehouses", headers=headers, json={"warehouse_code": f"WH-{suffix}", "warehouse_name": f"Warehouse {suffix}"})
    assert warehouse.status_code == 201, warehouse.text
    return group.json(), unit.json(), warehouse.json()


def create_stock_item(client, headers, suffix="1", reorder_level=5):
    group, unit, warehouse = create_inventory_master_set(client, headers, suffix)
    payload = {
        "sku": f"SKU-{suffix}",
        "item_name": f"Stock Item {suffix}",
        "stock_group_id": group["id"],
        "unit_id": unit["id"],
        "default_warehouse_id": warehouse["id"],
        "hsn_code": "8471",
        "purchase_rate": 100,
        "sales_rate": 150,
        "reorder_level": reorder_level,
        "min_stock": reorder_level,
    }
    response = client.post("/api/v1/fam/inventory/items", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json(), warehouse


def post_opening_stock(client, headers, item, warehouse, quantity=10, rate=100, suffix="1"):
    response = client.post("/api/v1/fam/inventory/opening-stock", headers=headers, json={"opening_number": f"OPEN-{suffix}", "opening_date": "2026-06-06", "stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity": quantity, "rate": rate})
    assert response.status_code == 201, response.text
    return response.json()
