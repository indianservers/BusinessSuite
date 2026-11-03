from tests.test_contact_directory import directory_identity
import io
import json
import pytest
from app.apps.crm.models import CRMProduct, CRMService, CRMCompany, CRMLead
from app.apps.srm.models import SRMProduct
from app.apps.project_management.models import PMSProject
from app.models.user import User, Role, Permission
from app.core.security import get_password_hash
from test_identity_utils import attach_test_identity
from tests.test_suite_access import access_account, secure, grant, apply, login

ROOT = "/api/v1/catalog"


@pytest.fixture
def headers(db, superuser_headers):
    attach_test_identity(db, db.query(User).filter_by(email="testadmin@test.com").one())
    db.commit()
    return superuser_headers


def item(kind="product", **extra):
    return {"kind": kind, "name": "Enterprise offering", "code": "ENT-001", "price": 125.50, "currency": "INR", "tax": 18, "unit": "seat", "category": "Software", "images": ["https://example.com/product.png"], "custom_fields": {"Edition": "Enterprise"}, "pricing_options": [{"id": "monthly", "name": "Monthly", "amount": 100, "currency": "INR", "interval": "month"}], **extra}


def create(client, headers, payload=None, source="pms"):
    r = client.post(ROOT + "/items", params={"source": source}, headers=headers, json=payload or item())
    assert r.status_code == 201, r.text
    return r.json()


def test_shared_crud_preserves_legacy_ids_and_projects(client, db, headers):
    project = PMSProject(name="Project stays a project", project_key="KEEP", organization_id=1)
    db.add(project); db.commit()
    product = create(client, headers)
    service = create(client, headers, item("service", code="SVC-001"), "crm")
    assert db.get(SRMProduct, product["id"]).sku == product["code"]
    assert db.get(SRMProduct, service["id"]).sku == service["code"]
    assert not db.query(CRMProduct).count() and not db.query(CRMService).count()
    for source in ("pms", "crm", "srm"):
        response = client.get(ROOT + "/items", params={"source": source}, headers=headers)
        assert response.status_code == 200, response.text
        assert {(v["kind"], v["id"]) for v in response.json()["items"]} == {("product", product["id"]), ("service", service["id"])}
    edited = {k: v for k, v in product.items() if k != "id"}; edited["price"] = 150
    r = client.put(f"{ROOT}/items/product/{product['id']}?source=crm", headers=headers, json=edited)
    assert r.status_code == 200, r.text
    assert client.get(f"{ROOT}/items/product/{product['id']}?source=pms", headers=headers).json()["price"] == 150
    assert client.put(f"{ROOT}/items/product/{product['id']}?source=pms", headers=headers, json=edited).status_code == 409
    copy = client.post(f"{ROOT}/items/product/{product['id']}/duplicate?source=crm", headers=headers)
    assert copy.status_code == 201, copy.text
    assert copy.json()["code"] != product["code"]
    assert copy.json()["custom_fields"] == product["custom_fields"]
    assert client.post(f"{ROOT}/items/product/{product['id']}/archive?source=pms", headers=headers).status_code == 200
    assert db.get(PMSProject, project.id).name == "Project stays a project"
    old_api = client.get(f"/api/v1/crm/products/{product['id']}", headers=headers)
    assert old_api.status_code == 200
    assert old_api.json()["active"] is False


def test_links_pricing_tax_and_tenant_isolation(client, db, headers):
    product = create(client, headers)
    customer = CRMCompany(organization_id=1, name="Customer")
    lead = CRMLead(organization_id=1, full_name="Lead", first_name="Lead", status="New")
    project = PMSProject(organization_id=1, name="Delivery", project_key="DEL")
    db.add_all([customer, lead, project]); db.commit()
    line = {"kind": "product", "item_id": product["id"], "pricing_id": "monthly", "quantity": 3, "discount": 10}
    for target, ident, source in (("customer", customer.id, "crm"), ("lead", lead.id, "crm"), ("project", project.id, "pms")):
        r = client.put(f"{ROOT}/links/{target}/{ident}?source={source}", headers=headers, json={"lines": [line]})
        assert r.status_code == 200, r.text
        saved = r.json()["lines"][0]
        assert saved["unit_price"] == 100
        assert saved["subtotal"] == 270
        assert saved["tax_amount"] == 48.6
        assert saved["total_amount"] == 318.6
    row = db.get(SRMProduct, product["id"]); row.organization_id = 2; db.commit()
    assert client.get(f"{ROOT}/items/product/{product['id']}?source=crm", headers=headers).status_code == 404
    assert not client.get(f"{ROOT}/items?source=pms", headers=headers).json()["items"]
    r = client.put(f"{ROOT}/links/customer/{customer.id}?source=crm", headers=headers, json={"lines": [line]})
    assert r.status_code == 404


