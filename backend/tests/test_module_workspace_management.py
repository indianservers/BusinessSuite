import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_pms_task_studio import studio
from tests.test_pms_workspaces import middleware_database
from app.shared.workspace_management.domains import DOMAINS
from app.apps.project_management.models import PMSWorkspace


def payload(module, **changes):
    return {"name": f"{module.upper()} Delivery", "description": "A focused team space", "icon": "team", "color": "#168354", "visibility": "private", "views": list(DOMAINS[module].views[:2]), "members": [], **changes}


@pytest.mark.parametrize("module", ["crm", "hrms", "srm", "fam", "pms"])
def test_workspace_lifecycle_and_audit(client, db, studio, module):
    owner, _, outsider, headers, _, outsider_headers, *_ = studio
    base = f"/api/v1/{DOMAINS[module].api}/workspace-directory"
    before = db.query(PMSWorkspace).count()
    result = client.post(base, json=payload(module), headers=headers)
    assert result.status_code == 201, result.text
    record = result.json()
    assert record["icon"] == "team" and record["owner_id"] == owner.id
    assert db.query(PMSWorkspace).count() == before + (1 if module == "pms" else 0)
    update = payload(module, name="Renamed space", expected_version=record["version"])
    changed = client.put(base + "/" + record["id"], json=update, headers=headers)
    assert changed.status_code == 200, changed.text
    assert changed.json()["name"] == "Renamed space"
    assert client.put(base + "/" + record["id"], json=update, headers=headers).status_code == 409
    archived = client.put(base + "/" + record["id"], json=payload(module, expected_version=changed.json()["version"], status="Archived"), headers=headers)
    assert archived.status_code == 200, archived.text
    restored = client.put(base + "/" + record["id"], json=payload(module, expected_version=archived.json()["version"]), headers=headers)
    assert restored.status_code == 200, restored.text
    activity = client.get(base + "/" + record["id"] + "/activity", headers=headers)
    assert activity.status_code == 200, activity.text
    assert len(activity.json()) == 4
    assert any("archived" in row["summary"].lower() for row in activity.json())
    assert client.get(base + "/" + record["id"] + "/activity", headers=outsider_headers).status_code in {403, 404}
    assert client.post(base, json=payload(module), headers=outsider_headers).status_code in {403, 404}
    assert client.get(base).status_code in {401, 403}


def test_pms_reuses_existing_workspace(client, db, studio):
    _, _, _, headers, _, _, project, *_ = studio
    before = db.query(PMSWorkspace).count()
    wid = str(project["workspace_id"])
    result = client.put("/api/v1/project-management/workspace-directory/" + wid, json=payload("pms", expected_version=0), headers=headers)
    assert result.status_code == 200, result.text
    assert db.query(PMSWorkspace).count() == before
    assert db.get(PMSWorkspace, int(wid)).name == "PMS Delivery"
    assert any(str(row["id"]) == wid for row in client.get("/api/v1/project-management/workspaces", headers=headers).json())


def test_tenant_branch_and_module_reassignment_denied(client, db, studio):
    _, _, _, headers, *_ = studio
    base = "/api/v1/crm/workspace-directory"
    created = client.post(base, json=payload("crm"), headers=headers)
    assert created.status_code == 201, created.text
    ref = created.json()["id"]
    assert client.put("/api/v1/fam/workspace-directory/" + ref, json=payload("fam", expected_version=1), headers=headers).status_code == 404
    assert client.post(base, json=payload("crm", views=["payables"]), headers=headers).status_code == 422
    assert client.post(base, json={**payload("crm"), "company_id": 99}, headers=headers).status_code == 422
    assert client.post(base, json=payload("crm", members=[{"user_id": 999999, "role": "Admin"}]), headers=headers).status_code == 422
    from app.models.company import Branch
    from app.branches.models import BranchGrant
    branch = Branch(company_id=1, name="Other workspace branch")
    db.add(branch); db.flush()
    db.add(BranchGrant(user_id=studio[0].id, company_id=1, branch_id=branch.id, can_write=True)); db.commit()
    other_headers = {**headers, "X-Suite-Branch": str(branch.id)}
    other = client.get(base, headers=other_headers)
    assert other.status_code == 200, other.text
    assert ref not in [row["id"] for row in other.json()["items"]]
    assert client.put(base + "/" + ref, json=payload("crm", expected_version=1), headers=other_headers).status_code == 404


