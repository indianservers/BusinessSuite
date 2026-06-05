from app.apps.srm.models import SRMAuditLog, SRMReceipt


def test_srm_receipt_create_and_confirm(client, db, superuser_headers):
    response = client.post("/api/v1/srm/receipts", headers=superuser_headers, json={"customer_id": 301, "amount": 25000, "reference_number": "BANK-1"})
    assert response.status_code == 201, response.text
    receipt = response.json()
    assert receipt["status"] == "draft"
    assert receipt["unallocated_amount"] == 25000.0

    confirmed = client.post(f"/api/v1/srm/receipts/{receipt['id']}/confirm", headers=superuser_headers)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert db.query(SRMReceipt).filter(SRMReceipt.id == receipt["id"]).first().status == "confirmed"
    assert db.query(SRMAuditLog).filter(SRMAuditLog.entity_type == "receipt", SRMAuditLog.entity_id == receipt["id"]).count() >= 2
