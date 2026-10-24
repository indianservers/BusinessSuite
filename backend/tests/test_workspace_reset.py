import pytest
from tests.test_pms_automations import setup_workspace
from tests.test_pms_workspaces import middleware_database, BASE
from tests.test_pms_recovery import isolated_audit
from app.apps.project_management.models import (
    PMSWorkspace,
    PMSWorkspaceMember,
    PMSProject,
    PMSTask,
)
from app.apps.project_management.workspace_lifecycle import WorkspaceArchive
from app.models.user import Permission, Role


def make_user_workspace(client, db, member, headers):
    role = Role(name="reset-workspace-creator")
    permission = Permission(name="pms_manage_projects", module="project_management")
    db.add_all([role, permission])
    db.flush()
    role.permissions.append(permission)
    member.role_id = role.id
    db.commit()
    response = client.post(
        BASE + "/workspaces", headers=headers, json={"name": "Created by user"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_reset_includes_admin_and_user_created_workspaces_and_preserves_data(
    client, db
):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    user_workspace = make_user_workspace(client, db, member, mh)
    foreign = PMSWorkspace(name="Other organization", organization_id=2)
    db.add(foreign)
    db.commit()
    task = client.post(
        f"{BASE}/projects/{pid}/tasks",
        headers=oh,
        json={"title": "Keep me", "task_key": "RESET-1"},
    )
    assert task.status_code == 200, task.text
    tid = task.json()["id"]
    membership_count = db.query(PMSWorkspaceMember).count()
    path = BASE + "/admin/workspaces"
    preview = client.get(path, headers=oh)
    assert preview.status_code == 200, preview.text
    assert {row["id"] for row in preview.json()["items"]} == {wid, user_workspace}
    assert preview.json()["active_count"] == 2
    for headers in (mh, ah, gh):
        assert client.get(path, headers=headers).status_code == 403
        assert (
            client.post(
                path + "/reset-all",
                headers=headers,
                json={
                    "confirmation": "RESET ALL WORKSPACES",
                    "preview_hash": preview.json()["preview_hash"],
                },
            ).status_code
            == 403
        )
    response = client.post(
        path + "/reset-all",
        headers=oh,
        json={
            "confirmation": "RESET ALL WORKSPACES",
            "preview_hash": preview.json()["preview_hash"],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["soft_deleted"] == 2 and response.json()["restorable"]
    assert client.get(BASE + "/workspaces", headers=oh).json() == []
    assert client.get(BASE + "/workspaces", headers=mh).json() == []
    assert (
        client.get(f"{BASE}/workspaces/{wid}/overview", headers=oh).status_code == 404
    )
    assert client.get(f"{BASE}/tasks/{tid}", headers=oh).status_code == 403
    assert not db.get(WorkspaceArchive, foreign.id)
    assert db.get(PMSTask, tid).deleted_at is None
    assert db.get(PMSProject, pid).deleted_at is None
    assert db.query(PMSWorkspaceMember).count() == membership_count
    assert client.post(path + f"/{wid}/restore", headers=mh).status_code == 403
    assert client.post(path + f"/{foreign.id}/restore", headers=oh).status_code == 404
    restored = client.post(path + f"/{wid}/restore", headers=oh)
    assert restored.status_code == 200, restored.text
    assert client.get(f"{BASE}/tasks/{tid}", headers=mh).json()["title"] == "Keep me"
    assert {
        row["id"] for row in client.get(BASE + "/workspaces", headers=mh).json()
    } == {wid}
    assert db.query(PMSWorkspaceMember).count() == membership_count


def test_stale_preview_and_confirmation_are_required(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = BASE + "/admin/workspaces"
    preview = client.get(path, headers=oh).json()
    body = {"confirmation": "wrong", "preview_hash": preview["preview_hash"]}
    assert client.post(path + "/reset-all", headers=oh, json=body).status_code == 422
    client.post(BASE + "/workspaces", headers=oh, json={"name": "New since preview"})
    body["confirmation"] = "RESET ALL WORKSPACES"
    assert client.post(path + "/reset-all", headers=oh, json=body).status_code == 409
    assert db.query(WorkspaceArchive).count() == 0
