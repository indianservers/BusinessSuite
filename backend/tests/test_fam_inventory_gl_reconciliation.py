from tests.fam_inventory_accounting_cases import accounting_setup


def test_fam_inventory_gl_reconciliation_endpoint_returns_status(client, db):
    headers, _, _, _ = accounting_setup(client, db, "GLREC")

    response = client.get("/api/v1/fam/inventory/reconciliation/gl", headers=headers)

    assert response.status_code == 200, response.text
    assert "difference" in response.json()
    assert response.json()["status"] in {"matched", "variance"}
