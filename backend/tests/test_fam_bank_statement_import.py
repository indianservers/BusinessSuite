from tests.fam_test_utils import create_bank_account, fam_admin_headers


def statement_payload(account_id: int):
    return {
        "bank_account_id": account_id,
        "statement_period_start": "2026-06-01",
        "statement_period_end": "2026-06-30",
        "imported_file_name": "hdfc-june.csv",
        "file_content": "transaction_date,description,reference_number,debit_amount,credit_amount,balance\n2026-06-06,Customer receipt,REF-1,0,1000,1000",
    }


def test_bank_statement_import_and_duplicate_prevention(client, db):
    headers = fam_admin_headers(client, db, "statement-import@example.com")
    account = create_bank_account(client, headers)
    response = client.post("/api/v1/fam/bank-statements/import", headers=headers, json=statement_payload(account["id"]))
    assert response.status_code == 201, response.text
    assert response.json()["summary"]["total_lines"] == 1
    assert response.json()["lines"][0]["matched_status"] == "unmatched"

    duplicate = client.post("/api/v1/fam/bank-statements/import", headers=headers, json=statement_payload(account["id"]))
    assert duplicate.status_code == 409

