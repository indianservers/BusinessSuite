"""Recovery ordering and fresh/existing PostgreSQL deployment contracts."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_operations(monkeypatch):
    # fcntl exists on the production Ubuntu host, but unit QA also runs on Windows.
    if sys.platform == "win32":
        monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(flock=Mock(), LOCK_EX=2))
    spec = importlib.util.spec_from_file_location("droplet_operations", ROOT / "deployment/digitalocean/operations.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("fail_dump,fail_upload", [(False, False), (True, False), (False, True)])
def test_backup_manifest_only_after_complete_recovery_set(monkeypatch, tmp_path, fail_dump, fail_upload):
    module = load_operations(monkeypatch)
    monkeypatch.setattr(module, "SHARED", tmp_path)
    (tmp_path / "uploads").mkdir()
    (tmp_path / "uploads/document.txt").write_text("private document")
    for name in ("backend", "frontend", "interns"):
        (tmp_path / f"{name}.env").write_text("setting=value")
    (tmp_path / "interns-config.js").write_text("window.__INTERNHUB_CONFIG__ = {};")
    (tmp_path / "backup.env").write_text("\n".join(f"{key}=test-value" for key in (
        "BACKUP_BUCKET", "BACKUP_ENDPOINT", "BACKUP_REGION", "BACKUP_ACCESS_KEY_ID", "BACKUP_SECRET_ACCESS_KEY")))
    from app.core.config import settings
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    import boto3
    client = Mock()
    monkeypatch.setattr(boto3, "client", lambda *a, **kw: client)
    if fail_upload:
        client.upload_file.side_effect = RuntimeError("upload failed")
    import postgres_backup
    monkeypatch.setattr(postgres_backup, "postgres_environment", lambda: {})
    monkeypatch.setattr(postgres_backup, "postgres_tool", lambda name: name)

    def run(args, **kwargs):
        if args[0] == "pg_dump":
            if fail_dump:
                raise RuntimeError("dump failed")
            Path(args[-1]).write_bytes(b"custom-format-dump")

    monkeypatch.setattr(module.subprocess, "run", run)
    if fail_dump or fail_upload:
        with pytest.raises(RuntimeError):
            module.backup()
        client.put_object.assert_not_called()
    else:
        module.backup()
        assert client.upload_file.call_count == 2
        manifest = json.loads(client.put_object.call_args.kwargs["Body"])
        assert set(manifest["files"]) == {"database.dump", "files.tar.gz"}
        assert all(len(item["sha256"]) == 64 for item in manifest["files"].values())
    assert not list(tmp_path.glob("backup-*")), "Temporary secrets must be cleaned up"


@pytest.mark.parametrize("has_version", [False, True])
def test_migration_accepts_fresh_and_existing_database(monkeypatch, has_version):
    from scripts import migrate_deployment as module
    import sqlalchemy
    import alembic.command
    import alembic.script
    connection = Mock()
    # Existing installations read before and after; new databases read only after.
    results = [["head"]] * (2 if has_version else 1)

    def execute(statement):
        result = Mock()
        if "SELECT version_num" in str(statement):
            result.scalars.return_value.all.return_value = results.pop(0)
        return result

    connection.execute.side_effect = execute
    engine = Mock()
    engine.connect.return_value.__enter__ = Mock(return_value=connection)
    engine.connect.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *a, **kw: engine)
    monkeypatch.setattr(sqlalchemy, "inspect", lambda conn: SimpleNamespace(has_table=lambda _: has_version))
    monkeypatch.setattr(alembic.script.ScriptDirectory, "from_config", lambda config: SimpleNamespace(get_current_head=lambda: "head"))
    upgrade = Mock()
    monkeypatch.setattr(alembic.command, "upgrade", upgrade)
    module.main()
    upgrade.assert_called_once()
    assert upgrade.call_args.args[1] == "head"


def test_real_fresh_postgresql_release_matches_models(db_engine, monkeypatch):
    """Run every migration in an isolated schema; never alter application tables."""
    if db_engine.dialect.name != "postgresql":
        pytest.skip("Requires disposable PostgreSQL test database")
    assert db_engine.url.database.endswith("_test")
    from scripts import migrate_deployment
    from app.db.base import Base
    from sqlalchemy import inspect, text
    import sqlalchemy
    original_create_engine = sqlalchemy.create_engine

    def isolated_engine(*args, **kwargs):
        kwargs["connect_args"] = {**kwargs.get("connect_args", {}), "options": "-c search_path=droplet_fresh_test"}
        return original_create_engine(*args, **kwargs)

    monkeypatch.setattr(sqlalchemy, "create_engine", isolated_engine)
    with db_engine.connect() as db:
        db.execute(text("CREATE SCHEMA droplet_fresh_test"))
        db.execute(text("SET search_path TO droplet_fresh_test"))
        db.commit()
        try:
            migrate_deployment.main()
            # Exercise the idempotent deploy path against an existing database too.
            migrate_deployment.main()
            inspector = inspect(db)
            tables = set(inspector.get_table_names(schema="droplet_fresh_test"))
            missing = set(Base.metadata.tables) - tables
            assert not missing, f"Models lack production migrations: {sorted(missing)}"
            for table in Base.metadata.tables.values():
                actual = {col["name"] for col in inspector.get_columns(table.name, schema="droplet_fresh_test")}
                assert {col.name for col in table.columns} <= actual, table.name
        finally:
            db.rollback()
            db.execute(text("SET search_path TO public"))
            db.execute(text("DROP SCHEMA droplet_fresh_test CASCADE"))
            db.commit()
