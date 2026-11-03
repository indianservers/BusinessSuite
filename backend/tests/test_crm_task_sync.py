import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.apps.crm.models import CRMTask


@pytest.fixture
def task_headers(db, superuser_headers):
    from app.models.user import User
    from test_identity_utils import attach_test_identity
    attach_test_identity(db, db.query(User).filter_by(email="testadmin@test.com").one())
    db.commit()
    return superuser_headers


def test_tasks_persist_across_sessions_and_support_edit_delete(client, db, task_headers):
    details = {"assignees": ["testadmin@test.com"], "acceptance": "Reviewed", "subtasks": ["Call customer"], "start": "2026-11-02", "attachments": ["brief.pdf"]}
    created = client.post("/api/v1/crm/tasks", headers=task_headers, json={
        "title": "Follow up", "description": "Customer context", "due_date": "2026-11-10T12:00:00Z", "task_details": details,
    })
    assert created.status_code == 201, created.text
    ident = created.json()["id"]
    db.expire_all()
    row = db.get(CRMTask, ident)
    assert row.task_details == details
    assert row.owner_user_id == row.created_by_user_id
    login = client.post("/api/v1/auth/login", json={"email": "testadmin@test.com", "password": "Admin@123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    listed = client.get("/api/v1/crm/tasks", headers=headers).json()["items"]
    assert next(t for t in listed if t["id"] == ident)["task_details"] == details
    updated = client.patch(f"/api/v1/crm/tasks/{ident}", headers=headers, json={"title": "Followed up", "status": "Done", "due_date": None, "task_details": {**details, "acceptance": "Approved"}})
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "Done"
    assert updated.json()["task_details"]["acceptance"] == "Approved"
    assert updated.json()["dueDate"] is None
    assert client.delete(f"/api/v1/crm/tasks/{ident}", headers=headers).status_code == 200
    assert ident not in [t["id"] for t in client.get("/api/v1/crm/tasks", headers=headers).json()["items"]]


def test_browser_import_is_retry_safe_including_after_delete(client, db, task_headers):
    payload = {"title": "Browser task", "import_key": "legacy-task-123", "task_details": {"workType": "Bug"}}
    first = client.post("/api/v1/crm/tasks", headers=task_headers, json=payload)
    assert first.status_code == 201, first.text
    ident = first.json()["id"]
    for _ in range(2):
        retry = client.post("/api/v1/crm/tasks", headers=task_headers, json=payload)
        assert retry.status_code == 201, retry.text
        assert retry.json()["id"] == ident
    assert db.query(CRMTask).filter_by(import_key=payload["import_key"]).count() == 1
    client.delete(f"/api/v1/crm/tasks/{ident}", headers=task_headers)
    assert client.post("/api/v1/crm/tasks", headers=task_headers, json=payload).json()["id"] == ident
    db.expire_all()
    assert db.get(CRMTask, ident).deleted_at is not None


def test_task_details_validation_and_tenant_isolation(client, db, task_headers):
    assert client.post("/api/v1/crm/tasks", headers=task_headers, json={"title": "Invalid", "task_details": []}).status_code == 422
    created = client.post("/api/v1/crm/tasks", headers=task_headers, json={"title": "Private tenant task"})
    assert created.status_code == 201, created.text
    ident = created.json()["id"]
    row = db.get(CRMTask, ident)
    row.organization_id = 987654
    db.commit()
    assert ident not in [t["id"] for t in client.get("/api/v1/crm/tasks", headers=task_headers).json()["items"]]
    for method, kwargs in ((client.get, {}), (client.patch, {"json": {"title": "Changed"}}), (client.delete, {})):
        assert method(f"/api/v1/crm/tasks/{ident}", headers=task_headers, **kwargs).status_code == 404


@pytest.mark.parametrize("path,parent", [
    ("alembic/versions/20261102_055_crm_task_sync.py", "20261101_054_service_currency"),
    ("alembic_postgresql/versions/pg_20261102_056_crm_task_sync.py", "pg_20261101_055_service_currency"),
])
def test_task_sync_migration_preserves_existing_tasks(path, parent):
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE crm_tasks (id INTEGER PRIMARY KEY, title TEXT, created_by_user_id INTEGER, organization_id INTEGER)"))
        connection.execute(sa.text("INSERT INTO crm_tasks VALUES (1, 'Existing task', 1, 1)"))
        spec = importlib.util.spec_from_file_location("crm_task_sync", Path(__file__).parents[1] / path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        assert migration.down_revision == parent
        assert len(migration.revision) <= 32
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        migration.upgrade()
        assert connection.execute(sa.text("SELECT title FROM crm_tasks WHERE id=1")).scalar() == "Existing task"
        connection.execute(sa.text("UPDATE crm_tasks SET task_details='{}', import_key='old-id' WHERE id=1"))
        assert connection.execute(sa.text("SELECT import_key FROM crm_tasks WHERE id=1")).scalar() == "old-id"
        migration.downgrade()
        assert connection.execute(sa.text("SELECT title FROM crm_tasks WHERE id=1")).scalar() == "Existing task"
    engine.dispose()
