from tests.fam_test_utils import balanced_voucher_payload, create_balanced_voucher, fam_admin_headers


def test_unbalanced_voucher_cannot_be_posted(client, db):
    headers = fam_admin_headers(client, db)
    payload = balanced_voucher_payload(client, headers)
    payload["lines"][1]["credit_amount"] = 900
    response = client.post("/api/v1/fam/vouchers", headers=headers, json=payload)
    assert response.status_code == 201
    response = client.post(f"/api/v1/fam/vouchers/{response.json()['id']}/post", headers=headers)
    assert response.status_code == 409


def test_posted_voucher_cannot_be_silently_edited(client, db):
    headers = fam_admin_headers(client, db)
    voucher = create_balanced_voucher(client, headers)
    assert client.post(f"/api/v1/fam/vouchers/{voucher['id']}/post", headers=headers).status_code == 200
    response = client.put(f"/api/v1/fam/vouchers/{voucher['id']}", headers=headers, json=balanced_voucher_payload(client, headers))
    assert response.status_code == 409
