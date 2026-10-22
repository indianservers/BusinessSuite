from tests.test_pms_workspaces import account, middleware_database, BASE


def test_shared_assignment_roundtrip_access_filters_and_workload(client, db):
    from app.apps.project_management.models import PMSWorkspaceMember
    owner, headers = account(db, "shared-owner@test.com", True)
    member, mh = account(db, "shared-member@test.com")
    guest, _ = account(db, "shared-guest@test.com")
    wid = client.post(BASE + "/workspaces", json={"name": "Shared work"}, headers=headers).json()["id"]
    db.add_all([PMSWorkspaceMember(workspace_id=wid, user_id=member.id, role="Member"), PMSWorkspaceMember(workspace_id=wid, user_id=guest.id, role="Guest")])
    db.commit()
    project = client.post(BASE + "/projects", json={"name": "Shared", "project_key": "SHARED", "workspace_id": wid}, headers=headers).json()
    pid = project["id"]
    people = client.get(BASE + "/users/search", params={"projectId": pid}, headers=headers).json()
    assert {p["id"] for p in people} == {owner.id, member.id}
    payload = {"title": "Shared task", "task_key": "SHARED-1", "assignee_user_ids": [member.id, owner.id, member.id], "estimated_hours": 16, "start_date": "2026-10-19", "due_date": "2026-10-23"}
    response = client.post(f"{BASE}/projects/{pid}/tasks", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    task = response.json()
    assert set(task["assignee_user_ids"]) == {owner.id, member.id}
    tid = task["id"]
    overview = client.get(f"{BASE}/workspaces/{wid}/overview", headers=mh).json()
    assert set(overview["tasks"][0]["assignee_user_ids"]) == {owner.id, member.id}
    filtered = client.get(f"{BASE}/projects/{pid}/tasks", params={"assignee_id": member.id}, headers=mh)
    assert any(t["id"] == tid for t in filtered.json())
    workload = client.get(BASE + "/workload", params={"projectId": pid, "from": "2026-10-19", "to": "2026-10-25"}, headers=headers)
    assert workload.status_code == 200, workload.text
    assert sorted(r["totals"]["planned_hours"] for r in workload.json()["rows"]) == [8, 8]
    denied = client.patch(f"{BASE}/tasks/{tid}", json={"assignee_user_ids": [guest.id]}, headers=headers)
    assert denied.status_code == 422
    assert client.patch(f"{BASE}/tasks/{tid}", json={"assignee_user_ids": []}, headers=headers).json()["assignee_user_ids"] == []
    legacy = client.patch(f"{BASE}/tasks/{tid}", json={"assignee_user_id": member.id}, headers=headers).json()
    assert legacy["assignee_user_ids"] == [member.id]
    sibling = client.post(f"{BASE}/projects/{pid}/tasks", json={"title": "Follow-up", "task_key": "SHARED-2", "start_date": "2026-10-26", "due_date": "2026-10-27"}, headers=headers).json()
    edge = {"source_task_id": tid, "target_task_id": sibling["id"], "dependency_type": "Finish To Start"}
    dependency = client.post(BASE + "/task-dependencies", json=edge, headers=headers)
    assert dependency.status_code == 201, dependency.text
    assert client.post(BASE + "/task-dependencies", json={**edge, "source_task_id": sibling["id"], "target_task_id": tid}, headers=headers).status_code == 400
    gantt = client.get(BASE + "/gantt", params={"projectId": pid, "assigneeId": member.id}, headers=mh).json()
    assert any(t["id"] == tid for t in gantt["tasks"])
    assert gantt["filters"]["projects"][0]["can_manage_tasks"] is True
    assert client.delete(BASE + f"/task-dependencies/{dependency.json()['id']}", headers=headers).status_code == 200
    assert client.patch(f"{BASE}/tasks/{tid}", json={"start_date": "2026-11-01"}, headers=headers).status_code == 422
    client.patch(f"{BASE}/tasks/{tid}", json={"assignee_user_ids": [owner.id, member.id]}, headers=headers)
    membership = db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, user_id=member.id).one()
    assert client.patch(f"{BASE}/workspaces/{wid}/members/{membership.id}", json={"role": "Guest"}, headers=headers).status_code == 200
    assert client.get(f"{BASE}/tasks/{tid}", headers=headers).json()["assignee_user_ids"] == [owner.id]
