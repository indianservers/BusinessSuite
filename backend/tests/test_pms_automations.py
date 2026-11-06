from tests.rich_text_test_utils import organization_context
from tests.test_pms_workspaces import account, middleware_database, BASE
from app.apps.project_management.models import PMSWorkspaceMember
import pytest


def setup_workspace(client, db):
    owner, oh = account(db, "auto-owner@test.com", True)
    admin, ah = account(db, "auto-admin@test.com")
    member, mh = account(db, "auto-member@test.com")
    guest, gh = account(db, "auto-guest@test.com")
    wid = client.post(BASE + "/workspaces", json={"name": "Automation"}, headers=oh).json()["id"]
    memberships=[PMSWorkspaceMember(workspace_id=wid, user_id=admin.id, role="Admin"), PMSWorkspaceMember(workspace_id=wid, user_id=member.id, role="Member"), PMSWorkspaceMember(workspace_id=wid, user_id=guest.id, role="Guest")]
    db.add_all(memberships)
    from test_identity_utils import own_workflow_records
    own_workflow_records(db, *memberships)
    db.commit()
    pid = client.post(BASE + "/projects", json={"name": "Rules", "project_key": "AUTO", "workspace_id": wid}, headers=oh).json()["id"]
    return wid, pid, owner, oh, ah, member, mh, guest, gh


def test_compound_conditions_reuse_shared_runtime(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    conditions = {"all": [{"field": "work_type", "operator": "equals", "value": "Bug"},
        {"any": [{"field": "title", "operator": "contains", "value": "outage"},
                 {"field": "priority", "operator": "in", "value": ["High", "Urgent"]}]}]}
    path = f"{BASE}/workspaces/{wid}/automations"
    response = client.post(path, headers=oh, json={"name": "Critical bugs", "project_id": pid,
        "trigger": "task.created", "action": "set_priority", "priority": "Urgent", "conditions": conditions})
    assert response.status_code == 201, response.text
    assert client.get(path, headers=oh).json()[0]["conditions"] == conditions
    for key, work_type, title, priority, expected in [
        ("MATCH-TEXT", "Bug", "Service OUTAGE", "Low", "Urgent"),
        ("MATCH-PRIO", "Bug", "Broken", "High", "Urgent"),
        ("MISS-OR", "Bug", "Cosmetic", "Low", "Low"),
        ("MISS-AND", "Task", "Service outage", "Low", "Low")]:
        task = client.post(f"{BASE}/projects/{pid}/tasks", headers=mh,
            json={"task_key": key, "title": title, "work_type": work_type, "priority": priority})
        assert task.status_code == 200, task.text
        assert task.json()["priority"] == expected
    assert len(client.get(f"{BASE}/workspaces/{wid}/automation-runs", headers=oh).json()) == 2


@pytest.mark.parametrize("condition", [
    {"all": []}, {"field": "organization_id", "value": 2},
    {"field": "title", "operator": "in", "value": "wrong"},
    {"field": "priority", "operator": "date_before", "value": "2026-11-07"},
    {"field": "title", "operator": "equals", "value": {"script": "no"}},
])
def test_invalid_compound_conditions_fail_before_saving(client, db, condition):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    result = client.post(f"{BASE}/workspaces/{wid}/automations", headers=oh,
        json={"name": "Invalid", "project_id": pid, "trigger": "task.created", "action": "set_priority", "conditions": condition})
    assert result.status_code in (400, 422), result.text
    assert client.get(f"{BASE}/workspaces/{wid}/automations", headers=oh).json() == []


def test_automation_executes_persists_and_enforces_roles(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = f"{BASE}/workspaces/{wid}/automations"
    payload = {"name": "New tasks high", "project_id": pid, "trigger": "task.created", "action": "set_priority", "priority": "High"}
    for headers in [mh, gh]:
        assert client.get(path, headers=headers).status_code == 403
        assert client.post(path, headers=headers, json=payload).status_code == 403
    rule = client.post(path, headers=ah, json=payload)
    assert rule.status_code == 201, rule.text
    rid = rule.json()["id"]
    assert client.get(path, headers=oh).json()[0]["name"] == payload["name"]
    task = client.post(f"{BASE}/projects/{pid}/tasks", headers=mh, json={"task_key": "AUTO-1", "title": "Created by member", "priority": "Low"})
    assert task.status_code == 200, task.text
    assert task.json()["priority"] == "High"
    runs = client.get(f"{BASE}/workspaces/{wid}/automation-runs", headers=oh).json()
    assert len(runs) == 1 and runs[0]["task_id"] == task.json()["id"]
    assert client.patch(path + f"/{rid}", headers=mh, json={"enabled": False}).status_code == 403
    assert client.patch(path + f"/{rid}", headers=ah, json={"enabled": False}).status_code == 200
    task2 = client.post(f"{BASE}/projects/{pid}/tasks", headers=mh, json={"task_key": "AUTO-2", "title": "Paused rule", "priority": "Low"})
    assert task2.json()["priority"] == "Low"
    assert client.post(f"{BASE}/projects/{pid}/tasks", headers=gh, json={"task_key": "AUTO-NO", "title": "Denied"}).status_code == 403


def test_status_rule_assignment_scope_and_idempotency(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = f"{BASE}/workspaces/{wid}/automations"
    payload = {"name": "Review collaborator", "project_id": pid, "trigger": "task.status_changed", "status": "In Review", "action": "assign_user", "assignee_id": member.id}
    assert client.post(path, headers=oh, json={**payload, "assignee_id": guest.id}).status_code == 422
    other = client.post(BASE + "/workspaces", headers=oh, json={"name": "Other"}).json()["id"]
    assert client.post(f"{BASE}/workspaces/{other}/automations", headers=oh, json=payload).status_code == 404
    rule = client.post(path, headers=oh, json=payload).json()
    assert client.patch(f"{BASE}/workspaces/{other}/automations/{rule['id']}", headers=oh, json={"enabled": False}).status_code == 404
    task = client.post(f"{BASE}/projects/{pid}/tasks", headers=mh, json={"task_key": "AUTO-3", "title": "Review", "assignee_user_ids": [owner.id]}).json()
    url = f"{BASE}/tasks/{task['id']}"
    unchanged = client.patch(url, headers=mh, json={"status": "In Progress"}).json()
    assert unchanged["assignee_user_ids"] == [owner.id]
    updated = client.patch(url, headers=mh, json={"status": "In Review"})
    assert set(updated.json()["assignee_user_ids"]) == {owner.id, member.id}, updated.text
    client.patch(url, headers=mh, json={"status": "In Review"})
    runs = client.get(f"{BASE}/workspaces/{wid}/automation-runs", headers=oh).json()
    assert len(runs) == 1


def test_rule_edits_preserve_scope_and_paused_state(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = f"{BASE}/workspaces/{wid}/automations"
    payload = {"name": "Priority rule", "project_id": pid, "trigger": "task.created", "action": "set_priority", "priority": "High", "enabled": False}
    rid = client.post(path, headers=oh, json=payload).json()["id"]
    assert client.put(path + f"/{rid}", headers=mh, json=payload).status_code == 403
    response = client.put(path + f"/{rid}", headers=ah, json={**payload, "priority": "Urgent"})
    assert response.status_code == 200
    assert response.json()["priority"] == "Urgent" and response.json()["enabled"] is False
    assert client.get(path, headers=oh).json()[0]["priority"] == "Urgent"
