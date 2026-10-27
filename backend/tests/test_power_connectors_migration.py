"""Frozen additive migration parity, repeatability and preservation checks."""

import importlib.util
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text, inspect
from alembic.operations import Operations
from alembic.migration import MigrationContext


@pytest.mark.parametrize(
    "directory,prefix", [("alembic", ""), ("alembic_postgresql", "pg_")]
)
def test_integrations_migration_is_additive_and_repeatable(directory, prefix):
    path = (
        Path(__file__).resolve().parents[1]
        / directory
        / "versions"
        / f"{prefix}20261027_036_integrations.py"
    )
    spec = importlib.util.spec_from_file_location(
        "integration_migration_" + directory, path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        for table in [
            "companies",
            "users",
            "power_apps_executions",
            "power_automation_steps",
            "power_apps_resources",
        ]:
            connection.execute(
                text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY,payload TEXT)")
            )
            connection.execute(
                text(f"INSERT INTO {table} VALUES (1,'existing record')")
            )
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        module.upgrade()
        names = inspect(connection).get_table_names()
        assert len([name for name in names if name.startswith("power_connector_")]) == 9
        columns = {
            column["name"]
            for column in inspect(connection).get_columns("power_connector_credentials")
        }
        assert "encrypted_value" in columns and "access_token" not in columns
        assert (
            connection.execute(
                text("SELECT payload FROM power_apps_resources")
            ).scalar()
            == "existing record"
        )
        module.downgrade()
        module.downgrade()
        assert not any(
            name.startswith("power_connector_")
            for name in inspect(connection).get_table_names()
        )
        assert (
            connection.execute(
                text("SELECT payload FROM power_apps_resources")
            ).scalar()
            == "existing record"
        )
    engine.dispose()
