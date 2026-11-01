from pathlib import Path
import importlib.util
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_communication_migration_preserves_unknown_and_conflicting_ownership():
    path = Path(__file__).parents[1] / "alembic_postgresql/versions/pg_20261101_051_communication_tenant.py"
    spec = importlib.util.spec_from_file_location("communication_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as c:
        for ddl in [
            "CREATE TABLE companies (id INTEGER PRIMARY KEY)",
            "CREATE TABLE security_resource_ownership (resource_table TEXT,resource_id INTEGER,company_id INTEGER)",
            "CREATE TABLE communication_whatsapp_templates (id INTEGER PRIMARY KEY)",
            "CREATE TABLE communication_email_templates (id INTEGER PRIMARY KEY,organization_id INTEGER)",
            "CREATE TABLE communication_auto_response_rules (id INTEGER PRIMARY KEY,template_id INTEGER)",
            "CREATE TABLE communication_webforms (id INTEGER PRIMARY KEY,auto_response_rule_id INTEGER)",
            "CREATE TABLE communication_timeline_events (record_type TEXT,record_id INTEGER,channel TEXT,event_type TEXT,organization_id INTEGER)",
            "INSERT INTO companies VALUES (1),(2)",
            "INSERT INTO communication_whatsapp_templates VALUES (1),(2)",
            "INSERT INTO communication_email_templates VALUES (10,1),(20,2)",
            "INSERT INTO communication_auto_response_rules VALUES (1,10),(2,NULL),(3,20)",
            "INSERT INTO communication_webforms VALUES (1,1),(2,NULL),(3,1),(4,NULL)",
            "INSERT INTO security_resource_ownership VALUES ('communication_whatsapp_templates',1,2),('communication_whatsapp_templates',2,1),('communication_whatsapp_templates',2,2),('communication_auto_response_rules',3,1)",
            "INSERT INTO communication_timeline_events VALUES ('webform',1,'webform','created',1),('webform',2,'webform','created',2),('webform',3,'webform','created',2)",
        ]:
            c.execute(sa.text(ddl))
        migration.op = Operations(MigrationContext.configure(c))
        migration.upgrade()
        assert c.execute(sa.text("SELECT organization_id FROM communication_whatsapp_templates ORDER BY id")).scalars().all() == [2, None]
        assert c.execute(sa.text("SELECT organization_id FROM communication_auto_response_rules ORDER BY id")).scalars().all() == [1, None, None]
        assert c.execute(sa.text("SELECT organization_id FROM communication_webforms ORDER BY id")).scalars().all() == [1, 2, None, None]
        migration.downgrade()
        assert c.execute(sa.text("SELECT count(*) FROM communication_webforms")).scalar_one() == 4
