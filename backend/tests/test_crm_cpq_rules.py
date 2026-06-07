from app.apps.crm.models import CRMCPQRule


def test_crm_cpq_rule_create_and_evaluate(client, db, superuser_headers):
    response = client.post("/api/v1/crm/cpq-rules", headers=superuser_headers, json={
        "name": "High discount approval",
        "ruleType": "approval",
        "condition": {"maxDiscount": 5000},
        "action": {"requiresApproval": True},
        "active": True,
    })
    assert response.status_code == 201, response.text
    assert db.query(CRMCPQRule).filter(CRMCPQRule.name == "High discount approval").count() == 1

    evaluate = client.post("/api/v1/crm/cpq/evaluate", headers=superuser_headers, json={"amount": 100000, "discount": 10000})
    assert evaluate.status_code == 200, evaluate.text
    assert evaluate.json()["warnings"][0]["rule"] == "High discount approval"