def test_workspace_membership_does_not_grant_module_access(client, db, studio):
    _, _, outsider, headers, _, outsider_headers, *_ = studio
    base = "/api/v1/crm/workspace-directory"
    created = client.post(base, json=payload("crm", members=[{"user_id": outsider.id, "role": "Admin"}]), headers=headers)
    assert created.status_code == 201, created.text
    assert client.get(base, headers=outsider_headers).status_code == 403
    assert client.get("/api/v1/fam/workspace-directory", headers=outsider_headers).status_code == 403

def test_foreign_company_metadata_and_activity_are_hidden(client, db, studio):
    from app.models.company import Company
    from app.shared.models import ServicePolicy
    owner, _, _, headers, *_ = studio
    if not db.get(Company, 2): db.add(Company(id=2, name="Foreign workspace company")); db.flush()
    foreign = ServicePolicy(organization_id=2, scope_key="workspace:crm:2:1:foreign", kind="module_workspace", module_key="crm", updated_by=owner.id, values_json={**payload("crm"), "owner_id": owner.id})
    db.add(foreign); db.commit()
    base = "/api/v1/crm/workspace-directory"
    result = client.get(base, headers=headers)
    assert result.status_code == 200, result.text
    assert all(row["id"] != "foreign" for row in result.json()["items"])
    assert client.get(base + "/foreign", headers=headers).status_code == 404
    assert client.get(base + "/foreign/activity", headers=headers).status_code == 404


def test_private_member_access_and_removal(client, db, studio):
    from app.models.user import Role, Permission
    owner, _, member, headers, _, member_headers, *_ = studio
    permission = db.query(Permission).filter_by(name="crm_view").first()
    if permission is None:
        permission = Permission(name="crm_view", description="View CRM", module="crm")
        db.add(permission); db.flush()
    role = Role(name="workspace_test_crm_reader", permissions=[permission])
    db.add(role); db.flush(); member.role = role; db.commit()
    base = "/api/v1/crm/workspace-directory"
    result = client.post(base, json=payload("crm", members=[{"user_id": member.id, "role": "Member"}]), headers=headers)
    assert result.status_code == 201, result.text
    row = result.json()
    detail = client.get(base + "/" + row["id"], headers=member_headers)
    assert detail.status_code == 200, detail.text
    assert not detail.json()["can_manage"]
    assert client.put(base + "/" + row["id"], json=payload("crm", expected_version=row["version"]), headers=member_headers).status_code == 403
    changed = client.put(base + "/" + row["id"], json=payload("crm", expected_version=row["version"], members=[]), headers=headers)
    assert changed.status_code == 200, changed.text
    assert client.get(base + "/" + row["id"], headers=member_headers).status_code == 404
    assert not any(item["id"] == row["id"] for item in client.get(base, headers=member_headers).json()["items"])


def test_disabled_module_rejects_workspace_access(client, db, studio, monkeypatch):
    from app.shared.workspace_management import domains
    monkeypatch.setattr(domains, "is_app_enabled", lambda key: False)
    assert client.get("/api/v1/crm/workspace-directory", headers=studio[3]).status_code == 403


def test_pms_legacy_archive_state_wins_and_stale_editor_cannot_restore(client, db, studio):
    _, _, _, headers, _, _, project, *_ = studio
    wid = str(project["workspace_id"])
    base = "/api/v1/project-management/workspace-directory/" + wid
    first = client.put(base, json=payload("pms", expected_version=0), headers=headers)
    assert first.status_code == 200, first.text
    version = first.json()["version"]
    from app.apps.project_management.workspace_lifecycle import WorkspaceArchive
    marker = WorkspaceArchive(workspace_id=int(wid), deleted_at=__import__('datetime').datetime.utcnow(), deleted_by=studio[0].id, batch_key="legacy-test")
    db.add(marker); db.commit()
    stale = client.put(base, json=payload("pms", expected_version=version, expected_status="Active"), headers=headers)
    assert stale.status_code == 409, stale.text
    db.refresh(marker)
    assert marker.deleted_at is not None
    current = client.get(base, headers=headers)
    assert current.status_code == 200 and current.json()["status"] == "Archived"
    restored = client.post(f"/api/v1/project-management/admin/workspaces/{wid}/restore", headers=headers)
    assert restored.status_code == 200, restored.text
    assert client.get(base, headers=headers).json()["status"] == "Active"


