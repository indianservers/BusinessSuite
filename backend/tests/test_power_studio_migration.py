import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

def test_studio_migration_keeps_existing_drafts_and_round_trips():
    path = Path(__file__).resolve().parents[1] / "alembic_postgresql/versions/pg_20261027_033_power_studio.py"
    spec = importlib.util.spec_from_file_location("studio_migration", path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.exec_driver_sql("CREATE TABLE power_apps_resources (id INTEGER PRIMARY KEY,organization_id INTEGER,environment TEXT,name TEXT,definition TEXT)")
        c.exec_driver_sql("INSERT INTO power_apps_resources VALUES (1,1,'development','Existing Phase 1 draft','{\"schema_version\":1}')")
        migration.op = Operations(MigrationContext.configure(c))
        migration.upgrade()
        assert "archived_at" in {column["name"] for column in inspect(c).get_columns("power_apps_resources")}
        assert c.execute(text("SELECT name, archived_at FROM power_apps_resources")).one() == ("Existing Phase 1 draft", None)
        migration.downgrade()
        assert "archived_at" not in {column["name"] for column in inspect(c).get_columns("power_apps_resources")}
        migration.upgrade()
        assert c.execute(text("SELECT definition FROM power_apps_resources")).scalar() == '{"schema_version":1}'
    engine.dispose()


def test_concurrent_pms_prerequisite_accepts_existing_columns_and_preserves_scopes():
    path = Path(__file__).resolve().parents[1] / "alembic_postgresql/versions/pg_20261027_034_custom_columns.py"
    spec = importlib.util.spec_from_file_location("prerequisite_migration", path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.exec_driver_sql("CREATE TABLE pms_projects (id INTEGER PRIMARY KEY, organization_id INTEGER)")
        c.exec_driver_sql("INSERT INTO pms_projects VALUES (10,1)")
        c.exec_driver_sql("CREATE TABLE pms_custom_fields (id INTEGER PRIMARY KEY, project_id INTEGER, name TEXT, organization_id INTEGER, scope_key VARCHAR(80), entity_type VARCHAR(12) NOT NULL DEFAULT 'task', archived BOOLEAN NOT NULL DEFAULT false)")
        c.exec_driver_sql("INSERT INTO pms_custom_fields VALUES (1,10,'Legacy',NULL,NULL,'task',false),(2,NULL,'Company field',2,'company:2','task',false)")
        migration.op = Operations(MigrationContext.configure(c)); migration.upgrade(); migration.upgrade()
        assert c.execute(text("SELECT organization_id,scope_key FROM pms_custom_fields WHERE id=1")).one() == (1,"project:10")
        assert c.execute(text("SELECT organization_id,scope_key FROM pms_custom_fields WHERE id=2")).one() == (2,"company:2")
        assert "pms_project_custom_field_values" in inspect(c).get_table_names()
    engine.dispose()
