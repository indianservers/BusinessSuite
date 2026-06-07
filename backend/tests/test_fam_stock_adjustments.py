from tests.fam_inventory_test_utils import create_stock_item, inventory_headers, post_opening_stock


def test_fam_stock_adjustment_posts_stock_and_accounting_voucher(client, db):
    headers = inventory_headers(client, db)
    item, warehouse = create_stock_item(client, headers, "ADJ")
    post_opening_stock(client, headers, item, warehouse, quantity=3, rate=100, suffix="ADJ")
    draft = client.post("/api/v1/fam/inventory/stock-adjustments", headers=headers, json={"adjustment_date": "2026-06-06", "warehouse_id": warehouse["id"], "reason": "Cycle count", "lines": [{"stock_item_id": item["id"], "quantity_in": 2, "rate": 100}]})
    assert draft.status_code == 201, draft.text
    posted = client.post(f"/api/v1/fam/inventory/stock-adjustments/{draft.json()['id']}/post", headers=headers, json={"adjustment_date": "2026-06-06", "warehouse_id": warehouse["id"], "lines": [{"stock_item_id": item["id"], "quantity_in": 2, "rate": 100}]})
    assert posted.status_code == 200, posted.text
    assert posted.json()["voucher_id"] is not None
    detail = client.get(f"/api/v1/fam/inventory/items/{item['id']}", headers=headers).json()
    assert detail["current_quantity"] == 5
