from tests.fam_test_utils import auth_headers_for, fam_admin_headers


def test_fam_gst_rbac_blocks_non_fam_employee(client, db):
    admin_headers = fam_admin_headers(client, db)
    assert client.get("/api/v1/fam/gst/rates", headers=admin_headers).status_code == 200
    employee_headers = auth_headers_for(client, db, "gst-employee@example.com", "employee", permissions=["fam_view"])
    response = client.post("/api/v1/fam/gst/rates", headers=employee_headers, json={"rate_name": "GST 5%", "tax_type": "goods", "effective_from": "2026-04-01"})
    assert response.status_code == 403
