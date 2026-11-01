from unittest.mock import Mock
import pytest
from scripts.migrate_deployment import migration_url, migration_lock, MIGRATION_LOCK_ID


def test_neon_migrations_use_direct_host_without_changing_credentials(monkeypatch):
    monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)
    url = migration_url("postgresql+psycopg://fixture:fixture@ep-example-pooler.us-east-1.aws.neon.tech/reporting?sslmode=require")
    assert url.host == "ep-example.us-east-1.aws.neon.tech"
    assert url.username == "fixture" and url.password == "fixture"
    assert url.database == "reporting" and url.query["sslmode"] == "require"


def test_other_postgres_hosts_are_preserved(monkeypatch):
    monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)
    assert migration_url("postgresql://fixture:fixture@custom-pooler.example/reporting").host == "custom-pooler.example"


def test_explicit_migration_connection_takes_precedence(monkeypatch):
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://fixture:fixture@direct.example/reporting")
    assert migration_url("postgresql://fixture:fixture@runtime.example/reporting").host == "direct.example"


@pytest.mark.parametrize("fail", [False, True])
def test_session_lock_is_released_after_success_or_failed_migration(fail):
    connection = Mock()
    def run():
        with migration_lock(connection):
            connection.commit()
            if fail:
                raise RuntimeError("fixture migration failed")
    if fail:
        with pytest.raises(RuntimeError, match="fixture migration failed"):
            run()
    else:
        run()
    statements = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert statements == ["SET lock_timeout = '60s'", f"SELECT pg_advisory_lock({MIGRATION_LOCK_ID})", f"SELECT pg_advisory_unlock({MIGRATION_LOCK_ID})"]
    connection.rollback.assert_called_once()
    assert connection.commit.call_count == 2


def test_lock_acquisition_failure_does_not_unlock_an_unowned_lock():
    connection = Mock()
    connection.execute.side_effect = [None, TimeoutError("fixture lock timeout")]
    with pytest.raises(TimeoutError):
        with migration_lock(connection):
            pytest.fail("Should not start migrating")
    connection.rollback.assert_not_called()
    assert connection.execute.call_count == 2


def test_direct_session_migration_can_run_while_legacy_pooled_lock_is_orphaned():
    connection = Mock()
    def execute(statement):
        sql = str(statement)
        if sql == "SELECT pg_advisory_lock(827460231)":
            raise TimeoutError("Legacy pooled session still owns this lock")
        assert sql != "SELECT pg_advisory_unlock(827460231)", "Do not release another deployment's lock"
    connection.execute.side_effect = execute
    with migration_lock(connection):
        connection.commit()
    connection.rollback.assert_called_once()
