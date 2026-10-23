from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from tests.test_ai_operator import setup_operator, mock_provider, isolate_generic_http_audit, preview
from app.ai_operator.extensions import check_monitors
from app.ai_operator.models import OperatorMonitor, OperatorProposal
from app.apps.project_management.models import PMSProject, PMSTask, PMSTaskDependency


def setup_plan():
    return {"summary": "Create launch work", "name": "Launch", "project_key": "LAUNCH", "milestones": [
        {"key": "release", "name": "Release"}], "tasks": [
        {"key": "L-1", "title": "Build", "estimated_hours": 8, "milestone_key": "release"},
        {"key": "L-2", "title": "Test", "blocked_by": ["L-1"], "parent_key": "L-1"}]}


@pytest.mark.parametrize("provider", ["openai", "gemini", "claude"])
def test_setup_approval_is_atomic_replay_safe_and_uses_canonical_operations(client, db, monkeypatch, provider):
    headers, _, _, _ = setup_operator(client, db, provider)
    calls = mock_provider(monkeypatch, setup_plan())
    body = {"brief": "Build and test a launch", "provider": provider, "request_key": str(uuid4())}
    response = client.post("/api/v1/ai-operator/setup/preview", headers=headers, json=body)
    assert response.status_code == 200, response.text
    row = response.json()
    assert row["status"] == "awaiting_approval"
    assert not db.query(PMSProject).filter_by(project_key="LAUNCH").first()
    again = client.post("/api/v1/ai-operator/setup/preview", headers=headers, json=body)
    assert again.json()["id"] == row["id"] and len(calls) == 1
    endpoint = f"/api/v1/ai-operator/proposals/{row['id']}/approve"
    assert client.post(endpoint, headers=headers, json={"plan_hash": "0"*64}).status_code == 409
    for _ in range(2):
        result = client.post(endpoint, headers=headers, json={"plan_hash": row["plan_hash"]})
        assert result.status_code == 200, result.text
        assert result.json()["status"] == "succeeded", result.text
    project_id = result.json()["result"]["project_id"]
    tasks = db.query(PMSTask).filter_by(project_id=project_id).order_by(PMSTask.id).all()
    assert len(tasks) == 2 and tasks[1].parent_task_id == tasks[0].id
    assert tasks[0].milestone_id
    assert db.query(PMSTaskDependency).filter_by(task_id=tasks[1].id, depends_on_task_id=tasks[0].id).count() == 1


def test_setup_rolls_back_project_and_all_tasks_on_duplicate_key(client, db, monkeypatch):
    headers, _, project, _ = setup_operator(client, db)
    plan = setup_plan()
    plan["tasks"][1]["key"] = "OP-2"
    mock_provider(monkeypatch, plan)
    response = client.post("/api/v1/ai-operator/setup/preview", headers=headers, json={
        "brief": "Add launch", "provider": "openai", "project_id": project, "request_key": str(uuid4())})
    assert response.status_code == 200, response.text
    row = response.json()
    # Simulate another user creating the same key after preview but before approval.
    concurrent = client.post(f"/api/v1/project-management/projects/{project}/tasks", headers=headers,
        json={"title": "Concurrent work", "task_key": "OP-2"})
    assert concurrent.status_code == 200, concurrent.text
    result = client.post(f"/api/v1/ai-operator/proposals/{row['id']}/approve", headers=headers, json={"plan_hash": row["plan_hash"]})
    assert result.status_code == 400, result.text
    assert db.query(PMSTask).filter_by(project_id=project).count() == 2


