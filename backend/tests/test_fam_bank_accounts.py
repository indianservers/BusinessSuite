from tests.fam_test_utils import create_bank_account, fam_admin_headers


def test_bank_account_create_view_update(client, db):
    headers = fam_admin_headers(client, db, "bank-account@example.com")
    account = create_bank_account(client, headers)
    assert account["bank_name"] == "HDFC Bank"

    listing = client.get("/api/v1/fam/bank-accounts", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    updated = client.put(f"/api/v1/fam/bank-accounts/{account['id']}", headers=headers, json={**account, "branch_name": "MG Road"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["branch_name"] == "MG Road"

