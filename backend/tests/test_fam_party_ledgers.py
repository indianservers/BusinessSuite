from app.apps.fam.models import FAMAuditLog, FAMLedger
from tests.fam_test_utils import fam_admin_headers, party_payload


def test_fam_party_ledger_can_be_created_after_party_creation(client, db):
    headers = fam_admin_headers(client, db)
    payload = party_payload("vendor", "VEND-100", "Reliable Vendor")
    payload["create_ledger"] = False

    created = client.post("/api/v1/fam/parties", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    party = created.json()
    assert party["ledger_id"] is None

    response = client.post(f"/api/v1/fam/parties/{party['id']}/create-ledger", headers=headers)
    assert response.status_code == 200, response.text

    body = response.json()
    ledger = db.query(FAMLedger).filter(FAMLedger.id == body["ledger"]["id"]).first()
    assert ledger.ledger_type == "vendor"
    assert ledger.ledger_code == "PARTY-VEND-100"
    assert body["party"]["ledger_id"] == ledger.id

    audit = db.query(FAMAuditLog).filter(FAMAuditLog.record_type == "party", FAMAuditLog.action == "CREATE_LEDGER").first()
    assert audit is not None

