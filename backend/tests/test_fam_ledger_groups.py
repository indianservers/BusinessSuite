from app.apps.fam.models import FAMLedgerGroup
from tests.fam_test_utils import fam_admin_headers


def test_fam_ledger_groups_seed_create_delete_rules(client, db):
    headers = fam_admin_headers(client, db)
    response = client.get("/api/v1/fam/ledger-groups", headers=headers)
    assert response.status_code == 200
    groups = response.json()["items"]
    assert any(item["group_name"] == "Current Assets" for item in groups)

    system_group = next(item for item in groups if item["system_group"])
    response = client.delete(f"/api/v1/fam/ledger-groups/{system_group['id']}", headers=headers)
    assert response.status_code == 409

    response = client.post("/api/v1/fam/ledger-groups", headers=headers, json={
        "group_name": "Deposits",
        "group_code": "DEP",
        "nature": "asset",
        "parent_group_id": None,
        "system_group": False,
        "gross_profit_affects": False,
        "sequence_order": 90,
        "active": True,
    })
    assert response.status_code == 201, response.text
    group_id = response.json()["id"]
    assert db.query(FAMLedgerGroup).filter_by(group_code="DEP").first()
    assert client.delete(f"/api/v1/fam/ledger-groups/{group_id}", headers=headers).status_code == 200


def test_fam_ledger_groups_reject_invalid_nature(client, db):
    headers = fam_admin_headers(client, db)
    response = client.post("/api/v1/fam/ledger-groups", headers=headers, json={
        "group_name": "Invalid",
        "group_code": "BAD",
        "nature": "magic",
        "sequence_order": 1,
    })
    assert response.status_code == 422
