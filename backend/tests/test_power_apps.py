import pytest
from app.models.user import User, Role, Permission
from app.access.models import AccessPolicy
from app.core.security import create_access_token
from app.apps.power_apps.registry import PERMISSIONS
from app.apps.power_apps.models import PowerEnvironment, PowerResource, PowerVersion, PowerExecution, PowerActivity
from tests.tenant_test_utils import assign_company

ROOT = "/api/v1/power-apps"

@pytest.fixture
def actors(db):
    permissions = []
    for name in PERMISSIONS:
        p = db.query(Permission).filter_by(name=name).first()
        if not p:
            p = Permission(name=name, module="power_apps")
            db.add(p)
        permissions.append(p)
    role = Role(name="power_builder", permissions=permissions)
    viewer = Role(name="power_viewer", permissions=[p for p in permissions if p.name == "power_apps_view"])
    db.add_all([role, viewer]); db.flush()
    users = []
    for i, company in enumerate([1, 2, 1, 1, 1]):
        user = User(email=f"power-{i}@example.com", hashed_password="unused", role_id=viewer.id if i == 2 else role.id, is_active=True)
        db.add(user); db.flush(); assign_company(db, user, company); users.append(user)
    for company in [1, 2]:
        for environment in ["development", "testing"]:
            db.add(PowerEnvironment(organization_id=company, key=environment, enabled=True))
    # Exercise central policy + ORM ownership in addition to unmanaged roles.
    db.add(AccessPolicy(user_id=users[3].id, company_id=1, status="active", grants={"power_apps": {
        "enabled": True, "permissions": list(PERMISSIONS), "actions": ["view", "create", "edit", "delete"], "scope": "own", "role": "contributor"
    }}))
    db.add(AccessPolicy(user_id=users[4].id, company_id=1, status="active", grants={"power_apps": {
        "enabled": False, "permissions": list(PERMISSIONS), "actions": ["view", "create", "edit", "delete"], "scope": "organization", "role": "admin"
    }}))
    db.commit()
    return [{"Authorization": "Bearer " + create_access_token(u.id)} for u in users]

