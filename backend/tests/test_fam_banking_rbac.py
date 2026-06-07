from tests.fam_test_utils import auth_headers_for, fam_admin_headers


def test_banking_rbac_blocks_non_fam_and_allows_read_only(client, db):
    fam_admin_headers(client, db, "banking-admin@example.com")
    viewer_permissions = ["fam_view", "fam_banking_view", "fam_bank_book_view", "fam_cash_book_view"]
    viewer = auth_headers_for(client, db, "banking-viewer@example.com", "fam_viewer", permissions=viewer_permissions)
    employee = auth_headers_for(client, db, "banking-employee@example.com", "employee", permissions=[])

    assert client.get("/api/v1/fam/bank-accounts", headers=employee).status_code == 403
    assert client.get("/api/v1/fam/bank-accounts", headers=viewer).status_code == 200
    denied = client.post("/api/v1/fam/payment-modes", headers=viewer, json={"name": "Cash", "type": "cash"})
    assert denied.status_code == 403
