from tests.fam_inventory_test_utils import create_stock_item, inventory_headers


def test_negative_stock_blocked_until_admin_control_allows_it(client, db):
    headers = inventory_headers(client, db, "phase9-negative@example.com")
    item, warehouse = create_stock_item(client, headers, "P9-NEG")

    blocked = client.post(
        "/api/v1/fam/inventory/stock-out",
        headers=headers,
        json={"movement_date": "2026-06-07", "movement_type": "stock_out", "lines": [{"stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity_out": 1, "rate": 100}]},
    )
    assert blocked.status_code == 409

    setting = client.put("/api/v1/fam/inventory/controls", headers=headers, json={"setting_key": "allow_negative_stock", "setting_value_json": {"value": True}, "description": "Temporary controlled exception"})
    assert setting.status_code == 200, setting.text

    allowed = client.post(
        "/api/v1/fam/inventory/stock-out",
        headers=headers,
        json={"movement_date": "2026-06-07", "movement_type": "stock_out", "lines": [{"stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity_out": 1, "rate": 100}]},
    )
    assert allowed.status_code == 201, allowed.text
    assert allowed.json()["status"] == "posted"
