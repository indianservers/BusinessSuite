import importlib.util
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text, inspect
from alembic.operations import Operations
from alembic.migration import MigrationContext


@pytest.mark.parametrize(
    "directory,prefix", [("alembic", ""), ("alembic_postgresql", "pg_")]
)
def test_approval_metadata_migration_preserves_existing_requests(directory, prefix):
    path = (
        Path(__file__).resolve().parents[1]
        / directory
        / "versions"
        / f"{prefix}20261027_037_approvals.py"
    )
    spec = importlib.util.spec_from_file_location(
        "approvals_migration_" + directory, path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        for name in [
            "companies",
            "users",
            "roles",
            "approval_requests",
            "power_apps_resources",
            "power_apps_versions",
            "power_apps_executions",
            "power_automation_steps",
        ]:
            connection.execute(
                text(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY,payload TEXT)")
            )
            connection.execute(
                text(f"INSERT INTO {name} VALUES (1,'preserved record')")
            )
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        module.upgrade()
        assert (
            len(
                [
                    name
                    for name in inspect(connection).get_table_names()
                    if name.startswith("power_approval_")
                ]
            )
            == 5
        )
        assert (
            connection.execute(text("SELECT payload FROM approval_requests")).scalar()
            == "preserved record"
        )
        module.downgrade()
        module.downgrade()
        assert (
            connection.execute(text("SELECT payload FROM approval_requests")).scalar()
            == "preserved record"
        )
        assert not any(
            name.startswith("power_approval_")
            for name in inspect(connection).get_table_names()
        )
    engine.dispose()
