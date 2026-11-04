"""End-to-end scope and authorization checks against the real API boundary."""
import pytest
from app.models.company import Branch
from app.models.user import User
from app.branches.models import BranchPolicy, BranchGrant
from test_identity_utils import attach_test_identity
from tests.test_shared_catalog import item


@pytest.fixture
def scope(db, superuser_headers):
    actor = db.query(User).filter_by(email="testadmin@test.com").one()
    attach_test_identity(db, actor)
    rows = [Branch(company_id=1, name=f"Availability {i}", code=f"AV{i}") for i in range(3)]
    db.add_all(rows); db.commit()
    return actor, rows, superuser_headers


def headers(scope, index=0):
    return {**scope[2], "X-Suite-Branch": str(scope[1][index].id)}


@pytest.mark.parametrize("kind", ["product", "service"])
def test_catalog_create_all_selected_edit_and_current_default(client, scope, kind):
    root = "/api/v1/catalog"
    payload = item(kind, code=f"AV-{kind}")
    created = client.post(root + "/items?source=srm", headers=headers(scope), json={**payload, "branch_availability": {"scope": "all"}})
    assert created.status_code == 201, created.text
    ident = created.json()["id"]
    for i in range(3):
        result = client.get(root + "/items?source=srm", headers=headers(scope, i))
        assert ident in {x["id"] for x in result.json()["items"]}
    updated = client.put(f"{root}/items/{kind}/{ident}?source=srm", headers=headers(scope), json={**payload, "version": created.json()["version"], "branch_availability": {"scope": "selected", "branch_ids": [scope[1][0].id, scope[1][1].id]}})
    assert updated.status_code == 200, updated.text
    assert ident not in {x["id"] for x in client.get(root + "/items?source=srm", headers=headers(scope, 2)).json()["items"]}


@pytest.mark.parametrize("role", ["Customer", "Vendor", "Supplier"])
def test_company_roles_share_and_revoke_without_sharing_transactions(client, scope, role):
    root = "/api/v1/master-data/companies"
    created = client.post(root, headers=headers(scope), json={"name": f"Available {role}", "roles": [role], "branch_availability": {"scope": "all"}})
    assert created.status_code == 201, created.text
    row = created.json()
    for i in range(3):
        listing = client.get(root, headers=headers(scope, i), params={"role": role})
        assert listing.status_code == 200, listing.text
        assert row["id"] in {x["id"] for x in listing.json()["items"]}
    saved = client.patch(f"{root}/{row['id']}", headers=headers(scope), json={"name": row["name"], "version": row["version"], "branch_availability": {"scope": "current"}})
    assert saved.status_code == 200, saved.text
    assert client.get(f"{root}/{row['id']}", headers=headers(scope, 1)).status_code == 404


def test_contact_all_and_revoke(client, scope):
    root = "/api/v1/crm/contact-directory"
    response = client.post(root, headers=headers(scope), json={"name": "Shared contact", "branch_availability": {"scope": "all"}})
    assert response.status_code == 200, response.text
    row = response.json()
    for i in range(3):
        assert client.get(f"{root}/{row['id']}", headers=headers(scope, i)).status_code == 200
    response = client.patch(f"{root}/{row['id']}", headers=headers(scope), json={"name": row["name"], "version": row["version"], "branch_availability": {"scope": "current"}})
    assert response.status_code == 200, response.text
    assert client.get(f"{root}/{row['id']}", headers=headers(scope, 1)).status_code == 404


def test_invalid_or_unauthorized_scope_is_atomic(client, db, scope):
    root = "/api/v1/master-data/companies"
    for availability, expected in [({"scope": "selected", "branch_ids": []}, 422), ({"scope": "selected", "branch_ids": [999999]}, 422), ({"scope": "selected", "branch_ids": [scope[1][0].id, 999999]}, 403)]:
        response = client.post(root, headers=headers(scope), json={"name": "Rejected scope", "branch_availability": availability})
        assert response.status_code == expected, response.text
    scope[0].is_superuser = False
    db.add(BranchPolicy(user_id=scope[0].id, company_id=1, use_home_branch=False))
    db.add(BranchGrant(user_id=scope[0].id, company_id=1, branch_id=scope[1][0].id, can_write=True))
    db.commit()
    response = client.post("/api/v1/catalog/items?source=srm", headers=headers(scope), json={**item("product", code="DENIED-ALL"), "branch_availability": {"scope": "all"}})
    assert response.status_code == 403, response.text


def test_all_is_snapshot_and_default_is_current(client, db, scope):
    root = "/api/v1/catalog/items?source=srm"
    shared = client.post(root, headers=headers(scope), json={**item("product", code="SNAPSHOT"), "branch_availability": {"scope": "all"}})
    assert shared.status_code == 201, shared.text
    local = client.post(root, headers=headers(scope), json=item("product", code="LOCAL-DEFAULT"))
    assert local.status_code == 201, local.text
    visible = client.get(root, headers=headers(scope, 1)).json()["items"]
    assert shared.json()["id"] in {x["id"] for x in visible}
    assert local.json()["id"] not in {x["id"] for x in visible}
    branch = Branch(company_id=1, name="Future branch", code="FUTURE-AV")
    db.add(branch); db.commit()
    visible = client.get(root, headers={**scope[2], "X-Suite-Branch": str(branch.id)}).json()["items"]
    assert shared.json()["id"] not in {x["id"] for x in visible}


def test_destination_module_viewer_cannot_receive_new_offering(client, db, scope):
    from app.models.user import Role, Permission
    permission = db.query(Permission).filter_by(name="srm_manage").first()
    if permission is None:
        permission = Permission(name="srm_manage", module="srm")
        db.add(permission); db.flush()
    role = Role(name="availability_srm_manager", is_system=False)
    role.permissions.append(permission)
    db.add(role); db.flush()
    scope[0].role_id = role.id
    scope[0].is_superuser = False
    db.add(BranchPolicy(user_id=scope[0].id, company_id=1, use_home_branch=False))
    db.add(BranchGrant(user_id=scope[0].id, company_id=1, branch_id=scope[1][0].id, can_write=True))
    db.add(BranchGrant(user_id=scope[0].id, company_id=1, branch_id=scope[1][1].id, can_write=True, module_grants={"srm": {"enabled": True, "role": "viewer", "permissions": ["srm_view"], "actions": ["view"], "scope": "organization"}}))
    db.commit()
    response = client.post("/api/v1/catalog/items?source=srm", headers=headers(scope), json={**item("product", code="VIEWER-DEST"), "branch_availability": {"scope": "selected", "branch_ids": [b.id for b in scope[1][:2]]}})
    assert response.status_code == 403, response.text
    assert "module role" in response.json()["detail"]