def test_import_export_validation_and_atomicity(client, db, headers):
    product = create(client, headers)
    for format in ("json", "csv"):
        exported = client.get(f"{ROOT}/export?source=pms&format={format}", headers=headers)
        assert exported.status_code == 200, exported.text
        assert "ENT-001" in exported.text
    invalid = client.post(ROOT + "/items?source=crm", headers=headers, json=item(code="BAD", price=-1))
    assert invalid.status_code == 422
    values = [item(code="NEW-001"), item(code=product["code"])]
    r = client.post(ROOT + "/import?source=crm", headers=headers, files={"file": ("catalog.json", io.BytesIO(json.dumps(values).encode()), "application/json")})
    assert r.status_code == 409, r.text
    assert db.query(SRMProduct).filter_by(sku="NEW-001").count() == 0
    values = [item("service", code="NEW-SVC")]
    r = client.post(ROOT + "/import?source=pms", headers=headers, files={"file": ("catalog.json", json.dumps(values).encode(), "application/json")})
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1


def scoped_headers(client, db, name, permissions, organization=1):
    role = Role(name=name, is_system=False); db.add(role); db.flush()
    for name in permissions:
        permission = db.query(Permission).filter_by(name=name).first()
        if not permission: permission = Permission(name=name, module="crm" if name.startswith("crm") else "project_management"); db.add(permission); db.flush()
        role.permissions.append(permission)
    user = User(email=f"{role.name}@example.com", is_active=True, hashed_password=get_password_hash("Catalog@12345"), role_id=role.id)
    db.add(user); attach_test_identity(db, user, company_id=organization); db.commit()
    result = client.post("/api/v1/auth/login", json={"email": user.email, "password": "Catalog@12345"})
    assert result.status_code == 200, result.text
    return {"Authorization": "Bearer " + result.json()["access_token"]}


def test_read_only_permissions_and_cross_module_access(client, db, headers):
    create(client, headers)
    viewer = scoped_headers(client, db, "pms_catalog_viewer", ["pms_view"])
    assert client.get(ROOT + "/items?source=pms", headers=viewer).status_code == 200
    assert client.post(ROOT + "/items?source=pms", headers=viewer, json=item(code="DENIED")).status_code == 403
    assert client.get(ROOT + "/items?source=crm", headers=viewer).status_code == 403
    other = scoped_headers(client, db, "other_catalog_admin", ["pms_admin"], 2)
    assert not client.get(ROOT + "/items?source=pms", headers=other).json()["items"]
    assert client.get(ROOT + "/items").status_code in {401, 403}


def test_customer_creation_links_are_atomic(client, db, headers):
    product = create(client, headers)
    r = client.post("/api/v1/crm/companies", headers=headers, json={"name": "Linked on creation", "catalog_lines": [{"kind": "product", "item_id": product["id"], "quantity": 2, "discount": 0}]})
    assert r.status_code == 201, r.text
    ident = r.json()["id"]
    assert client.get(f"{ROOT}/links/customer/{ident}?source=crm", headers=headers).json()["lines"][0]["quantity"] == 2
    r = client.post("/api/v1/crm/companies", headers=headers, json={"name": "Must roll back", "catalog_lines": [{"kind": "product", "item_id": 999999, "quantity": 1}]})
    assert r.status_code == 404
    db.rollback()
    db.expire_all()
    assert db.query(CRMCompany).filter_by(name="Must roll back").count() == 0


def test_lead_capture_saves_catalog_lines_with_lead(client, db, headers):
    service = create(client, headers, item("service", code="LEAD-SERVICE"))
    response = client.post("/api/v1/crm/lead-management/leads", headers=headers, json={"values": {"full_name": "Catalog Lead", "email": "catalog-lead@example.com"}, "catalog_lines": [{"kind": "service", "item_id": service["id"], "quantity": 2, "unit_price": 200, "discount": 5}]})
    assert response.status_code == 201, response.text
    saved = client.get(f"{ROOT}/links/lead/{response.json()['id']}?source=crm", headers=headers)
    assert saved.status_code == 200, saved.text
    assert saved.json()["lines"][0]["subtotal"] == 380


def test_managed_pms_catalog_works_without_crm_grant(client, db, headers, access_account):
    if not db.query(Permission).filter_by(name="pms_manage_projects").first():
        db.add(Permission(name="pms_manage_projects", module="project_management")); db.commit()
    admin = secure(client, headers)
    pms = grant(client, admin, "project_management", "admin")
    applied = apply(client, admin, access_account, {"project_management": pms, "crm": {**grant(client, admin, "crm", "viewer"), "enabled": False}})
    assert applied.status_code == 200, applied.text
    actor = login(client)
    created = create(client, actor, item(code="PMS-ONLY"), "pms")
    listed = client.get(ROOT + "/items?source=pms", headers=actor)
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"][0]["id"] == created["id"]
    assert client.get(ROOT + "/items?source=crm", headers=actor).status_code == 403
    crm = grant(client, admin, "crm", "admin")
    applied = apply(client, admin, access_account, {"project_management": pms, "crm": crm}, version=1)
    assert applied.status_code == 200, applied.text
    actor = login(client)
    result = client.get(ROOT + "/items?source=crm", headers=actor)
    assert result.status_code == 200, result.text
    assert any(row["code"] == "PMS-ONLY" for row in result.json()["items"])


