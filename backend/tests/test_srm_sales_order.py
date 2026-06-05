from app.apps.srm.models import SRMAuditLog, SRMSalesOrder

from tests.srm_test_utils import create_sales_order


def test_srm_sales_order_create_submit_confirm_audits(client, db, superuser_headers):
    order = create_sales_order(client, superuser_headers)
    line = client.post(f"/api/v1/srm/sales-orders/{order['id']}/lines", headers=superuser_headers, json={
        "description": "Expansion pack",
        "quantity": 2,
        "unit_price": 10000,
        "tax_amount": 3600,
    })
    assert line.status_code == 201, line.text
    updated_line = client.patch(f"/api/v1/srm/sales-orders/{order['id']}/lines/{line.json()['id']}", headers=superuser_headers, json={"quantity": 3})
    assert updated_line.status_code == 200, updated_line.text

    submit = client.post(f"/api/v1/srm/sales-orders/{order['id']}/submit", headers=superuser_headers)
    assert submit.status_code == 200, submit.text

    confirm = client.post(f"/api/v1/srm/sales-orders/{order['id']}/confirm", headers=superuser_headers)
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["status"] == "confirmed"
    assert confirm.json()["engagement"]["sales_order_id"] == order["id"]

    saved = db.query(SRMSalesOrder).filter(SRMSalesOrder.id == order["id"]).first()
    assert saved is not None
    assert len(saved.lines) == 2
    assert db.query(SRMAuditLog).filter(SRMAuditLog.entity_type == "sales_order", SRMAuditLog.entity_id == order["id"]).count() >= 2


def test_srm_sales_order_cancel_close_and_duplicate_validation(client, db, superuser_headers):
    duplicate_number = "SO-DUP-001"
    first = client.post("/api/v1/srm/sales-orders", headers=superuser_headers, json={"order_number": duplicate_number, "title": "Duplicate check"})
    assert first.status_code == 201, first.text
    duplicate = client.post("/api/v1/srm/sales-orders", headers=superuser_headers, json={"order_number": duplicate_number, "title": "Duplicate check"})
    assert duplicate.status_code == 409

    cancellable = create_sales_order(client, superuser_headers, "Cancellation order")
    cancelled = client.post(f"/api/v1/srm/sales-orders/{cancellable['id']}/cancel", headers=superuser_headers)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"

    closable = create_sales_order(client, superuser_headers, "Closure order")
    client.post(f"/api/v1/srm/sales-orders/{closable['id']}/submit", headers=superuser_headers)
    client.post(f"/api/v1/srm/sales-orders/{closable['id']}/confirm", headers=superuser_headers)
    closed = client.post(f"/api/v1/srm/sales-orders/{closable['id']}/close", headers=superuser_headers)
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"
