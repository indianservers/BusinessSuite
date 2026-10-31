from tests.rich_text_test_utils import organization_context
from tests.test_pms_task_studio import studio
from tests.test_pms_workspaces import BASE, middleware_database
from app.apps.project_management.models import PMSProject, PMSWorkspaceMember, PMSWorkspaceTeamMember
from app.models.user import Role


def test_general_tasks_are_workspace_scoped_and_support_subtasks(client, db, studio):
    owner, member, outsider, h, mh, oh, project, team, batch = studio
    endpoint = BASE + "/task-studio/general-scope"
    r = client.post(endpoint, params={"workspace_id": project["workspace_id"]}, headers=h)
    assert r.status_code == 200, r.text
    collection = r.json()
    again = client.post(endpoint, params={"workspace_id": project["workspace_id"]}, headers=h)
    assert again.json()["id"] == collection["id"]
    assert db.get(PMSProject, collection["id"]).is_task_collection
    listed = client.get(BASE + "/projects", headers=h).json()
    assert collection["id"] not in {p["id"] for p in listed}
    management = client.get(BASE + "/management/home", headers=h)
    assert management.status_code == 200, management.text
    assert next(p for p in management.json()["projects"] if p["id"] == collection["id"])["is_task_collection"]
    task = client.post(f"{BASE}/task-studio/projects/{collection['id']}/tasks", headers=h,
        json={"task": {"title": "General office work", "task_key": "GENERAL-1"}, "assignment": {"people": [owner.id]}})
    assert task.status_code == 201, task.text
    parent = task.json()["task"]
    subtask = client.post(f"{BASE}/task-studio/projects/{collection['id']}/tasks", headers=h,
        json={"task": {"title": "Prepare checklist", "task_key": "GENERAL-2", "parent_task_id": parent["id"], "work_type": "Sub-task"}})
    assert subtask.status_code == 201, subtask.text
    assert subtask.json()["task"]["parent_task_id"] == parent["id"]
    tasks = client.get(BASE + "/tasks", headers=h, params={"workspaceId": project["workspace_id"]}).json()
    assert tasks["total"] == 2
    assert all(t["is_general"] for t in tasks["items"])
    assert client.post(endpoint, params={"workspace_id": project["workspace_id"]}, headers=oh).status_code in (403, 404)
    bad_parent = client.post(f"{BASE}/task-studio/projects/{project['id']}/tasks", headers=h,
        json={"task": {"title": "Invalid cross-project child", "task_key": "BAD-PARENT", "parent_task_id": parent["id"]}})
    assert bad_parent.status_code in (400, 422)



def test_team_adds_workspace_member_without_confirmation(client, db, studio):
    owner, member, outsider, h, _, _, project, team, batch = studio
    r = client.post(f"{BASE}/people-workspace/teams/{team.id}/members", headers=h,
        json={"user_ids": [outsider.id, outsider.id], "action": "add", "reason": "Add colleague"})
    assert r.status_code == 200, r.text
    assert r.json()["workspace_access_added"] == 1
    assert db.query(PMSWorkspaceMember).filter_by(workspace_id=project["workspace_id"], user_id=outsider.id).one().role == "Member"
    assert db.query(PMSWorkspaceTeamMember).filter_by(team_id=team.id, user_id=outsider.id).count() == 1


def test_super_admin_aliases_share_one_filter(client, db, studio):
    owner, member, outsider, h, _, _, project, team, batch = studio
    role = Role(name="super_admin")
    db.add(role)
    db.flush()
    outsider.role_id = role.id
    db.commit()
    reference = client.get(BASE + "/people-workspace/reference", headers=h)
    assert reference.status_code == 200, reference.text
    assert "super_admin" not in reference.json()["roles"]
    rows = client.get(BASE + "/people-workspace/people", headers=h, params={"role": "superuser"})
    assert rows.status_code == 200, rows.text
    assert {p["id"] for p in rows.json()["items"]} == {owner.id, outsider.id}
    assert all(p["role"] == "Super Admin" for p in rows.json()["items"])


def test_workspace_collection_migration_keeps_project_tasks():
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine, text
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / "alembic/versions/20261031_046_general_tasks.py"
    spec = importlib.util.spec_from_file_location("general_tasks_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE pms_projects (id INTEGER PRIMARY KEY, workspace_id INTEGER, name VARCHAR(180))"))
        connection.execute(text("CREATE TABLE pms_tasks (id INTEGER PRIMARY KEY, project_id INTEGER, title VARCHAR(220))"))
        connection.execute(text("INSERT INTO pms_projects VALUES (1, 1, 'Existing project')"))
        connection.execute(text("INSERT INTO pms_tasks VALUES (1, 1, 'Existing task')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert connection.execute(text("SELECT is_task_collection FROM pms_projects WHERE id=1")).scalar() == 0
        assert connection.execute(text("SELECT title FROM pms_tasks WHERE id=1")).scalar() == "Existing task"
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert connection.execute(text("SELECT project_id FROM pms_tasks WHERE id=1")).scalar() == 1
    engine.dispose()
