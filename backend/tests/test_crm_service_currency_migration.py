"""Regress the production schema gap when the prior revision is already applied."""
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


@pytest.mark.parametrize("path,parent", [
    ("alembic_postgresql/versions/pg_20261101_055_service_currency.py", "pg_20261101_054_deal_workspace"),
    ("alembic/versions/20261101_054_service_currency.py", "20261101_053_deal_workspace"),
])
@pytest.mark.parametrize("already_present", [False, True])
def test_followup_repairs_applied_workspace_revision_without_replacing_services(path, parent, already_present):
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        currency = ", currency VARCHAR(10) DEFAULT 'INR'" if already_present else ""
        connection.execute(sa.text("CREATE TABLE crm_services (id INTEGER PRIMARY KEY, name TEXT, unit_price NUMERIC" + currency + ")"))
        connection.execute(sa.text("INSERT INTO crm_services(id,name,unit_price) VALUES (1,'Existing service',1200)"))
        if already_present:
            connection.execute(sa.text("UPDATE crm_services SET currency='USD' WHERE id=1"))
        connection.execute(sa.text("CREATE TABLE alembic_version(version_num VARCHAR(32))"))
        connection.execute(sa.text("INSERT INTO alembic_version VALUES(:revision)"), {"revision": parent})
        spec = importlib.util.spec_from_file_location("service_currency_followup", Path(__file__).parents[1] / path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        assert migration.down_revision == parent
        assert len(migration.revision) <= 32
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        migration.upgrade()
        row = connection.execute(sa.text("SELECT id,name,unit_price,currency FROM crm_services")).mappings().one()
        assert dict(row) == {"id": 1, "name": "Existing service", "unit_price": 1200, "currency": "USD" if already_present else "INR"}
        connection.execute(sa.text("INSERT INTO crm_services(id,name,unit_price) VALUES(2,'New service',500)"))
        assert connection.execute(sa.text("SELECT currency FROM crm_services WHERE id=2")).scalar() == "INR"
        migration.downgrade()
        assert connection.execute(sa.text("SELECT count(*) FROM crm_services")).scalar() == 2
        assert connection.execute(sa.text("SELECT currency FROM crm_services WHERE id=1")).scalar() == ("USD" if already_present else "INR")
    engine.dispose()
