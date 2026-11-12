from tests.rich_text_test_utils import organization_context
from tests.test_pms_workspaces import middleware_database, BASE
from tests.test_pms_automations import setup_workspace
from tests.test_pms_workflow_schemes import task
from app.apps.project_management.models import PMSTask


def test_bulk_review_versions_reject_stale_cross_project_batch_atomically(client, db):
    wid, pid, _, oh, _, _, mh, _, gh = setup_workspace(client, db)
    first = task(client, pid, mh, "BULK-1")
    project = client.post(f"{BASE}/projects", headers=oh, json={"name":"Second reviewed project","project_key":"BRV","workspace_id":wid})
    assert project.status_code == 200
    second = task(client, project.json()["id"], mh, "BULK-2")
    tokens = {str(tid):client.get(f"{BASE}/tasks/{tid}",headers=mh).json()["updated_at"] for tid in [first,second]}
    changed = client.patch(f"{BASE}/tasks/{second}",headers=mh,json={"title":"Peer changed second project task"})
    assert changed.status_code == 200
    response=client.patch(f"{BASE}/tasks/bulk",headers=mh,json={"task_ids":[first,second],"status":"Done","expected_updated_at_by_task":tokens})
    assert response.status_code == 409,response.text
    db.expire_all()
    assert db.get(PMSTask,first).status == "To Do"
    assert db.get(PMSTask,second).status == "To Do"
    assert db.get(PMSTask,second).title == "Peer changed second project task"
    tokens[str(second)]=changed.json()["updated_at"]
    denied=client.patch(f"{BASE}/tasks/bulk",headers=gh,json={"task_ids":[first,second],"status":"Done","expected_updated_at_by_task":tokens})
    assert denied.status_code == 403
    saved=client.patch(f"{BASE}/tasks/bulk",headers=mh,json={"task_ids":[first,second],"status":"Done","expected_updated_at_by_task":tokens})
    assert saved.status_code == 200,saved.text
    assert saved.json()["updated_count"] == 2
    assert all(row["status"] == "Done" for row in saved.json()["tasks"])


def test_bulk_review_requires_complete_token_map_and_keeps_legacy_callers(client, db):
    _,pid,_,_,_,_,mh,_,_=setup_workspace(client,db)
    first,second=task(client,pid,mh,"MAP-1"),task(client,pid,mh,"MAP-2")
    for tokens in [{str(first):None},{str(first):None,str(second):None,"999999":None}]:
        response=client.patch(f"{BASE}/tasks/bulk",headers=mh,json={"task_ids":[first,second],"priority":"Low","expected_updated_at_by_task":tokens})
        assert response.status_code == 422,response.text
    assert client.patch(f"{BASE}/tasks/{first}",headers=mh,json={"priority":"High"}).status_code == 200
    stale=client.patch(f"{BASE}/tasks/bulk",headers=mh,json={"task_ids":[first],"priority":"Low","expected_updated_at_by_task":{str(first):None}})
    assert stale.status_code == 409
    legacy=client.patch(f"{BASE}/tasks/bulk",headers=mh,json={"task_ids":[first,second],"priority":"Low"})
    assert legacy.status_code == 200


def test_reviewed_bulk_keeps_approval_consumption_atomic(client, db):
    from tests.test_pms_transition_approvals import setup_route, request, decide
    from app.models.workflow_engine import WorkflowInstance
    _,pid,first,_,_,reviewer_headers,_,mh,_,_,_=setup_route(client,db)
    second=task(client,pid,mh,"APPROVED-BULK-2")
    first_review=request(client,first,mh)
    assert decide(client,first_review["steps"][0]["id"],reviewer_headers).status_code == 200
    def tokens():
        return {str(tid):client.get(f"{BASE}/tasks/{tid}",headers=mh).json()["updated_at"] for tid in [first,second]}
    denied=client.patch(f"{BASE}/tasks/bulk",headers=mh,json={"task_ids":[first,second],"status":"Done","expected_updated_at_by_task":tokens()})
    assert denied.status_code == 409
    db.expire_all()
    assert db.get(PMSTask,first).status == "To Do"
    assert db.get(WorkflowInstance,first_review["id"]).status == "Approved"
    second_review=request(client,second,mh)
    assert decide(client,second_review["steps"][0]["id"],reviewer_headers).status_code == 200
    saved=client.patch(f"{BASE}/tasks/bulk",headers=mh,json={"task_ids":[first,second],"status":"Done","expected_updated_at_by_task":tokens()})
    assert saved.status_code == 200,saved.text
    db.expire_all()
    assert all(db.get(PMSTask,tid).status == "Done" for tid in [first,second])
    assert all(db.get(WorkflowInstance,r["id"]).status == "Applied" for r in [first_review,second_review])
