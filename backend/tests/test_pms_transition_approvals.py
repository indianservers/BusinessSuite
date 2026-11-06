import os
import json
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_pms_workspaces import middleware_database, BASE, account
from tests.test_pms_automations import setup_workspace
from tests.test_pms_workflow_schemes import task
from app.apps.project_management.models import PMSTask, PMSWorkspaceMember
from app.models.workflow_engine import WorkflowInstance, WorkflowTask, WorkflowAuditEvent

ENGINE = "/api/v1/workflow-engine"


def setup_route(client, db, sequential=False):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    admin_id = db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, role="Admin").one().user_id
    reviewers = [admin_id, owner.id] if sequential else [admin_id]
    scheme = {"revision": 0, "enabled": True, "transitions": [
        {"source": "To Do", "target": "Done", "approval_user_ids": reviewers},
        {"source": "Done", "target": "To Do"}],
        "work_type_transitions": {"Bug": [{"source": "To Do", "target": "In Review", "approval_user_ids": reviewers}]}}
    response = client.put(f"{BASE}/projects/{pid}/workflow-scheme", headers=oh, json=scheme)
    assert response.status_code == 200, response.text
    tid = task(client, pid, mh)
    return wid, pid, tid, owner, oh, ah, member, mh, guest, gh, scheme


def request(client, tid, headers, target="Done"):
    response = client.post(f"{BASE}/tasks/{tid}/transition-approvals", headers=headers, json={"target": target})
    assert response.status_code == 201, response.text
    return response.json()


def decide(client, approval, headers, decision="approve"):
    return client.put(f"{ENGINE}/tasks/{approval}/decision", headers=headers, json={"decision": decision})


def test_sequential_approval_apply_and_single_use(client, db):
    wid, pid, tid, owner, oh, ah, member, mh, guest, gh, scheme = setup_route(client, db, True)
    url = f"{BASE}/tasks/{tid}"
    assert client.patch(url, headers=mh, json={"status": "Done"}).status_code == 409
    approval = request(client, tid, mh)
    assert request(client, tid, mh)["id"] == approval["id"]
    assert decide(client, approval["steps"][0]["id"], mh).status_code == 403
    assert decide(client, approval["steps"][0]["id"], ah).status_code == 200
    assert client.patch(url, headers=mh, json={"status": "Done"}).status_code == 409
    pending = client.get(f"{BASE}/tasks/{tid}/transition-approvals", headers=oh).json()["requests"][0]
    assert len(pending["steps"]) == 2 and pending["steps"][1]["can_decide"]
    assert decide(client, pending["steps"][1]["id"], oh).status_code == 200
    assert db.get(WorkflowInstance, approval["id"]).status == "Approved"
    # Reviews do not change task status until an authorized task editor applies them.
    assert db.get(PMSTask, tid).status == "To Do"
    assert client.patch(url, headers=mh, json={"status": "Done"}).status_code == 200
    assert db.get(WorkflowInstance, approval["id"]).status == "Applied"
    assert client.patch(url, headers=mh, json={"status": "To Do"}).status_code == 200
    assert client.patch(url, headers=mh, json={"status": "Done"}).status_code == 409
    assert db.query(WorkflowAuditEvent).filter_by(instance_id=approval["id"], event_type="transition_applied").count() == 1


def test_reject_retry_and_decision_replay(client, db):
    wid, pid, tid, owner, oh, ah, member, mh, guest, gh, scheme = setup_route(client, db, True)
    first = request(client, tid, mh)
    step = first["steps"][0]["id"]
    assert decide(client, step, ah, "reject").status_code == 200
    assert db.get(WorkflowInstance, first["id"]).status == "Rejected"
    assert decide(client, step, ah).status_code in [400, 409]
    assert client.patch(f"{BASE}/tasks/{tid}", headers=mh, json={"status": "Done"}).status_code == 409
    assert request(client, tid, mh)["id"] != first["id"]


