from tests.rich_text_test_utils import organization_context
from tests.test_pms_workspaces import account, middleware_database, BASE
from tests.test_pms_automations import setup_workspace
from app.apps.project_management.models import PMSTask


def test_project_trash_restore_permissions_and_children(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    outsider, xh = account(db, "trash-outsider@test.com", True)
    project_url = f"{BASE}/projects/{pid}"
    task = client.post(project_url + "/tasks", headers=oh, json={"title":"Keep child", "task_key":"KEEP-1"})
    assert task.status_code == 200, task.text
    tid = task.json()["id"]
    for headers in (mh, gh):
        row = next(p for p in client.get(BASE+"/projects", headers=headers).json() if p["id"] == pid)
        assert row["can_edit_project"] is False
        assert client.delete(project_url, headers=headers).status_code == 403
    row = next(p for p in client.get(BASE+"/projects", headers=oh).json() if p["id"] == pid)
    assert row["can_edit_project"] is True
    assert client.delete(project_url, headers=oh).status_code == 200
    assert client.get(project_url, headers=oh).status_code == 404
    assert not any(p["id"]==pid for p in client.get(BASE+"/projects", headers=oh).json())
    recovery = f"{BASE}/trash/projects/{pid}/restore"
    assert client.get(BASE+"/trash/projects", headers=xh).json() == []
    assert client.post(recovery, headers=xh).status_code == 404
    for headers in (mh, gh):
        row = next(p for p in client.get(BASE+"/trash/projects", headers=headers).json() if p["id"]==pid)
        assert row["can_restore"] is False
        assert client.post(recovery, headers=headers).status_code == 403
    assert client.post(recovery, headers=ah).status_code == 200
    assert client.post(recovery, headers=oh).status_code == 404
    assert client.get(project_url, headers=oh).status_code == 200
    assert client.get(f"{BASE}/tasks/{tid}", headers=mh).status_code == 200
    assert db.get(PMSTask, tid).deleted_at is None


def test_dashboard_storage_markers_fit_existing_postgres_column():
    from app.apps.project_management.dashboards import KIND, HISTORY, PREFERENCES
    from app.apps.project_management.models import PMSWorkspaceEntry
    limit = PMSWorkspaceEntry.__table__.c.kind.type.length
    assert all(len(kind) <= limit for kind in (KIND, HISTORY, PREFERENCES))
