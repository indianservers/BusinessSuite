from app.apps.fam.models import FAMAuditLog, FAMBillReference
from tests.fam_test_utils import create_bill, create_party, fam_admin_headers


def test_fam_bill_allocation_reduces_target_outstanding_and_audits(client, db):
    headers = fam_admin_headers(client, db)
    party = create_party(client, headers, "customer", "CUST-ALLOC", "Allocation Customer")
    advance = create_bill(client, headers, party, "ADV-100", "advance", 500)
    invoice = create_bill(client, headers, party, "INV-ALLOC", "invoice", 1000)

    response = client.post("/api/v1/fam/bill-allocations", headers=headers, json={
        "allocation_date": "2026-06-06",
        "party_id": party["id"],
        "from_bill_reference_id": advance["id"],
        "to_bill_reference_id": invoice["id"],
        "allocated_amount": 400,
        "allocation_type": "advance_adjustment",
    })

    assert response.status_code == 201, response.text
    allocation = response.json()
    assert allocation["allocated_amount"] == 400.0

    invoice_row = db.query(FAMBillReference).filter(FAMBillReference.id == invoice["id"]).first()
    advance_row = db.query(FAMBillReference).filter(FAMBillReference.id == advance["id"]).first()
    assert float(invoice_row.outstanding_amount) == 600.0
    assert float(advance_row.outstanding_amount) == 100.0

    audit = db.query(FAMAuditLog).filter(FAMAuditLog.record_type == "bill_allocation", FAMAuditLog.record_id == allocation["id"]).first()
    assert audit is not None


def test_fam_bill_allocation_cannot_exceed_target_outstanding(client, db):
    headers = fam_admin_headers(client, db)
    party = create_party(client, headers, "customer", "CUST-ALLOC-BLOCK", "Allocation Block Customer")
    advance = create_bill(client, headers, party, "ADV-BLOCK", "advance", 500)
    invoice = create_bill(client, headers, party, "INV-BLOCK", "invoice", 300)

    response = client.post("/api/v1/fam/bill-allocations", headers=headers, json={
        "allocation_date": "2026-06-06",
        "party_id": party["id"],
        "from_bill_reference_id": advance["id"],
        "to_bill_reference_id": invoice["id"],
        "allocated_amount": 400,
        "allocation_type": "advance_adjustment",
    })

    assert response.status_code == 409
    assert "exceeds" in response.json()["detail"]

