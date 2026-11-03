import pytest
from sqlalchemy import select
from app.models.user import User, Role, Permission
from app.models.company import Branch
from app.apps.srm.models import SRMProduct
from app.branches.models import BranchAudit, BranchGrant, BranchPolicy
from test_identity_utils import attach_test_identity
from tests.test_shared_catalog import item, ROOT


@pytest.fixture
def scope(db, superuser_headers):
    admin = db.query(User).filter_by(email="testadmin@test.com").one()
    attach_test_identity(db, admin)
    db.flush()
    branches = [Branch(company_id=1, name=name, code=name) for name in ("SOURCE", "DEST", "THIRD")]
    db.add_all(branches); db.commit()
    return admin, branches, superuser_headers


def headers(scope, index=0):
    return {**scope[2], "X-Suite-Branch": str(scope[1][index].id)}


def create(client, scope, kind="product"):
    response = client.post(ROOT + "/items?source=srm", headers=headers(scope), json=item(kind, code=kind.upper(), barcode="BAR-" + kind))
    assert response.status_code == 201, response.text
    return response.json()


def reuse(client, scope, values, operation="share", destinations=None, index=0):
    return client.post(ROOT + "/branches/reuse?source=srm", headers=headers(scope, index), json={"operation": operation, "items": [{key: value[key] for key in ("id", "kind", "version")} for value in values], "branch_ids": destinations or [scope[1][1].id]})


def listed(client, scope, index=0, source="srm"):
    response = client.get(ROOT + "/items", params={"source": source}, headers=headers(scope, index))
    assert response.status_code == 200, response.text
    return response.json()["items"]


def test_bulk_share_move_and_history(client, db, scope):
    offerings = [create(client, scope, kind) for kind in ("product", "service")]
    product = db.get(SRMProduct, offerings[0]["id"])
    product.current_quantity = 12
    db.commit()
    sale = {"title": "Existing branch sale", "lines": [{"product_id": offerings[0]["id"], "description": "Original offering", "quantity": 1, "unit_price": 125.50}]}
    historical = client.post("/api/v1/srm/sales-orders", headers=headers(scope), json=sale)
    assert historical.status_code == 201, historical.text
    assert len(listed(client, scope)) == 2
    assert not listed(client, scope, 1)
    shared = reuse(client, scope, offerings)
    assert shared.status_code == 200, shared.text
    for source in ("srm", "crm", "pms"):
        assert {row["id"] for row in listed(client, scope, 1, source)} == {row["id"] for row in offerings}
    # Sharing keeps a single master and prevents an old selection overwriting it.
    assert db.query(SRMProduct).count() == 2
    assert reuse(client, scope, offerings, "move").status_code == 409
    current = listed(client, scope)
    moved = reuse(client, scope, current, "move", [scope[1][2].id])
    assert moved.status_code == 200, moved.text
    assert not listed(client, scope)
    assert len(listed(client, scope, 1)) == 2
    assert len(listed(client, scope, 2)) == 2
    # Detail reads remain possible for historical links after moving availability.
    original = offerings[0]
    assert client.get(f"{ROOT}/items/product/{original['id']}?source=srm", headers=headers(scope)).status_code == 200
    current_product = next(row for row in listed(client, scope, 2) if row["id"] == original["id"])
    edit = {key: value for key, value in current_product.items() if key != "id"}
    assert client.put(f"{ROOT}/items/product/{original['id']}?source=srm", headers=headers(scope), json=edit).status_code == 403
    assert client.put(f"/api/v1/srm/inventory/items/{original['id']}", headers=headers(scope), json={"sales_rate": 1}).status_code == 403
    assert db.scalar(select(BranchAudit.id).where(BranchAudit.operation == "catalog.branch.move"))
    stock = client.get("/api/v1/srm/inventory/items", headers=headers(scope))
    assert stock.status_code == 200, stock.text
    assert stock.json()["total"] == 0
    assert db.get(SRMProduct, offerings[0]["id"]).current_quantity == 12
    assert client.get(f"/api/v1/srm/sales-orders/{historical.json()['id']}", headers=headers(scope)).status_code == 200
    assert client.post("/api/v1/srm/sales-orders", headers=headers(scope), json=sale).status_code == 422
    destination_sale = client.post("/api/v1/srm/sales-orders", headers=headers(scope, 2), json={**sale, "order_number": "DEST-SALE-001"})
    assert destination_sale.status_code == 201, destination_sale.text


