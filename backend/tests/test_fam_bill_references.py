from app.apps.fam.models import FAMAuditLog, FAMBillReference
from tests.fam_test_utils import create_bill, create_party, fam_admin_headers


def test_fam_bill_reference_uses_party_terms_and_tracks_outstanding(client, db):
    headers = fam_admin_headers(client, db)
    party = create_party(client, headers, "customer", "CUST-BILL", "Bill Customer")

    bill = create_bill(client, headers, party, "INV-100", "invoice", 2500)

    assert bill["due_date"] == "2026-07-01"
    assert bill["outstanding_amount"] == 2500.0
    assert bill["status"] == "open"

    row = db.query(FAMBillReference).filter(FAMBillReference.id == bill["id"]).first()
    assert row.bill_number == "INV-100"

    audit = db.query(FAMAuditLog).filter(FAMAuditLog.record_type == "bill_reference", FAMAuditLog.record_id == bill["id"]).first()
    assert audit is not None


def test_fam_duplicate_bill_number_for_same_party_is_blocked(client, db):
    headers = fam_admin_headers(client, db)
    party = create_party(client, headers, "customer", "CUST-DUP-BILL", "Duplicate Bill Customer")
    create_bill(client, headers, party, "INV-DUP", "invoice", 1000)

    response = client.post("/api/v1/fam/bill-references", headers=headers, json={
        "party_id": party["id"],
        "bill_number": "INV-DUP",
        "bill_date": "2026-06-01",
        "bill_type": "invoice",
        "original_amount": 1000,
    })

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]
