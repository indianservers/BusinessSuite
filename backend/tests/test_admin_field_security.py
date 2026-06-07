from admin_security_test_utils import auth_headers, create_profile


def test_field_security_masks_response_and_blocks_update(client, db):
    headers = auth_headers(client, db, role_name="crm_sales_executive")
    profile = create_profile(client, headers, "crm_sales_executive")
    rule = client.post("/api/v1/admin/field-security", headers=headers, json={"module_name": "leads", "field_name": "email", "profile_id": profile["id"], "can_view": True, "can_edit": False, "mask_value": True})
    assert rule.status_code == 201, rule.text

    preview = client.post("/api/v1/admin/security/apply-field-security", headers=headers, json={"module_name": "leads", "record": {"first_name": "Asha", "email": "asha@example.com"}})
    assert preview.status_code == 200
    assert preview.json()["record"]["email"] == "********"

    blocked = client.post("/api/v1/admin/security/validate-field-update", headers=headers, json={"module_name": "leads", "record": {"email": "new@example.com"}})
    assert blocked.status_code == 403
