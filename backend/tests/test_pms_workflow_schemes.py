from tests.rich_text_test_utils import organization_context
from tests.test_pms_automations import setup_workspace
from tests.test_pms_workspaces import middleware_database, BASE, account
from app.apps.project_management.models import PMSActivity, PMSTask
import os
import pytest


def policy():
    return {"revision": 0, "enabled": True, "transitions": [
        {"source": "To Do", "target": "In Progress", "required_fields": ["assignee", "due_date", "description"]},
        {"source": "In Progress", "target": "In Review"},
        {"source": "In Review", "target": "Done"},
    ]}


def task(client, pid, headers, key="WF"):
    response = client.post(f"{BASE}/projects/{pid}/tasks", headers=headers,
                           json={"task_key": key, "title": "Workflow delivery"})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_scheme_publication_permissions_conflicts_and_scope(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = f"{BASE}/projects/{pid}/workflow-scheme"
    assert client.get(path, headers=gh).json()["enabled"] is False
    for headers in [mh, gh]:
        assert client.put(path, headers=headers, json=policy()).status_code == 403
    saved = client.put(path, headers=oh, json=policy())
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 1
    assert client.get(path, headers=mh).json() == saved.json()
    assert client.put(path, headers=oh, json=policy()).status_code == 409
    outsider, xh = account(db, "workflow-outsider@test.com")
    assert client.get(path, headers=xh).status_code in [403, 404]
    other = client.post(BASE + "/projects", headers=oh, json={"name": "Other", "project_key": "OTHER", "workspace_id": wid}).json()["id"]
    assert client.get(f"{BASE}/projects/{other}/workflow-scheme", headers=oh).json()["revision"] == 0
    assert db.query(PMSActivity).filter_by(project_id=pid, action="workflow.updated").count() == 1


def test_transitions_validate_proposed_fields_and_keep_completion_guards(client, db):
    from app.apps.project_management.models import PMSChecklistItem
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    tid = task(client, pid, mh)
    path = f"{BASE}/tasks/{tid}"
    assert client.put(f"{BASE}/projects/{pid}/workflow-scheme", headers=oh, json=policy()).status_code == 200
    assert client.patch(path, headers=mh, json={"status": "Done"}).status_code == 409
    required = client.patch(path, headers=mh, json={"status": "In Progress"})
    assert required.status_code == 409 and "assignee" in required.text
    started = client.patch(path, headers=mh, json={"status": "In Progress", "assignee_user_ids": [member.id], "due_date": "2026-12-01", "description": "Delivery plan"})
    assert started.status_code == 200, started.text
    assert client.patch(path, headers=mh, json={"status": "In Review"}).status_code == 200
    check = PMSChecklistItem(task_id=tid, title="Review delivery", is_completed=False)
    db.add(check); db.commit()
    assert client.patch(path, headers=mh, json={"status": "Done"}).status_code == 409
    check.is_completed = True; db.commit()
    assert client.patch(path, headers=mh, json={"status": "Done"}).status_code == 200


def test_bulk_and_management_cannot_skip_workflow_and_disable_restores_defaults(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    first, second = task(client, pid, mh, "WF1"), task(client, pid, mh, "WF2")
    path = f"{BASE}/projects/{pid}/workflow-scheme"
    assert client.put(path, headers=oh, json=policy()).status_code == 200
    assert client.patch(BASE + "/tasks/bulk", headers=mh, json={"task_ids": [first, second], "status": "Done"}).status_code == 409
    assert client.patch(f"{BASE}/management/tasks/{first}", headers=mh, json={"status": "Done"}).status_code == 409
    assert db.get(PMSTask, first).status == db.get(PMSTask, second).status == "To Do"
    assert client.put(path, headers=oh, json={"revision": 1, "enabled": False, "transitions": []}).status_code == 200
    assert client.patch(f"{BASE}/tasks/{first}", headers=mh, json={"status": "Done"}).status_code == 200


def test_invalid_graphs_are_rejected(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = f"{BASE}/projects/{pid}/workflow-scheme"
    for edges in [[], [{"source": "Done", "target": "Done"}],
                  [{"source": "To Do", "target": "Done"}]*2,
                  [{"source": "Unknown", "target": "Done"}],
                  [{"source": "To Do", "target": "Done", "required_fields": ["execute_script"]}]]:
        assert client.put(path, headers=oh, json={**policy(), "transitions": edges}).status_code == 422


def test_required_fields_cannot_be_cleared_in_same_transition(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    tid = task(client, pid, mh)
    url = f"{BASE}/tasks/{tid}"
    client.patch(url, headers=mh, json={"assignee_user_ids": [member.id], "description": "Ready", "due_date": "2026-12-01"})
    client.put(f"{BASE}/projects/{pid}/workflow-scheme", headers=oh, json=policy())
    for cleared in [{"assignee_user_ids": []}, {"assignee_user_id": None}, {"due_date": None}, {"description": "  "}, {"description": "<!--suite-richtext:v1--><p><br></p>"}]:
        result = client.patch(url, headers=mh, json={"status": "In Progress", **cleared})
        assert result.status_code == 409, result.text
    assert db.get(PMSTask, tid).status == "To Do"


def test_board_and_assignment_rollup_cannot_skip_policy(client, db):
    from fastapi import HTTPException
    from app.apps.project_management.work import sync_parent
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    tid = task(client, pid, mh)
    client.put(f"{BASE}/projects/{pid}/workflow-scheme", headers=oh, json=policy())
    board = client.get(f"{BASE}/projects/{pid}/board", headers=mh).json()
    done = next(c for c in board["columns"] if c["status_key"] == "DONE")
    result = client.post(f"{BASE}/projects/{pid}/board/reorder", headers=mh,
                         json={"task_id": tid, "column_id": done["id"], "position": 0})
    assert result.status_code == 409, result.text
    from app.apps.project_management.models import PMSTaskAssignee
    db.add(PMSTaskAssignee(task_id=tid, user_id=member.id, execution_status="In Progress"))
    db.commit()
    with pytest.raises(HTTPException) as denied:
        sync_parent(db, db.get(PMSTask, tid))
    assert denied.value.status_code == 409


def test_merge_keeps_development_evidence_without_bypassing_workflow(client, db):
    from app.apps.project_management.api.router import _upsert_dev_link
    from app.apps.project_management.models import PMSProject, PMSDevLink
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    tid = task(client, pid, mh)
    assert client.put(f"{BASE}/projects/{pid}/workflow-scheme", headers=oh, json=policy()).status_code == 200
    link = _upsert_dev_link(db, db.get(PMSTask, tid), db.get(PMSProject, pid),
                            "github", "pr", "12", "Delivery", "https://github.com/example/repo/pull/12",
                            "merged", "test-developer")
    db.commit()
    assert db.get(PMSTask, tid).status == "To Do"
    assert db.get(PMSDevLink, link.id).status == "merged"
    assert db.query(PMSActivity).filter_by(task_id=tid, action="workflow.transition_skipped").count() == 1


def test_recovery_cannot_restore_a_forbidden_transition(client, db):
    from fastapi import HTTPException
    from app.apps.project_management.recovery import apply_state, task_state
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    tid = task(client, pid, mh)
    client.put(f"{BASE}/projects/{pid}/workflow-scheme", headers=oh, json=policy())
    item = db.get(PMSTask, tid)
    state = {**task_state(item), "status": "Done"}
    with pytest.raises(HTTPException) as denied:
        apply_state(db, item, state, wid)
    assert denied.value.status_code == 409
    assert item.status == "To Do"


@pytest.mark.skipif(os.environ.get("RUN_PMS_WORKFLOW_BROWSER") != "1", reason="Explicit real-browser integration run")
def test_workflow_browser_with_disposable_api(client, db):
    if db.get_bind().dialect.name == "postgresql":
        pytest.skip("PostgreSQL browser coverage uses the committed acceptance fixture")
    from tests.workflow_browser_utils import run_browser
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    tid = task(client, pid, mh)
    bug_tid = task(client, pid, mh, "BROWSER-BUG")
    assert client.patch(f"{BASE}/tasks/{bug_tid}", headers=mh, json={"work_type": "Bug"}).status_code == 200
    run_browser(client, db, "test-workflow-schemes.cjs", {
        "WORKFLOW_TEST_TOKEN": oh["Authorization"].split(" ", 1)[1],
        "WORKFLOW_TEST_PROJECT": str(pid), "WORKFLOW_TEST_TASK": str(tid),
        "WORKFLOW_TEST_ASSIGNEE": str(member.id), "WORKFLOW_TEST_BUG_TASK": str(bug_tid)})