@pytest.mark.parametrize("kind", ["product", "service"])
def test_copy_preserves_details_and_is_independent(client, db, scope, kind):
    original = create(client, scope, kind)
    response = reuse(client, scope, [original], "copy", [branch.id for branch in scope[1][1:]])
    assert response.status_code == 200, response.text
    assert len(response.json()["results"]) == 2
    assert len(listed(client, scope)) == 1
    copy = listed(client, scope, 1)[0]
    other = listed(client, scope, 2)[0]
    assert len({original["id"], copy["id"], other["id"]}) == 3
    assert len({original["code"], copy["code"], other["code"]}) == 3
    for key in ("name", "price", "tax", "images", "custom_fields", "pricing_options"):
        assert copy[key] == original[key]
    values = {key: value for key, value in copy.items() if key != "id"}
    values["price"] = 888
    update = client.put(f"{ROOT}/items/{kind}/{copy['id']}?source=srm", headers=headers(scope, 1), json=values)
    assert update.status_code == 200, update.text
    assert listed(client, scope)[0]["price"] == original["price"]
    row = db.get(SRMProduct, copy["id"])
    assert row.track_inventory == (kind == "product")
    assert not row.current_quantity
    assert row.barcode is None


def test_reuse_validates_entire_batch_and_destinations(client, db, scope):
    original = create(client, scope)
    invalid = {**original, "id": 999999}
    assert reuse(client, scope, [original, invalid]).status_code == 404
    assert not listed(client, scope, 1)
    assert reuse(client, scope, [original], destinations=[999999]).status_code == 403
    assert reuse(client, scope, [original], destinations=[scope[1][0].id]).status_code == 422
    assert reuse(client, scope, [original], "move", [branch.id for branch in scope[1][1:]]).status_code == 422
    assert reuse(client, scope, [original, original]).status_code == 422
    # Writable branch access is checked even for an otherwise privileged actor.
    scope[0].is_superuser = False
    db.add(BranchPolicy(user_id=scope[0].id, company_id=1, use_home_branch=False))
    db.add(BranchGrant(user_id=scope[0].id, company_id=1, branch_id=scope[1][0].id, can_write=True))
    db.add(BranchGrant(user_id=scope[0].id, company_id=1, branch_id=scope[1][1].id, can_write=False))
    db.commit()
    assert reuse(client, scope, [original]).status_code == 403


def test_legacy_catalogues_stay_shared(client, db, scope):
    db.add(SRMProduct(organization_id=1, sku="LEGACY", item_name="Existing shared master", product_type="stock", active=True))
    db.commit()
    assert all(listed(client, scope, index)[0]["code"] == "LEGACY" for index in range(3))


def test_destination_module_role_is_enforced(client, db, scope):
    original = create(client, scope)
    permission = db.query(Permission).filter_by(name="srm_manage").first()
    if permission is None:
        permission = Permission(name="srm_manage", module="srm")
        db.add(permission); db.flush()
    role = Role(name="catalog_branch_manager", is_system=False)
    role.permissions.append(permission)
    db.add(role); db.flush()
    scope[0].role_id = role.id
    scope[0].is_superuser = False
    db.add(BranchPolicy(user_id=scope[0].id, company_id=1, use_home_branch=False))
    db.add(BranchGrant(user_id=scope[0].id, company_id=1, branch_id=scope[1][0].id, can_write=True))
    db.add(BranchGrant(user_id=scope[0].id, company_id=1, branch_id=scope[1][1].id, can_write=True, module_grants={"srm": {"enabled": True, "role": "viewer", "permissions": ["srm_view"], "actions": ["view"], "scope": "organization"}}))
    db.commit()
    response = reuse(client, scope, [original])
    assert response.status_code == 403, response.text
    assert "module role" in response.json()["detail"]


def test_existing_catalog_crud_with_concrete_branch(client, db, scope):
    from tests.test_shared_catalog import test_shared_crud_preserves_legacy_ids_and_projects
    test_shared_crud_preserves_legacy_ids_and_projects(client, db, headers(scope))


def test_existing_import_export_with_concrete_branch(client, db, scope):
    from tests.test_shared_catalog import test_import_export_validation_and_atomicity
    test_import_export_validation_and_atomicity(client, db, headers(scope))
