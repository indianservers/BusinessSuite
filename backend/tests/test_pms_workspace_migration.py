"""Upgrade an existing project table and verify bootstrap compatibility."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


def test_workspace_migration_preserves_projects():
    path = Path(__file__).parents[1] / "alembic/versions/20261022_001_pms_workspaces.py"
    spec = importlib.util.spec_from_file_location("workspace_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(sa.text("CREATE TABLE pms_projects (id INTEGER PRIMARY KEY, name VARCHAR(180))"))
        connection.execute(sa.text("INSERT INTO pms_projects (id, name) VALUES (1, 'Existing project')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
            assert connection.execute(sa.text("SELECT name, workspace_id FROM pms_projects")).one() == ("Existing project", None)
            assert sa.inspect(connection).get_foreign_keys("pms_projects")[0]["referred_table"] == "pms_workspaces"
            migration.downgrade()
            assert connection.execute(sa.text("SELECT name FROM pms_projects")).scalar() == "Existing project"
    engine.dispose()