def test_deal_lines_reuse_existing_pricing_and_recalculate_value(client, db, headers):
    from tests.test_crm_deal_catalog import seed
    payload, _, _ = seed(client, db, headers)
    product = create(client, headers)
    line = {"kind": "product", "item_id": product["id"], "pricing_id": "monthly", "quantity": 3, "unit_price": 100, "discount": 10}
    response = client.post("/api/v1/crm/deals", headers=headers, json={**payload, "currency": "INR", "catalog_items": [line]})
    assert response.status_code == 201, response.text
    assert response.json()["amount"] == 270
    ident = response.json()["id"]
    response = client.put(f"{ROOT}/links/deal/{ident}?source=crm", headers=headers, json={"lines": [{**line, "quantity": 4, "discount": 5}]})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 380
    assert client.post(f"{ROOT}/items/product/{product['id']}/archive?source=pms", headers=headers).status_code == 200
    # An existing archived line remains usable; a new deal cannot add it.
    response = client.put(f"{ROOT}/links/deal/{ident}?source=crm", headers=headers, json={"lines": [{**line, "quantity": 2}]})
    assert response.status_code == 200, response.text
    response = client.post("/api/v1/crm/deals", headers=headers, json={**payload, "name": "New deal", "currency": "INR", "catalog_items": [line]})
    assert response.status_code == 422
    response = client.put(f"{ROOT}/links/deal/{ident}?source=crm", headers=headers, json={"lines": []})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 0


def test_workspace_scope_applies_to_shared_and_legacy_apis(client, db, headers):
    created = client.post("/api/v1/project-management/workspaces", headers=headers, json={"name": "Private catalog workspace"})
    assert created.status_code in {200, 201}, created.text
    workspace_id = created.json()["id"]
    product = create(client, headers, item(workspace_id=workspace_id))
    outsider = scoped_headers(client, db, "catalog_outsider", ["crm_view", "pms_view"])
    for source in ("pms", "crm"):
        listed = client.get(ROOT + f"/items?source={source}", headers=outsider)
        assert listed.status_code == 200, listed.text
        assert not listed.json()["items"]
        assert client.get(f"{ROOT}/items/product/{product['id']}?source={source}", headers=outsider).status_code in {403, 404}
    listed = client.get("/api/v1/crm/products", headers=outsider)
    assert listed.status_code == 200
    assert not listed.json()["items"]


@pytest.mark.parametrize("path,parent", [
    ("alembic/versions/20261102_056_shared_catalog.py", "20261102_055_crm_task_sync"),
    ("alembic_postgresql/versions/pg_20261102_057_shared_catalog.py", "pg_20261102_056_crm_task_sync"),
])
def test_catalog_migration_preserves_legacy_records(path, parent):
    import importlib.util
    from pathlib import Path
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        for name in ("crm_products", "crm_services", "pms_workspaces", "pms_projects"):
            connection.execute(sa.text(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY, name TEXT)"))
            connection.execute(sa.text(f"INSERT INTO {name} VALUES (1, 'Existing')"))
        spec = importlib.util.spec_from_file_location("shared_catalog_migration", Path(__file__).parents[1] / path)
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        assert migration.down_revision == parent and len(migration.revision) <= 32
        migration.op = Operations(MigrationContext.configure(connection)); migration.upgrade()
        assert sa.inspect(connection).has_table("shared_catalog_links")
        migration.downgrade()
        for name in ("crm_products", "crm_services", "pms_projects"):
            assert connection.execute(sa.text(f"SELECT name FROM {name} WHERE id=1")).scalar() == "Existing"
    engine.dispose()



def test_all_branches_catalog_creation_uses_discovered_default(client, db, headers):
    from sqlalchemy import select
    from app.branches.models import BranchOwnership
    from app.models.company import Branch

    db.add(Branch(company_id=1, organization_id=1, name="Default catalog branch", code="CAT-DEFAULT", is_active=True))
    db.commit()
    overview = client.get("/api/v1/branches/context", headers={**headers, "X-Suite-Branch": "all"})
    assert overview.status_code == 200, overview.text
    data = overview.json()
    assert data["selected"] == data["default_branch_id"]
    destination = data["default_branch_id"]
    assert destination in {branch["id"] for branch in data["branches"] if branch["can_write"]}
    product = create(client, {**headers, "X-Suite-Branch": "all"}, source="srm")
    assert db.get(SRMProduct, product["id"]) is not None
    # Catalog definitions are shared; their business audit trail needs a branch.
    owners = db.connection().execute(select(BranchOwnership.branch_id).where(
        BranchOwnership.resource_table == "audit_logs")).scalars().all()
    assert owners and set(owners) == {destination}
    assert client.get("/api/v1/branches/context", headers={**headers, "X-Suite-Branch": "all"}).json()["selected"] == destination
