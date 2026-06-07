from admin_security_test_utils import auth_headers


def test_export_controls(client, db):
    headers = auth_headers(client, db)
    create = client.post("/api/v1/admin/export-controls", headers=headers, json={"module_name": "leads", "max_rows": 10, "require_approval": True, "watermark": True})
    assert create.status_code == 201
    listing = client.get("/api/v1/admin/export-controls", headers=headers)
    assert listing.json()["items"][0]["require_approval"] is True
