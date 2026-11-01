import importlib.util
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text, inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations


@pytest.mark.parametrize("directory,filename", [
    ("alembic_postgresql", "pg_20261101_052_timesheet_tenant.py"),
    ("alembic", "20261101_051_timesheet_tenant.py"),
])
def test_timesheet_tenant_migration_preserves_unknown_and_conflicting_ownership(directory, filename):
    path = Path(__file__).resolve().parents[1] / directory / "versions" / filename
    spec = importlib.util.spec_from_file_location("timesheet_tenant_migration", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        for sql in [
            "CREATE TABLE companies (id INTEGER PRIMARY KEY)",
            "INSERT INTO companies VALUES (1),(2)",
            "CREATE TABLE branches (id INTEGER PRIMARY KEY, company_id INTEGER)",
            "INSERT INTO branches VALUES (1,1)",
            "CREATE TABLE employees (id INTEGER PRIMARY KEY, branch_id INTEGER)",
            "INSERT INTO employees VALUES (1,1)",
            "CREATE TABLE projects (id INTEGER PRIMARY KEY, owner_employee_id INTEGER)",
            "INSERT INTO projects VALUES (1,1),(2,NULL),(3,1)",
            "CREATE TABLE security_resource_ownership (resource_table TEXT,resource_id INTEGER,company_id INTEGER)",
            "INSERT INTO security_resource_ownership VALUES ('projects',3,2)",
        ]: connection.execute(text(sql))
        module.op = Operations(MigrationContext.configure(connection)); module.upgrade()
        assert connection.execute(text("SELECT id,organization_id FROM projects ORDER BY id")).all() == [(1,1),(2,None),(3,None)]
        module.downgrade()
        assert "organization_id" not in {c["name"] for c in inspect(connection).get_columns("projects")}
        assert connection.execute(text("SELECT COUNT(*) FROM projects")).scalar_one() == 3
