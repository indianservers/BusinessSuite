from tests.fam_inventory_accounting_cases import accounting_setup


def test_fam_inventory_valuation_reconciliation_returns_item_layers(client, db):
    headers, item, _, _ = accounting_setup(client, db, "VALREC")

    response = client.get(f"/api/v1/fam/inventory/valuation/{item['id']}", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["id"] == item["id"]
    assert response.json()["valuation_method"] == "weighted_average"
    assert response.json()["layers"]
