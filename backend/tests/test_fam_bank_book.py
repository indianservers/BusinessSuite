from tests.test_fam_bank_statement_matching import post_bank_voucher
from tests.fam_test_utils import fam_admin_headers


def test_bank_book_is_ledger_driven(client, db):
    headers = fam_admin_headers(client, db, "bank-book@example.com")
    post_bank_voucher(client, headers)
    response = client.get("/api/v1/fam/bank-book", headers=headers)
    assert response.status_code == 200
    assert response.json()["debitTotal"] >= 1000
    assert response.json()["items"]

