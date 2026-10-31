from tests.rich_text_test_utils import organization_context
from tests.test_pms_task_studio import studio
from tests.test_pms_workspaces import BASE, middleware_database
from app.apps.project_management.models import PMSTimeLog, PMSActivity


def task(client, fixture):
    owner, member, outsider, h, mh, oh, project, team, batch = fixture
    r = client.post(f"{BASE}/task-studio/projects/{project['id']}/tasks", headers=h,
        json={"task": {"title": "Task collaboration", "task_key": "COLLAB-1"}, "assignment": {"people": [owner.id]}})
    assert r.status_code == 201, r.text
    return r.json()["task"]["id"], h


def test_updates_time_progress_stale_drafts_and_history(client, db, studio):
    tid, h = task(client, studio)
    root = BASE + f"/task-workspace/tasks/{tid}"
    d = client.get(root, headers=h)
    assert d.status_code == 200, d.text
    r = client.post(root + "/entries", headers=h, json={"body": "Tested Android rotation", "progress": 35, "minutes": 25, "revision": 0})
    assert r.status_code == 201, r.text
    assert client.get(root, headers=h).json()["progress"] == 35
    assert db.query(PMSTimeLog).filter_by(task_id=tid).one().duration_minutes == 25
    stale = client.post(root + "/entries", headers=h, json={"body": "Outdated progress", "progress": 10, "revision": 0})
    assert stale.status_code == 409
    assert client.get(root, headers=h).json()["progress"] == 35
    entry = r.json()
    changed = client.patch(BASE + f"/task-workspace/entries/{entry['id']}", headers=h, json={"revision": entry["revision"], "body": "Updated QA findings"})
    assert changed.status_code == 200, changed.text
    assert db.query(PMSActivity).filter_by(task_id=tid, action="task.update_edited").count() == 1
    assert client.get(root+"/history", headers=h).json()["total"] >= 3


def test_blockers_guard_completion_and_review_feedback(client, db, studio):
    tid, h = task(client, studio)
    root = BASE + f"/task-workspace/tasks/{tid}"
    blocked = client.post(root+"/entries", headers=h, json={"kind":"blocker", "body":"Missing test device", "category":"Access", "severity":"High", "responsible_user_id":studio[0].id, "revision":0})
    assert blocked.status_code == 201, blocked.text
    d = client.get(root, headers=h).json()
    assert len(d["blockers"]) == 1
    assert client.post(root+"/actions", headers=h, json={"action":"submit", "version":d["version"]}).status_code == 409
    row = blocked.json()
    r = client.patch(BASE+f"/task-workspace/entries/{row['id']}", headers=h, json={"revision":row["revision"], "resolved":True})
    assert r.status_code == 200, r.text
    d = client.get(root, headers=h).json()
    r = client.post(root+"/actions", headers=h, json={"action":"submit", "version":d["version"]})
    assert r.status_code == 200, r.text
    assert r.json()["task"]["status"] == "In Review"
    d = r.json()
    r = client.post(root+"/actions", headers=h, json={"action":"rework", "version":d["version"], "feedback":"Test the landscape layout"})
    assert r.status_code == 200, r.text
    assert r.json()["task"]["status"] == "In Progress"


def test_unavailable_people_files_and_outsiders_are_rejected(client, db, studio):
    tid, h = task(client, studio)
    root = BASE+f"/task-workspace/tasks/{tid}"
    assert client.get(root, headers=studio[5]).status_code in (403,404)
    r = client.post(root+"/entries", headers=h, json={"body":"Wrong collaborator", "mentioned_user_ids":[studio[2].id], "revision":0})
    assert r.status_code == 422
    r = client.post(root+"/entries", headers=h, json={"body":"Wrong attachment", "file_ids":[999999], "revision":0})
    assert r.status_code == 422
    assert client.get(root+"/entries", headers=h).json()["total"] == 0


