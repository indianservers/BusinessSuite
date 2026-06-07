from tests.fam_inventory_test_utils import create_stock_item, inventory_headers, post_opening_stock


def test_inventory_srm_reconciliation_exposes_duplicate_guard_position(client, db):
    headers = inventory_headers(client, db, "phase9-srm-recon@example.com")
    item, warehouse = create_stock_item(client, headers, "P9-SRM-REC")
    post_opening_stock(client, headers, item, warehouse, quantity=3, rate=100, suffix="P9-SRM-REC")
    client.post("/api/v1/fam/inventory/reserve-stock", headers=headers, json={"stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity": 1, "source_module": "srm", "source_record_type": "sales_order", "source_record_id": "SO-REC"})

    response = client.get("/api/v1/fam/inventory/reconciliation/srm", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["inventory_reservations"] == 1
    assert "duplicate" in response.json()["duplicate_deduction_guard"]
