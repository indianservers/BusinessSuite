from app.apps.fam.models import FAMStockMovement, FAMVoucher
from tests.fam_inventory_test_utils import create_stock_item, inventory_headers, post_opening_stock


def test_inventory_delivery_posts_stock_and_cogs_voucher(client, db):
    headers = inventory_headers(client, db, "phase9-accounting@example.com")
    item, warehouse = create_stock_item(client, headers, "P9-ACC")
    post_opening_stock(client, headers, item, warehouse, quantity=8, rate=100, suffix="P9-ACC")

    delivery = client.post(
        "/api/v1/fam/inventory/delivery-notes",
        headers=headers,
        json={"movement_date": "2026-06-07", "movement_type": "delivery_note", "reference_number": "DN-P9", "source_module": "srm", "source_record_type": "invoice", "source_record_id": "9", "lines": [{"stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity_out": 3, "rate": 100}]},
    )
    assert delivery.status_code == 201, delivery.text
    assert delivery.json()["voucher_id"]

    movement = db.query(FAMStockMovement).filter(FAMStockMovement.id == delivery.json()["id"]).one()
    assert movement.status == "posted"
    assert db.query(FAMVoucher).filter(FAMVoucher.id == movement.voucher_id).one().status == "posted"


def test_post_cogs_rejects_duplicate_source_deduction(client, db):
    headers = inventory_headers(client, db, "phase9-cogs@example.com")
    item, warehouse = create_stock_item(client, headers, "P9-COGS")
    post_opening_stock(client, headers, item, warehouse, quantity=5, rate=100, suffix="P9-COGS")
    payload = {"stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity": 1, "posting_date": "2026-06-07", "source_module": "srm", "source_record_type": "invoice_line", "source_record_id": "77"}

    first = client.post("/api/v1/fam/inventory/post-cogs", headers=headers, json=payload)
    assert first.status_code == 200, first.text
    second = client.post("/api/v1/fam/inventory/post-cogs", headers=headers, json=payload)
    assert second.status_code == 409
