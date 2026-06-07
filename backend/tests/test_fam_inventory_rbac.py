from tests.fam_test_utils import auth_headers_for


def test_fam_inventory_requires_backend_permissions(client, db):
    headers = auth_headers_for(client, db, "fam-no-inventory@example.com", "fam_no_inventory", permissions=["fam_view"])
    response = client.get("/api/v1/fam/inventory/items", headers=headers)
    assert response.status_code == 403
