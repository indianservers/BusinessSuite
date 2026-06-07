from tests.fam_inventory_test_utils import create_stock_item, inventory_headers


def test_fam_inventory_item_create_view_and_duplicate_prevention(client, db):
    headers = inventory_headers(client, db)
    item, _warehouse = create_stock_item(client, headers, "ITEM")
    detail = client.get(f"/api/v1/fam/inventory/items/{item['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["sku"] == "SKU-ITEM"
    duplicate = client.post("/api/v1/fam/inventory/items", headers=headers, json={"sku": "SKU-ITEM", "item_name": "Duplicate"})
    assert duplicate.status_code == 409
