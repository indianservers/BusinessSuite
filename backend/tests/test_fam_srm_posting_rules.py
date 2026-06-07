from app.apps.fam.models import FAMPostingRule


def test_fam_posting_rules_crud_for_srm_transactions(client, db, superuser_headers):
    response = client.post("/api/v1/fam/posting-rules", headers=superuser_headers, json={
        "source_module": "srm",
        "transaction_type": "sales_invoice",
        "debit_ledger_rule_json": {"type": "customer_ledger"},
        "credit_ledger_rule_json": {"ledger_code": "SALES"},
        "tax_ledger_rule_json": {"cgst": "OUTPUT-CGST", "sgst": "OUTPUT-SGST"},
        "active": True,
    })

    assert response.status_code == 201, response.text
    rule = response.json()
    assert rule["transaction_type"] == "sales_invoice"

    updated = client.put(f"/api/v1/fam/posting-rules/{rule['id']}", headers=superuser_headers, json={**rule, "active": False})
    assert updated.status_code == 200, updated.text
    assert updated.json()["active"] is False
    assert db.query(FAMPostingRule).filter(FAMPostingRule.id == rule["id"]).first().active is False

    listing = client.get("/api/v1/fam/posting-rules", headers=superuser_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

