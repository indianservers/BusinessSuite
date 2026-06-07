from tests.fam_inventory_test_utils import create_stock_item, inventory_headers, post_opening_stock


def test_inventory_srm_link_shows_reservations_and_movements(client, db):
    headers = inventory_headers(client, db, "phase9-srm@example.com")
    item, warehouse = create_stock_item(client, headers, "P9-SRM")
    post_opening_stock(client, headers, item, warehouse, quantity=10, rate=100, suffix="P9-SRM")

    reserve = client.post(
        "/api/v1/fam/inventory/reserve-stock",
        headers=headers,
        json={"stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity": 2, "source_module": "srm", "source_record_type": "sales_order", "source_record_id": "SO-P9"},
    )
    assert reserve.status_code == 201, reserve.text
    movement = client.post(
        "/api/v1/fam/inventory/delivery-notes",
        headers=headers,
        json={"movement_date": "2026-06-07", "movement_type": "delivery_note", "source_module": "srm", "source_record_type": "invoice", "source_record_id": "INV-P9", "lines": [{"stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity_out": 1, "rate": 100}]},
    )
    assert movement.status_code == 201, movement.text

    link = client.get("/api/v1/fam/inventory/srm-link", headers=headers)
    assert link.status_code == 200, link.text
    assert link.json()["total"] >= 2