def test_saved_task_changes_and_policy_revisions_invalidate_reviews(client, db):
    wid, pid, tid, owner, oh, ah, member, mh, guest, gh, scheme = setup_route(client, db)
    first = request(client, tid, mh)
    url = f"{BASE}/tasks/{tid}"
    assert client.patch(url, headers=mh, json={"description": "Changed after request"}).status_code == 200
    assert decide(client, first["steps"][0]["id"], ah).status_code == 409
    second = request(client, tid, mh)
    assert db.get(WorkflowInstance, first["id"]).status == "Cancelled"
    assert decide(client, second["steps"][0]["id"], ah).status_code == 200
    assert client.patch(url, headers=mh, json={"status": "Done", "description": "Unreviewed change"}).status_code == 409
    assert db.get(WorkflowInstance, second["id"]).status == "Approved"
    assert client.put(f"{BASE}/projects/{pid}/workflow-scheme", headers=oh, json={**scheme, "revision": 1}).status_code == 200
    assert client.patch(url, headers=mh, json={"status": "Done"}).status_code == 409


def test_work_type_route_membership_self_review_and_forged_instances(client, db):
    wid, pid, tid, owner, oh, ah, member, mh, guest, gh, scheme = setup_route(client, db)
    url = f"{BASE}/tasks/{tid}"
    client.patch(url, headers=mh, json={"work_type": "Bug"})
    approval = request(client, tid, mh, "In Review")
    assert approval["target"] == "In Review"
    assert client.post(url+"/transition-approvals", headers=gh, json={"target": "In Review"}).status_code == 403
    assert client.post(url+"/transition-approvals", headers=ah, json={"target": "In Review"}).status_code == 422
    outsider, xh = account(db, "approval-outsider@test.com")
    assert client.get(url+"/transition-approvals", headers=xh).status_code == 403
    assert decide(client, approval["steps"][0]["id"], xh).status_code == 403
    assert client.post(ENGINE+"/instances", headers=mh, json={"module": "project_management", "entity_type": "pms_transition", "entity_id": tid}).status_code == 403
    reviewer = db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, role="Admin").one()
    db.delete(reviewer); db.commit()
    assert decide(client, approval["steps"][0]["id"], ah).status_code == 403
    assert not any(t["id"] == approval["steps"][0]["id"] for t in client.get(ENGINE+"/tasks", headers=ah).json())


def test_completion_guards_do_not_spend_approval_on_failed_transition(client, db):
    from app.apps.project_management.models import PMSChecklistItem
    wid, pid, tid, owner, oh, ah, member, mh, guest, gh, scheme = setup_route(client, db)
    check = PMSChecklistItem(task_id=tid, title="Evidence check", is_completed=False)
    db.add(check); db.commit()
    approval = request(client, tid, mh)
    assert decide(client, approval["steps"][0]["id"], ah).status_code == 200
    url = f"{BASE}/management/tasks/{tid}"
    assert client.patch(url, headers=mh, json={"status": "Done"}).status_code == 409
    assert db.get(WorkflowInstance, approval["id"]).status == "Approved"
    check.is_completed = True; db.commit()
    assert client.patch(url, headers=mh, json={"status": "Done"}).status_code == 200


def test_board_applies_review_and_bulk_failure_rolls_back_consumption(client, db):
    wid, pid, tid, owner, oh, ah, member, mh, guest, gh, scheme = setup_route(client, db)
    other = task(client, pid, mh, "UNREVIEWED")
    approval = request(client, tid, mh)
    assert decide(client, approval["steps"][0]["id"], ah).status_code == 200
    response = client.patch(BASE+"/tasks/bulk", headers=mh, json={"task_ids": [tid, other], "status": "Done"})
    assert response.status_code == 409
    assert db.get(PMSTask, tid).status == "To Do"
    assert db.get(WorkflowInstance, approval["id"]).status == "Approved"
    board = client.get(f"{BASE}/projects/{pid}/board", headers=mh).json()
    done = next(c for c in board["columns"] if c["status_key"] == "DONE")
    response = client.post(f"{BASE}/projects/{pid}/board/reorder", headers=mh,
                          json={"task_id": tid, "column_id": done["id"], "position": 0})
    assert response.status_code == 200, response.text
    assert db.get(WorkflowInstance, approval["id"]).status == "Applied"


