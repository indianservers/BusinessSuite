from datetime import datetime, timedelta
import json
import zipfile
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from fastapi import HTTPException

from tests.test_pms_automations import setup_workspace
from tests.test_pms_workspaces import middleware_database, BASE, account
from app.apps.project_management.models import PMSTask, PMSWorkspaceMember
from app.apps.project_management.recovery import run_due
from app.apps.project_management.recovery_models import RecoveryPoint, RecoveryPolicy


@pytest.fixture(autouse=True)
def isolated_audit(db):
    from app.main import app

    app.state.audit_session_factory = lambda: db
    app.state.audit_close_session = False
    app.state.audit_commit = False
    yield
    for key in ("audit_session_factory", "audit_close_session", "audit_commit"):
        delattr(app.state, key)


def task(client, pid, headers):
    response = client.post(
        f"{BASE}/projects/{pid}/tasks",
        headers=headers,
        json={
            "title": "Original",
            "task_key": "RC-" + uuid4().hex[:8],
            "description": "Initial text",
            "status": "To Do",
            "priority": "Medium",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_undo_redo_branch_conflict_and_softdelete(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    tid = task(client, pid, mh)
    path = f"{BASE}/workspaces/{wid}/recovery"
    for title in ["First edit", "Second edit"]:
        assert (
            client.patch(
                f"{BASE}/tasks/{tid}", headers=mh, json={"title": title}
            ).status_code
            == 200
        )
    assert client.post(path + "/actions/undo", headers=mh).status_code == 200
    assert db.get(PMSTask, tid).title == "First edit"
    assert client.post(path + "/actions/undo", headers=mh).status_code == 200
    assert db.get(PMSTask, tid).title == "Original"
    assert client.post(path + "/actions/redo", headers=mh).status_code == 200
    assert db.get(PMSTask, tid).title == "First edit"
    client.patch(f"{BASE}/tasks/{tid}", headers=mh, json={"title": "New branch"})
    assert client.post(path + "/actions/redo", headers=mh).status_code == 409
    # Concurrent teammate work must not be silently overwritten.
    client.patch(f"{BASE}/tasks/{tid}", headers=oh, json={"title": "Teammate change"})
    response = client.post(path + "/actions/undo", headers=mh)
    assert response.status_code == 409, response.text
    assert db.get(PMSTask, tid).title == "Teammate change"
    assert client.delete(f"{BASE}/tasks/{tid}", headers=oh).status_code == 200
    assert db.get(PMSTask, tid).deleted_at
    assert client.post(path + "/actions/undo", headers=oh).status_code == 200
    assert not db.get(PMSTask, tid).deleted_at
    assert client.post(path + "/actions/redo", headers=oh).status_code == 200
    assert db.get(PMSTask, tid).deleted_at
    assert client.get(path + "/history", headers=gh).status_code == 403


def test_undo_creation_and_assignment_revocation(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    tid = task(client, pid, mh)
    path = f"{BASE}/workspaces/{wid}/recovery"
    assert client.post(path + "/actions/undo", headers=mh).status_code == 200
    assert db.get(PMSTask, tid).deleted_at
    assert client.post(path + "/actions/redo", headers=mh).status_code == 200
    assert not db.get(PMSTask, tid).deleted_at
    client.patch(
        f"{BASE}/tasks/{tid}", headers=mh, json={"assignee_user_ids": [member.id]}
    )
    client.patch(f"{BASE}/tasks/{tid}", headers=mh, json={"assignee_user_ids": []})
    membership = (
        db.query(PMSWorkspaceMember)
        .filter_by(workspace_id=wid, user_id=member.id)
        .one()
    )
    membership.role = "Guest"
    db.commit()
    # Former members cannot recover their permissions through task history.
    assert client.post(path + "/actions/undo", headers=oh).status_code == 409
    assert client.post(path + "/actions/undo", headers=mh).status_code == 403


def test_undo_refuses_to_reassign_removed_member(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    tid = task(client, pid, oh)
    client.patch(
        f"{BASE}/tasks/{tid}", headers=oh, json={"assignee_user_ids": [member.id]}
    )
    client.patch(f"{BASE}/tasks/{tid}", headers=oh, json={"assignee_user_ids": []})
    membership = (
        db.query(PMSWorkspaceMember)
        .filter_by(workspace_id=wid, user_id=member.id)
        .one()
    )
    db.delete(membership)
    db.commit()
    response = client.post(f"{BASE}/workspaces/{wid}/recovery/actions/undo", headers=oh)
    assert response.status_code == 409, response.text
    assert not db.get(PMSTask, tid).assignee_user_ids


def test_structural_change_is_not_partially_undone(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    tid = task(client, pid, mh)
    client.patch(f"{BASE}/tasks/{tid}", headers=mh, json={"title": "An edit"})
    client.patch(f"{BASE}/tasks/{tid}", headers=mh, json={"actual_hours": "12.50"})
    response = client.post(f"{BASE}/workspaces/{wid}/recovery/actions/undo", headers=mh)
    assert response.status_code == 409, response.text
    assert db.get(PMSTask, tid).title == "An edit"


def test_savepoint_preview_safety_scope_and_permissions(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    tid = task(client, pid, mh)
    path = f"{BASE}/workspaces/{wid}/recovery"
    for headers in (mh, gh):
        assert (
            client.post(
                path + "/savepoints", headers=headers, json={"name": "Checkpoint"}
            ).status_code
            == 403
        )
    response = client.post(
        path + "/savepoints", headers=ah, json={"name": "Checkpoint"}
    )
    assert response.status_code == 201, response.text
    saved = response.json()["id"]
    client.patch(
        f"{BASE}/tasks/{tid}",
        headers=mh,
        json={"title": "Newer work", "status": "Done"},
    )
    new_id = task(client, pid, mh)
    preview_path = path + f"/savepoints/{saved}/preview"
    preview = client.get(preview_path, headers=oh).json()
    assert preview["changed_tasks"] == 1 and preview["newer_tasks_kept"] == 1
    body = {
        "confirm_name": "wrong",
        "expected_current_hash": preview["expected_current_hash"],
    }
    assert (
        client.post(
            path + f"/savepoints/{saved}/restore", headers=oh, json=body
        ).status_code
        == 422
    )
    workspace_name = client.get(BASE + "/workspaces", headers=oh).json()[0]["name"]
    body["confirm_name"] = workspace_name
    # A task changed after preview, including by the caller.
    client.patch(
        f"{BASE}/tasks/{tid}", headers=mh, json={"description": "Changed again"}
    )
    assert (
        client.post(
            path + f"/savepoints/{saved}/restore", headers=oh, json=body
        ).status_code
        == 409
    )
    body["expected_current_hash"] = client.get(preview_path, headers=oh).json()[
        "expected_current_hash"
    ]
    response = client.post(path + f"/savepoints/{saved}/restore", headers=oh, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["safety_savepoint_id"] != saved
    assert (
        db.get(PMSTask, tid).title == "Original"
        and db.get(PMSTask, tid).status == "To Do"
    )
    assert not db.get(PMSTask, new_id).deleted_at
    exported = client.get(path + f"/savepoints/{saved}/download", headers=oh)
    assert exported.status_code == 200
    data = exported.json()
    assert data["workspace_id"] == wid and len(data["tables"]["pms_tasks"]) == 1
    assert "users" not in data["tables"] and "pms_direct_messages" not in data["tables"]
    _, outsider_headers = account(db, "recovery-outsider@test.com", True)
    assert client.get(path, headers=outsider_headers).status_code == 404
    assert (
        client.get(path + f"/savepoints/{saved}/download", headers=mh).status_code
        == 403
    )
    point = db.get(RecoveryPoint, saved)
    point.checksum = "0" * 64
    db.commit()
    assert (
        client.get(path + f"/savepoints/{saved}/download", headers=oh).status_code
        == 409
    )


def test_automatic_schedule_retention_and_role_recheck(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = f"{BASE}/workspaces/{wid}/recovery"
    task(client, pid, oh)
    client.post(path + "/savepoints", headers=oh, json={"name": "Keep manual"})
    assert (
        client.put(
            path + "/policy",
            headers=oh,
            json={"enabled": True, "interval_hours": 1, "retain_automatic": 2},
        ).status_code
        == 200
    )
    start = datetime.utcnow()
    assert len(run_due(db, start)) == 1
    assert run_due(db, start + timedelta(minutes=30)) == []
    for hour in range(1, 4):
        assert len(run_due(db, start + timedelta(hours=hour))) == 1
    assert (
        db.query(RecoveryPoint).filter_by(workspace_id=wid, automatic=True).count() == 2
    )
    assert (
        db.query(RecoveryPoint).filter_by(workspace_id=wid, automatic=False).count()
        == 1
    )
    policy = db.get(RecoveryPolicy, wid)
    policy.actor_id = member.id  # policy setter loses admin access
    db.commit()
    assert run_due(db, start + timedelta(hours=5)) == []


def test_full_archive_roundtrip_schedule_and_integrity(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.services.data_backups import (
        create_archive,
        verify_archive,
        extract_archive,
        run_full_due,
        write_policy,
    )

    backup_dir = tmp_path / "backups"
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "contract.txt").write_text("Important attachment")
    monkeypatch.setenv("BUSINESSSUITE_BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(uploads))
    monkeypatch.setattr(settings, "SERVERLESS", False)
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    engine = create_engine("sqlite:///" + (tmp_path / "live.sqlite3").as_posix())
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE all_module_data (value TEXT)"))
        connection.execute(text("INSERT INTO all_module_data VALUES ('preserved')"))
    info = create_archive(engine, actor_id=7)
    archive = backup_dir / (info["id"] + ".zip")
    assert verify_archive(archive)["actor_id"] == 7
    restored = extract_archive(archive, tmp_path / "restored")
    recovered = create_engine("sqlite:///" + (restored / "database.sqlite3").as_posix())
    with recovered.connect() as connection:
        assert (
            connection.execute(text("SELECT value FROM all_module_data")).scalar()
            == "preserved"
        )
    assert (restored / "uploads/contract.txt").read_text() == "Important attachment"
    with pytest.raises(FileExistsError):
        extract_archive(archive, restored)
    write_policy(
        backup_dir,
        {
            "enabled": True,
            "interval_hours": 24,
            "retain_automatic": 2,
            "last_success_at": None,
        },
    )
    assert run_full_due(engine)["automatic"]
    assert run_full_due(engine) is None
    # Corrupt a file with a valid ZIP CRC: SHA-256 still detects tampering.
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(bad, "w") as target:
        for name in source.namelist():
            target.writestr(
                name,
                b"changed" if name == "uploads/contract.txt" else source.read(name),
            )
    with pytest.raises(ValueError, match="checksum"):
        verify_archive(bad)
    from app.services.data_backups import archive_catalog, full_download

    corrupt_id = "f" * 32
    (backup_dir / (corrupt_id + ".zip")).write_bytes(b"invalid archive")
    assert (
        next(item for item in archive_catalog(backup_dir) if item["id"] == corrupt_id)[
            "state"
        ]
        == "unreadable"
    )
    with pytest.raises(HTTPException) as corrupt:
        full_download(corrupt_id, user=None)
    assert corrupt.value.status_code == 409
    (backup_dir / ".backup.lock").write_text("Other worker")
    with pytest.raises(HTTPException) as error:
        create_archive(engine)
    assert error.value.status_code == 409
    engine.dispose()
    recovered.dispose()


def test_s3_backup_streams_authoritative_objects_and_fails_closed(
    tmp_path, monkeypatch
):
    import io
    from app.core.config import settings
    from app.core import storage
    from app.services.data_backups import create_archive, verify_archive

    monkeypatch.setenv("BUSINESSSUITE_BACKUP_DIR", str(tmp_path / "archives"))
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "SERVERLESS", False)
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "S3_PREFIX", "suite")

    class FakeS3:
        fail = False

        def get_paginator(self, name):
            return self

        def paginate(self, **kwargs):
            assert kwargs["Prefix"] == "suite/"
            yield {"Contents": [{"Key": "suite/documents/a.txt"}]}

        def get_object(self, **kwargs):
            if self.fail:
                raise RuntimeError("Provider down")
            return {"Body": io.BytesIO(b"cloud document")}

    s3 = FakeS3()
    monkeypatch.setattr(storage, "s3_client", lambda: s3)
    engine = create_engine("sqlite:///" + (tmp_path / "db.sqlite3").as_posix())
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE records (id INTEGER)"))
    result = create_archive(engine)
    path = tmp_path / "archives" / (result["id"] + ".zip")
    manifest = verify_archive(path)
    assert not manifest["local_uploads_only"]
    with zipfile.ZipFile(path) as archive:
        assert archive.read("uploads/documents/a.txt") == b"cloud document"
    s3.fail = True
    with pytest.raises(RuntimeError, match="Provider down"):
        create_archive(engine)
    assert len(list((tmp_path / "archives").glob("*.zip"))) == 1
    assert not (tmp_path / "archives/.backup.lock").exists()
    engine.dispose()


def test_full_backup_only_system_admin_and_no_serverless_success(
    client, db, monkeypatch
):
    from app.core.config import settings

    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    assert client.get(BASE + "/data-backups", headers=mh).status_code == 403
    monkeypatch.setattr(settings, "SERVERLESS", True)
    response = client.post(BASE + "/data-backups", headers=oh)
    assert response.status_code == 503
    assert "durable" in response.json()["detail"]


def test_vercel_blob_streaming_uses_configured_private_prefix(tmp_path, monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace
    from app.core.config import settings
    from app.core import storage
    import vercel.blob.sync as blob
    from app.services.data_backups import create_archive, verify_archive

    monkeypatch.setenv("BUSINESSSUITE_BACKUP_DIR", str(tmp_path / "archives"))
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "SERVERLESS", False)
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "vercel_blob")
    monkeypatch.setattr(settings, "S3_PREFIX", "suite")
    monkeypatch.setattr(storage, "blob_session", lambda: nullcontext())

    def objects(**kwargs):
        assert kwargs["prefix"] == "suite/"
        return iter([SimpleNamespace(pathname="suite/photos/profile.png")])

    def stream(path, **kwargs):
        assert path == "suite/photos/profile.png" and kwargs["access"] == "private"
        return nullcontext(iter([b"private ", b"photo"]))

    monkeypatch.setattr(blob, "query_blobs", objects)
    monkeypatch.setattr(blob, "stream_blob", stream)
    engine = create_engine("sqlite:///" + (tmp_path / "db.sqlite3").as_posix())
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE records (id INTEGER)"))
    result = create_archive(engine)
    path = tmp_path / "archives" / (result["id"] + ".zip")
    assert verify_archive(path)["storage_backend"] == "vercel_blob"
    with zipfile.ZipFile(path) as archive:
        assert archive.read("uploads/photos/profile.png") == b"private photo"
    engine.dispose()


def test_recovery_migrations_are_additive_and_replayable(tmp_path):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect

    engine = create_engine("sqlite:///" + (tmp_path / "old.sqlite3").as_posix())
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE pms_workspaces (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE pms_tasks (id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO pms_workspaces VALUES (42)"))
        for folder, prefix in (("alembic", ""), ("alembic_postgresql", "pg_")):
            path = (
                Path(__file__).parents[1]
                / folder
                / "versions"
                / f"{prefix}20261024_008_recovery.py"
            )
            spec = importlib.util.spec_from_file_location(
                "test_recovery_migration", path
            )
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.upgrade()
                migration.downgrade()
        assert {
            "pms_recovery_changes",
            "pms_recovery_points",
            "pms_recovery_policies",
        }.issubset(inspect(connection).get_table_names())
        assert connection.execute(text("SELECT id FROM pms_workspaces")).scalar() == 42
    engine.dispose()


def test_scheduled_worker_starts_in_a_fresh_process(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path

    path = tmp_path / "worker.sqlite3"
    engine = create_engine("sqlite:///" + path.as_posix())
    RecoveryPolicy.__table__.create(engine)
    engine.dispose()
    backend = Path(__file__).parents[1]
    env = dict(
        os.environ,
        DATABASE_URL="sqlite:///" + path.as_posix(),
        ENVIRONMENT="test",
        SERVERLESS="false",
        INSTALLED_APPS="hrms,crm,project_management,srm,fam",
        STORAGE_BACKEND="local",
        BUSINESSSUITE_BACKUP_DIR=str(tmp_path / "backups"),
        UPLOAD_DIR=str(tmp_path / "uploads"),
    )
    result = subprocess.run(
        [sys.executable, "scripts/data_recovery.py", "--due"],
        cwd=backend,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert (
        "'workspace_savepoints': []" in result.stdout
        and "'full_backup': None" in result.stdout
    )
