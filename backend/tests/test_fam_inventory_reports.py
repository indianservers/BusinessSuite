from tests.fam_inventory_test_utils import create_stock_item, inventory_headers, post_opening_stock


def test_inventory_phase9_reports_render_from_stock_ledgers(client, db):
    headers = inventory_headers(client, db, "phase9-reports@example.com")
    item, warehouse = create_stock_item(client, headers, "P9-REP", reorder_level=20)
    post_opening_stock(client, headers, item, warehouse, quantity=10, rate=100, suffix="P9-REP")

    endpoints = [
        "/api/v1/fam/inventory/reports/stock-summary",
        f"/api/v1/fam/inventory/reports/item-ledger/{item['id']}",
        "/api/v1/fam/inventory/reports/warehouse-stock",
        "/api/v1/fam/inventory/reports/stock-aging",
        "/api/v1/fam/inventory/reports/reorder",
        "/api/v1/fam/inventory/reports/dead-stock",
        "/api/v1/fam/inventory/reports/fast-slow-moving",
        "/api/v1/fam/inventory/reports/valuation",
        "/api/v1/fam/inventory/reports/gross-margin",
        "/api/v1/fam/inventory/reports/purchase-item-register",
        "/api/v1/fam/inventory/reports/sales-item-register",
        "/api/v1/fam/inventory/reports/stock-movement-audit",
    ]
    for endpoint in endpoints:
        response = client.get(endpoint, headers=headers)
        assert response.status_code == 200, f"{endpoint}: {response.text}"
        assert "total" in response.json() or "total_inventory_value" in response.json()
