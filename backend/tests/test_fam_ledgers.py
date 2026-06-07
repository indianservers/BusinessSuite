from app.apps.fam.models import FAMLedger, FAMLedgerGroup
from tests.fam_test_utils import fam_admin_headers


def test_fam_ledgers_seed_create_duplicate_validation(client, db):
    headers = fam_admin_headers(client, db)
    response = client.get("/api/v1/fam/ledgers", headers=headers)
    assert response.status_code == 200
    assert any(item["ledger_name"] == "Cash" for item in response.json()["items"])

    group = db.query(FAMLedgerGroup).filter_by(group_name="Current Assets").first()
    payload = {
        "ledger_code": "BANK-HDFC",
        "ledger_name": "HDFC Bank",
        "ledger_group_id": group.id,
        "nature": "asset",
        "ledger_type": "bank",
        "opening_balance_dr": 0,
        "opening_balance_cr": 0,
        "active": True,
    }
    response = client.post("/api/v1/fam/ledgers", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    assert db.query(FAMLedger).filter_by(ledger_code="BANK-HDFC").first()

    duplicate = client.post("/api/v1/fam/ledgers", headers=headers, json={**payload, "ledger_name": "HDFC Bank 2"})
    assert duplicate.status_code == 409


def test_fam_ledgers_reject_unknown_group_and_type(client, db):
    headers = fam_admin_headers(client, db)
    response = client.post("/api/v1/fam/ledgers", headers=headers, json={
        "ledger_code": "BAD",
        "ledger_name": "Bad Ledger",
        "ledger_group_id": 9999,
        "nature": "asset",
        "ledger_type": "bank",
    })
    assert response.status_code == 404

    group = db.query(FAMLedgerGroup).first()
    response = client.post("/api/v1/fam/ledgers", headers=headers, json={
        "ledger_code": "BADTYPE",
        "ledger_name": "Bad Type",
        "ledger_group_id": group.id,
        "nature": "asset",
        "ledger_type": "crypto",
    })
    assert response.status_code == 422
