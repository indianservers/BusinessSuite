from tests.customization_test_utils import customization_headers


def test_rollup_field_create_and_validation(client, db):
    headers = customization_headers(client, db)
    response = client.post("/api/v1/customization/rollups", headers=headers, json={"module_name": "partner_projects", "field_api_name": "total_revenue", "related_module_name": "partner_invoices", "aggregate_function": "sum", "aggregate_field": "amount"})
    assert response.status_code == 201, response.text
    invalid = client.post("/api/v1/customization/fields", headers=headers, json={"module_name": "partner_projects", "field_api_name": "bad_rollup", "field_label": "Bad Rollup", "field_type": "rollup", "rollup_config_json": {"aggregate_function": "median"}})
    assert invalid.status_code == 400

