from app.apps.fam.models import FAMAuditLog, FAMBillReference
from tests.fam_test_utils import create_bill, create_party, fam_admin_headers
from tests.test_pms_workflow_postgresql import live, race


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


def test_fam_bill_allocation_preserves_source_and_target_on_insufficient_credit(client, db):
    headers = fam_admin_headers(client, db)
    party = create_party(client, headers, "customer", "CUST-ALLOC-CREDIT", "Allocation Credit Customer")
    advance = create_bill(client, headers, party, "ADV-CREDIT", "advance", 100)
    invoice = create_bill(client, headers, party, "INV-CREDIT", "invoice", 500)

    response = client.post("/api/v1/fam/bill-allocations", headers=headers, json={
        "allocation_date": "2026-06-06",
        "party_id": party["id"],
        "from_bill_reference_id": advance["id"],
        "to_bill_reference_id": invoice["id"],
        "allocated_amount": 200,
        "allocation_type": "advance_adjustment",
    })

    assert response.status_code == 409, response.text
    assert db.get(FAMBillReference, advance["id"]).outstanding_amount == 100
    assert db.get(FAMBillReference, invoice["id"]).outstanding_amount == 500


def test_concurrent_fam_bill_allocations_share_one_source_balance(live):
    with live.factory() as db:
        headers = fam_admin_headers(live.client, db)
    party = create_party(live.client, headers, "customer", "CUST-RACE", "Allocation Race Customer")
    advance = create_bill(live.client, headers, party, "ADV-RACE", "advance", 500)
    invoices = [
        create_bill(live.client, headers, party, f"INV-RACE-{number}", "invoice", 1000)
        for number in (1, 2)
    ]

    def allocate(invoice):
        return live.client.post("/api/v1/fam/bill-allocations", headers=headers, json={
            "allocation_date": "2026-06-06",
            "party_id": party["id"],
            "from_bill_reference_id": advance["id"],
            "to_bill_reference_id": invoice["id"],
            "allocated_amount": 400,
            "allocation_type": "advance_adjustment",
        })

    results = race(lambda: allocate(invoices[0]), lambda: allocate(invoices[1]))
    assert sorted(response.status_code for response in results) == [201, 409], [response.text for response in results]
    with live.factory() as db:
        assert db.get(FAMBillReference, advance["id"]).outstanding_amount == 100
        assert sorted(db.get(FAMBillReference, invoice["id"]).outstanding_amount for invoice in invoices) == [600, 1000]

