from tests.fam_inventory_test_utils import create_stock_item, inventory_headers, post_opening_stock


def test_fam_reorder_alerts_return_low_stock_items(client, db):
    headers = inventory_headers(client, db)
    item, warehouse = create_stock_item(client, headers, "REORDER", reorder_level=10)
    post_opening_stock(client, headers, item, warehouse, quantity=4, rate=25, suffix="REORDER")
    response = client.get("/api/v1/fam/inventory/reorder-alerts", headers=headers)
    assert response.status_code == 200
    assert any(record["id"] == item["id"] for record in response.json()["items"])
