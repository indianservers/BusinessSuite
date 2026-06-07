from app.apps.fam.models import FAMAuditLog
from tests.fam_inventory_test_utils import create_stock_item, inventory_headers, post_opening_stock


def test_inventory_postings_are_audited_and_posted_records_are_not_reposted(client, db):
    headers = inventory_headers(client, db, "phase9-audit@example.com")
    item, warehouse = create_stock_item(client, headers, "P9-AUD")
    opening = post_opening_stock(client, headers, item, warehouse, quantity=2, rate=100, suffix="P9-AUD")

    movement_id = opening["movement"]["id"]
    repost = client.post(
        f"/api/v1/fam/inventory/stock-movements/{movement_id}/post",
        headers=headers,
        json={"movement_date": "2026-06-07", "movement_type": "opening_stock", "lines": [{"stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity_in": 1, "rate": 100}]},
    )
    assert repost.status_code == 409
    assert db.query(FAMAuditLog).filter(FAMAuditLog.record_type.like("inventory_%")).count() >= 1

    audit = client.get("/api/v1/fam/inventory/audit", headers=headers)
    assert audit.status_code == 200, audit.text
    assert audit.json()["total"] >= 1
