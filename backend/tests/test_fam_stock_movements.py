from tests.fam_inventory_test_utils import create_stock_item, inventory_headers, post_opening_stock


def test_fam_stock_out_posts_and_blocks_negative_stock(client, db):
    headers = inventory_headers(client, db)
    item, warehouse = create_stock_item(client, headers, "MOV")
    post_opening_stock(client, headers, item, warehouse, quantity=5, rate=100, suffix="MOV")
    draft = client.post("/api/v1/fam/inventory/stock-movements", headers=headers, json={"movement_date": "2026-06-06", "movement_type": "stock_out"})
    assert draft.status_code == 201, draft.text
    posted = client.post(f"/api/v1/fam/inventory/stock-movements/{draft.json()['id']}/post", headers=headers, json={"movement_date": "2026-06-06", "movement_type": "stock_out", "lines": [{"stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity_out": 2, "rate": 100}]})
    assert posted.status_code == 200, posted.text
    detail = client.get(f"/api/v1/fam/inventory/items/{item['id']}", headers=headers).json()
    assert detail["current_quantity"] == 3
    too_much = client.post("/api/v1/fam/inventory/stock-movements", headers=headers, json={"movement_date": "2026-06-06", "movement_type": "stock_out"})
    rejected = client.post(f"/api/v1/fam/inventory/stock-movements/{too_much.json()['id']}/post", headers=headers, json={"movement_date": "2026-06-06", "movement_type": "stock_out", "lines": [{"stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity_out": 99, "rate": 100}]})
    assert rejected.status_code == 409
