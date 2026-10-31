"""Real API coverage for responsibility, filters, pagination and optimistic editing."""
from tests.rich_text_test_utils import organization_context
from tests.test_pms_task_studio import studio
from tests.test_pms_workspaces import BASE, middleware_database
from app.apps.project_management.models import PMSTaskGroupTarget, PMSChecklistItem, PMSTaskAssignee
from app.models.notification import Notification
import pytest
from app.models.user import Role

@pytest.fixture(autouse=True)
def member_roles(db, studio):
    role = Role(name="employee")
    db.add(role)
    db.flush()
    studio[1].role_id = role.id
    studio[2].role_id = role.id
    from app.access.models import AccessPolicy
    db.add(AccessPolicy(user_id=studio[1].id, company_id=1, status="active", grants={"project_management": {"enabled": True, "role": "custom", "permissions": ["pms_view"], "actions": ["read"], "scope": "all"}}))
    db.commit()


def create(client, studio, key="MY-1", **fields):
    owner, member, other, h, mh, oh, project, team, batch = studio
    response = client.post(f"{BASE}/task-studio/projects/{project['id']}/tasks", headers=h,
        json={"task": {"title": key, "task_key": key, **fields}, "assignment": {"people": [owner.id]}})
    assert response.status_code == 201, response.text
    return response.json()["task"]["id"]


