from app.apps.fam.models import FAMInventoryReservation
from tests.fam_inventory_test_utils import create_stock_item, inventory_headers, post_opening_stock


def test_inventory_reserve_and_release_stock(client, db):
    headers = inventory_headers(client, db, "phase9-reserve@example.com")
    item, warehouse = create_stock_item(client, headers, "P9-RSV")
    post_opening_stock(client, headers, item, warehouse, quantity=12, rate=100, suffix="P9-RSV")

    reserve = client.post(
        "/api/v1/fam/inventory/reserve-stock",
        headers=headers,
        json={"stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity": 4, "source_module": "srm", "source_record_type": "sales_order", "source_record_id": "SO-1"},
    )
    assert reserve.status_code == 201, reserve.text
    assert reserve.json()["reserved_quantity"] == 4

    detail = client.get(f"/api/v1/fam/inventory/items/{item['id']}", headers=headers)
    assert detail.json()["available_quantity"] == 8

    repeat = client.post(
        "/api/v1/fam/inventory/reserve-stock",
        headers=headers,
        json={"stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity": 4, "source_module": "srm", "source_record_type": "sales_order", "source_record_id": "SO-1"},
    )
    assert repeat.status_code == 201
    assert repeat.json()["idempotent"] is True

    release = client.post("/api/v1/fam/inventory/release-reservation", headers=headers, json={"reservation_id": reserve.json()["id"], "notes": "Quote expired"})
    assert release.status_code == 200, release.text
    assert release.json()["status"] == "released"
    assert db.query(FAMInventoryReservation).filter(FAMInventoryReservation.status == "active").count() == 0