def test_pms_native_activity_preserves_manage_permission(client, db, studio):
    from app.apps.project_management.models import PMSActivity, PMSWorkspaceMember
    from app.models.user import Role, Permission
    owner, _, reader, headers, _, reader_headers, project, *_ = studio
    permission = db.query(Permission).filter_by(name="pms_view").first()
    if permission is None:
        permission = Permission(name="pms_view", description="View projects", module="project_management")
        db.add(permission); db.flush()
    role = Role(name="workspace_test_pms_reader", permissions=[permission])
    db.add(role); db.flush(); reader.role = role
    wid = project["workspace_id"]
    db.add(PMSWorkspaceMember(workspace_id=wid, user_id=reader.id, role="Member"))
    db.add(PMSActivity(project_id=project["id"], actor_user_id=owner.id, action="updated", entity_type="project", entity_id=project["id"], summary="Native owner activity"))
    db.commit()
    base = f"/api/v1/project-management/workspace-directory/{wid}/activity"
    owner_result = client.get(base, headers=headers)
    assert owner_result.status_code == 200, owner_result.text
    assert any(event["summary"] == "Native owner activity" for event in owner_result.json())
    reader_result = client.get(base, headers=reader_headers)
    assert reader_result.status_code == 200, reader_result.text
    assert not any(event["summary"] == "Native owner activity" for event in reader_result.json())

def test_read_only_branch_hides_mutations_and_rejects_writes(client, db, studio):
    from app.models.user import Role, Permission
    from app.branches.models import BranchGrant
    actor, headers = studio[2], studio[5]
    permissions = []
    for name in ("crm_view", "crm_manage"):
        permission = db.query(Permission).filter_by(name=name).first()
        if permission is None:
            permission = Permission(name=name, description=name, module="crm"); db.add(permission); db.flush()
        permissions.append(permission)
    role = Role(name="workspace_test_crm_manager", permissions=permissions)
    db.add(role); db.flush(); actor.role = role; db.commit()
    base = "/api/v1/crm/workspace-directory"
    created = client.post(base, json=payload("crm"), headers=headers)
    assert created.status_code == 201, created.text
    row = created.json()
    grant = db.query(BranchGrant).filter_by(user_id=actor.id, company_id=1, branch_id=int(headers["X-Suite-Branch"])).one()
    grant.can_write = False; db.commit()
    response = client.get(base, headers=headers)
    assert response.status_code == 200, response.text
    assert not response.json()["can_create"]
    current = next(item for item in response.json()["items"] if item["id"] == row["id"])
    assert not current["can_manage"] and not current["can_archive"]
    assert client.put(base + "/" + row["id"], json=payload("crm", expected_version=row["version"]), headers=headers).status_code == 403


def test_workspace_admin_cannot_promote_or_remove_administrators(client, db, studio):
    from app.models.user import Role, Permission
    actor, actor_headers = studio[2], studio[5]
    permission = db.query(Permission).filter_by(name="crm_manage").first()
    if permission is None:
        permission = Permission(name="crm_manage", description="Manage CRM", module="crm"); db.add(permission); db.flush()
    role = Role(name="workspace_test_delegated_admin", permissions=[permission])
    db.add(role); db.flush(); actor.role = role; db.commit()
    base = "/api/v1/crm/workspace-directory"
    created = client.post(base, json=payload("crm", members=[{"user_id": actor.id, "role": "Admin"}]), headers=studio[3])
    assert created.status_code == 201, created.text
    row = created.json()
    denied = client.put(base + "/" + row["id"], json=payload("crm", expected_version=row["version"], members=[]), headers=actor_headers)
    assert denied.status_code == 403, denied.text
    assert client.get(base + "/" + row["id"], headers=actor_headers).json()["can_manage"]
