from app.apps.fam.models import FAMAuditLog, FAMLedger
from tests.fam_test_utils import create_party, fam_admin_headers, party_payload


def test_fam_create_list_and_get_customer_party(client, db):
    headers = fam_admin_headers(client, db)

    party = create_party(client, headers, "customer", "CUST-100", "Northwind Customer")

    assert party["party_type"] == "customer"
    assert party["ledger_id"]
    assert party["contacts"][0]["email"] == "accounts@example.com"

    listed = client.get("/api/v1/fam/parties?party_type=customer", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1

    detail = client.get(f"/api/v1/fam/parties/{party['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["legal_name"] == "Northwind Customer"

    ledger = db.query(FAMLedger).filter(FAMLedger.id == party["ledger_id"]).first()
    assert ledger.ledger_type == "customer"
    assert ledger.ledger_code == "PARTY-CUST-100"

    audit = db.query(FAMAuditLog).filter(FAMAuditLog.record_type == "party", FAMAuditLog.record_id == party["id"]).first()
    assert audit is not None
    assert audit.action == "CREATE"


def test_fam_duplicate_party_code_is_blocked(client, db):
    headers = fam_admin_headers(client, db)
    create_party(client, headers, "customer", "CUST-DUP", "Duplicate Customer")

    response = client.post("/api/v1/fam/parties", headers=headers, json=party_payload("customer", "CUST-DUP", "Duplicate Customer 2"))

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]

