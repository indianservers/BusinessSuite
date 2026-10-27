import importlib.util
from pathlib import Path
import pytest
from sqlalchemy import create_engine, inspect, text
from alembic.migration import MigrationContext
from alembic.operations import Operations


@pytest.mark.parametrize(
    "folder,prefix", [("alembic", ""), ("alembic_postgresql", "pg_")]
)
@pytest.mark.parametrize("companies", [1, 2])
def test_security_state_migration_preserves_records_and_never_guesses_multi_company_ownership(
    folder, prefix, companies
):
    engine = create_engine("sqlite://")
    path = (
        Path(__file__).resolve().parents[1]
        / folder
        / "versions"
        / (prefix + "20261027_030_security_boundary.py")
    )
    spec = importlib.util.spec_from_file_location("security_state_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as c:
        c.exec_driver_sql("CREATE TABLE companies (id INTEGER PRIMARY KEY, name TEXT)")
        c.exec_driver_sql("INSERT INTO companies VALUES (1, 'Alpha')")
        if companies == 2:
            c.exec_driver_sql("INSERT INTO companies VALUES (2, 'Beta')")
        c.exec_driver_sql(
            "CREATE TABLE admin_profiles (id INTEGER PRIMARY KEY, name TEXT)"
        )
        c.exec_driver_sql(
            "INSERT INTO admin_profiles VALUES (1, 'Existing configuration')"
        )
        migration.op = Operations(MigrationContext.configure(c))
        migration.upgrade()
        assert {
            "security_resource_ownership",
            "security_rate_buckets",
            "security_work_leases",
        } <= set(inspect(c).get_table_names())
        assert c.execute(
            text("SELECT count(*) FROM security_resource_ownership")
        ).scalar_one() == (1 if companies == 1 else 0)
        assert (
            c.execute(text("SELECT name FROM admin_profiles")).scalar_one()
            == "Existing configuration"
        )
        migration.downgrade()
        assert "security_rate_buckets" not in inspect(c).get_table_names()
        assert (
            c.execute(text("SELECT name FROM admin_profiles")).scalar_one()
            == "Existing configuration"
        )
        migration.upgrade()
    engine.dispose()
