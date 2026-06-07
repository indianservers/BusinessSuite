from tests.fam_inventory_test_utils import create_stock_item, inventory_headers, post_opening_stock


def test_fam_inventory_cogs_posts_voucher(client, db):
    headers = inventory_headers(client, db)
    item, warehouse = create_stock_item(client, headers, "COGS")
    post_opening_stock(client, headers, item, warehouse, quantity=10, rate=40, suffix="COGS")
    response = client.post("/api/v1/fam/inventory/cogs/post", headers=headers, json={"stock_item_id": item["id"], "quantity": 2, "posting_date": "2026-06-06", "reference_number": "COGS-001"})
    assert response.status_code == 200, response.text
    assert response.json()["amount"] == 80
    assert response.json()["voucher"]["status"] == "posted"
