from tests.fam_test_utils import create_balanced_voucher, fam_admin_headers


def test_ledger_entries_list_and_drilldown(client, db):
    headers = fam_admin_headers(client, db)
    voucher = create_balanced_voucher(client, headers)
    assert client.post(f"/api/v1/fam/vouchers/{voucher['id']}/post", headers=headers).status_code == 200
    response = client.get("/api/v1/fam/ledger-entries", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 2
    ledger_id = response.json()["items"][0]["ledger_id"]
    drill = client.get(f"/api/v1/fam/ledgers/{ledger_id}/entries", headers=headers)
    assert drill.status_code == 200
    assert drill.json()["items"]
