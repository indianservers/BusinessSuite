from app.apps.fam.models import FAMStockMovement, FAMVoucher
from tests.fam_inventory_test_utils import create_stock_item, inventory_headers
from tests.test_erp_audit_procurement import procurement


def test_audit_finance_stock_documents_are_atomic_and_match_quantity_direction(client, db):
    headers = inventory_headers(client, db)
    item, warehouse = create_stock_item(client, headers, "AUD-DOC")
    base = "/api/v1/fam/inventory"
    opening = {"stock_item_id": item["id"], "warehouse_id": warehouse["id"], "opening_date": "2026-06-06", "quantity": 5, "rate": 10}
    for change in [{"quantity": 0}, {"quantity": -1}, {"rate": -1}]:
        assert client.post(f"{base}/opening-stock", headers=headers, json={**opening, **change}).status_code == 422
    assert db.query(FAMStockMovement).count() == 0
    response = client.post(f"{base}/opening-stock", headers=headers, json=opening)
    assert response.status_code == 201, response.text
    expected = 5
    for path, kind, incoming in [("stock-in", "stock_in", True), ("purchase-receipts", "purchase_receipt", True), ("stock-out", "stock_out", False), ("delivery-notes", "delivery_note", False)]:
        direction = "quantity_in" if incoming else "quantity_out"
        wrong = "quantity_out" if incoming else "quantity_in"
        line = {"stock_item_id": item["id"], "warehouse_id": warehouse["id"], direction: 2, "rate": 10}
        payload = {"movement_date": "2026-06-07", "movement_type": kind, "lines": [line]}
        movements, vouchers = db.query(FAMStockMovement).count(), db.query(FAMVoucher).count()
        invalid = [{**payload, "lines": []}, {**payload, "lines": [{**line, direction: 0}]}, {**payload, "lines": [{**line, direction: -1}]}, {**payload, "lines": [{**line, "rate": -1}]}, {**payload, "lines": [{**line, direction: 0, wrong: 1}]}, {**payload, "lines": [{**line, "stock_item_id": 999999}]}]
        if not incoming:
            invalid.append({**payload, "lines": [{**line, direction: 999}]})
        for bad in invalid:
            response = client.post(f"{base}/{path}", headers=headers, json=bad)
            assert response.status_code in (404, 409, 422), response.text
            assert db.query(FAMStockMovement).count() == movements
            assert db.query(FAMVoucher).count() == vouchers
            assert client.get(f"{base}/items/{item['id']}", headers=headers).json()["current_quantity"] == expected
        response = client.post(f"{base}/{path}", headers=headers, json=payload)
        assert response.status_code == 201, response.text
        assert response.json()["status"] == "posted"
        expected += 2 if incoming else -2
        assert client.get(f"{base}/items/{item['id']}", headers=headers).json()["current_quantity"] == expected
        assert db.query(FAMStockMovement).count() == movements + 1
        assert db.query(FAMVoucher).count() == vouchers + (0 if kind == "stock_in" else 1)


def test_audit_sales_stock_documents_reject_invalid_amounts_and_preserve_stock_on_failure(client, db, procurement):
    from app.apps.srm.models import SRMInventoryMovement
    headers, selected, _ = procurement
    base = "/api/v1/srm/inventory"
    opening = {"product_id": selected["product_id"], "warehouse_id": selected["warehouse_id"], "quantity": 5, "rate": 10}
    for change in [{"quantity": 0}, {"quantity": -1}, {"rate": -1}]:
        assert client.post(f"{base}/opening-stock", headers=headers, json={**opening, **change}).status_code == 422
    response = client.post(f"{base}/opening-stock", headers=headers, json=opening)
    assert response.status_code == 201, response.text
    expected = 5
    for kind, incoming in [("stock_in", True), ("purchase_receipt", True), ("stock_out", False), ("delivery_note", False)]:
        payload = {**opening, "movement_type": kind, "quantity": 2}
        count = db.query(SRMInventoryMovement).count()
        changes = [{"quantity": 0}, {"quantity": -1}, {"rate": -1}, {"product_id": 999999}, {"warehouse_id": 999999}]
        if not incoming:
            changes.append({"quantity": 999})
        for change in changes:
            response = client.post(f"{base}/stock-movements", headers=headers, json={**payload, **change})
            assert response.status_code in (404, 409, 422), response.text
            assert db.query(SRMInventoryMovement).count() == count
            assert client.get(f"{base}/items/{selected['product_id']}", headers=headers).json()["current_quantity"] == expected
        response = client.post(f"{base}/stock-movements", headers=headers, json=payload)
        assert response.status_code == 201, response.text
        expected += 2 if incoming else -2
        assert client.get(f"{base}/items/{selected['product_id']}", headers=headers).json()["current_quantity"] == expected
