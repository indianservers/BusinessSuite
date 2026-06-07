from tests.fam_inventory_test_utils import inventory_headers


def test_fam_inventory_source_audit_uses_existing_app(client, db):
    headers = inventory_headers(client, db)
    response = client.get("/api/v1/fam/inventory/source-audit", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["source_exists"] is True
    assert data["merged_under"] == "FAM"
    assert any(item["path"] == "app/services/stock_service.py" and item["exists"] for item in data["files"])
