import pytest

from app.apps.business_os.services.module_service import ensure_business_os_seed
from app.main import app
from tests.srm_test_utils import auth_headers_for


@pytest.fixture
def procurement(client, db):
    app.state.business_os_session_factory = lambda: db
    app.state.business_os_close_session = False
    try:
        ensure_business_os_seed(db, company_id=1)
        headers = auth_headers_for(client, db, "audit-procurement@srm.example.com", "srm_sales_manager", permissions=["srm_view", "srm_manage"])
        warehouse = client.post("/api/v1/srm/inventory/warehouses", headers=headers, json={"warehouse_code": "QA", "warehouse_name": "Audit store"})
        assert warehouse.status_code == 201
        product = client.post("/api/v1/srm/inventory/items", headers=headers, json={"sku": "AUDIT-PAPER", "item_name": "Office paper", "default_warehouse_id": warehouse.json()["id"]})
        assert product.status_code == 201
        line = {"product_id": product.json()["id"], "warehouse_id": warehouse.json()["id"], "quantity": 5, "unit_price": 12}
        order = client.post("/api/v1/srm/procurement/purchase-orders", headers=headers, json={"vendor_name": "Office supplier", "lines": [line]})
        assert order.status_code == 201
        yield headers, line, order.json()
    finally:
        delattr(app.state, "business_os_session_factory")
        delattr(app.state, "business_os_close_session")


@pytest.mark.parametrize("field,value", [("quantity", 0), ("quantity", -1), ("unit_price", -1), ("tax_amount", -1), ("product_id", 999999), ("warehouse_id", 999999)])
def test_audit_purchase_order_rejects_invalid_values_without_writing(client, procurement, field, value):
    headers, line, _ = procurement
    before = client.get("/api/v1/srm/procurement/purchase-orders", headers=headers).json()["total"]
    response = client.post("/api/v1/srm/procurement/purchase-orders", headers=headers, json={"lines": [{**line, field: value}]})
    assert response.status_code in (404, 422)
    assert client.get("/api/v1/srm/procurement/purchase-orders", headers=headers).json()["total"] == before


@pytest.mark.parametrize("change", [
    {"purchase_order_id": 999999},
    {"line": {"purchase_order_line_id": 999999}},
    {"line": {"product_id": 999999}},
    {"line": {"warehouse_id": 999999}},
    {"line": {"quantity": 0}},
    {"line": {"accepted_quantity": -1}},
    {"line": {"unit_price": -1}},
    {"line": {"tax_amount": -1}},
    {"line": {"quantity": 2, "accepted_quantity": 1}},
    {"line": {"quantity": 6, "accepted_quantity": 6}},
])
def test_audit_receipt_rejects_invalid_links_and_amounts_without_stock_write(client, procurement, change):
    headers, line, order = procurement
    receipt_line = {"purchase_order_line_id": order["lines"][0]["id"], "quantity": 1, "accepted_quantity": 1, "unit_price": 12}
    response = client.post("/api/v1/srm/procurement/grn", headers=headers, json={"purchase_order_id": change.get("purchase_order_id", order["id"]), "lines": [{**receipt_line, **change.get("line", {})}]})
    assert response.status_code in (404, 409, 422)
    assert client.get("/api/v1/srm/procurement/grn", headers=headers).json()["total"] == 0
    assert client.get(f"/api/v1/srm/inventory/items/{line['product_id']}", headers=headers).json()["current_quantity"] == 0


def test_audit_receipt_posts_selected_order_line_and_updates_stock(client, procurement):
    headers, line, order = procurement
    response = client.post("/api/v1/srm/procurement/grn", headers=headers, json={"purchase_order_id": order["id"], "lines": [{"purchase_order_line_id": order["lines"][0]["id"], "quantity": 3, "accepted_quantity": 2, "rejected_quantity": 1, "unit_price": 12}]})
    assert response.status_code == 201
    assert response.json()["lines"][0]["purchase_order_line_id"] == order["lines"][0]["id"]
    assert client.get(f"/api/v1/srm/inventory/items/{line['product_id']}", headers=headers).json()["current_quantity"] == 2
