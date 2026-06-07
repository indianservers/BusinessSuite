from tests.fam_inventory_test_utils import inventory_headers


def test_fam_inventory_warehouse_create_and_list(client, db):
    headers = inventory_headers(client, db)
    response = client.post("/api/v1/fam/inventory/warehouses", headers=headers, json={"warehouse_code": "BLR", "warehouse_name": "Bengaluru Warehouse", "address": "Bengaluru"})
    assert response.status_code == 201, response.text
    listed = client.get("/api/v1/fam/inventory/warehouses", headers=headers)
    assert listed.status_code == 200
    assert any(item["warehouse_code"] == "BLR" for item in listed.json()["items"])
