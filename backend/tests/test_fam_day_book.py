from tests.fam_test_utils import create_balanced_voucher, fam_admin_headers


def test_day_book_returns_voucher_register_totals(client, db):
    headers = fam_admin_headers(client, db)
    create_balanced_voucher(client, headers)
    response = client.get("/api/v1/fam/day-book", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] >= 1
    assert response.json()["debitTotal"] == response.json()["creditTotal"]
