"""The additive migration preserves legacy draft and execution tables and their data."""

import importlib.util
from pathlib import Path
from sqlalchemy import create_engine, text, inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_runtime_migration_preserves_drafts_versions_and_is_idempotent():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic_postgresql/versions/pg_20261027_035_power_runtime.py"
    )
    spec = importlib.util.spec_from_file_location("runtime_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        for name in [
            "companies",
            "users",
            "power_apps_resources",
            "power_apps_versions",
            "power_apps_executions",
        ]:
            connection.execute(
                text(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY, payload TEXT)")
            )
            connection.execute(
                text(
                    f"INSERT INTO {name} (id,payload) VALUES (1,'retained legacy data')"
                )
            )
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        module.upgrade()
        assert "power_automation_jobs" in inspect(connection).get_table_names()
        assert {"kind", "event_key", "wake_at"} <= {
            c["name"] for c in inspect(connection).get_columns("power_automation_waits")
        }
        for name in [
            "companies",
            "users",
            "power_apps_resources",
            "power_apps_versions",
            "power_apps_executions",
        ]:
            assert (
                connection.execute(text(f"SELECT payload FROM {name}")).scalar()
                == "retained legacy data"
            )
        module.downgrade()
        assert "power_automation_jobs" not in inspect(connection).get_table_names()
        assert (
            connection.execute(
                text("SELECT payload FROM power_apps_resources")
            ).scalar()
            == "retained legacy data"
        )
