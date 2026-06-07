from tests.fam_inventory_test_utils import create_stock_item, inventory_headers, post_opening_stock


def test_fam_inventory_opening_stock_updates_quantity_and_valuation(client, db):
    headers = inventory_headers(client, db)
    item, warehouse = create_stock_item(client, headers, "OPEN")
    opening = post_opening_stock(client, headers, item, warehouse, quantity=12, rate=80, suffix="OPEN")
    assert opening["value"] == 960
    detail = client.get(f"/api/v1/fam/inventory/items/{item['id']}", headers=headers).json()
    assert detail["current_quantity"] == 12
    assert detail["average_cost"] == 80
    valuation = client.get("/api/v1/fam/inventory/valuation", headers=headers)
    assert valuation.status_code == 200
    assert valuation.json()["total_inventory_value"] >= 960
