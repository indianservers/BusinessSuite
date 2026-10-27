from tests.rich_text_test_utils import organization_context
from uuid import uuid4
from tests.test_pms_automations import setup_workspace as base_setup_workspace
from tests.test_pms_workspaces import middleware_database, BASE


def setup_workspace(client, db):
    from app.access.models import AccessMembership
    from app.apps.project_management.models import PMSWorkspaceMember

    result = base_setup_workspace(client, db)
    # Workflow participants also need verified company membership under the tenant boundary.
    for membership in db.query(PMSWorkspaceMember).filter_by(workspace_id=result[0]).all():
        db.add(AccessMembership(user_id=membership.user_id, company_id=1, active=True))
    db.commit()
    return result


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


def test_blueprints_customized_runs_permissions_and_retry(client, db):
    from app.apps.project_management.models import PMSTask
    from tests.test_pms_workspaces import account

    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = f"{BASE}/workspaces/{wid}/blueprints/apply"
    body = {"request_id": str(uuid4()), "name": "October onboarding", "project_id": pid,
            "description": "Complete access checks with the team buddy", "task_titles": [" Prepare approved accounts ", "Meet the buddy"]}
    _, outsider_headers = account(db, "blueprint-outsider@test.com", True)
    assert client.post(path, headers=gh, json=body).status_code == 403
    assert client.post(path, headers=outsider_headers, json=body).status_code == 404
    for titles in [[], ["ok", " "], ["x" * 221], ["step"] * 21]:
        assert client.post(path, headers=mh, json={**body, "task_titles": titles}).status_code == 422
    assert db.query(PMSTask).filter_by(project_id=pid).count() == 0
    result = client.post(path, headers=mh, json=body)
    assert result.status_code == 200, result.text
    ids = result.json()["task_ids"]
    tasks = [client.get(f"{BASE}/tasks/{task_id}", headers=mh).json() for task_id in ids]
    assert [task["title"] for task in tasks] == ["Prepare approved accounts", "Meet the buddy"]
    assert all(task["description"] == body["description"] and task["board_id"] and task["column_id"] for task in tasks)
    replay = client.post(path, headers=mh, json=body)
    assert replay.json() == {"task_ids": ids, "replayed": True}
    assert db.query(PMSTask).filter_by(project_id=pid).count() == 2
    assert client.get(f"{BASE}/workspaces/{wid}/tools", headers=mh).json() == []
    other = client.post(BASE + "/workspaces", headers=oh, json={"name": "Other blueprint workspace"}).json()["id"]
    assert client.post(f"{BASE}/workspaces/{other}/blueprints/apply", headers=oh, json=body).status_code == 404


def test_saved_blueprint_edit_and_single_run_override(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = f"{BASE}/workspaces/{wid}/tools"
    template = client.post(path, headers=oh, json={"kind": "template", "name": "Original", "project_id": pid,
                                                "description": "Original instructions", "task_titles": ["Original step"]}).json()
    url = path + f"/{template['id']}"
    changes = {"name": "Updated playbook", "description": "New instructions", "task_titles": [" Updated step ", "Review outcome"]}
    for headers in [mh, gh]:
        assert client.patch(url, headers=headers, json=changes).status_code == 403
    for change in [{"name": " "}, {"task_titles": []}, {"task_titles": [" "]}, {"task_titles": ["x" * 221]}, {"enabled": None}, {}]:
        assert client.patch(url, headers=oh, json=change).status_code == 422
    updated = client.patch(url, headers=ah, json=changes)
    assert updated.status_code == 200, updated.text
    assert updated.json()["task_titles"] == ["Updated step", "Review outcome"]
    result = client.post(url + "/apply", headers=mh, json={"request_id": str(uuid4()), "task_titles": ["This run only"], "description": "One-time instructions"})
    assert result.status_code == 200, result.text
    task = client.get(f"{BASE}/tasks/{result.json()['task_ids'][0]}", headers=mh).json()
    assert task["title"] == "This run only" and task["description"] == "One-time instructions"
    saved = client.get(path, headers=mh).json()[0]
    assert saved["name"] == changes["name"] and saved["task_titles"] == ["Updated step", "Review outcome"]
    normal = client.post(url + "/apply", headers=mh, json={"request_id": str(uuid4())})
    assert len(normal.json()["task_ids"]) == 2
    original_task = client.get(f"{BASE}/tasks/{normal.json()['task_ids'][0]}", headers=mh).json()
    assert original_task["description"] == "New instructions"
    cleared = client.post(url + "/apply", headers=mh, json={"request_id": str(uuid4()), "task_titles": ["No instructions this time"], "description": ""})
    assert cleared.status_code == 200, cleared.text
    assert client.get(f"{BASE}/tasks/{cleared.json()['task_ids'][0]}", headers=mh).json()["description"] == ""
    intake = client.post(path, headers=oh, json={"kind": "intake", "name": "Request", "project_id": pid}).json()
    assert client.patch(path + f"/{intake['id']}", headers=oh, json=changes).status_code == 422
    assert client.post(path + f"/{intake['id']}/apply", headers=mh, json={"request_id": str(uuid4()), "title": "Request", "task_titles": ["Invalid override"]}).status_code == 422
