from tests.fam_inventory_accounting_cases import accounting_setup


def test_fam_inventory_gst_reconciliation_endpoint_lists_hsn_readiness(client, db):
    headers, _, _, _ = accounting_setup(client, db, "GSTREC")

    response = client.get("/api/v1/fam/inventory/reconciliation/gst", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["items"]
    assert "exceptions" in response.json()
