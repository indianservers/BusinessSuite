from tests.fam_test_utils import fam_admin_headers, ledger_by_nature, ledger_by_type


def test_cash_book_is_ledger_driven(client, db):
    headers = fam_admin_headers(client, db, "cash-book@example.com")
    voucher_types = client.get("/api/v1/fam/voucher-types", headers=headers).json()["items"]
    cash = ledger_by_type(client, headers, "cash")
    equity = ledger_by_nature(client, headers, "equity")
    created = client.post("/api/v1/fam/vouchers", headers=headers, json={
        "voucher_type_id": voucher_types[0]["id"],
        "voucher_date": "2026-06-06",
        "reference_number": "CASH-1",
        "narration": "Cash receipt",
        "lines": [
            {"ledger_id": cash["id"], "debit_amount": 500, "credit_amount": 0},
            {"ledger_id": equity["id"], "debit_amount": 0, "credit_amount": 500},
        ],
    })
    assert created.status_code == 201, created.text
    client.post(f"/api/v1/fam/vouchers/{created.json()['id']}/post", headers=headers)

    response = client.get("/api/v1/fam/cash-book", headers=headers)
    assert response.status_code == 200
    assert response.json()["debitTotal"] >= 500