def create(client, headers, name="Customer welcome", env="development"):
    response = client.post(ROOT + "/automations", headers=headers, params={"environment": env}, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()

def test_catalog_real_empty_counts_and_auth(client, actors):
    assert client.get(ROOT + "/catalog").status_code in [401, 403]
    catalog = client.get(ROOT + "/catalog", headers=actors[0]).json()
    assert len(catalog["applications"]) == 12
    assert len({a["icon"] for a in catalog["applications"]}) == 12
    assert catalog["execution_enabled"] is True
    assert all(a["route"] == "/power-apps/" + a["id"] for a in catalog["applications"])
    result = client.get(ROOT + "/overview", headers=actors[0])
    assert result.status_code == 200, result.text
    assert all(value == 0 for value in result.json()["counts"].values())
    assert result.json()["recent"] == []
    assert client.get(ROOT + "/activity", headers=actors[0]).json()["items"] == []

def test_draft_versions_conflicts_and_activity(client, db, actors):
    row = create(client, actors[0])
    assert row["status"] == "draft" and row["version"] == 1
    payload = {"name": "Updated welcome", "description": "A versioned draft", "definition": row["definition"], "expected_version": 1}
    response = client.put(f"{ROOT}/automations/{row['id']}", headers=actors[0], json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["version"] == 2
    assert client.put(f"{ROOT}/automations/{row['id']}", headers=actors[0], json=payload).status_code == 409
    assert client.get(f"{ROOT}/automations/{row['id']}", headers=actors[0]).json()["name"] == "Updated welcome"
    versions = client.get(f"{ROOT}/automations/{row['id']}/versions", headers=actors[0]).json()["items"]
    assert [v["version"] for v in versions] == [2, 1]
    assert versions[1]["snapshot"]["name"] == "Customer welcome"
    assert [a["action"] for a in client.get(ROOT + "/activity", headers=actors[0]).json()["items"]] == ["draft_updated", "draft_created"]
    recent = client.get(ROOT + "/overview", headers=actors[0]).json()["recent"]
    assert recent[0]["id"] == row["id"]
    assert db.query(PowerExecution).count() == 0

@pytest.mark.parametrize("actor", [0, 3])
def test_tenant_environment_ownership_isolation(client, db, actors, actor):
    own = create(client, actors[actor])
    foreign = create(client, actors[1], "Foreign tenant private draft")
    other_owner = create(client, actors[0 if actor == 3 else 3], "Other owner draft")
    testing = create(client, actors[actor], "Testing only", "testing")
    result = client.get(ROOT + "/automations", headers=actors[actor])
    assert result.status_code == 200, result.text
    assert [r["id"] for r in result.json()["items"]] == [own["id"]]
    for row in [foreign, other_owner, testing]:
        path = f"{ROOT}/automations/{row['id']}"
        assert client.get(path, headers=actors[actor]).status_code == 404
        assert client.put(path, headers=actors[actor], json={"name": "stolen", "expected_version": 1}).status_code == 404
        assert client.delete(path + "?expected_version=1", headers=actors[actor]).status_code == 404
        assert client.get(path + "/versions", headers=actors[actor]).status_code == 404
    assert client.get(ROOT + "/overview", headers=actors[actor], params={"organization_id": 2}).json()["recent"][0]["id"] == own["id"]
    assert client.get(ROOT + "/catalog", headers={**actors[actor], "X-Suite-Organization": "2"}).status_code == 403
    assert "Foreign tenant private draft" not in client.get(ROOT + "/activity", headers=actors[actor]).text

def test_permissions_environment_validation_and_revocation(client, actors):
    assert client.post(ROOT + "/automations", headers=actors[2], json={"name": "No permission"}).status_code == 403
    assert client.get(ROOT + "/activity", headers=actors[2]).status_code == 403
    assert client.put(ROOT + "/environments/production", headers=actors[2], json={"enabled": True}).status_code == 403
    assert client.get(ROOT + "/catalog", headers=actors[4]).status_code == 403
    assert client.get(ROOT + "/overview?environment=unknown", headers=actors[0]).status_code == 422
    assert client.get(ROOT + "/overview?environment=production", headers=actors[0]).status_code == 403
    result = client.put(ROOT + "/environments/production", headers=actors[3], json={"enabled": True})
    assert result.status_code == 200, result.text
    assert client.get(ROOT + "/overview?environment=production", headers=actors[3]).status_code == 200
    assert client.put(ROOT + "/environments/production", headers=actors[0], json={"enabled": False}).status_code == 200
    assert client.get(ROOT + "/overview?environment=production", headers=actors[0]).status_code == 403

@pytest.mark.parametrize("payload", [{"status": "published"}, {"organization_id": 2}, {"owner_user_id": 99}, {"definition": {"api_key": "secret"}}, {"definition": {"nodes": [{"id": "a", "type": "action", "next": ["missing"]}]}}, {"definition": {"nodes": [{"id": "a", "type": "action"}, {"id": "a", "type": "delay"}]}}, {"name": "   "}])
def test_reject_unsafe_or_invalid_definitions(client, actors, payload):
    response = client.post(ROOT + "/automations", headers=actors[0], json={"name": "Draft", **payload})
    assert response.status_code == 422, response.text

def test_unvalidated_publication_inactive_execution_and_delete_audited(client, db, actors):
    row = create(client, actors[0])
    for action in ["publish", "execute"]:
        body = {"expected_version":1} if action=="publish" else {"input":{},"idempotency_key":"inactive-request"}
        response = client.post(f"{ROOT}/automations/{row['id']}/{action}", headers=actors[0],json=body)
        assert response.status_code == 409, response.text
        assert client.post(f"{ROOT}/automations/{row['id']}/{action}", headers=actors[2]).status_code == 403
    assert db.query(PowerExecution).count() == 0
    assert client.delete(f"{ROOT}/automations/{row['id']}?expected_version=2", headers=actors[0]).status_code == 409
    response = client.delete(f"{ROOT}/automations/{row['id']}?expected_version=1", headers=actors[0])
    assert response.status_code == 204, response.text
    assert client.get(f"{ROOT}/automations/{row['id']}", headers=actors[0]).status_code == 404
    assert db.query(PowerVersion).count() == 0
    assert db.query(PowerActivity).filter_by(action="draft_deleted").count() == 1


def test_editing_presets_do_not_grant_environment_or_runtime_powers():
    from app.access.catalog import action_permissions
    for tier in ["viewer", "contributor", "editor"]:
        selected = action_permissions(list(PERMISSIONS), tier)
        assert not set(selected).intersection({"power_apps_manage_environment", "power_apps_manage_credentials", "power_apps_publish", "power_apps_execute"})
    assert set(action_permissions(list(PERMISSIONS), "admin")) == set(PERMISSIONS)


def test_power_apps_remains_separate_from_existing_automation_registry():
    from app.module_registry import COMMON_ROUTER_MODULES, COMMON_MODEL_MODULES
    assert "app.apps.power_apps.router" in COMMON_ROUTER_MODULES
    assert "app.apps.automation.api.router" in COMMON_ROUTER_MODULES
    assert "app.apps.power_apps.models" in COMMON_MODEL_MODULES
    from app.apps.power_apps.registry import COMPONENTS, TEMPLATES
    assert not COMPONENTS and not TEMPLATES



def test_database_backed_metrics_are_scoped_to_environment_and_owner(client, db, actors):
    draft = create(client, actors[0])
    db.add(PowerResource(organization_id=1, environment="development", application_id="app-builder", name="Fixture app", description="", owner_user_id=draft["owner_user_id"], status="draft", version=1, definition={}))
    db.add(PowerResource(organization_id=1, environment="testing", application_id="app-builder", name="Other environment app", description="", owner_user_id=draft["owner_user_id"], status="draft", version=1, definition={}))
    # Historical run fixture verifies aggregation; no executor is invoked.
    db.add(PowerExecution(organization_id=1, environment="development", resource_id=draft["id"], owner_user_id=draft["owner_user_id"], workflow_version=1, actor_user_id=draft["owner_user_id"], idempotency_key="fixture-only", status="failed", attempt=1))
    db.commit()
    result = client.get(ROOT + "/overview", headers=actors[0]).json()["counts"]
    assert result["total_apps"] == 1
    assert result["workflow_executions"] == 1 and result["failed_runs"] == 1
    other = client.get(ROOT + "/overview", headers=actors[1]).json()["counts"]
    assert all(value == 0 for value in other.values())


def test_disabled_company_module_blocks_all_power_apps_apis(client, db, actors):
    from app.apps.business_os.models import BOSEnabledModule
    db.add(BOSEnabledModule(company_id=1, module_key="power_apps", display_name="Power Apps", enabled=False))
    db.commit()
    assert client.get(ROOT + "/catalog", headers=actors[0]).status_code == 403
    assert client.get(ROOT + "/overview", headers=actors[0]).status_code == 403
    assert client.post(ROOT + "/automations", headers=actors[0], json={"name": "Blocked"}).status_code == 403


def test_write_permissions_without_view_do_not_bypass_module_access(client, db, actors):
    user = db.query(User).filter_by(email="power-0@example.com").one()
    user.role.permissions = [p for p in user.role.permissions if p.name != "power_apps_view"]
    db.commit()
    assert client.post(ROOT + "/automations", headers=actors[0], json={"name": "Blocked"}).status_code == 403