def test_followups_reactions_read_positions_and_watching(client, db, studio):
    tid, h = task(client, studio)
    root = BASE+f"/task-workspace/tasks/{tid}"
    assert client.post(root+"/watch", headers=h).json()["watching"]
    assert client.get(root, headers=h).json()["watcher_count"] == 1
    followup = client.post(root+"/entries", headers=h, json={"kind":"followup", "body":"Retest the layout", "follow_up_date":"2026-11-05", "responsible_user_id":studio[0].id, "revision":0})
    assert followup.status_code == 201, followup.text
    row = followup.json()
    assert row["follow_up_date"] == "2026-11-05"
    assert client.get(root+"/entries", params={"kind":"followup"}, headers=h).json()["total"] == 1
    assert client.patch(BASE+f"/task-workspace/entries/{row['id']}", headers=h, json={"revision":row["revision"],"resolved":True}).status_code == 200
    comment = client.post(BASE+f"/tasks/{tid}/comments", headers=h, json={"body":"Discussion thread"})
    assert comment.status_code == 200, comment.text
    cid = comment.json()["id"]
    reaction = client.post(BASE+f"/task-workspace/comments/{cid}/actions", headers=h, json={"emoji":"like"})
    assert reaction.status_code == 200, reaction.text
    comments = client.get(BASE+f"/tasks/{tid}/comments", headers=h).json()
    assert comments[0]["reactions"] == [{"emoji":"like","count":1,"mine":True}]
    assert comments[0]["author"]["id"] == studio[0].id
    assert client.post(BASE+f"/task-workspace/comments/{cid}/actions", headers=h, json={"resolved":True}).status_code == 200
    assert client.get(BASE+f"/tasks/{tid}/comments", headers=h).json()[0]["is_resolved"]
    assert client.post(root+"/read", headers=h).status_code == 200
    assert client.get(root, headers=h).json()["unread_comments"] == 0


def test_comment_parent_must_belong_to_task(client, db, studio):
    tid, h = task(client, studio)
    other = client.post(f"{BASE}/task-studio/projects/{studio[6]['id']}/tasks", headers=h,
        json={"task":{"title":"Other task","task_key":"COLLAB-2"}}).json()["task"]["id"]
    parent = client.post(BASE+f"/tasks/{other}/comments", headers=h, json={"body":"Other discussion"}).json()
    result = client.post(BASE+f"/tasks/{tid}/comments", headers=h, json={"body":"Wrong thread", "parent_comment_id":parent["id"]})
    assert result.status_code == 404


def test_collaboration_migration_preserves_legacy_comments_and_tasks():
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine, text, inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / "alembic/versions/20261031_047_task_workspace.py"
    spec = importlib.util.spec_from_file_location("task_workspace_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE pms_tasks (id INTEGER PRIMARY KEY, title TEXT)"))
        connection.execute(text("CREATE TABLE pms_comments (id INTEGER PRIMARY KEY, body TEXT)"))
        connection.execute(text("INSERT INTO pms_tasks VALUES (1, 'Original task')"))
        connection.execute(text("INSERT INTO pms_comments VALUES (1, 'Original comment')"))
        with Operations.context(MigrationContext.configure(connection)): module.upgrade()
        assert "pms_task_update_entries" in inspect(connection).get_table_names()
        assert connection.execute(text("SELECT body FROM pms_comments WHERE id=1")).scalar() == "Original comment"
        with Operations.context(MigrationContext.configure(connection)): module.downgrade()
        assert connection.execute(text("SELECT title FROM pms_tasks WHERE id=1")).scalar() == "Original task"
    engine.dispose()


def test_assigned_intern_can_post_but_cannot_read_unassigned_work(client, db, studio):
    from app.access.models import AccessPolicy
    from app.apps.project_management.models import PMSTask
    from app.models.user import Role
    tid, h = task(client, studio)
    owner, member, _, _, mh, _, project, team, batch = studio
    role = Role(name="intern")
    db.add(role); db.flush()
    member.role_id = role.id
    db.add(AccessPolicy(user_id=member.id, company_id=1, status="active", grants={"project_management":{"enabled":True,"role":"custom","scope":"assigned","permissions":["pms_view","pms_manage_tasks","pms_time_manage"],"actions":["view","read","create","edit","update","comment","log_time","submit"]}}))
    db.commit()
    root = BASE+f"/task-workspace/tasks/{tid}"
    item = db.get(PMSTask, tid)
    item.assignee_user_ids = [owner.id, member.id]
    db.commit()
    detail = client.get(root, headers=mh)
    assert detail.status_code == 200, detail.text
    update = client.post(root+"/entries", headers=mh, json={"body":"Intern QA findings", "progress":25,"revision":0})
    assert update.status_code == 201, update.text
    assert not client.get(root, headers=mh).json()["can_review"]
    collective = client.post(f"{BASE}/task-studio/projects/{project['id']}/tasks", headers=h, json={"task":{"title":"Batch follow-up","task_key":"COLLAB-BATCH"},"assignment":{"batches":[batch.id],"group_responsibility":True}})
    assert collective.status_code == 201, collective.text
    collective_id = collective.json()["task"]["id"]
    collective_detail = client.get(BASE+f"/task-workspace/tasks/{collective_id}", headers=mh)
    assert collective_detail.status_code == 200, collective_detail.text
    assert collective_detail.json()["can_work"]
    other = client.post(f"{BASE}/task-studio/projects/{project['id']}/tasks", headers=h, json={"task":{"title":"Unassigned intern work","task_key":"COLLAB-UNASSIGNED"}}).json()["task"]["id"]
    assert client.get(BASE+f"/task-workspace/tasks/{other}", headers=mh).status_code == 404
