from tests.fam_inventory_test_utils import create_inventory_master_set, create_stock_item, inventory_headers, post_opening_stock


def test_fam_stock_transfer_posts_without_changing_total_quantity(client, db):
    headers = inventory_headers(client, db)
    item, warehouse_from = create_stock_item(client, headers, "TRF")
    _group, _unit, warehouse_to = create_inventory_master_set(client, headers, "TRF2")
    post_opening_stock(client, headers, item, warehouse_from, quantity=6, rate=100, suffix="TRF")
    draft = client.post("/api/v1/fam/inventory/stock-transfers", headers=headers, json={"transfer_date": "2026-06-06", "from_warehouse_id": warehouse_from["id"], "to_warehouse_id": warehouse_to["id"], "lines": [{"stock_item_id": item["id"], "quantity": 2, "rate": 100}]})
    assert draft.status_code == 201, draft.text
    posted = client.post(f"/api/v1/fam/inventory/stock-transfers/{draft.json()['id']}/post", headers=headers)
    assert posted.status_code == 200, posted.text
    detail = client.get(f"/api/v1/fam/inventory/items/{item['id']}", headers=headers).json()
    assert detail["current_quantity"] == 6
    duplicate_post = client.post(f"/api/v1/fam/inventory/stock-transfers/{draft.json()['id']}/post", headers=headers)
    assert duplicate_post.status_code == 409