def test_engine_delegation_preserves_project_access_and_prevents_self_review(client, db):
    from app.models.workflow_engine import WorkflowDelegation
    from datetime import datetime, timedelta, timezone
    wid, pid, tid, owner, oh, ah, member, mh, guest, gh, scheme = setup_route(client, db)
    reviewer = db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, role="Admin").one().user_id
    now = datetime.now(timezone.utc)
    delegation = WorkflowDelegation(organization_id=1, delegator_user_id=reviewer,
        delegate_to_user_id=member.id, module="project_management", starts_at=now-timedelta(days=1), ends_at=now+timedelta(days=1), is_active=True)
    db.add(delegation); db.commit()
    response = client.post(f"{BASE}/tasks/{tid}/transition-approvals", headers=mh, json={"target": "Done"})
    assert response.status_code == 409
    delegation = db.get(WorkflowDelegation, delegation.id)
    delegation.delegate_to_user_id = owner.id; db.commit()
    approval = request(client, tid, mh)
    step = approval["steps"][0]
    assert step["assigned_to_user_id"] == owner.id
    inbox = client.get(BASE+"/transition-approvals/inbox", headers=oh)
    assert inbox.status_code == 200 and inbox.json()[0]["task_id"] == tid
    assert decide(client, step["id"], ah).status_code == 403
    assert decide(client, step["id"], oh).status_code == 200
    assert client.patch(f"{BASE}/tasks/{tid}", headers=mh, json={"status": "Done"}).status_code == 200


def test_invalid_reviewer_and_reviewer_revoked_after_approval(client, db):
    wid, pid, tid, owner, oh, ah, member, mh, guest, gh, scheme = setup_route(client, db)
    invalid = {**scheme, "revision": 1, "transitions": [{"source": "To Do", "target": "Done", "approval_user_ids": [guest.id]}]}
    assert client.put(f"{BASE}/projects/{pid}/workflow-scheme", headers=oh, json=invalid).status_code == 422
    approval = request(client, tid, mh)
    assert decide(client, approval["steps"][0]["id"], ah).status_code == 200
    reviewer = db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, role="Admin").one()
    db.delete(reviewer); db.commit()
    assert client.patch(f"{BASE}/tasks/{tid}", headers=mh, json={"status": "Done"}).status_code == 409


def test_pms_only_reviewer_uses_shared_engine_without_automation_grant(client, db):
    from app.access.models import AccessPolicy
    wid, pid, tid, owner, oh, ah, member, mh, guest, gh, scheme = setup_route(client, db)
    reviewer = db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, role="Admin").one().user_id
    db.add(AccessPolicy(user_id=reviewer, company_id=1, status="active", version=1, grants={
        "project_management": {"enabled": True, "role": "PMS reviewer", "scope": "organization",
            "permissions": ["pms_view", "pms_manage_tasks"], "actions": ["view", "edit", "approve"]}}))
    db.commit()
    approval = request(client, tid, mh)
    step = approval["steps"][0]["id"]
    assert decide(client, step, ah).status_code == 403
    url = f"{BASE}/tasks/{tid}/transition-approvals/{approval['id']}/steps/{step}/decision"
    response = client.put(url, headers=ah, json={"decision": "approve"})
    assert response.status_code == 200, response.text
    assert db.get(WorkflowInstance, approval["id"]).status == "Approved"
    other = task(client, pid, mh, "UNRELATED")
    wrong = f"{BASE}/tasks/{other}/transition-approvals/{approval['id']}/steps/{step}/decision"
    assert client.put(wrong, headers=oh, json={"decision": "approve"}).status_code == 404


@pytest.mark.skipif(os.environ.get("RUN_PMS_WORKFLOW_BROWSER") != "1", reason="Explicit real-browser integration run")
def test_approval_browser_with_disposable_api(client, db):
    if db.get_bind().dialect.name == "postgresql":
        pytest.skip("PostgreSQL browser coverage uses the committed acceptance fixture")
    from tests.workflow_browser_utils import run_browser
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    tid = task(client, pid, mh)
    admin_id = db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, role="Admin").one().user_id
    actors = {"owner": {"id": owner.id, "token": oh["Authorization"].split(" ", 1)[1]},
              "requester": {"id": member.id, "token": mh["Authorization"].split(" ", 1)[1]},
              "reviewer": {"id": admin_id, "token": ah["Authorization"].split(" ", 1)[1]}}
    run_browser(client, db, "test-transition-approvals.cjs", {"WORKFLOW_TEST_ACTORS": json.dumps(actors),
                "WORKFLOW_TEST_PROJECT": str(pid), "WORKFLOW_TEST_TASK": str(tid)})
