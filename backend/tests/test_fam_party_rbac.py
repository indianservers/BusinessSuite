from tests.fam_test_utils import auth_headers_for, create_party, fam_admin_headers, party_payload


def test_fam_viewer_can_read_but_cannot_manage_parties(client, db):
    admin_headers = fam_admin_headers(client, db)
    create_party(client, admin_headers, "customer", "CUST-RBAC", "RBAC Customer")
    viewer_headers = auth_headers_for(client, db, "fam-viewer-rbac@example.com", "fam_viewer", permissions=[
        "fam_view",
        "fam_parties_view",
        "fam_ar_view",
        "fam_ap_view",
        "fam_party_statement_view",
    ])

    list_response = client.get("/api/v1/fam/parties", headers=viewer_headers)
    assert list_response.status_code == 200, list_response.text

    create_response = client.post("/api/v1/fam/parties", headers=viewer_headers, json=party_payload("customer", "CUST-DENIED", "Denied Customer"))
    assert create_response.status_code == 403


def test_non_fam_employee_is_blocked_from_fam_parties(client, db):
    employee_headers = auth_headers_for(client, db, "plain-employee@example.com", "employee", permissions=["hrms_employee"])

    response = client.get("/api/v1/fam/parties", headers=employee_headers)

    assert response.status_code == 403

