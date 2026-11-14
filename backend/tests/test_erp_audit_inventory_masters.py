from app.apps.fam.models import FAMBranch, FAMStockGroup
from tests.fam_inventory_test_utils import inventory_headers


def test_audit_stock_group_parent_is_scoped_and_cannot_create_cycles(client, db):
    headers = inventory_headers(client, db)
    base = "/api/v1/fam/inventory/stock-groups"
    def create(code, parent=None):
        response = client.post(base, headers=headers, json={"group_code": code, "group_name": code, "parent_group_id": parent})
        assert response.status_code == 201, response.text
        return response.json()
    root = create("ROOT")
    child = create("CHILD", root["id"])
    grandchild = create("GRAND", child["id"])
    for parent in [root["id"], child["id"], grandchild["id"]]:
        response = client.put(f"{base}/{root['id']}", headers=headers, json={"parent_group_id": parent})
        assert response.status_code == 422
        assert db.get(FAMStockGroup, root["id"]).parent_group_id is None
    foreign = FAMStockGroup(company_id=root["company_id"] + 1000, group_code="OTHER", group_name="Other company group")
    inactive = FAMStockGroup(company_id=root["company_id"], group_code="OLD", group_name="Retired group", active=False)
    db.add_all([foreign, inactive])
    db.commit()
    for parent in [foreign.id, inactive.id, 999999]:
        response = client.post(base, headers=headers, json={"group_code": "INVALID", "group_name": "Rejected group", "parent_group_id": parent})
        assert response.status_code == 422
    assert len(client.get(base, headers=headers).json()["items"]) == 3
    response = client.put(f"{base}/{grandchild['id']}", headers=headers, json={"parent_group_id": None})
    assert response.status_code == 200
    assert response.json()["parent_group_id"] is None


def test_audit_warehouse_branch_is_active_and_company_scoped(client, db):
    headers = inventory_headers(client, db)
    client.get("/api/v1/fam/module-info", headers=headers)
    seeded = client.post("/api/v1/fam/inventory/stock-groups", headers=headers, json={"group_code":"BRANCH-SEED", "group_name":"Branch seed"})
    assert seeded.status_code == 201
    company = seeded.json()["company_id"]
    local = FAMBranch(company_id=company, branch_code="AUD-LOCAL", branch_name="Local branch")
    foreign = FAMBranch(company_id=company + 1000, branch_code="AUD-OTHER", branch_name="Other company branch")
    inactive = FAMBranch(company_id=company, branch_code="AUD-OLD", branch_name="Closed branch", active=False)
    db.add_all([local, foreign, inactive])
    from test_identity_utils import own_workflow_records
    from app.branches.models import AccountingBranchMap
    own_workflow_records(db, local, inactive, company_id=company)
    db.add(AccountingBranchMap(accounting_branch_id=local.id, company_id=company, branch_id=int(headers["X-Suite-Branch"])))
    db.add(AccountingBranchMap(accounting_branch_id=inactive.id, company_id=company, branch_id=int(headers["X-Suite-Branch"])))
    db.commit()
    base = "/api/v1/fam/inventory/warehouses"
    for branch in [foreign.id, inactive.id, 999999]:
        response = client.post(base, headers=headers, json={"warehouse_code": "INVALID", "warehouse_name": "Rejected warehouse", "branch_id": branch})
        assert response.status_code == 422
    response = client.post(base, headers=headers, json={"warehouse_code": " AUD ", "warehouse_name": " Audit store ", "branch_id": local.id})
    assert response.status_code == 201, response.text
    warehouse = response.json()
    assert warehouse["warehouse_code"] == "AUD"
    assert warehouse["warehouse_name"] == "Audit store"
    for branch in [foreign.id, inactive.id]:
        response = client.put(f"{base}/{warehouse['id']}", headers=headers, json={"branch_id": branch})
        assert response.status_code == 422
    response = client.put(f"{base}/{warehouse['id']}", headers=headers, json={"branch_id": None})
    assert response.status_code == 403
    response = client.put(f"{base}/{warehouse['id']}", headers=headers, json={"warehouse_name":"Updated audit store"})
    assert response.status_code == 200, response.text
    assert response.json()["branch_id"] == local.id
    for path, payload in [("stock-groups", {"group_code": " ", "group_name": "Blank"}), ("units", {"unit_code": "AUD", "unit_name": " "}), ("warehouses", {"warehouse_code": "AUD2", "warehouse_name": " "})]:
        assert client.post(f"/api/v1/fam/inventory/{path}", headers=headers, json=payload).status_code == 422
