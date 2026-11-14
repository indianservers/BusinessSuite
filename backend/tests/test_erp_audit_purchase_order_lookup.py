from datetime import date

from app.apps.srm.models import SRMPurchaseOrder
from tests.test_erp_audit_procurement import procurement


def test_audit_purchase_order_lookup_pages_old_orders_and_escapes_literal_search(client, db, procurement):
    headers, _, original = procurement
    rows = []
    for index in range(105):
        vendor = "Audit supplier"
        if index == 104:
            vendor = "Audit 100%_done"
        elif index == 103:
            vendor = "Audit 100Xdone"
        elif index == 102:
            vendor = "Audit A\\B"
        row = SRMPurchaseOrder(organization_id=original["organization_id"], po_number=f"QA-{index:03d}", vendor_name=vendor, status="received" if index == 0 else "cancelled" if index == 1 else "ordered", order_date=date(2026, 11, 13), created_by=original["created_by"])
        db.add(row)
        rows.append(row)
    foreign = SRMPurchaseOrder(organization_id=original["organization_id"] + 1000, po_number="QA-FOREIGN", vendor_name="Audit supplier", status="ordered", order_date=date(2026, 11, 13))
    db.add(foreign)
    from test_identity_utils import own_workflow_records
    own_workflow_records(db, *rows, company_id=original["organization_id"])
    db.commit()
    base = "/api/v1/srm/procurement/purchase-orders"
    # Serializing a page must not run one line query for every order.
    from sqlalchemy import event
    line_reads = []
    def capture_lines(_connection, _cursor, statement, _parameters, _context, _executemany):
        if "from srm_purchase_order_lines" in statement.lower():
            line_reads.append(statement)
    event.listen(db.bind, "before_cursor_execute", capture_lines)
    try:
        first = client.get(base, headers=headers)
    finally:
        event.remove(db.bind, "before_cursor_execute", capture_lines)
    assert len(line_reads) == 1
    assert first.status_code == 200
    first = first.json()
    assert first["total"] == 106
    assert len(first["items"]) == 100
    assert first["has_more"] is True
    assert original["id"] not in {row["id"] for row in first["items"]}
    second = client.get(base, headers=headers, params={"page": 2}).json()
    assert len(second["items"]) == 6
    assert second["has_more"] is False
    assert original["id"] in {row["id"] for row in second["items"]}
    assert not {row["id"] for row in first["items"]} & {row["id"] for row in second["items"]}
    result = client.get(base, headers=headers, params={"search": original["po_number"], "receivable_only": True, "per_page": 30}).json()
    assert result["total"] == 1
    assert result["items"][0]["id"] == original["id"]
    result = client.get(base, headers=headers, params={"search": "100%_"}).json()
    assert result["total"] == 1
    assert result["items"][0]["vendor_name"] == "Audit 100%_done"
    result = client.get(base, headers=headers, params={"search": "a\\b"}).json()
    assert result["total"] == 1
    assert result["items"][0]["vendor_name"] == "Audit A\\B"
    all_options = client.get(base, headers=headers, params={"receivable_only": True, "per_page": 100}).json()
    assert all_options["total"] == 104
    assert all(row["status"] in ("ordered", "partially_received") for row in all_options["items"])
    assert all(row["id"] != foreign.id for row in all_options["items"])
    for params in [{"page": 0}, {"per_page": 0}, {"per_page": 101}]:
        assert client.get(base, headers=headers, params=params).status_code == 422


def test_audit_receipt_rechecks_order_status_before_stock_write(client, db, procurement):
    headers, selected, original = procurement
    order = db.get(SRMPurchaseOrder, original["id"])
    for status in ["received", "cancelled", "closed"]:
        order.status = status
        db.commit()
        response = client.post("/api/v1/srm/procurement/grn", headers=headers, json={"purchase_order_id": order.id, "lines": [{"purchase_order_line_id": original["lines"][0]["id"], "quantity": 1, "accepted_quantity": 1, "unit_price": 12}]})
        assert response.status_code == 409, response.text
        assert client.get("/api/v1/srm/procurement/grn", headers=headers).json()["total"] == 0
        assert client.get(f"/api/v1/srm/inventory/items/{selected['product_id']}", headers=headers).json()["current_quantity"] == 0
