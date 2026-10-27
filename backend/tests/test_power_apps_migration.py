import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

def test_power_apps_migration_is_additive_and_round_trips():
    path = Path(__file__).resolve().parents[1] / "alembic_postgresql/versions/pg_20261027_032_power_apps.py"
    spec = importlib.util.spec_from_file_location("power_apps_migration", path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.exec_driver_sql("CREATE TABLE companies (id INTEGER PRIMARY KEY, name TEXT)")
        c.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        c.exec_driver_sql("CREATE TABLE permissions (id INTEGER PRIMARY KEY, name TEXT, description TEXT, module TEXT)")
        c.exec_driver_sql("INSERT INTO companies VALUES (1,'Alpha'),(2,'Beta')")
        migration.op = Operations(MigrationContext.configure(c))
        migration.upgrade()
        assert len([t for t in inspect(c).get_table_names() if t.startswith("power_apps_")]) == 5
        assert c.execute(text("SELECT organization_id,key,enabled FROM power_apps_environments ORDER BY organization_id")).all() == [(1,"development",1),(2,"development",1)]
        assert c.execute(text("SELECT count(*) FROM permissions WHERE module='power_apps'")).scalar() == 9
        assert c.execute(text("SELECT count(*) FROM power_apps_resources")).scalar() == 0
        assert c.execute(text("SELECT count(*) FROM power_apps_executions")).scalar() == 0
        migration.downgrade()
        assert not [t for t in inspect(c).get_table_names() if t.startswith("power_apps_")]
        assert c.execute(text("SELECT name FROM companies ORDER BY id")).scalars().all() == ["Alpha", "Beta"]
        migration.upgrade()
        assert c.execute(text("SELECT count(*) FROM permissions")).scalar() == 9
    engine.dispose()