def current(client, tid, headers):
    response = client.get(f"{BASE}/my-work/tasks/{tid}/assignment", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_groups_are_distinct_from_people_persist_and_filter(client, db, studio):
    owner, member, _, h, _, oh, project, team, batch = studio
    tid = create(client, studio)
    before = current(client, tid, h)
    payload = {"people": [owner.id, owner.id], "teams": [team.id, team.id], "batches": [batch.id], "version": before["version"], "note": "Prepare handover", "notify": True}
    response = client.put(f"{BASE}/my-work/tasks/{tid}/assignment", headers=h, json=payload)
    assert response.status_code == 200, response.text
    saved = current(client, tid, h)
    assert saved["task"]["assignee_user_ids"] == [owner.id]
    assert len(saved["group_targets"]) == 2
    assert db.query(PMSTaskGroupTarget).filter_by(task_id=tid).count() == 2
    for filters in ({"workView": "teams", "teamId": team.id}, {"workView": "batches", "batchId": batch.id}):
        listing = client.get(BASE + "/tasks", headers=h, params=filters)
        assert listing.status_code == 200, listing.text
        assert listing.json()["total"] == 1
        assert listing.json()["items"][0]["assignees"][0]["id"] == owner.id
    assert client.get(f"{BASE}/my-work/tasks/{tid}/assignment", headers=oh).status_code in (403, 404)
    assert client.put(f"{BASE}/my-work/tasks/{tid}/assignment", headers=h, json=payload).status_code == 409


def test_invalid_group_rolls_back_and_individual_notifications(client, db, studio):
    owner, member, _, h, _, oh, project, team, batch = studio
    tid = create(client, studio)
    before = current(client, tid, h)
    endpoint = f"{BASE}/my-work/tasks/{tid}/assignment"
    bad = client.put(endpoint, headers=h, json={"people": [member.id], "teams": [999999], "version": before["version"]})
    assert bad.status_code == 422
    assert current(client, tid, h)["task"]["assignee_user_ids"] == [owner.id]
    good = client.put(endpoint, headers=h, json={"people": [member.id, member.id], "version": before["version"], "note": "Review the checklist"})
    assert good.status_code == 200, good.text
    assert db.query(Notification).filter_by(user_id=member.id, event_type="task.assigned").count() == 1
    assert client.put(endpoint, headers=oh, json={"people": [], "version": good.json()["version"]}).status_code in (403, 404)


def test_stats_all_pages_progress_and_workspace_boundary(client, db, studio):
    owner, member, _, h, mh, oh, project, team, batch = studio
    owner.person.profile.directory_visibility = "private"
    owner.person.profile.profile_photo_url = "/private-profile.png"
    db.commit()
    first = create(client, studio, "MY-1")
    create(client, studio, "MY-2", status="In Progress", priority="High")
    create(client, studio, "MY-3", status="In Review")
    db.add_all([PMSChecklistItem(task_id=first, title="One", is_completed=True), PMSChecklistItem(task_id=first, title="Two", is_completed=False)])
    db.commit()
    r = client.get(BASE + "/tasks", headers=h, params={"workView": "mine", "pageSize": 1, "sortBy": "title", "sortOrder": "asc"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3 and len(body["items"]) == 1 and body["pages"] == 3
    assert body["summary"]["todo"] == 1 and body["summary"]["in_review"] == 1 and body["summary"]["in_progress"] == 1
    assert body["items"][0]["progress"] == 50
    assert body["items"][0]["assignees"][0]["photo_url"] is None
    mine = client.get(BASE + "/tasks", headers=mh, params={"workView": "mine"})
    assert mine.status_code == 403 and "Intern accounts" in mine.text
    denied = client.get(BASE + "/tasks", headers=oh)
    assert denied.status_code == 403 or denied.json()["total"] == 0
    assert client.get(BASE + "/tasks", headers=h, params={"workspaceId": 999999}).json()["total"] == 0
    assert client.get(BASE + "/tasks", headers=h, params={"priority": "High"}).json()["summary"]["total"] == 1


def test_group_members_search_is_scoped_and_removal_is_explicit(client, db, studio):
    owner, member, _, h, _, oh, project, team, batch = studio
    response = client.get(BASE + "/task-studio/people", headers=h,
        params={"project_id": project["id"], "group_kind": "batches", "group_id": batch.id})
    assert response.status_code == 200, response.text
    assert [p["id"] for p in response.json()["items"]] == [member.id]
    tid = create(client, studio)
    d = current(client, tid, h)
    r = client.put(f"{BASE}/my-work/tasks/{tid}/assignment", headers=h, json={"people": [], "teams": [team.id], "version": d["version"]})
    assert r.status_code == 200, r.text
    assert r.json()["task"]["assignee_user_ids"] == []
    assert client.get(BASE + "/tasks", headers=h, params={"workView": "unassigned"}).json()["total"] == 0
    r = client.put(f"{BASE}/my-work/tasks/{tid}/assignment", headers=h, json={"people": [], "version": r.json()["version"]})
    assert r.status_code == 200, r.text
    assert db.query(PMSTaskGroupTarget).filter_by(task_id=tid).count() == 0
    assert client.get(BASE + "/tasks", headers=h, params={"workView": "unassigned"}).json()["total"] == 1


def test_full_page_group_responsibility_survives_detail_edits(client, db, studio):
    owner, member, _, h, _, _, project, team, batch = studio
    r = client.post(f"{BASE}/task-studio/projects/{project['id']}/tasks", headers=h, json={
        "task": {"title": "Collective work", "task_key": "GROUP-NEW"},
        "assignment": {"people": [owner.id], "teams": [team.id], "batches": [batch.id], "group_responsibility": True}})
    assert r.status_code == 201, r.text
    saved = r.json()
    assert saved["task"]["assignee_user_ids"] == [owner.id]
    assert len(saved["group_targets"]) == 2
    r = client.put(f"{BASE}/task-studio/tasks/{saved['task']['id']}", headers=h,
        json={"task": {"title": "Edited collective work"}, "assignment": saved["assignment"], "version": saved["version"]})
    assert r.status_code == 200, r.text
    assert len(r.json()["group_targets"]) == 2
    assert r.json()["task"]["assignee_user_ids"] == [owner.id]


def test_additive_migration_preserves_existing_tasks():
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine, text, inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / "alembic/versions/20261031_045_task_groups.py"
    spec = importlib.util.spec_from_file_location("task_groups_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE pms_tasks (id INTEGER PRIMARY KEY, title VARCHAR(220))"))
        connection.execute(text("INSERT INTO pms_tasks VALUES (1, 'Existing task')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert "pms_task_group_targets" in inspect(connection).get_table_names()
        assert connection.execute(text("SELECT title FROM pms_tasks WHERE id=1")).scalar() == "Existing task"
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert connection.execute(text("SELECT count(*) FROM pms_tasks")).scalar() == 1
    engine.dispose()


def test_task_ids_filter_is_scoped_paginated_and_validated(client, studio):
    owner, member, other, h, mh, oh, project, team, batch = studio
    wanted = create(client, studio, "STAR-1")
    excluded = create(client, studio, "STAR-2")
    response = client.get(BASE + "/tasks", headers=h, params={"taskIds": f"{wanted},{wanted},999999", "pageSize": 1})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert [item["id"] for item in response.json()["items"]] == [wanted]
    assert excluded != wanted
    denied = client.get(BASE + "/tasks", headers=oh, params={"taskIds": str(wanted)})
    assert denied.status_code in (200, 403)
    if denied.status_code == 200:
        assert denied.json()["total"] == 0
    assert client.get(BASE + "/tasks", headers=h, params={"taskIds": "bad"}).status_code == 422
    assert client.get(BASE + "/tasks", headers=h, params={"taskIds": ",".join(map(str, range(101)))}).status_code == 422
