import pytest

from tests.fam_inventory_test_utils import create_inventory_master_set, create_stock_item, inventory_headers
from tests.srm_test_utils import auth_headers_for


@pytest.mark.parametrize("source", ["fam", "srm"])
def test_audit_invalid_stock_movements_do_not_create_records_or_change_stock(client, db, source):
    if source == "fam":
        headers = inventory_headers(client, db)
        item, warehouse = create_stock_item(client, headers, "AUD-MOV")
        _, _, destination = create_inventory_master_set(client, headers, "AUD-DEST")
    else:
        headers = auth_headers_for(client, db, "audit-stock@srm.example.com", "srm_sales_manager", permissions=["srm_view", "srm_manage"])
        response = client.post("/api/v1/srm/inventory/warehouses", headers=headers, json={"warehouse_code": "AUD-MAIN", "warehouse_name": "Main store"})
        assert response.status_code == 201
        warehouse = response.json()
        response = client.post("/api/v1/srm/inventory/warehouses", headers=headers, json={"warehouse_code": "AUD-DEST", "warehouse_name": "Reserve store"})
        assert response.status_code == 201
        destination = response.json()
        response = client.post("/api/v1/srm/inventory/items", headers=headers, json={"sku": "AUD-MOV", "item_name": "Audit paper", "default_warehouse_id": warehouse["id"]})
        assert response.status_code == 201
        item = response.json()
    base = f"/api/v1/{source}/inventory"
    transfer_line = {"stock_item_id": item["id"], "quantity": 2, "rate": 12}
    adjustment_line = {"stock_item_id": item["id"], "quantity_in": 2, "quantity_out": 0, "rate": 12}
    if source == "fam":
        transfer = {"transfer_date": "2026-11-13", "from_warehouse_id": warehouse["id"], "to_warehouse_id": destination["id"], "lines": [transfer_line]}
        adjustment = {"adjustment_date": "2026-11-13", "warehouse_id": warehouse["id"], "lines": [adjustment_line]}
        invalid_transfers = [{**transfer, "lines": [{**transfer_line, **change}]} for change in [{"quantity": 0}, {"quantity": -2}, {"rate": -12}, {"stock_item_id": 999999}]] + [{**transfer, "lines": []}]
        invalid_adjustments = [{**adjustment, "lines": [{**adjustment_line, **change}]} for change in [{"quantity_in": -1}, {"quantity_in": 0}, {"quantity_out": 1}, {"rate": -12}, {"stock_item_id": 999999}]] + [{**adjustment, "lines": []}]
    else:
        transfer = {"product_id": item["id"], "from_warehouse_id": warehouse["id"], "to_warehouse_id": destination["id"], "quantity": 2, "rate": 12}
        adjustment = {"product_id": item["id"], "warehouse_id": warehouse["id"], "quantity_in": 2, "quantity_out": 0, "rate": 12}
        invalid_transfers = [{**transfer, **change} for change in [{"quantity": 0}, {"quantity": -2}, {"rate": -12}, {"product_id": 999999}]]
        invalid_adjustments = [{**adjustment, **change} for change in [{"quantity_in": -1}, {"quantity_in": 0}, {"quantity_out": 1}, {"rate": -12}, {"product_id": 999999}]]
    invalid_transfers += [{**transfer, "to_warehouse_id": warehouse["id"]}, {**transfer, "to_warehouse_id": 999999}]
    invalid_adjustments += [{**adjustment, "warehouse_id": 999999}]
    for path, payloads in [("stock-transfers", invalid_transfers), ("stock-adjustments", invalid_adjustments)]:
        for payload in payloads:
            response = client.post(f"{base}/{path}", headers=headers, json=payload)
            assert response.status_code in (400, 404, 422), response.text
        if source == "fam":
            assert client.get(f"{base}/{path}", headers=headers).json()["total"] == 0
    detail = client.get(f"{base}/items/{item['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["current_quantity"] == 0
