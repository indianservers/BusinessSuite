import pytest

from app.apps.srm.models import SRMInventoryBatch, SRMSerialNumber
from tests.test_erp_audit_procurement import procurement


@pytest.mark.parametrize("kind,change", [
    ("batches", {"batch_number": "   "}),
    ("batches", {"unit_cost": -1}),
    ("batches", {"quantity": -1}),
    ("batches", {"available_quantity": 6}),
    ("serial-numbers", {"serial_number": "   "}),
])
def test_inventory_tracking_rejects_invalid_identity_and_amounts(client, db, procurement, kind, change):
    headers, line, _ = procurement
    payload = {"product_id": line["product_id"], "warehouse_id": line["warehouse_id"]}
    payload.update({"batch_number": "AUDIT-LOT", "quantity": 5, "unit_cost": 12} if kind == "batches" else {"serial_number": "AUDIT-SERIAL"})
    payload.update(change)
    response = client.post("/api/v1/srm/inventory/" + kind, headers=headers, json=payload)
    assert response.status_code in {400, 422}, response.text
    assert db.query(SRMInventoryBatch).count() == 0
    assert db.query(SRMSerialNumber).count() == 0


def test_tracking_trims_identity_and_retains_duplicate_guards(client, db, procurement):
    headers, line, _ = procurement
    base = {"product_id": line["product_id"], "warehouse_id": line["warehouse_id"]}
    batch = client.post("/api/v1/srm/inventory/batches", headers=headers, json={**base, "batch_number": "  AUDIT-LOT  ", "quantity": 0, "unit_cost": 0})
    assert batch.status_code == 201, batch.text
    assert batch.json()["batch_number"] == "AUDIT-LOT"
    assert client.post("/api/v1/srm/inventory/batches", headers=headers, json={**base, "batch_number": "AUDIT-LOT"}).status_code == 409
    serial = client.post("/api/v1/srm/inventory/serial-numbers", headers=headers, json={**base, "batch_id": batch.json()["id"], "serial_number": "  AUDIT-SERIAL  "})
    assert serial.status_code == 201, serial.text
    assert serial.json()["serial_number"] == "AUDIT-SERIAL"
    assert serial.json()["batch_id"] == batch.json()["id"]
    assert client.post("/api/v1/srm/inventory/serial-numbers", headers=headers, json={**base, "serial_number": "AUDIT-SERIAL"}).status_code == 409
    assert db.query(SRMInventoryBatch).count() == db.query(SRMSerialNumber).count() == 1


def test_batch_lookup_pages_beyond_200_and_matches_literal_numbers(client, db, procurement):
    headers, line, order = procurement
    lots = [SRMInventoryBatch(organization_id=order["organization_id"], product_id=line["product_id"], warehouse_id=line["warehouse_id"], batch_number="OLD%_\\LOT" if index == 0 else f"LOT-{index:03d}", quantity=5, available_quantity=5) for index in range(205)]
    db.add_all(lots)
    from test_identity_utils import own_workflow_records
    own_workflow_records(db, *lots, company_id=order["organization_id"])
    db.commit()
    serial = client.post("/api/v1/srm/inventory/serial-numbers", headers=headers, json={"product_id": line["product_id"], "batch_id": lots[-1].id, "serial_number": "LOOKUP-SERIAL"})
    assert serial.status_code == 201, serial.text
    assert serial.json()["warehouse_id"] == line["warehouse_id"]
    base = "/api/v1/srm/inventory/batches"
    from sqlalchemy import event
    serial_reads = []
    def observe(_conn, _cursor, statement, _params, _context, _many):
        if "from srm_serial_numbers" in statement.lower():
            serial_reads.append(statement)
    event.listen(db.bind, "before_cursor_execute", observe)
    try:
        first = client.get(base, headers=headers)
    finally:
        event.remove(db.bind, "before_cursor_execute", observe)
    assert first.status_code == 200, first.text
    assert len(serial_reads) == 1
    assert len(first.json()["items"]) == 200
    assert first.json()["total"] == 205
    assert first.json()["has_more"] is True
    assert next(row for row in first.json()["items"] if row["id"] == lots[-1].id)["serial_count"] == 1
    second = client.get(base, headers=headers, params={"page": 2}).json()
    assert len(second["items"]) == 5 and second["has_more"] is False
    assert lots[0].id in {row["id"] for row in second["items"]}
    for term in ["%_", "\\", "old%_\\lot"]:
        result = client.get(base, headers=headers, params={"product_id": line["product_id"], "search": term, "per_page": 30})
        assert result.status_code == 200, result.text
        assert [row["id"] for row in result.json()["items"]] == [lots[0].id]
    for params in [{"page": 0}, {"per_page": 0}, {"per_page": 201}]:
        assert client.get(base, headers=headers, params=params).status_code == 422
