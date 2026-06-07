from tests.customization_test_utils import customization_headers


def test_formula_field_and_safe_formula_tester(client, db):
    headers = customization_headers(client, db)
    response = client.post("/api/v1/customization/formulas", headers=headers, json={"module_name": "partner_projects", "field_api_name": "margin", "expression": "revenue - cost", "return_type": "decimal"})
    assert response.status_code == 201, response.text
    response = client.post("/api/v1/customization/formulas/test", headers=headers, json={"expression": "revenue - cost", "record": {"revenue": 1000, "cost": 250}})
    assert response.status_code == 200
    assert response.json()["result"] == "750"
    unsafe = client.post("/api/v1/customization/formulas/test", headers=headers, json={"expression": "__import__('os').system('dir')", "record": {}})
    assert unsafe.status_code == 400