def test_monitor_dedup_pause_and_scope(client, db):
    headers, _, project, task = setup_operator(client, db)
    response = client.post("/api/v1/ai-operator/monitors", headers=headers, json={"project_id": project, "name": "Delivery health"})
    assert response.status_code == 200, response.text
    monitor_id = response.json()["id"]
    assert check_monitors(db) == {"checked": 1, "changed": 1}
    row = db.get(OperatorMonitor, monitor_id)
    assert row.findings[0]["task_id"] == task and "unassigned" in row.findings[0]["reasons"]
    row.next_check_at = datetime.now(timezone.utc)-timedelta(minutes=1)
    db.commit()
    assert check_monitors(db) == {"checked": 1, "changed": 0}
    assert client.put(f"/api/v1/ai-operator/monitors/{monitor_id}", headers=headers, json={
        "project_id": project, "name": "Delivery health", "enabled": False}).status_code == 200
    assert check_monitors(db)["checked"] == 0


def test_resolver_literal_search_and_capacity(client, db):
    headers, _, project, task = setup_operator(client, db)
    response = client.get(f"/api/v1/ai-operator/resolve?project_id={project}&q=OP-1", headers=headers)
    assert response.status_code == 200 and response.json()["items"][0]["id"] == task
    assert not client.get(f"/api/v1/ai-operator/resolve?project_id={project}&q=%25", headers=headers).json()["items"]
    response = client.get(f"/api/v1/ai-operator/capacity?project_id={project}&week_start=2026-10-24", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["week_start"] == "2026-10-19"


def test_remove_dependency_uses_reviewed_task_execution(client, db, monkeypatch):
    headers, _, project, task = setup_operator(client, db)
    other = client.post(f"/api/v1/project-management/projects/{project}/tasks", headers=headers,
        json={"title": "Blocker", "task_key": "OP-2"}).json()["id"]
    dep = PMSTaskDependency(task_id=task, depends_on_task_id=other, dependency_type="Finish To Start", lag_days=0)
    db.add(dep)
    db.commit()
    dep_id = dep.id
    mock_provider(monkeypatch, {"summary": "Remove blocker", "steps": [{"tool": "remove_dependency", "task_id": task, "dependency_id": dep_id}]})
    run = preview(client, headers, project, task, task_ids=[task, other]).json()
    assert run["status"] == "awaiting_approval", run
    response = client.post(f"/api/v1/ai-operator/runs/{run['id']}/approve", headers=headers, json={"plan_hash": run["plan_hash"]})
    assert response.json()["status"] == "succeeded", response.text
    assert db.get(PMSTaskDependency, dep_id) is None


def test_local_plan_needs_no_provider_and_remains_subject_to_validation_and_approval(client, db, monkeypatch):
    from app.ai_operator.models import OperatorProvider, OperatorApiLog, OperatorJob
    headers, _, project, task = setup_operator(client, db)
    db.query(OperatorProvider).delete()
    db.commit()
    def no_provider_call(*args, **kwargs):
        raise AssertionError("Local commands must never call a model provider")
    monkeypatch.setattr("app.ai_operator.api.generate_json", no_provider_call)
    local = {"summary": "Set high priority locally", "steps": [{"tool": "update_task", "task_id": task, "changes": {"priority": "High"}}]}
    response = preview(client, headers, project, task, local_plan=local, background=True)
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["status"] == "awaiting_approval"
    assert db.get(PMSTask, task).priority != "High"
    assert db.query(OperatorJob).filter_by(run_id=run["id"], kind="plan").count() == 0
    assert db.query(OperatorApiLog).count() == 0
    assert client.get('/api/v1/ai-operator/analytics', headers=headers).json()['local_plans'] == 1
    response = client.post(f"/api/v1/ai-operator/runs/{run['id']}/approve", headers=headers, json={"plan_hash": run["plan_hash"]})
    assert response.status_code == 200, response.text
    from app.ai_operator.jobs import process_batch
    process_batch(db, limit=1)
    db.expire_all()
    assert db.get(PMSTask, task).priority == "High"
    bad = {"summary": "Forged selection", "steps": [{"tool": "update_task", "task_id": task+10000, "changes": {"priority": "High"}}]}
    assert preview(client, headers, project, task, local_plan=bad, background=True).status_code == 422


def test_extensions_migration_is_repeatable_on_empty_feature_tables(db):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.ai_operator.models import OperatorMonitor, OperatorProposal
    bind = db.connection()
    OperatorMonitor.__table__.drop(bind)
    OperatorProposal.__table__.drop(bind)
    spec = importlib.util.spec_from_file_location('operator_extension_migration', Path(__file__).parents[1] / 'alembic_postgresql/versions/pg_20261024_003_operator_extensions.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with Operations.context(MigrationContext.configure(bind)):
        module.upgrade()
        module.upgrade()
    assert db.query(OperatorMonitor).count() == 0
    assert db.query(OperatorProposal).count() == 0


def test_local_creation_and_existing_subtask_parent_are_reviewed_without_llm(client, db, monkeypatch):
    from app.ai_operator.models import OperatorProvider, OperatorApiLog
    headers, user, project, parent_id = setup_operator(client, db)
    db.query(OperatorProvider).delete()
    db.commit()
    def forbidden(*args, **kwargs):
        raise AssertionError('Local setup must not call a provider')
    monkeypatch.setattr('app.ai_operator.extensions.generate_json', forbidden)
    context = client.get(f'/api/v1/ai-operator/local-context?project_id={project}', headers=headers)
    assert context.status_code == 200, context.text
    assert context.json()['tasks'][0]['task_key'] == 'OP-1'
    plan = {'summary': 'Create local subtask', 'name': 'Operator', 'project_key': 'OP', 'tasks': [
        {'key': 'OP-21', 'title': 'Test checkout', 'existing_parent_task_id': parent_id, 'due_date': '2026-11-02', 'assignee_user_ids': [user.id]}]}
    response = client.post('/api/v1/ai-operator/setup/preview', headers=headers, json={
        'brief': 'create subtask Test checkout', 'provider': 'openai', 'project_id': project, 'request_key': str(uuid4()), 'local_plan': plan})
    assert response.status_code == 200, response.text
    proposal = response.json()
    assert db.query(PMSTask).filter_by(task_key='OP-21').count() == 0
    for _ in range(2):
        result = client.post(f"/api/v1/ai-operator/proposals/{proposal['id']}/approve", headers=headers, json={'plan_hash': proposal['plan_hash']})
        assert result.status_code == 200 and result.json()['status'] == 'succeeded', result.text
    tasks = db.query(PMSTask).filter_by(task_key='OP-21').all()
    assert len(tasks) == 1 and tasks[0].parent_task_id == parent_id
    assert tasks[0].assignee_user_ids == [user.id]
    assert db.query(OperatorApiLog).count() == 0


def test_local_setup_rejects_other_project_parent_and_invalid_assignment(client, db):
    headers, _, project, task = setup_operator(client, db)
    plan = setup_plan()
    plan['tasks'][0]['existing_parent_task_id'] = task+99999
    body = {'brief':'create local work', 'provider':'openai', 'project_id':project, 'request_key':str(uuid4()), 'local_plan':plan}
    assert client.post('/api/v1/ai-operator/setup/preview', headers=headers, json=body).status_code == 404
    plan['tasks'][0].pop('existing_parent_task_id')
    plan['tasks'][0]['assignee_user_ids'] = [999999]
    assert client.post('/api/v1/ai-operator/setup/preview', headers=headers, json=body).status_code == 422


def test_local_revision_invalidates_old_preview_without_provider_call(client, db):
    headers, _, project, task = setup_operator(client, db)
    plan = {'summary':'High locally', 'steps':[{'tool':'update_task','task_id':task,'changes':{'priority':'High'}}]}
    parent = preview(client, headers, project, task, local_plan=plan, background=True).json()
    plan['steps'][0]['changes']['priority'] = 'Urgent'
    child = preview(client, headers, project, task, local_plan=plan, background=True, parent_run_id=parent['id'], parent_plan_hash=parent['plan_hash'])
    assert child.status_code == 200, child.text
    assert child.json()['revision'] == 2 and child.json()['status'] == 'awaiting_approval'
    assert client.get(f"/api/v1/ai-operator/runs/{parent['id']}", headers=headers).json()['status'] == 'superseded'
    old = client.post(f"/api/v1/ai-operator/runs/{parent['id']}/approve", headers=headers, json={'plan_hash':parent['plan_hash']})
    assert old.status_code in [400,409], old.text


@pytest.mark.parametrize('mode', ['sync','atomic','checkpointed'])
def test_expanded_tools_reuse_pms_operations_and_replay_receipts(client, db, mode):
    from app.apps.project_management.models import PMSChecklistItem, PMSComment
    from app.ai_operator.models import OperatorApiLog
    from app.ai_operator.jobs import process_batch
    headers, _, project, task = setup_operator(client, db)
    first = PMSChecklistItem(task_id=task, title='QA review', position=0)
    second = PMSChecklistItem(task_id=task, title='Obsolete check', position=1)
    db.add_all([first,second]); db.commit()
    first_id, second_id = first.id, second.id
    plan = {'summary':'Update estimates, complete QA and add a comment', 'steps':[
        {'tool':'update_task','task_id':task,'changes':{'title':'Updated title','description':'Acceptance criteria','estimated_hours':3.5,'story_points':8}},
        {'tool':'update_checklist','task_id':task,'item_id':first_id,'is_completed':True},
        {'tool':'add_comment','task_id':task,'body':'Ready for QA'},
        {'tool':'remove_checklist','task_id':task,'item_id':second_id}]}
    response = preview(client, headers, project, task, local_plan=plan, background=mode!='sync', execution_mode='checkpointed' if mode=='checkpointed' else 'atomic')
    assert response.status_code == 200, response.text
    run = response.json()
    assert db.query(PMSComment).filter_by(task_id=task).count() == 0
    for _ in range(2):
        response = client.post(f"/api/v1/ai-operator/runs/{run['id']}/approve",headers=headers,json={'plan_hash':run['plan_hash']})
        assert response.status_code == 200, response.text
        if mode!='sync': process_batch(db,limit=10)
    db.expire_all()
    record = db.get(PMSTask,task)
    assert record.title == 'Updated title' and float(record.estimated_hours) == 3.5 and record.story_points == 8
    assert db.get(PMSChecklistItem,first_id).is_completed
    assert db.get(PMSChecklistItem,second_id) is None
    comments = db.query(PMSComment).filter_by(task_id=task).all()
    assert len(comments)==1 and comments[0].body=='Ready for QA' and comments[0].is_internal
    assert db.query(OperatorApiLog).count()==0


def test_checklist_tools_reject_cross_task_items_and_stale_previews(client, db):
    from app.apps.project_management.models import PMSChecklistItem, PMSComment
    headers, _, project, task = setup_operator(client, db)
    other = client.post(f'/api/v1/project-management/projects/{project}/tasks',headers=headers,json={'title':'Other','task_key':'OP-2'}).json()['id']
    item = PMSChecklistItem(task_id=other,title='Other check',position=0)
    db.add(item);db.commit()
    bad = {'summary':'Wrong item','steps':[{'tool':'remove_checklist','task_id':task,'item_id':item.id}]}
    assert preview(client,headers,project,task,local_plan=bad).status_code==422
    item = PMSChecklistItem(task_id=task,title='Review',position=0)
    db.add(item);db.commit()
    plan = {'summary':'Review and comment','steps':[{'tool':'update_checklist','task_id':task,'item_id':item.id,'is_completed':True},
        {'tool':'add_comment','task_id':task,'body':'Complete'}]}
    run = preview(client,headers,project,task,local_plan=plan).json()
    item.title='Changed after preview';db.commit()
    response=client.post(f"/api/v1/ai-operator/runs/{run['id']}/approve",headers=headers,json={'plan_hash':run['plan_hash']})
    assert response.json()['status']=='failed',response.text
    assert db.query(PMSComment).filter_by(task_id=task).count()==0
    assert not item.is_completed
