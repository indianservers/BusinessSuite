from uuid import uuid4
from fastapi.testclient import TestClient
from tests.test_pms_automations import setup_workspace
from tests.test_pms_workspaces import middleware_database, BASE
from app.apps.project_management.models import PMSTask, PMSWorkspaceEntry


def definition(pid=None):
    return {"name": "Support intake", "fields": [
        {"id": "title", "type": "text", "label": "Request title", "required": True},
        {"id": "kind", "type": "select", "label": "Category", "options": ["Bug", "Other"]},
        {"id": "detail", "type": "textarea", "label": "Bug detail", "required": True, "condition": {"field": "kind", "value": "Bug"}},
        {"id": "email", "type": "email", "label": "Email"}],
        "workflow": {"enabled": bool(pid), "project_id": pid, "title_field": "title", "priority": "Medium", "due_days": 2}}


def publish(client, path, headers, d):
    result = client.post(path, headers=headers, json=d)
    assert result.status_code == 201, result.text
    form = result.json()
    saved = client.put(path + f"/{form['id']}", headers=headers, json={"revision": form["revision"], "definition": d, "publish": True})
    assert saved.status_code == 200, saved.text
    return saved.json()


def test_forms_publish_workflow_validation_replay_and_exports(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = f"{BASE}/workspaces/{wid}/forms"
    d = definition(pid)
    d["workflow"]["assignee_id"] = member.id
    client.post(f"{BASE}/workspaces/{wid}/automations", headers=oh, json={"name": "Escalate", "project_id": pid, "trigger": "task.created", "action": "set_priority", "priority": "High"})
    form = publish(client, path, ah, d)
    url = path + f"/{form['id']}"
    body = {"request_id": str(uuid4()), "version": 1, "answers": {"title": "=DANGER()", "kind": "Other", "detail": "hidden injection", "email": "person@example.com"}}
    for answers in [{"title": "x", "kind": "Bug"}, {"title": "x", "email": "bad"}, {"title": "x", "unknown": "bad"}]:
        assert client.post(url + "/submit", headers=mh, json={**body, "answers": answers}).status_code == 422
    result = client.post(url + "/submit", headers=mh, json=body)
    assert result.status_code == 201, result.text
    replay = client.post(url + "/submit", headers=mh, json=body)
    assert replay.json()["replayed"] is True
    assert replay.json()["task_id"] == result.json()["task_id"]
    task = db.get(PMSTask, result.json()["task_id"])
    assert task.priority == "High" and task.assignee_user_ids == [member.id]
    assert task.due_date and "hidden injection" not in task.description and len(task.task_key) <= 30
    rows = client.get(url + "/responses", headers=oh).json()
    assert rows["total"] == 1 and "detail" not in rows["items"][0]["answers"]
    exported = client.get(url + "/export?format=csv", headers=ah)
    assert exported.status_code == 200 and "'=DANGER()" in exported.text
    assert "attachment" in exported.headers["content-disposition"]
    assert len(client.get(url + "/export?format=json", headers=ah).json()) == 1
    assert client.get(url + "/responses?limit=101", headers=oh).status_code == 422
    assert client.get(path, headers=mh).json()[0]["definition"]["name"] == d["name"]
    assert "draft" not in client.get(path, headers=mh).json()[0]


def test_forms_roles_workspace_boundaries_and_versions(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = f"{BASE}/workspaces/{wid}/forms"
    for h in [mh, gh]:
        assert client.post(path, headers=h, json=definition()).status_code == 403
    draft = client.post(path, headers=oh, json=definition()).json()
    assert client.get(path, headers=mh).json() == []
    url = path + f"/{draft['id']}"
    for suffix in ["/responses", "/export"]:
        assert client.get(url + suffix, headers=mh).status_code == 403
    d = definition()
    published = client.put(url, headers=oh, json={"revision": 1, "definition": d, "publish": True}).json()
    assert client.put(url, headers=oh, json={"revision": 1, "definition": d}).status_code == 409
    d["name"] = "Draft edits"
    saved = client.put(url, headers=oh, json={"revision": published["revision"], "definition": d}).json()
    assert saved["published"]["name"] == "Support intake" and saved["draft"]["name"] == "Draft edits"
    body = {"request_id": str(uuid4()), "version": 1, "answers": {"title": "Hello"}}
    assert client.post(url + "/submit", headers=gh, json=body).status_code == 403
    assert client.post(url + "/submit", json=body).status_code in [401, 403]
    changed = client.put(url, headers=oh, json={"revision": saved["revision"], "definition": d, "publish": True}).json()
    assert client.post(url + "/submit", headers=mh, json=body).status_code == 409
    closed = client.put(url, headers=oh, json={"revision": changed["revision"], "definition": d, "close": True})
    assert closed.status_code == 200
    assert client.post(url + "/submit", headers=mh, json={**body, "version": 2}).status_code == 422
    other = client.post(BASE + "/workspaces", headers=oh, json={"name": "Other"}).json()["id"]
    assert client.get(f"{BASE}/workspaces/{other}/forms/{draft['id']}/responses", headers=oh).status_code == 404
    assert client.post(f"{BASE}/workspaces/{other}/forms", headers=oh, json=definition(pid)).status_code == 422


def test_forms_schema_ranges_conditions_and_transaction_rollback(client, db, monkeypatch):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = f"{BASE}/workspaces/{wid}/forms"
    for modify in [lambda d: d.update(name=" "), lambda d: d["fields"].append(d["fields"][0]), lambda d: d["fields"][0].update(condition={"field": "detail"}), lambda d: d["workflow"].update(title_field="email")]:
        d = definition(pid)
        modify(d)
        assert client.post(path, headers=oh, json=d).status_code == 422
    d = definition(pid)
    d["fields"] += [{"id": "score", "type": "rating", "label": "Score"}, {"id": "count", "type": "number", "label": "Count", "min": 0, "max": 10}, {"id": "consent", "type": "checkbox", "label": "Consent", "required": True}]
    form = publish(client, path, oh, d)
    url = path + f"/{form['id']}/submit"
    base = {"title": "Hello", "consent": True}
    for invalid in [{"score": 6}, {"count": -1}, {"count": "nan"}, {"consent": False}]:
        assert client.post(url, headers=mh, json={"request_id": str(uuid4()), "version": 1, "answers": {**base, **invalid}}).status_code == 422
    from app.apps.project_management import forms
    def broken(*args):
        raise RuntimeError("workflow failure")
    monkeypatch.setattr(forms, "apply_task_rules", broken)
    before = db.query(PMSTask).count()
    result = TestClient(client.app, raise_server_exceptions=False).post(url, headers=mh, json={"request_id": str(uuid4()), "version": 1, "answers": base})
    assert result.status_code == 500
    db.expire_all()
    assert db.query(PMSTask).count() == before
    assert client.get(path + f"/{form['id']}/responses", headers=oh).json()["total"] == 0


def test_all_answer_controls_and_payload_limits():
    import pytest
    from fastapi import HTTPException
    from app.apps.project_management.forms import Definition, clean_answers
    d = Definition.model_validate({"name": "Controls", "fields": [
        {"id": "phone", "type": "phone", "label": "Phone"},
        {"id": "site", "type": "url", "label": "Website"},
        {"id": "date", "type": "date", "label": "Date"},
        {"id": "choice", "type": "radio", "label": "Choice", "options": ["A", "B"]},
        {"id": "multiple", "type": "multiselect", "label": "Multiple", "options": ["A", "B"], "required": True},
        {"id": "number", "type": "number", "label": "Number"},
        {"id": "followup", "type": "text", "label": "Follow-up", "required": True, "condition": {"field": "number", "value": "1"}},
        {"id": "section", "type": "section", "label": "Section"}]})
    valid = {"phone": "1234567890", "phone_country_code": "+91", "site": "https://example.com", "date": "2026-10-24", "choice": "A", "multiple": ["A", "B"], "number": 1, "followup": "yes"}
    assert clean_answers(d, valid)["followup"] == "yes"
    for change in [{"site": "javascript:alert(1)"}, {"date": "2026-02-30"}, {"phone": "abc"}, {"choice": "C"}, {"multiple": ["A", "A"]}, {"multiple": []}, {"followup": ""}, {"number": True}, {"followup": "x" * 20001}]:
        with pytest.raises(HTTPException) as error:
            clean_answers(d, {**valid, **change})
        assert error.value.status_code == 422
