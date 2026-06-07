from tests.fam_test_utils import create_bill, create_party, fam_admin_headers


def test_fam_party_statement_shows_party_bills_allocations_and_outstanding(client, db):
    headers = fam_admin_headers(client, db)
    party = create_party(client, headers, "customer", "CUST-STMT", "Statement Customer")
    advance = create_bill(client, headers, party, "ADV-STMT", "advance", 500)
    invoice = create_bill(client, headers, party, "INV-STMT", "invoice", 1000)
    client.post("/api/v1/fam/bill-allocations", headers=headers, json={
        "allocation_date": "2026-06-06",
        "party_id": party["id"],
        "from_bill_reference_id": advance["id"],
        "to_bill_reference_id": invoice["id"],
        "allocated_amount": 250,
        "allocation_type": "advance_adjustment",
    })

    response = client.get(f"/api/v1/fam/parties/{party['id']}/statement", headers=headers)

    assert response.status_code == 200, response.text
    statement = response.json()
    assert statement["party"]["party_code"] == "CUST-STMT"
    assert len(statement["billReferences"]) == 2
    assert len(statement["allocations"]) == 1
    assert statement["outstanding"] == 1000.0

