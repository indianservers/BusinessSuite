from tests.test_pms_automations import setup_workspace
from tests.test_pms_workspaces import middleware_database, BASE, account
from app.apps.project_management.models import PMSWorkspace, PMSWorkspaceEntry


def test_private_dashboard_owner_cas_trash_restore_and_feed(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = BASE + "/dashboards"
    payload = {"workspace_id": wid, "name": "Private dashboard", "visibility": "private"}
    assert client.post(path, headers=gh, json=payload).status_code == 403
    assert client.post(path, headers=oh, json={**payload, "name": "   "}).status_code == 422
    made = client.post(path, headers=oh, json=payload)
    assert made.status_code == 201, made.text
    data = made.json()
    url = path + f"/{data['id']}"
    assert client.get(url, headers=mh).status_code == 404
    assert client.get(path, headers=mh).json() == []
    feed = client.get(f"{BASE}/workspaces/{wid}/entries", headers=mh).json()
    assert not any(x["kind"] == "dashboard_v1" for x in feed)
    edit = {"name": "Renamed", "description": "new", "visibility": "private", "revision": 1}
    assert client.put(url, headers=oh, json=edit).status_code == 200
    assert client.put(url, headers=oh, json=edit).status_code == 409
    assert client.post(url + "/trash", headers=oh, json={"revision": 2}).status_code == 200
    assert client.get(url, headers=oh).status_code == 404
    assert db.get(PMSWorkspaceEntry, data['id']) is not None
    assert client.post(url + "/restore", headers=mh, json={"revision": 3}).status_code == 404
    assert client.post(url + "/restore", headers=oh, json={"revision": 3}).status_code == 200
    assert client.get(url, headers=oh).json()["name"] == "Renamed"
    assert client.post(path, headers=oh, json={**payload, "visibility": "organization"}).status_code == 201


def test_org_shared_visibility_cross_org_and_owner_only(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    outsider, xh = account(db, "other-org@example.invalid", True)
    from tests.tenant_test_utils import assign_company
    assign_company(db, owner, 77)
    assign_company(db, member, 77)
    assign_company(db, outsider, 88)
    db.get(PMSWorkspace, wid).organization_id = 77
    db.commit()
    payload = {"workspace_id": wid, "name": "Shared", "visibility": "organization"}
    created = client.post(BASE + "/dashboards", headers=oh, json=payload)
    assert created.status_code == 201, created.text
    data = created.json()
    url = BASE + f"/dashboards/{data['id']}"
    assert client.get(url, headers=mh).status_code == 200
    assert client.get(url, headers=xh).status_code == 404
    assert client.get(BASE + "/dashboards", headers=xh).json() == []
    assert client.post(url + "/trash", headers=mh, json={"revision": 1}).status_code == 403
    saved = client.put(url, headers=oh, json={"name":"Shared", "visibility":"private", "revision":1})
    assert saved.status_code == 200
    assert client.get(url, headers=mh).status_code == 404
