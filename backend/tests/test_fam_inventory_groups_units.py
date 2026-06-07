from tests.fam_inventory_test_utils import inventory_headers


def test_fam_inventory_groups_and_units_crud(client, db):
    headers = inventory_headers(client, db)
    group = client.post("/api/v1/fam/inventory/stock-groups", headers=headers, json={"group_code": "FIN", "group_name": "Finished Goods"})
    assert group.status_code == 201, group.text
    unit = client.post("/api/v1/fam/inventory/units", headers=headers, json={"unit_code": "BOX", "unit_name": "Boxes", "symbol": "box"})
    assert unit.status_code == 201, unit.text
    groups = client.get("/api/v1/fam/inventory/stock-groups", headers=headers)
    units = client.get("/api/v1/fam/inventory/units", headers=headers)
    assert groups.status_code == 200
    assert units.status_code == 200
    assert any(item["group_code"] == "FIN" for item in groups.json()["items"])
    assert any(item["unit_code"] == "BOX" for item in units.json()["items"])
