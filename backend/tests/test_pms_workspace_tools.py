from tests.rich_text_test_utils import organization_context
from uuid import uuid4
from tests.test_pms_automations import setup_workspace
from tests.test_pms_workspaces import middleware_database, BASE


def test_templates_intake_goals_persist_scope_and_permissions(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = f"{BASE}/workspaces/{wid}/tools"
    template = {"kind": "template", "name": "Release checklist", "project_id": pid, "task_titles": ["Review", "Release"]}
    for headers in [mh, gh]:
        assert client.post(path, headers=headers, json=template).status_code == 403
    response = client.post(path, headers=ah, json=template)
    assert response.status_code == 201, response.text
    tid = response.json()["id"]
    apply_path = path + f"/{tid}/apply"
    body = {"request_id": str(uuid4())}
    assert client.post(apply_path, headers=gh, json=body).status_code == 403
    applied = client.post(apply_path, headers=mh, json=body)
    assert applied.status_code == 200, applied.text
    ids = applied.json()["task_ids"]
    assert len(ids) == 2
    replayed = client.post(apply_path, headers=mh, json=body).json()
    assert replayed["task_ids"] == ids and replayed["replayed"] is True
    tasks = [client.get(f"{BASE}/tasks/{task_id}", headers=mh).json() for task_id in ids]
    assert [task["title"] for task in tasks] == ["Review", "Release"]
    assert all(task["board_id"] and task["column_id"] for task in tasks)
    goal = client.post(path, headers=oh, json={"kind": "goal", "name": "Ship", "project_id": pid, "task_ids": ids})
    assert goal.status_code == 201, goal.text
    assert goal.json()["progress"] == 0
    client.patch(f"{BASE}/tasks/{ids[0]}", headers=mh, json={"status": "Done"})
    saved = client.get(path, headers=gh).json()
    assert next(row for row in saved if row["kind"] == "goal")["progress"] == 50
    intake = client.post(path, headers=oh, json={"kind": "intake", "name": "Support request", "project_id": pid, "description": "Explain what you need"}).json()
    request = client.post(path + f"/{intake['id']}/apply", headers=mh, json={"request_id": str(uuid4()), "title": "Need a review", "description": "Detailed request"})
    assert request.status_code == 200, request.text
    task = client.get(f"{BASE}/tasks/{request.json()['task_ids'][0]}", headers=mh).json()
    assert task["title"] == "Need a review" and task["description"] == "Detailed request"
    assert client.patch(path + f"/{tid}", headers=mh, json={"enabled": False}).status_code == 403
    client.patch(path + f"/{tid}", headers=ah, json={"enabled": False})
    assert client.post(apply_path, headers=mh, json={"request_id": str(uuid4())}).status_code == 422
    other = client.post(BASE + "/workspaces", headers=oh, json={"name": "Other"}).json()["id"]
    assert client.post(f"{BASE}/workspaces/{other}/tools", headers=oh, json=template).status_code == 404
    assert client.post(f"{BASE}/workspaces/{other}/tools/{tid}/apply", headers=oh, json={"request_id": str(uuid4())}).status_code == 404


def test_tool_validation_and_no_partial_template(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = f"{BASE}/workspaces/{wid}/tools"
    for data in [{"kind": "template", "task_titles": []}, {"kind": "template", "task_titles": ["ok", " "]}, {"kind": "goal", "task_ids": [999999]}]:
        response = client.post(path, headers=oh, json={"name": "Invalid", "project_id": pid, **data})
        assert response.status_code == 422, response.text
    assert client.get(path, headers=oh).json() == []
