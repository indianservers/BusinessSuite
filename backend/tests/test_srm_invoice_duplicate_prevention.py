from tests.srm_test_utils import create_sales_order


def test_srm_sales_order_and_manual_source_duplicate_prevention(client, db, superuser_headers):
    order = create_sales_order(client, superuser_headers)

    first = client.post(f"/api/v1/srm/invoices/draft-from-sales-order/{order['id']}", headers=superuser_headers)
    assert first.status_code == 201, first.text

    duplicate = client.post(f"/api/v1/srm/invoices/draft-from-sales-order/{order['id']}", headers=superuser_headers)
    assert duplicate.status_code == 409

    manual = client.post("/api/v1/srm/invoices/manual", headers=superuser_headers, json={
        "customer_id": 101,
        "lines": [{"description": "Manual source guard", "source_type": "external_adjustment", "source_id": 77, "quantity": 1, "unit_price": 1000}],
    })
    assert manual.status_code == 201, manual.text
    duplicate_manual = client.post("/api/v1/srm/invoices/manual", headers=superuser_headers, json={
        "customer_id": 101,
        "lines": [{"description": "Manual source guard duplicate", "source_type": "external_adjustment", "source_id": 77, "quantity": 1, "unit_price": 1000}],
    })
    assert duplicate_manual.status_code == 409
