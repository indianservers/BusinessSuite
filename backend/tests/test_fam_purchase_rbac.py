from tests.fam_test_utils import auth_headers_for, fam_admin_headers


def test_fam_purchase_rbac_blocks_employee_mutation(client, db):
    headers = fam_admin_headers(client, db)
    assert client.get("/api/v1/fam/purchase-bills", headers=headers).status_code == 200
    employee = auth_headers_for(client, db, "purchase-employee@example.com", "employee", permissions=["fam_view"])
    response = client.post("/api/v1/fam/tds/sections", headers=employee, json={"section_code": "194Q", "description": "Purchase goods", "default_rate": 0.1, "threshold_amount": 5000000, "effective_from": "2026-04-01"})
    assert response.status_code == 403
