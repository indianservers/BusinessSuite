from tests.rich_text_test_utils import organization_context
from tests.test_pms_workspaces import middleware_database, BASE
from tests.test_pms_automations import setup_workspace
from tests.test_pms_workflow_schemes import task


def test_work_type_override_fallback_and_bypass_protection(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    policy = {"revision": 0, "enabled": True, "transitions": [{"source": "To Do", "target": "Done"}],
              "work_type_transitions": {"Bug": [{"source": "To Do", "target": "In Review"}]}}
    path = f"{BASE}/projects/{pid}/workflow-scheme"
    saved = client.put(path, headers=oh, json=policy)
    assert saved.status_code == 200, saved.text
    normal = task(client, pid, mh, "NORMAL")
    bug = task(client, pid, mh, "BUG")
    url = f"{BASE}/tasks/{bug}"
    assert client.patch(url, headers=mh, json={"work_type": "Bug"}).status_code == 200
    assert client.patch(url, headers=mh, json={"status": "Done"}).status_code == 409
    assert client.patch(f"{BASE}/tasks/{normal}", headers=mh, json={"status": "Done"}).status_code == 200
    assert client.patch(url, headers=mh, json={"work_type": "Task", "status": "Done"}).status_code == 409
    assert client.patch(url, headers=mh, json={"status": "In Review"}).status_code == 200
    assert client.patch(url, headers=mh, json={"work_type": "Task"}).status_code == 409
    assert client.get(path, headers=gh).json()["work_type_transitions"] == saved.json()["work_type_transitions"]


def test_work_type_scopes_validate_registered_types_and_each_graph(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = f"{BASE}/projects/{pid}/workflow-scheme"
    base = {"revision": 0, "enabled": True, "transitions": [{"source": "To Do", "target": "Done"}]}
    for scopes in [{"Invented": base["transitions"]}, {"Bug": []},
                   {"Bug": [{"source": "Done", "target": "Done"}]}, {"Bug": base["transitions"]*2}]:
        assert client.put(path, headers=oh, json={**base, "work_type_transitions": scopes}).status_code == 422
    created = client.post(BASE+"/task-types", headers=oh, json={"name": "Security review"})
    assert created.status_code == 201, created.text
    result = client.put(path, headers=oh, json={**base, "work_type_transitions": {"Security review": base["transitions"]}})
    assert result.status_code == 200, result.text
