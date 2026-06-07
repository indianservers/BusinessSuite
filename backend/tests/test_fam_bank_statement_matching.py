from tests.fam_test_utils import create_bank_account, fam_admin_headers, ledger_by_nature, ledger_by_type


def post_bank_voucher(client, headers, amount=1000):
    voucher_types = client.get("/api/v1/fam/voucher-types", headers=headers).json()["items"]
    bank = ledger_by_type(client, headers, "bank")
    equity = ledger_by_nature(client, headers, "equity")
    created = client.post("/api/v1/fam/vouchers", headers=headers, json={
        "voucher_type_id": voucher_types[0]["id"],
        "voucher_date": "2026-06-06",
        "reference_number": "REF-1",
        "narration": "Customer receipt REF-1",
        "lines": [
            {"ledger_id": bank["id"], "debit_amount": amount, "credit_amount": 0, "narration": "Customer receipt REF-1"},
            {"ledger_id": equity["id"], "debit_amount": 0, "credit_amount": amount, "narration": "Customer receipt REF-1"},
        ],
    })
    assert created.status_code == 201, created.text
    posted = client.post(f"/api/v1/fam/vouchers/{created.json()['id']}/post", headers=headers)
    assert posted.status_code == 200, posted.text
    return posted.json()


def test_auto_match_suggests_statement_to_voucher(client, db):
    headers = fam_admin_headers(client, db, "statement-match@example.com")
    account = create_bank_account(client, headers)
    voucher = post_bank_voucher(client, headers)
    statement = client.post("/api/v1/fam/bank-statements/import", headers=headers, json={
        "bank_account_id": account["id"],
        "statement_period_start": "2026-06-01",
        "statement_period_end": "2026-06-30",
        "imported_file_name": "match.csv",
        "lines": [{"transaction_date": "2026-06-06", "description": "Customer receipt REF-1", "reference_number": "REF-1", "debit_amount": 0, "credit_amount": 1000, "balance": 1000}],
    }).json()

    response = client.post(f"/api/v1/fam/bank-statements/{statement['id']}/auto-match", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["suggestions"][0]["voucher_id"] == voucher["id"]

