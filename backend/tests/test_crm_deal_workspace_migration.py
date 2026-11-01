import importlib.util
from pathlib import Path
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


@pytest.mark.parametrize("path", ["alembic/versions/20261101_053_deal_workspace.py", "alembic_postgresql/versions/pg_20261101_054_deal_workspace.py"])
def test_workspace_migrations_preserve_records_backfill_and_downgrade(path):
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE crm_services (id INTEGER PRIMARY KEY, name TEXT)"))
        connection.execute(sa.text("INSERT INTO crm_services VALUES(1,'Existing service')"))
        connection.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(sa.text("CREATE TABLE crm_pipeline_stages (id INTEGER PRIMARY KEY)"))
        connection.execute(sa.text("CREATE TABLE crm_deals (id INTEGER PRIMARY KEY, organization_id INTEGER, name TEXT, last_activity_at TIMESTAMP)"))
        connection.execute(sa.text("CREATE TABLE crm_tasks (id INTEGER PRIMARY KEY, deal_id INTEGER, organization_id INTEGER, created_at TIMESTAMP)"))
        connection.execute(sa.text("INSERT INTO crm_deals(id,organization_id,name) VALUES(1,1,'Existing customer deal')"))
        connection.execute(sa.text("INSERT INTO crm_tasks VALUES(1,1,1,'2026-10-15 12:00:00'),(2,1,999,'2026-10-30 12:00:00')"))
        spec = importlib.util.spec_from_file_location("deal_workspace_migration", Path(__file__).parents[1] / path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        module.upgrade()
        item = connection.execute(sa.text("SELECT name, priority, version, last_activity_at FROM crm_deals WHERE id=1")).mappings().one()
        assert item["name"] == "Existing customer deal"
        assert item["priority"] == "Medium"
        assert item["version"] == 1
        assert str(item["last_activity_at"]).startswith("2026-10-15")
        assert connection.execute(sa.text("SELECT currency FROM crm_services WHERE id=1")).scalar() == "INR"
        assert sa.inspect(connection).has_table("crm_deal_collaborators")
        module.downgrade()
        assert connection.execute(sa.text("SELECT name FROM crm_deals WHERE id=1")).scalar() == "Existing customer deal"
        assert connection.execute(sa.text("SELECT name FROM crm_services WHERE id=1")).scalar() == "Existing service"
        assert "currency" not in {column["name"] for column in sa.inspect(connection).get_columns("crm_services")}
        assert "planning" not in {column["name"] for column in sa.inspect(connection).get_columns("crm_deals")}
    engine.dispose()
