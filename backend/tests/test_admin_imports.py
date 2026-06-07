from admin_security_test_utils import auth_headers, create_profile


def test_import_upload_mapping_run_errors_and_fls_block(client, db):
    headers = auth_headers(client, db, role_name="crm_sales_executive")
    profile = create_profile(client, headers, "crm_sales_executive")
    client.post("/api/v1/admin/field-security", headers=headers, json={"module_name": "leads", "field_name": "email", "profile_id": profile["id"], "can_view": True, "can_edit": False})
    upload = client.post("/api/v1/admin/imports/upload", headers=headers, json={"module_name": "leads", "filename": "leads.csv", "rows": [{"First Name": "Asha", "Email": "asha@example.com"}, {"First Name": "Asha", "Email": "asha@example.com"}]})
    assert upload.status_code == 201
    job_id = upload.json()["id"]
    mapped = client.post(f"/api/v1/admin/imports/{job_id}/map-fields", headers=headers, json={"mapping": {"First Name": "first_name", "Email": "email"}})
    assert mapped.status_code == 200
    run = client.post(f"/api/v1/admin/imports/{job_id}/run", headers=headers)
    assert run.status_code == 200
    assert run.json()["failed_rows"] == 2
    errors = client.get(f"/api/v1/admin/imports/{job_id}/errors", headers=headers)
    assert errors.json()["total"] == 2
